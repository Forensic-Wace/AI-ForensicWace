"""The shim must speak fw-analyzer/1 outward and each sidecar dialect inward."""

import json

import httpx
import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from forensicwace_analyzer_shim.main import TARGETS, create_app  # noqa: E402


def _upstreams(seen: list[httpx.Request]) -> httpx.MockTransport:
    """One fake transport impersonating every sidecar's native API."""

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "GET":  # healthz reachability probe
            return httpx.Response(405)
        path = request.url.path
        if path.endswith("/api/text"):  # DeepPass
            return httpx.Response(200, json={
                "model_password_candidates": [{"password": "hunter2"}],
                "regex_password_candidates": [{"password": "hunter2"}, {"password": "s3cret!"}],
            })
        if path.endswith("/asr"):  # Whisper webservice
            return httpx.Response(200, text="ci vediamo alle nove\n")
        if path.endswith("/v1/ocr"):  # Tesseract server
            return httpx.Response(200, json={"data": {"stdout": "FORENSIC WACE"}})
        return httpx.Response(200, json={"caption": "a cat in a bucket"})  # LAVIS

    return httpx.MockTransport(handler)


def make_client(kind: str, url: str, seen=None) -> TestClient:
    return TestClient(create_app(kind, url, transport=_upstreams(seen if seen is not None else [])))


@pytest.mark.parametrize("kind", sorted(TARGETS))
def test_manifests_conform_to_contract(kind):
    """Every shim manifest validates against the platform's contract models."""
    contract = pytest.importorskip("forensicwace_core.analysis.contract")
    client = make_client(kind, "http://upstream")
    manifest = contract.AnalyzerManifest.model_validate(client.get("/manifest").json())
    assert manifest.trust == "local"
    assert manifest.key == TARGETS[kind].key


def test_manifest_key_override():
    client = TestClient(create_app("deeppass", "http://u", key="deeppass_lab2", transport=_upstreams([])))
    assert client.get("/manifest").json()["key"] == "deeppass_lab2"


def test_healthz_reflects_upstream_reachability():
    assert make_client("deeppass", "http://upstream").get("/healthz").status_code == 200

    def refuse(request):
        raise httpx.ConnectError("connection refused")

    down = TestClient(create_app("deeppass", "http://down", transport=httpx.MockTransport(refuse)))
    assert down.get("/healthz").status_code == 503


def test_deeppass_translation_dedupes_model_and_regex():
    seen: list[httpx.Request] = []
    client = make_client("deeppass", "http://deeppass:5000", seen)
    response = client.post("/analyze", json={"text": "la password è hunter2", "config": {}})
    values = [f["value"] for f in response.json()["findings"]]
    assert values == ["hunter2", "s3cret!"]  # regex duplicate of the model hit dropped
    assert seen[-1].url.path == "/api/text"
    assert seen[-1].content == "la password è hunter2".encode()


def test_whisper_translation():
    seen: list[httpx.Request] = []
    client = make_client("whisper", "http://whisper:9000/asr", seen)
    response = client.post(
        "/analyze",
        files={"file": ("voice.opus", b"fake-opus", "audio/ogg")},
        data={"config": "{}"},
    )
    assert response.json()["enrichment"] == {"transcription": "ci vediamo alle nove"}
    assert dict(seen[-1].url.params) == {"encode": "true", "task": "transcribe", "output": "txt"}


def test_tesseract_translation_honors_language_config():
    seen: list[httpx.Request] = []
    client = make_client("tesseract", "http://tesseract:8884/v1/ocr", seen)
    response = client.post(
        "/analyze",
        files={"file": ("shot.png", b"fake-png", "image/png")},
        data={"config": json.dumps({"languages": ["ita", "eng"]})},
    )
    assert response.json()["enrichment"]["ocr_text"] == "FORENSIC WACE"
    assert b'{"languages": ["ita", "eng"]}' in seen[-1].content


def test_lavis_translation():
    client = make_client("lavis", "http://lavis:7866")
    response = client.post("/analyze", files={"file": ("img.jpg", b"fake-jpg", "image/jpeg")}, data={"config": "{}"})
    assert response.json()["enrichment"]["caption"] == "a cat in a bucket"
