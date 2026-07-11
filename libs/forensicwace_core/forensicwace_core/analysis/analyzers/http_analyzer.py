"""Generic adapter for containers implementing the fw-analyzer/1 contract.

This is the whole point of the marketplace: one adapter for every conforming
analyzer, instead of one bespoke module each. Evidence reaches the analyzer
only through the request payload — never volume mounts.
"""

import json
from functools import lru_cache

import httpx

from ..contract import AnalyzeResponse, AnalyzerManifest
from ..types import AnalyzerStatus, Finding, Message

TIMEOUT = 120.0


class HttpAnalyzer:
    def __init__(self, endpoint: str, config: dict | None = None, transport: httpx.BaseTransport | None = None):
        self.endpoint = endpoint.rstrip("/")
        self.config = config or {}
        self._client = httpx.Client(base_url=self.endpoint, timeout=TIMEOUT, transport=transport)

    def manifest(self) -> AnalyzerManifest:
        response = self._client.get("/manifest")
        response.raise_for_status()
        return AnalyzerManifest.model_validate(response.json())

    def healthz(self) -> AnalyzerStatus:
        try:
            response = self._client.get("/healthz")
            response.raise_for_status()
            return AnalyzerStatus(self.endpoint, True, "Healthy")
        except Exception as exc:
            return AnalyzerStatus(self.endpoint, False, str(exc))

    def analyze_text(self, text: str) -> list[Finding]:
        response = self._client.post("/analyze", json={"text": text, "config": self.config})
        response.raise_for_status()
        payload = AnalyzeResponse.model_validate(response.json())
        return [
            Finding(kind=f.kind, value=f.value, entity_type=f.entity_type, source="")
            for f in payload.findings
        ]

    def enrich(self, message: Message) -> None:
        """Send the media file, apply the returned enrichment to the message."""
        if message.media_path is None:
            return
        with open(message.media_path, "rb") as media:
            response = self._client.post(
                "/analyze",
                files={"file": (message.media_path.name, media, message.mime_type or "application/octet-stream")},
                data={"config": json.dumps(self.config)},
            )
        response.raise_for_status()
        payload = AnalyzeResponse.model_validate(response.json())
        if payload.enrichment is not None:
            if payload.enrichment.transcription is not None:
                message.transcription = payload.enrichment.transcription
            if payload.enrichment.ocr_text is not None:
                message.ocr_text = payload.enrichment.ocr_text
            if payload.enrichment.caption is not None:
                message.caption = payload.enrichment.caption


@lru_cache(maxsize=64)
def _cached_client(endpoint: str, config_json: str) -> HttpAnalyzer:
    return HttpAnalyzer(endpoint, json.loads(config_json))


def client_for(endpoint: str, config: dict | None) -> HttpAnalyzer:
    """Reuse one client per (endpoint, config) across the many per-message calls."""
    return _cached_client(endpoint, json.dumps(config or {}, sort_keys=True))


def clear_client_cache() -> None:
    _cached_client.cache_clear()
