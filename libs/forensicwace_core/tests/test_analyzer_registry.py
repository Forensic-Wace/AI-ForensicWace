"""Analyzer contract, generic HTTP adapter and registry resolution."""

import json
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from forensicwace_core import __version__
from forensicwace_core.analysis import registry
from forensicwace_core.analysis.analyzers import BUILTINS
from forensicwace_core.analysis.analyzers.http_analyzer import HttpAnalyzer
from forensicwace_core.analysis.contract import AnalyzeResponse, AnalyzerManifest
from forensicwace_core.analysis.types import Message
from forensicwace_core.config import clear_settings_cache

REPO_ROOT = Path(__file__).parents[3]

VALID_MANIFEST = {
    "contract": "fw-analyzer/1",
    "key": "my_detector",
    "name": "My detector",
    "version": "1.0.0",
    "capabilities": ["pii"],
    "input": "text",
}


@pytest.fixture(autouse=True)
def _fresh_registry(monkeypatch):
    monkeypatch.delenv("FW_DATABASE_URL", raising=False)
    monkeypatch.delenv("FW_USE_MS_S2T", raising=False)
    monkeypatch.delenv("FW_USE_MS_OCR_CAPTION", raising=False)
    clear_settings_cache()
    registry.clear_registry_cache()
    yield
    clear_settings_cache()
    registry.clear_registry_cache()


# --- Contract ----------------------------------------------------------------


def test_valid_manifest_parses():
    manifest = AnalyzerManifest.model_validate(VALID_MANIFEST)
    assert manifest.key == "my_detector"
    assert manifest.trust == "local"


@pytest.mark.parametrize(
    "override",
    [
        {"capabilities": ["transcription"]},  # transcription requires input=audio
        {"capabilities": ["pii", "ocr"]},  # mixed text+image capabilities
        {"key": "Bad Key!"},
        {"contract": "fw-analyzer/2"},
        {"capabilities": []},
    ],
)
def test_invalid_manifests_are_rejected(override):
    with pytest.raises(ValidationError):
        AnalyzerManifest.model_validate({**VALID_MANIFEST, **override})


def test_json_schemas_in_sync_with_models():
    """schemas/analyzer/*.schema.json are generated from the pydantic models."""
    for model, name in ((AnalyzerManifest, "manifest"), (AnalyzeResponse, "analyze-response")):
        expected = model.model_json_schema()
        expected["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        on_disk = json.loads((REPO_ROOT / "schemas" / "analyzer" / f"{name}.schema.json").read_text())
        assert on_disk == expected, f"{name}.schema.json is stale — regenerate from contract.py"


# --- Generic HTTP adapter -----------------------------------------------------


def _fake_analyzer_transport(tmp_path):
    """In-memory fw-analyzer/1 implementation."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/manifest":
            return httpx.Response(200, json=VALID_MANIFEST)
        if request.url.path == "/healthz":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path == "/analyze":
            if b"multipart/form-data" in request.headers.get("content-type", "").encode():
                return httpx.Response(200, json={"enrichment": {"transcription": "hello from audio"}})
            text = json.loads(request.content)["text"]
            findings = [{"kind": "pii", "value": w, "entity_type": "WORD"} for w in text.split()]
            return httpx.Response(200, json={"findings": findings})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_http_adapter_roundtrip(tmp_path):
    analyzer = HttpAnalyzer("http://fake", transport=_fake_analyzer_transport(tmp_path))

    manifest = analyzer.manifest()
    assert manifest.key == "my_detector"
    assert analyzer.healthz().available

    findings = analyzer.analyze_text("uno due")
    assert [(f.kind, f.value) for f in findings] == [("pii", "uno"), ("pii", "due")]

    audio = tmp_path / "voice.opus"
    audio.write_bytes(b"fake-opus")
    message = Message(id=1, chat_id=1, chat_name="c", sent=False, timestamp=datetime(2024, 1, 1),
                      message_type="audio", media_path=audio, mime_type="audio/ogg; codecs=opus")
    analyzer.enrich(message)
    assert message.transcription == "hello from audio"


# --- Resolution ----------------------------------------------------------------


def test_builtin_fallback_without_database():
    installed = registry.installed_analyzers()
    assert set(installed) == set(BUILTINS)
    assert all(a.type == "builtin" and a.enabled for a in installed.values())
    assert installed["presidio"].version == __version__


def test_legacy_aliases_default_to_local_providers():
    assert registry.expand_aliases(["S2T", "image_OCR", "presidio"]) == [
        "whisper", "tesseract", "lavis", "presidio",
    ]


def test_legacy_aliases_prefer_azure_when_enabled(monkeypatch):
    monkeypatch.setenv("FW_USE_MS_S2T", "true")
    monkeypatch.setenv("FW_MS_S2T_KEY", "k")
    monkeypatch.setenv("FW_USE_MS_OCR_CAPTION", "true")
    monkeypatch.setenv("FW_MS_CV_KEY", "k")
    clear_settings_cache()
    assert registry.expand_aliases(["S2T", "image_OCR"]) == ["microsoft_s2t", "microsoft_vision"]


def test_resolve_skips_unknown_keys():
    resolved = registry.resolve(["presidio", "nope"])
    assert [a.key for a in resolved] == ["presidio"]


def test_validate_requested_reports_unknown():
    assert registry.validate_requested(["presidio"]) == []
    assert registry.validate_requested(["nope"]) == ["unknown analyzer 'nope'"]


def test_media_applicability():
    installed = registry.installed_analyzers()
    audio_msg = Message(id=1, chat_id=1, chat_name="c", sent=False,
                        timestamp=datetime(2024, 1, 1),
                        message_type="audio", media_path=Path("x.opus"), mime_type="audio/ogg")
    image_msg = Message(id=2, chat_id=1, chat_name="c", sent=False,
                        timestamp=datetime(2024, 1, 1),
                        message_type="image", media_path=Path("x.jpg"), mime_type="image/jpeg")
    assert registry.applies_to_message(installed["whisper"], audio_msg)
    assert not registry.applies_to_message(installed["whisper"], image_msg)
    assert registry.applies_to_message(installed["tesseract"], image_msg)
    assert not registry.applies_to_message(installed["tesseract"], audio_msg)


def test_provenance_stamped_on_findings(monkeypatch):
    from forensicwace_core.analysis.analyzers import http_analyzer as http_mod
    from forensicwace_core.analysis.types import Finding

    class StubClient:
        def analyze_text(self, text):
            return [Finding(kind="password", value="hunter2", source="")]

    monkeypatch.setattr(http_mod, "client_for", lambda endpoint, config: StubClient())
    analyzer = registry.ResolvedAnalyzer(
        key="ext", type="http", name="Ext", capabilities=("password",), input="text",
        trust="local", version="9.9.9", enabled=True,
        endpoint="http://ext", image_digest="sha256:abc",
    )
    findings = registry.run_text_analyzer(analyzer, "x")
    assert findings[0].source == "ext"
    assert findings[0].analyzer_version == "9.9.9"
    assert findings[0].analyzer_digest == "sha256:abc"
