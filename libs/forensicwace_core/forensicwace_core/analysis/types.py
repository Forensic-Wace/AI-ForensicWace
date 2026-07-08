"""Data types flowing through the analysis pipeline."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class Message:
    """A normalized chat message, platform-independent."""

    id: int | str
    chat_id: int | str | None
    chat_name: str | None
    sent: bool
    timestamp: datetime
    message_type: str  # logical type: text, image, audio, video, ...
    text: str | None = None
    media_path: Path | None = None
    mime_type: str | None = None
    media_caption: str | None = None

    # Enrichment produced by media analyzers
    transcription: str | None = None
    caption: str | None = None
    ocr_text: str | None = None

    def analysis_text(self) -> str | None:
        """The text handed to the PII/password analyzers: original text plus
        everything extracted from media."""
        parts = [p for p in (self.text, self.transcription, self.caption, self.ocr_text, self.media_caption) if p]
        return " ".join(parts) if parts else None


@dataclass
class AnalyzerStatus:
    name: str
    available: bool
    detail: str = ""


@dataclass
class Finding:
    """A single PII entity or password detected in a message."""

    kind: str  # "pii" | "password"
    value: str
    source: str
    entity_type: str | None = None  # for PII


@dataclass
class AnalysisOutcome:
    findings: list[Finding] = field(default_factory=list)
