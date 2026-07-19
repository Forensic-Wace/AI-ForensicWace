"""Phase C provisioner: k8s object shapes, scale-to-zero, marketplace wiring."""

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from forensicwace_core.analysis import registry  # noqa: E402
from forensicwace_core.analysis.contract import AnalyzerManifest  # noqa: E402
from forensicwace_core.config import clear_settings_cache  # noqa: E402
from forensicwace_core.resultsdb.engine import dispose_engine  # noqa: E402

DIGEST = "sha256:" + "cd" * 32

GPU_MANIFEST = {
    "contract": "fw-analyzer/1",
    "key": "lavis_caption_x",
    "name": "LAVIS captioning",
    "version": "1.0.0",
    "capabilities": ["caption"],
    "input": "image",
    "resources": {"cpu": "2", "memory": "6Gi", "gpu": True},
    "trust": "local",
}

TEXT_MANIFEST = {
    "contract": "fw-analyzer/1",
    "key": "iban_hunter",
    "name": "IBAN hunter",
    "version": "3.0.0",
    "capabilities": ["pii"],
    "input": "text",
    "trust": "local",
}

CATALOG = {
    "format": "fw-catalog/1",
    "entries": [
        {
            "manifest": GPU_MANIFEST,
            "image": f"ghcr.io/example/lavis@{DIGEST}",
            "port": 9300,
            "env": {"FW_SHIM_TARGET": "lavis"},
        },
        {"manifest": TEXT_MANIFEST, "image": f"ghcr.io/example/iban@{DIGEST}"},
    ],
}


class FakeBackend:
    """Records operations; every created runtime is instantly ready."""

    def __init__(self):
        self.created = []
        self.destroyed = []
        self.scaled = []
        self.replica_state: dict[str, int] = {}

    def create(self, spec):
        self.created.append(spec)
        self.replica_state[spec.key] = 1
        return f"http://{spec.resource_name}.test.svc:80"

    def scale(self, key, replicas):
        if key not in self.replica_state:
            return False
        self.scaled.append((key, replicas))
        self.replica_state[key] = replicas
        return True

    def replicas(self, key):
        return self.replica_state.get(key)

    def ready(self, key):
        return self.replica_state.get(key, 0) >= 1

    def destroy(self, key):
        self.destroyed.append(key)
        self.replica_state.pop(key, None)


def _reset_runtime():
    clear_settings_cache()
    registry.clear_registry_cache()
    dispose_engine()

    from forensicwace_api import catalog, provisioner

    catalog.clear_catalog_cache()
    provisioner.clear_backend_cache()


def _entry(manifest: dict, **overrides):
    from forensicwace_api.catalog import CatalogEntry

    body = {"manifest": manifest, "image": f"ghcr.io/example/x@{DIGEST}", **overrides}
    return CatalogEntry.model_validate(body)


# --- Kubernetes object shapes ---------------------------------------------------


def test_deployment_body_enforces_hardening_and_gpu():
    from forensicwace_api import provisioner

    spec = provisioner.RuntimeSpec.from_entry(_entry(GPU_MANIFEST, env={"A": "1"}))
    body = provisioner.deployment_body(spec, "lab")

    assert body["metadata"]["name"] == "fw-analyzer-lavis-caption-x"  # _ -> -
    container = body["spec"]["template"]["spec"]["containers"][0]
    assert "@sha256:" in container["image"]
    assert container["securityContext"]["runAsNonRoot"] is True
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert container["resources"]["limits"]["nvidia.com/gpu"] == "1"
    assert container["resources"]["requests"] == {"cpu": "2", "memory": "6Gi"}
    assert {"name": "A", "value": "1"} in container["env"]
    assert body["spec"]["template"]["spec"]["automountServiceAccountToken"] is False


def test_network_policy_denies_external_egress():
    from forensicwace_api import provisioner

    spec = provisioner.RuntimeSpec.from_entry(_entry(TEXT_MANIFEST))
    policy = provisioner.network_policy_body(spec, "lab")

    assert policy["spec"]["policyTypes"] == ["Ingress", "Egress"]
    # egress: same-namespace pods + DNS only — no rule ever selects the internet
    egress = policy["spec"]["egress"]
    assert {"to": [{"podSelector": {}}]} in egress
    assert any("ports" in rule for rule in egress)
    assert all("ipBlock" not in json.dumps(rule) for rule in egress)


def test_service_routes_port_80_to_the_analyzer():
    from forensicwace_api import provisioner

    spec = provisioner.RuntimeSpec.from_entry(_entry(TEXT_MANIFEST, port=9317))
    service = provisioner.service_body(spec, "lab")
    assert service["spec"]["ports"] == [{"name": "http", "port": 80, "targetPort": 9317}]


# --- Provision / scale-to-zero ---------------------------------------------------


@pytest.fixture
def fake_backend(monkeypatch):
    from forensicwace_api import provisioner

    fake = FakeBackend()
    monkeypatch.setattr(provisioner, "_backend_instance", fake)
    yield fake
    provisioner.clear_backend_cache()


def test_provision_returns_endpoint_once_ready(fake_backend):
    from forensicwace_api import provisioner

    endpoint = provisioner.provision(_entry(TEXT_MANIFEST))
    assert endpoint == "http://fw-analyzer-iban-hunter.test.svc:80"
    assert fake_backend.created[0].key == "iban_hunter"


def test_provision_times_out_when_never_ready(fake_backend, monkeypatch):
    from forensicwace_api import provisioner

    monkeypatch.setattr(provisioner, "READY_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(FakeBackend, "ready", lambda self, key: False)
    with pytest.raises(provisioner.ProvisionerError, match="did not become ready"):
        provisioner.provision(_entry(TEXT_MANIFEST))


def test_ensure_running_wakes_only_managed_runtimes(fake_backend, monkeypatch, tmp_path):
    from forensicwace_api import provisioner

    monkeypatch.setenv("FW_PROVISIONER", "kubernetes")
    clear_settings_cache()
    fake_backend.replica_state["iban_hunter"] = 0
    provisioner.ensure_running(["iban_hunter", "presidio"])  # presidio: not provisioned
    assert ("iban_hunter", 1) in fake_backend.scaled
    assert all(key == "iban_hunter" for key, _ in fake_backend.scaled)
    clear_settings_cache()


def test_ensure_running_failure_never_blocks_dispatch(fake_backend, monkeypatch):
    from forensicwace_api import provisioner

    monkeypatch.setenv("FW_PROVISIONER", "kubernetes")
    clear_settings_cache()
    monkeypatch.setattr(FakeBackend, "scale", lambda self, key, replicas: (_ for _ in ()).throw(RuntimeError("boom")))
    provisioner.ensure_running(["iban_hunter"])  # must not raise
    clear_settings_cache()


# --- Idle reaper -----------------------------------------------------------------


@pytest.fixture
def db_env(tmp_path, monkeypatch):
    monkeypatch.setenv("FW_DATABASE_URL", f"sqlite:///{(tmp_path / 'results.db').as_posix()}")
    monkeypatch.setenv("FW_PROVISIONER", "kubernetes")
    _reset_runtime()

    from forensicwace_core.resultsdb.engine import init_db

    init_db()
    yield
    _reset_runtime()


def _seed_analyzer_and_process(status: str, end_ago_minutes: int | None, analyzers: str = "iban_hunter"):
    from forensicwace_core.resultsdb.engine import session_scope
    from forensicwace_core.resultsdb.models import Analyzer, ProcessStatus

    now = datetime.now(timezone.utc)
    with session_scope() as session:
        if session.query(Analyzer).filter_by(key="iban_hunter").first() is None:
            session.add(
                Analyzer(
                    key="iban_hunter", name="IBAN hunter", version="3.0.0", type="http",
                    capabilities=["pii"], input="text", trust="local",
                    endpoint="http://fw-analyzer-iban-hunter.test.svc:80", enabled=True,
                )
            )
        session.add(
            ProcessStatus(
                process_id=f"p-{status}-{end_ago_minutes}",
                OS="android",
                status=status,
                analyzers=analyzers,
                end_time=None if end_ago_minutes is None else now - timedelta(minutes=end_ago_minutes),
            )
        )


def test_reaper_scales_idle_runtimes_to_zero(db_env, fake_backend):
    from forensicwace_api import provisioner

    fake_backend.replica_state["iban_hunter"] = 1
    _seed_analyzer_and_process("Finish", end_ago_minutes=120)
    registry.clear_registry_cache()

    assert provisioner.reap_idle() == ["iban_hunter"]
    assert fake_backend.replica_state["iban_hunter"] == 0


def test_reaper_keeps_active_and_recent_runtimes(db_env, fake_backend):
    from forensicwace_api import provisioner

    fake_backend.replica_state["iban_hunter"] = 1
    _seed_analyzer_and_process("Analyzing", end_ago_minutes=None)
    registry.clear_registry_cache()
    assert provisioner.reap_idle() == []

    _seed_analyzer_and_process("Finish", end_ago_minutes=2)  # finished moments ago
    registry.clear_registry_cache()
    assert provisioner.reap_idle() == []
    assert fake_backend.replica_state["iban_hunter"] == 1


# --- Marketplace wiring -----------------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch, fake_backend):
    catalog_file = tmp_path / "catalog.json"
    raw = json.dumps(CATALOG).encode()
    catalog_file.write_bytes(raw)
    private = Ed25519PrivateKey.generate()
    (tmp_path / "catalog.json.sig").write_bytes(base64.b64encode(private.sign(raw)))
    public_b64 = base64.b64encode(private.public_key().public_bytes_raw()).decode()

    monkeypatch.setenv("FW_DATABASE_URL", f"sqlite:///{(tmp_path / 'results.db').as_posix()}")
    monkeypatch.setenv("FW_IOS_EXTRACTIONS_DIR", str(tmp_path / "ios"))
    monkeypatch.setenv("FW_ANDROID_EXTRACTIONS_DIR", str(tmp_path / "android"))
    monkeypatch.setenv("FW_CATALOG_URL", Path(catalog_file).as_uri())
    monkeypatch.setenv("FW_CATALOG_PUBLIC_KEY", public_b64)
    monkeypatch.setenv("FW_PROVISIONER", "kubernetes")
    clear_settings_cache()
    registry.clear_registry_cache()
    dispose_engine()

    from forensicwace_api import catalog as catalog_mod
    from forensicwace_api import provisioner

    catalog_mod.clear_catalog_cache()
    monkeypatch.setattr(provisioner, "_backend_instance", fake_backend)

    from forensicwace_api.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
    _reset_runtime()


def stub_live_manifest(monkeypatch, manifest: dict):
    from forensicwace_core.analysis.analyzers.http_analyzer import HttpAnalyzer

    parsed = AnalyzerManifest.model_validate(manifest)
    monkeypatch.setattr(HttpAnalyzer, "manifest", lambda self: parsed)


def test_install_provisions_and_uses_the_service_endpoint(client, fake_backend, monkeypatch):
    stub_live_manifest(monkeypatch, TEXT_MANIFEST)
    assert client.get("/api/v1/marketplace").json()["provisioner"] is True

    created = client.post("/api/v1/marketplace/install/iban_hunter", json={})
    assert created.status_code == 201, created.text
    assert created.json()["endpoint"] == "http://fw-analyzer-iban-hunter.test.svc:80"
    # provisioned installs run the pinned image, so the digest IS provenance
    assert created.json()["image_digest"] == DIGEST
    assert fake_backend.created[0].image.endswith(DIGEST)


def test_failed_install_rolls_the_runtime_back(client, fake_backend, monkeypatch):
    stub_live_manifest(monkeypatch, TEXT_MANIFEST)  # wrong key for this entry
    response = client.post("/api/v1/marketplace/install/lavis_caption_x", json={})
    assert response.status_code == 422
    assert "lavis_caption_x" not in {a["key"] for a in client.get("/api/v1/analyzers").json()}
    assert fake_backend.destroyed == ["lavis_caption_x"]


def test_uninstall_deprovisions_the_runtime(client, fake_backend, monkeypatch):
    stub_live_manifest(monkeypatch, TEXT_MANIFEST)
    assert client.post("/api/v1/marketplace/install/iban_hunter", json={}).status_code == 201
    assert client.delete("/api/v1/analyzers/iban_hunter").status_code == 204
    assert fake_backend.destroyed == ["iban_hunter"]
