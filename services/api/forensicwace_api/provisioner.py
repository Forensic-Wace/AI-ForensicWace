"""Runtime provisioning of installed analyzers (marketplace phase C).

When ``FW_PROVISIONER`` is set, installing from the catalog also creates the
analyzer's runtime, and the platform scales it to zero when idle:

- ``kubernetes``: a Deployment + Service per analyzer, plus — for
  ``trust=local`` — a NetworkPolicy that denies egress outside the namespace
  (evidence cannot be exfiltrated even by a malicious image). GPU manifests
  get ``nvidia.com/gpu`` limits. Runs with the pod's service account.
- ``docker``: compose labs only. Requires the docker socket, which is host
  root — deliberately opt-in, never a default.

Scale-to-zero happens at *analysis granularity*: the API scales requested
analyzers 0→1 right before dispatching to the queue (workers retry while the
model warms up), and a reaper thread returns runtimes to zero after
``FW_PROVISIONER_IDLE_MINUTES`` without activity.

Everything the runtime needs comes from the catalog entry — image pinned by
digest, port, static env, resources. Evidence still reaches analyzers only
through request payloads: no volumes are ever mounted.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from forensicwace_core.config import get_settings
from forensicwace_core.exceptions import ConfigurationError

from .catalog import CatalogEntry

logger = logging.getLogger(__name__)

RESOURCE_PREFIX = "fw-analyzer-"
MANAGED_BY = "forensicwace"
READY_TIMEOUT_SECONDS = 180  # image pull + model load can be slow
SUBMIT_WAIT_SECONDS = 5  # best-effort wait at analysis submit; retries do the rest
REAP_INTERVAL_SECONDS = 60


class ProvisionerError(Exception):
    """The runtime could not be created, scaled or destroyed."""


@dataclass(frozen=True)
class RuntimeSpec:
    key: str
    image: str
    port: int
    trust: str
    env: dict = field(default_factory=dict)
    cpu: str | None = None
    memory: str | None = None
    gpu: bool = False

    @property
    def resource_name(self) -> str:
        # registry keys allow "_", DNS-1123 names do not
        return RESOURCE_PREFIX + self.key.replace("_", "-")

    @classmethod
    def from_entry(cls, entry: CatalogEntry) -> "RuntimeSpec":
        manifest = entry.manifest
        return cls(
            key=manifest.key,
            image=entry.image,
            port=entry.port,
            trust=manifest.trust,
            env=dict(entry.env),
            cpu=manifest.resources.cpu,
            memory=manifest.resources.memory,
            gpu=manifest.resources.gpu,
        )


def resource_name_for(key: str) -> str:
    return RESOURCE_PREFIX + key.replace("_", "-")


def enabled() -> bool:
    return bool(get_settings().provisioner)


# --- Kubernetes object builders (pure: unit-testable without a cluster) -------


def deployment_body(spec: RuntimeSpec, namespace: str, replicas: int = 1) -> dict:
    labels = {
        "app.kubernetes.io/managed-by": MANAGED_BY,
        "forensicwace.io/analyzer": spec.resource_name,
    }
    resources: dict = {"requests": {}, "limits": {}}
    if spec.cpu:
        resources["requests"]["cpu"] = spec.cpu
    if spec.memory:
        resources["requests"]["memory"] = spec.memory
        resources["limits"]["memory"] = spec.memory
    if spec.gpu:
        resources["limits"]["nvidia.com/gpu"] = "1"
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": spec.resource_name, "namespace": namespace, "labels": labels},
        "spec": {
            "replicas": replicas,
            "selector": {"matchLabels": labels},
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "automountServiceAccountToken": False,
                    "securityContext": {"seccompProfile": {"type": "RuntimeDefault"}},
                    "containers": [
                        {
                            "name": "analyzer",
                            "image": spec.image,  # digest-pinned by the catalog model
                            "env": [{"name": k, "value": v} for k, v in sorted(spec.env.items())],
                            "ports": [{"containerPort": spec.port}],
                            "resources": resources,
                            "securityContext": {
                                "runAsNonRoot": True,
                                "allowPrivilegeEscalation": False,
                                "readOnlyRootFilesystem": True,
                                "capabilities": {"drop": ["ALL"]},
                            },
                            "volumeMounts": [{"name": "tmp", "mountPath": "/tmp"}],
                            "readinessProbe": {
                                "httpGet": {"path": "/healthz", "port": spec.port},
                                "initialDelaySeconds": 5,
                                "periodSeconds": 10,
                            },
                        }
                    ],
                    "volumes": [{"name": "tmp", "emptyDir": {}}],
                },
            },
        },
    }


def service_body(spec: RuntimeSpec, namespace: str) -> dict:
    labels = {
        "app.kubernetes.io/managed-by": MANAGED_BY,
        "forensicwace.io/analyzer": spec.resource_name,
    }
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": spec.resource_name, "namespace": namespace, "labels": labels},
        "spec": {
            "selector": labels,
            "ports": [{"name": "http", "port": 80, "targetPort": spec.port}],
        },
    }


def network_policy_body(spec: RuntimeSpec, namespace: str) -> dict:
    """trust=local: evidence must not leave the deployment. Ingress only from
    this namespace; egress only to this namespace (a shim may proxy to its
    in-cluster sidecar) and to DNS — nothing external."""
    labels = {
        "app.kubernetes.io/managed-by": MANAGED_BY,
        "forensicwace.io/analyzer": spec.resource_name,
    }
    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {"name": spec.resource_name, "namespace": namespace, "labels": labels},
        "spec": {
            "podSelector": {"matchLabels": labels},
            "policyTypes": ["Ingress", "Egress"],
            "ingress": [{"from": [{"podSelector": {}}]}],
            "egress": [
                {"to": [{"podSelector": {}}]},
                {
                    "to": [{"namespaceSelector": {}}],
                    "ports": [
                        {"protocol": "UDP", "port": 53},
                        {"protocol": "TCP", "port": 53},
                    ],
                },
            ],
        },
    }


# --- Backends ------------------------------------------------------------------


class KubernetesBackend:
    def __init__(self):
        try:
            from kubernetes import client, config as k8s_config
        except ImportError:
            raise ConfigurationError(
                "FW_PROVISIONER=kubernetes requires the 'kubernetes' package "
                "(pip install 'forensicwace-api[k8s]')"
            )
        try:
            k8s_config.load_incluster_config()
        except Exception:
            k8s_config.load_kube_config()
        self._apps = client.AppsV1Api()
        self._core = client.CoreV1Api()
        self._networking = client.NetworkingV1Api()
        self._api_exception = client.exceptions.ApiException
        self.namespace = get_settings().provisioner_namespace or _pod_namespace()

    def create(self, spec: RuntimeSpec) -> str:
        objects = [
            (self._apps.create_namespaced_deployment, self._apps.replace_namespaced_deployment,
             deployment_body(spec, self.namespace)),
            (self._core.create_namespaced_service, self._core.replace_namespaced_service,
             service_body(spec, self.namespace)),
        ]
        if spec.trust == "local":
            objects.append(
                (self._networking.create_namespaced_network_policy,
                 self._networking.replace_namespaced_network_policy,
                 network_policy_body(spec, self.namespace))
            )
        try:
            for create_fn, replace_fn, body in objects:
                try:
                    create_fn(namespace=self.namespace, body=body)
                except self._api_exception as exc:
                    if exc.status != 409:
                        raise
                    replace_fn(name=body["metadata"]["name"], namespace=self.namespace, body=body)
        except self._api_exception as exc:
            raise ProvisionerError(f"Kubernetes refused the analyzer runtime: {exc.reason}")
        return f"http://{spec.resource_name}.{self.namespace}.svc:80"

    def scale(self, key: str, replicas: int) -> bool:
        name = resource_name_for(key)
        try:
            self._apps.patch_namespaced_deployment_scale(
                name=name, namespace=self.namespace, body={"spec": {"replicas": replicas}}
            )
            return True
        except self._api_exception as exc:
            if exc.status == 404:
                return False  # not a provisioned analyzer
            raise ProvisionerError(f"Cannot scale {name}: {exc.reason}")

    def replicas(self, key: str) -> int | None:
        name = resource_name_for(key)
        try:
            deployment = self._apps.read_namespaced_deployment(name=name, namespace=self.namespace)
        except self._api_exception as exc:
            if exc.status == 404:
                return None
            raise ProvisionerError(f"Cannot read {name}: {exc.reason}")
        return deployment.spec.replicas or 0

    def ready(self, key: str) -> bool:
        name = resource_name_for(key)
        try:
            deployment = self._apps.read_namespaced_deployment(name=name, namespace=self.namespace)
        except self._api_exception:
            return False
        return (deployment.status.ready_replicas or 0) >= 1

    def destroy(self, key: str) -> None:
        name = resource_name_for(key)
        for deleter in (
            self._apps.delete_namespaced_deployment,
            self._core.delete_namespaced_service,
            self._networking.delete_namespaced_network_policy,
        ):
            try:
                deleter(name=name, namespace=self.namespace)
            except self._api_exception as exc:
                if exc.status != 404:
                    logger.warning("Could not delete %s (%s): %s", name, deleter.__name__, exc.reason)


def _pod_namespace() -> str:
    try:
        with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace", encoding="ascii") as f:
            return f.read().strip()
    except OSError:
        return "default"


class DockerBackend:
    """Compose labs: one container per analyzer on a shared network.

    Mounting the docker socket is host-root equivalent; this backend exists
    behind an explicit opt-in flag and never by default.
    """

    def __init__(self):
        try:
            import docker
        except ImportError:
            raise ConfigurationError(
                "FW_PROVISIONER=docker requires the 'docker' package (pip install 'forensicwace-api[docker]')"
            )
        settings = get_settings()
        if not settings.provisioner_docker_network:
            raise ConfigurationError("FW_PROVISIONER=docker requires FW_PROVISIONER_DOCKER_NETWORK")
        self.network = settings.provisioner_docker_network
        self._docker = docker
        self._client = docker.from_env()

    def create(self, spec: RuntimeSpec) -> str:
        name = spec.resource_name
        try:
            existing = self._container(name)
            if existing is not None:
                existing.remove(force=True)
            self._client.containers.run(
                spec.image,
                name=name,
                detach=True,
                network=self.network,
                environment=spec.env,
                labels={"app.kubernetes.io/managed-by": MANAGED_BY},
                read_only=True,
                tmpfs={"/tmp": ""},
                security_opt=["no-new-privileges"],
                restart_policy={"Name": "unless-stopped"},
            )
        except self._docker.errors.DockerException as exc:
            raise ProvisionerError(f"Docker refused the analyzer runtime: {exc}")
        return f"http://{name}:{spec.port}"

    def _container(self, name: str):
        try:
            return self._client.containers.get(name)
        except self._docker.errors.NotFound:
            return None

    def scale(self, key: str, replicas: int) -> bool:
        container = self._container(resource_name_for(key))
        if container is None:
            return False
        try:
            if replicas > 0 and container.status != "running":
                container.start()
            elif replicas == 0 and container.status == "running":
                container.stop(timeout=20)
            return True
        except self._docker.errors.DockerException as exc:
            raise ProvisionerError(f"Cannot scale {resource_name_for(key)}: {exc}")

    def replicas(self, key: str) -> int | None:
        container = self._container(resource_name_for(key))
        if container is None:
            return None
        return 1 if container.status == "running" else 0

    def ready(self, key: str) -> bool:
        return self.replicas(key) == 1

    def destroy(self, key: str) -> None:
        container = self._container(resource_name_for(key))
        if container is not None:
            container.remove(force=True)


_backend_lock = threading.Lock()
_backend_instance = None


def _backend():
    global _backend_instance
    with _backend_lock:
        if _backend_instance is None:
            kind = (get_settings().provisioner or "").lower()
            if kind in ("kubernetes", "k8s"):
                _backend_instance = KubernetesBackend()
            elif kind == "docker":
                _backend_instance = DockerBackend()
            else:
                raise ConfigurationError(f"Unknown FW_PROVISIONER {kind!r} (kubernetes | docker)")
        return _backend_instance


def clear_backend_cache() -> None:
    global _backend_instance
    with _backend_lock:
        _backend_instance = None


# --- Operations ------------------------------------------------------------------


def provision(entry: CatalogEntry, config: dict | None = None) -> str:
    """Create (or recreate) the runtime for a catalog entry; returns its endpoint."""
    spec = RuntimeSpec.from_entry(entry)
    backend = _backend()
    endpoint = backend.create(spec)
    deadline = time.monotonic() + READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if backend.ready(spec.key):
            return endpoint
        time.sleep(2)
    raise ProvisionerError(
        f"Runtime for {spec.key!r} did not become ready within {READY_TIMEOUT_SECONDS}s "
        f"(image {spec.image})"
    )


def deprovision(key: str) -> None:
    _backend().destroy(key)


def ensure_running(keys: list[str]) -> None:
    """Scale the requested analyzers 0→1 before dispatch (analysis submit).

    Best-effort by design: a failure here must never block an analysis whose
    analyzers might not even be provisioned (BYO endpoints, builtins).
    """
    if not enabled() or not keys:
        return
    try:
        backend = _backend()
        woken = [key for key in keys if backend.scale(key, 1)]
        if not woken:
            return
        deadline = time.monotonic() + SUBMIT_WAIT_SECONDS
        while time.monotonic() < deadline and not all(backend.ready(k) for k in woken):
            time.sleep(0.5)
        logger.info("Scaled up analyzer runtimes for dispatch: %s", ", ".join(woken))
    except Exception:
        logger.warning("Analyzer scale-up failed — dispatch continues, workers will retry", exc_info=True)


def _active_analyzer_keys(idle_cutoff: datetime) -> set[str]:
    """Keys referenced by analyses that are running or finished after the cutoff."""
    from forensicwace_core.analysis import registry
    from forensicwace_core.resultsdb.engine import session_scope
    from forensicwace_core.resultsdb.models import ProcessStatus

    with session_scope() as session:
        rows = (
            session.query(ProcessStatus.analyzers, ProcessStatus.status, ProcessStatus.end_time)
            .filter(
                ProcessStatus.status.in_(("Started", "Analyzing"))
                | (ProcessStatus.end_time >= idle_cutoff)
            )
            .all()
        )
    active: set[str] = set()
    for row in rows:
        requested = [key for key in (row.analyzers or "").split(",") if key]
        active.update(registry.expand_aliases(requested))
    return active


def reap_idle() -> list[str]:
    """Scale provisioned analyzers with no recent activity back to zero."""
    from forensicwace_core.analysis import registry

    settings = get_settings()
    backend = _backend()
    idle_cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.provisioner_idle_minutes)
    active = _active_analyzer_keys(idle_cutoff)

    reaped = []
    for key, analyzer in registry.installed_analyzers().items():
        if analyzer.type != "http" or key in active:
            continue
        if backend.replicas(key) not in (None, 0) and backend.scale(key, 0):
            reaped.append(key)
    if reaped:
        logger.info("Scaled idle analyzer runtimes to zero: %s", ", ".join(reaped))
    return reaped


_reaper_stop = threading.Event()


def start_reaper() -> None:
    """Run the idle reaper in a daemon thread (API lifespan)."""

    def loop() -> None:
        while not _reaper_stop.wait(REAP_INTERVAL_SECONDS):
            try:
                reap_idle()
            except Exception:
                logger.warning("Idle reaper pass failed", exc_info=True)

    _reaper_stop.clear()
    threading.Thread(target=loop, name="analyzer-reaper", daemon=True).start()


def stop_reaper() -> None:
    _reaper_stop.set()
