"""Marketplace phase B: signed catalog, install with digest pinning + consent."""

import base64
import json
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from forensicwace_core.analysis import registry  # noqa: E402
from forensicwace_core.analysis.contract import AnalyzerManifest  # noqa: E402
from forensicwace_core.config import clear_settings_cache  # noqa: E402
from forensicwace_core.resultsdb.engine import dispose_engine  # noqa: E402

DIGEST = "sha256:" + "ab" * 32

LOCAL_MANIFEST = {
    "contract": "fw-analyzer/1",
    "key": "iban_hunter",
    "name": "IBAN hunter",
    "version": "3.0.0",
    "capabilities": ["pii"],
    "input": "text",
    "trust": "local",
}

CLOUD_MANIFEST = {
    "contract": "fw-analyzer/1",
    "key": "cloud_pii",
    "name": "Cloud PII service",
    "version": "1.0.0",
    "capabilities": ["pii"],
    "input": "text",
    "trust": "cloud",
}

CATALOG = {
    "format": "fw-catalog/1",
    "name": "Test catalog",
    "entries": [
        {
            "manifest": LOCAL_MANIFEST,
            "image": f"ghcr.io/example/iban-hunter@{DIGEST}",
            "description": "Finds IBANs",
            "publisher": "Example",
        },
        {
            "manifest": CLOUD_MANIFEST,
            "image": f"example.azurecr.io/cloud-pii@{DIGEST}",
        },
    ],
}


def _reset_runtime():
    clear_settings_cache()
    registry.clear_registry_cache()
    dispose_engine()

    from forensicwace_api import catalog

    catalog.clear_catalog_cache()


def write_catalog(tmp_path: Path, payload: dict, sign: bool = True) -> tuple[str, str]:
    """Write catalog(.sig) to disk; returns (file:// URL, base64 public key)."""
    catalog_file = tmp_path / "catalog.json"
    raw = json.dumps(payload).encode()
    catalog_file.write_bytes(raw)
    private = Ed25519PrivateKey.generate()
    if sign:
        (tmp_path / "catalog.json.sig").write_bytes(base64.b64encode(private.sign(raw)))
    public_b64 = base64.b64encode(private.public_key().public_bytes_raw()).decode()
    return catalog_file.as_uri(), public_b64


@pytest.fixture
def client(tmp_path, monkeypatch):
    url, public_key = write_catalog(tmp_path, CATALOG)
    monkeypatch.setenv("FW_DATABASE_URL", f"sqlite:///{(tmp_path / 'results.db').as_posix()}")
    monkeypatch.setenv("FW_IOS_EXTRACTIONS_DIR", str(tmp_path / "ios"))
    monkeypatch.setenv("FW_ANDROID_EXTRACTIONS_DIR", str(tmp_path / "android"))
    monkeypatch.setenv("FW_CATALOG_URL", url)
    monkeypatch.setenv("FW_CATALOG_PUBLIC_KEY", public_key)
    _reset_runtime()

    from forensicwace_api.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
    _reset_runtime()


def stub_live_manifest(monkeypatch, manifest: dict):
    from forensicwace_core.analysis.analyzers.http_analyzer import HttpAnalyzer

    parsed = AnalyzerManifest.model_validate(manifest)
    monkeypatch.setattr(HttpAnalyzer, "manifest", lambda self: parsed)


def test_browse_shows_verified_catalog_with_install_state(client):
    catalog = client.get("/api/v1/marketplace").json()
    assert catalog["verified"] is True
    assert catalog["provisioner"] is False
    entries = {e["key"]: e for e in catalog["entries"]}
    assert entries["iban_hunter"]["image_digest"] == DIGEST
    assert entries["iban_hunter"]["installed"] is False
    assert entries["cloud_pii"]["trust"] == "cloud"


def test_install_requires_endpoint_without_provisioner(client):
    response = client.post("/api/v1/marketplace/install/iban_hunter", json={})
    assert response.status_code == 422
    assert "FW_PROVISIONER" in response.json()["detail"]


def test_install_records_catalog_identity(client, monkeypatch):
    stub_live_manifest(monkeypatch, LOCAL_MANIFEST)
    created = client.post(
        "/api/v1/marketplace/install/iban_hunter", json={"endpoint": "http://iban:9300/"}
    )
    assert created.status_code == 201, created.text
    body = created.json()
    # bring-your-own endpoint: nobody verified the running image, so the
    # catalog digest is NOT stamped (only provisioned installs get it)
    assert body["image_digest"] is None
    assert body["endpoint"] == "http://iban:9300"
    assert body["version"] == "3.0.0"  # live manifest version

    catalog = client.get("/api/v1/marketplace").json()
    entry = next(e for e in catalog["entries"] if e["key"] == "iban_hunter")
    assert entry["installed"] is True and entry["installed_version"] == "3.0.0"

    # duplicate install conflicts; unknown key 404s
    assert client.post(
        "/api/v1/marketplace/install/iban_hunter", json={"endpoint": "http://iban:9300"}
    ).status_code == 409
    assert client.post("/api/v1/marketplace/install/nope", json={}).status_code == 404


def test_container_serving_wrong_key_is_rejected(client, monkeypatch):
    stub_live_manifest(monkeypatch, CLOUD_MANIFEST)  # catalog key iban_hunter, live key cloud_pii
    response = client.post(
        "/api/v1/marketplace/install/iban_hunter", json={"endpoint": "http://iban:9300"}
    )
    assert response.status_code == 422
    assert "serves analyzer 'cloud_pii'" in response.json()["detail"]


def test_cloud_analyzer_requires_consent_and_audits_it(client, monkeypatch):
    stub_live_manifest(monkeypatch, CLOUD_MANIFEST)
    refused = client.post("/api/v1/marketplace/install/cloud_pii", json={"endpoint": "http://c:9300"})
    assert refused.status_code == 422
    assert "consent" in refused.json()["detail"]

    accepted = client.post(
        "/api/v1/marketplace/install/cloud_pii", json={"endpoint": "http://c:9300", "consent": True}
    )
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["trust"] == "cloud"

    actions = [e["action"] for e in client.get("/api/v1/audit").json()]
    assert "analyzer.consent" in actions and "analyzer.installed" in actions


def test_live_escalation_to_cloud_still_requires_consent(client, monkeypatch):
    """Catalog says local, container says cloud: the consent gate must hold."""
    stub_live_manifest(monkeypatch, {**LOCAL_MANIFEST, "trust": "cloud"})
    refused = client.post(
        "/api/v1/marketplace/install/iban_hunter", json={"endpoint": "http://iban:9300"}
    )
    assert refused.status_code == 422
    assert "consent" in refused.json()["detail"]
    # and no phantom consent entry was written
    assert all(e["action"] != "analyzer.consent" for e in client.get("/api/v1/audit").json())

    accepted = client.post(
        "/api/v1/marketplace/install/iban_hunter", json={"endpoint": "http://iban:9300", "consent": True}
    )
    assert accepted.status_code == 201
    assert accepted.json()["trust"] == "cloud"


def test_manifest_returning_junk_is_422(client, monkeypatch):
    import json as json_mod

    from forensicwace_core.analysis.analyzers.http_analyzer import HttpAnalyzer

    def broken(self):
        raise json_mod.JSONDecodeError("Expecting value", "<html>", 0)

    monkeypatch.setattr(HttpAnalyzer, "manifest", broken)
    response = client.post(
        "/api/v1/marketplace/install/iban_hunter", json={"endpoint": "http://not-an-analyzer:80"}
    )
    assert response.status_code == 422
    assert "did not return valid JSON" in response.json()["detail"]


def test_byo_registration_applies_the_same_consent_rule(client, monkeypatch):
    stub_live_manifest(monkeypatch, CLOUD_MANIFEST)
    refused = client.post("/api/v1/analyzers", json={"endpoint": "http://c:9300"})
    assert refused.status_code == 422
    assert "consent" in refused.json()["detail"]

    accepted = client.post("/api/v1/analyzers", json={"endpoint": "http://c:9300", "consent": True})
    assert accepted.status_code == 201
    actions = [e["action"] for e in client.get("/api/v1/audit").json()]
    assert "analyzer.consent" in actions


def test_tampered_catalog_is_refused(tmp_path, monkeypatch):
    url, public_key = write_catalog(tmp_path, CATALOG)
    tampered = dict(CATALOG, name="Evil catalog")
    (tmp_path / "catalog.json").write_bytes(json.dumps(tampered).encode())

    monkeypatch.setenv("FW_DATABASE_URL", f"sqlite:///{(tmp_path / 'results.db').as_posix()}")
    monkeypatch.setenv("FW_IOS_EXTRACTIONS_DIR", str(tmp_path / "ios"))
    monkeypatch.setenv("FW_ANDROID_EXTRACTIONS_DIR", str(tmp_path / "android"))
    monkeypatch.setenv("FW_CATALOG_URL", url)
    monkeypatch.setenv("FW_CATALOG_PUBLIC_KEY", public_key)
    _reset_runtime()
    from forensicwace_api.main import create_app

    with TestClient(create_app()) as client:
        response = client.get("/api/v1/marketplace")
        assert response.status_code == 502
        assert "signature verification FAILED" in response.json()["detail"]
        # nothing is installable off an unverifiable catalog
        assert client.post(
            "/api/v1/marketplace/install/iban_hunter", json={"endpoint": "http://x:9300"}
        ).status_code == 502
    _reset_runtime()


def test_unpinned_key_loads_catalog_as_unverified(tmp_path, monkeypatch):
    url, _ = write_catalog(tmp_path, CATALOG, sign=False)
    monkeypatch.setenv("FW_DATABASE_URL", f"sqlite:///{(tmp_path / 'results.db').as_posix()}")
    monkeypatch.setenv("FW_IOS_EXTRACTIONS_DIR", str(tmp_path / "ios"))
    monkeypatch.setenv("FW_ANDROID_EXTRACTIONS_DIR", str(tmp_path / "android"))
    monkeypatch.setenv("FW_CATALOG_URL", url)
    monkeypatch.delenv("FW_CATALOG_PUBLIC_KEY", raising=False)
    _reset_runtime()
    from forensicwace_api.main import create_app

    with TestClient(create_app()) as client:
        assert client.get("/api/v1/marketplace").json()["verified"] is False
    _reset_runtime()


def test_tag_pinned_images_are_rejected_by_the_model(tmp_path, monkeypatch):
    bad = {
        "format": "fw-catalog/1",
        "entries": [{"manifest": LOCAL_MANIFEST, "image": "ghcr.io/example/iban-hunter:latest"}],
    }
    url, public_key = write_catalog(tmp_path, bad)
    monkeypatch.setenv("FW_DATABASE_URL", f"sqlite:///{(tmp_path / 'results.db').as_posix()}")
    monkeypatch.setenv("FW_IOS_EXTRACTIONS_DIR", str(tmp_path / "ios"))
    monkeypatch.setenv("FW_ANDROID_EXTRACTIONS_DIR", str(tmp_path / "android"))
    monkeypatch.setenv("FW_CATALOG_URL", url)
    monkeypatch.setenv("FW_CATALOG_PUBLIC_KEY", public_key)
    _reset_runtime()
    from forensicwace_api.main import create_app

    with TestClient(create_app()) as client:
        response = client.get("/api/v1/marketplace")
        assert response.status_code == 502
        assert "fw-catalog/1" in response.json()["detail"]
    _reset_runtime()


def test_marketplace_disabled_without_catalog_url(tmp_path, monkeypatch):
    monkeypatch.setenv("FW_DATABASE_URL", f"sqlite:///{(tmp_path / 'results.db').as_posix()}")
    monkeypatch.setenv("FW_IOS_EXTRACTIONS_DIR", str(tmp_path / "ios"))
    monkeypatch.setenv("FW_ANDROID_EXTRACTIONS_DIR", str(tmp_path / "android"))
    monkeypatch.delenv("FW_CATALOG_URL", raising=False)
    _reset_runtime()
    from forensicwace_api.main import create_app

    with TestClient(create_app()) as client:
        response = client.get("/api/v1/marketplace")
        assert response.status_code == 503
        assert "FW_CATALOG_URL" in response.json()["detail"]
    _reset_runtime()
