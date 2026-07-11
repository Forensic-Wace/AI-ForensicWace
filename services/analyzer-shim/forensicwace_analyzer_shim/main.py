"""fw-analyzer/1 shim for the historical analyzer sidecars.

One image, one target per instance: ``FW_SHIM_TARGET`` selects which sidecar
this shim wraps (deeppass | whisper | tesseract | lavis) and
``FW_SHIM_TARGET_URL`` points at it. The shim translates the standard
contract (see docs/analyzer-contract.md) into each sidecar's native API, so
the sidecars become installable through the analyzer registry like any other
conforming container — no bespoke adapter in the platform.

Run: ``uvicorn --factory forensicwace_analyzer_shim.main:build``
"""

import json
import os
from dataclasses import dataclass, field

import httpx
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse

from . import __version__

TIMEOUT = 120.0

_TESSERACT_CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "languages": {"type": "array", "items": {"type": "string"}, "default": ["eng"]},
    },
}


@dataclass(frozen=True)
class Target:
    key: str  # default registry key (override with FW_SHIM_KEY)
    name: str
    capabilities: tuple[str, ...]
    input: str  # text | audio | image
    config_schema: dict = field(default_factory=dict)


TARGETS: dict[str, Target] = {
    "deeppass": Target("deeppass", "DeepPass password detector", ("password",), "text"),
    "whisper": Target("whisper_asr", "Whisper ASR transcription", ("transcription",), "audio"),
    "tesseract": Target("tesseract_ocr", "Tesseract image OCR", ("ocr",), "image", _TESSERACT_CONFIG_SCHEMA),
    "lavis": Target("lavis_caption", "LAVIS image captioning", ("caption",), "image"),
}


# --- Native-API translations (mirroring the platform's legacy adapters) ------


def _analyze_deeppass(client: httpx.Client, url: str, text: str) -> list[dict]:
    response = client.post(f"{url.rstrip('/')}/api/text", content=text)
    response.raise_for_status()
    payload = response.json()
    model = [c["password"] for c in payload.get("model_password_candidates", [])]
    regex = [c["password"] for c in payload.get("regex_password_candidates", [])]
    findings = [{"kind": "password", "value": p} for p in model]
    findings += [{"kind": "password", "value": p} for p in regex if p not in model]
    return findings


def _enrich_whisper(client, url, filename, content, mime, config) -> dict:
    # encode=true lets the ASR webservice transcode opus/mp4 voice notes itself
    response = client.post(
        url,
        params={"encode": "true", "task": "transcribe", "output": "txt"},
        files={"audio_file": (filename, content, mime or "application/octet-stream")},
        headers={"accept": "application/json"},
    )
    response.raise_for_status()
    return {"transcription": response.text.strip()}


def _enrich_tesseract(client, url, filename, content, mime, config) -> dict:
    options = {"languages": config.get("languages", ["eng"])}
    response = client.post(
        url,
        data={"options": json.dumps(options)},
        files=[("file", (filename, content, mime or "image/jpeg"))],
    )
    response.raise_for_status()
    return {"ocr_text": response.json()["data"]["stdout"]}


def _enrich_lavis(client, url, filename, content, mime, config) -> dict:
    response = client.post(url, files=[("file", (filename, content, mime or "image/jpeg"))])
    response.raise_for_status()
    return {"caption": response.json()["caption"]}


_MEDIA_HANDLERS = {
    "whisper": _enrich_whisper,
    "tesseract": _enrich_tesseract,
    "lavis": _enrich_lavis,
}


# --- App ----------------------------------------------------------------------


def create_app(
    target_kind: str,
    target_url: str,
    key: str | None = None,
    transport: httpx.BaseTransport | None = None,
) -> FastAPI:
    target = TARGETS[target_kind]
    client = httpx.Client(timeout=TIMEOUT, transport=transport)
    app = FastAPI(title=f"fw-analyzer shim: {target.name}")

    manifest_doc = {
        "contract": "fw-analyzer/1",
        "key": key or target.key,
        "name": f"{target.name} (shim)",
        "version": __version__,
        "capabilities": list(target.capabilities),
        "input": target.input,
        "config_schema": target.config_schema,
        "trust": "local",
    }

    @app.get("/manifest")
    def manifest() -> dict:
        return manifest_doc

    @app.get("/healthz")
    def healthz():
        # any HTTP answer from the sidecar (even 405 on GET) proves it is alive
        try:
            client.get(target_url)
        except httpx.HTTPError as exc:
            return JSONResponse(status_code=503, content={"status": "upstream unreachable", "detail": str(exc)})
        return {"status": "ok"}

    if target.input == "text":

        @app.post("/analyze")
        def analyze_text(body: dict) -> dict:
            return {"findings": _analyze_deeppass(client, target_url, body.get("text", ""))}

    else:
        handler = _MEDIA_HANDLERS[target_kind]

        @app.post("/analyze")
        def analyze_media(file: UploadFile = File(...), config: str = Form("{}")) -> dict:
            parsed = json.loads(config or "{}")
            enrichment = handler(client, target_url, file.filename, file.file.read(), file.content_type, parsed)
            return {"enrichment": enrichment}

    return app


def build() -> FastAPI:
    """uvicorn factory: configuration comes from FW_SHIM_* env variables."""
    target = os.environ.get("FW_SHIM_TARGET", "")
    url = os.environ.get("FW_SHIM_TARGET_URL", "")
    if target not in TARGETS or not url:
        raise RuntimeError(f"Set FW_SHIM_TARGET (one of: {', '.join(sorted(TARGETS))}) and FW_SHIM_TARGET_URL")
    return create_app(target, url, key=os.environ.get("FW_SHIM_KEY"))
