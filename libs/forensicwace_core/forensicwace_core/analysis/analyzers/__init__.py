"""Built-in analyzer specs.

Built-ins are analyzers whose adapter ships inside the core library: the
in-process ones (Presidio, StarPII), the bespoke local sidecars (DeepPass,
Whisper, Tesseract, LAVIS — until they conform to fw-analyzer/1 in marketplace
phase B) and the cloud SaaS ones (Azure, OpenAI). They are seeded into the
``analyzers`` registry table at API startup; runtime-installed analyzers are
``http`` rows handled by :mod:`.http_analyzer` instead.

Heavy dependencies (torch, transformers, presidio, Azure SDKs) are imported
lazily inside each module so the platform runs with any subset installed.
"""

from collections.abc import Callable
from dataclasses import dataclass

from ..types import AnalyzerStatus, Finding, Message


@dataclass(frozen=True)
class BuiltinSpec:
    key: str  # registry key: part of the public API contract
    name: str
    capabilities: tuple[str, ...]
    input: str  # text | audio | image
    trust: str  # local | cloud
    status_fn: Callable[[], AnalyzerStatus]
    text_fn: Callable[[str], list[Finding]] | None = None
    media_fn: Callable[[Message], None] | None = None


BUILTINS: dict[str, BuiltinSpec] = {}


def _register() -> None:
    from . import azure_pii, deeppass, gpt, presidio, speech, starpii, vision

    specs = [
        BuiltinSpec("presidio", "Presidio (local PII)", ("pii",), "text", "local",
                    presidio.check_status, text_fn=presidio.analyze),
        BuiltinSpec("starpii", "StarPII (local NER)", ("pii", "password"), "text", "local",
                    starpii.check_status, text_fn=starpii.analyze),
        BuiltinSpec("deep_password", "DeepPass (passwords)", ("password",), "text", "local",
                    deeppass.check_status, text_fn=deeppass.analyze),
        BuiltinSpec("gpt", "OpenAI GPT assistant", ("pii", "password"), "text", "cloud",
                    gpt.check_status, text_fn=gpt.analyze),
        BuiltinSpec("microsoftPII", "Azure Text Analytics PII", ("pii",), "text", "cloud",
                    azure_pii.check_status, text_fn=azure_pii.analyze),
        BuiltinSpec("whisper", "Whisper ASR (transcription)", ("transcription",), "audio", "local",
                    speech.check_status_whisper, media_fn=speech.transcribe_whisper),
        BuiltinSpec("microsoft_s2t", "Azure Speech-to-Text", ("transcription",), "audio", "cloud",
                    speech.check_status_microsoft, media_fn=speech.transcribe_azure),
        BuiltinSpec("tesseract", "Tesseract (image OCR)", ("ocr",), "image", "local",
                    vision.check_status_tesseract, media_fn=vision.ocr_tesseract),
        BuiltinSpec("lavis", "LAVIS (image captioning)", ("caption",), "image", "local",
                    vision.check_status_lavis, media_fn=vision.caption_lavis),
        BuiltinSpec("microsoft_vision", "Azure Computer Vision (OCR + caption)", ("ocr", "caption"), "image", "cloud",
                    vision.check_status_microsoft, media_fn=vision.describe_azure),
    ]
    BUILTINS.update({spec.key: spec for spec in specs})


_register()
