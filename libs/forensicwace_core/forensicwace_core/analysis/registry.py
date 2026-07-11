"""Dynamic analyzer registry: resolution, execution and builtin seeding.

Analysis requests reference analyzer *keys*; this module resolves them
against the ``analyzers`` table (seeded with the built-ins, extended at
runtime with fw-analyzer/1 containers) and executes the right adapter.

Legacy aliases: old clients and stored processes may reference the historic
pseudo-keys ``S2T`` and ``image_OCR``; they expand to the configured
provider(s) exactly like the old settings-priority logic did.

Reads are cached briefly (workers resolve per message task); the registry
falls back to the builtin specs when the results database is unavailable so
status pages keep working on extraction-only deployments.
"""

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from .. import __version__
from ..config import get_settings
from .analyzers import BUILTINS, http_analyzer
from .types import AnalyzerStatus, Finding, Message

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 15.0

TEXT_CAPABILITIES = frozenset({"pii", "password"})
MEDIA_CAPABILITIES = frozenset({"transcription", "ocr", "caption"})


@dataclass(frozen=True)
class ResolvedAnalyzer:
    key: str
    type: str  # builtin | http
    name: str
    capabilities: tuple[str, ...]
    input: str  # text | audio | image
    trust: str
    version: str
    enabled: bool
    endpoint: str | None = None
    config: dict | None = None
    image_digest: str | None = None

    @property
    def is_media(self) -> bool:
        return self.input in ("audio", "image")


def _from_spec(spec) -> ResolvedAnalyzer:
    return ResolvedAnalyzer(
        key=spec.key,
        type="builtin",
        name=spec.name,
        capabilities=spec.capabilities,
        input=spec.input,
        trust=spec.trust,
        version=__version__,
        enabled=True,
    )


def resolved_from_row(row) -> ResolvedAnalyzer:
    return ResolvedAnalyzer(
        key=row.key,
        type=row.type,
        name=row.name,
        capabilities=tuple(row.capabilities or ()),
        input=row.input,
        trust=row.trust,
        version=row.version,
        enabled=bool(row.enabled),
        endpoint=row.endpoint,
        config=row.config or {},
        image_digest=row.image_digest,
    )


# --- Loading (with a short cache: workers resolve once per message task) ----

_cache_lock = threading.Lock()
_cache: tuple[float, dict[str, ResolvedAnalyzer]] | None = None


def _builtin_defaults() -> dict[str, ResolvedAnalyzer]:
    return {key: _from_spec(spec) for key, spec in BUILTINS.items()}


def _load_installed(strict: bool) -> dict[str, ResolvedAnalyzer]:
    if not get_settings().database_url:
        return _builtin_defaults()
    try:
        from ..resultsdb.engine import session_scope
        from ..resultsdb.models import Analyzer

        with session_scope() as session:
            installed = {row.key: resolved_from_row(row) for row in session.query(Analyzer).all()}
    except Exception:
        if strict:
            raise
        logger.warning("Analyzer registry unavailable — falling back to builtin defaults", exc_info=True)
        return _builtin_defaults()
    # built-ins resolve even before the seeding ran (e.g. worker up before API)
    for key, spec in BUILTINS.items():
        installed.setdefault(key, _from_spec(spec))
    return installed


def installed_analyzers(strict: bool = False) -> dict[str, ResolvedAnalyzer]:
    """All installed analyzers by key, cached for CACHE_TTL_SECONDS."""
    global _cache
    with _cache_lock:
        if _cache is not None and time.monotonic() - _cache[0] < CACHE_TTL_SECONDS:
            return _cache[1]
    loaded = _load_installed(strict)
    with _cache_lock:
        _cache = (time.monotonic(), loaded)
    return loaded


def clear_registry_cache() -> None:
    global _cache
    with _cache_lock:
        _cache = None


# --- Request resolution ------------------------------------------------------


def _s2t_targets() -> list[str]:
    settings = get_settings()
    return ["microsoft_s2t"] if settings.use_ms_s2t and settings.ms_s2t_key else ["whisper"]


def _vision_targets() -> list[str]:
    settings = get_settings()
    if settings.use_ms_ocr_caption and settings.ms_cv_key:
        return ["microsoft_vision"]
    return ["tesseract", "lavis"]


def expand_aliases(requested: list[str]) -> list[str]:
    keys: list[str] = []
    for key in requested:
        if key == "S2T":
            keys.extend(_s2t_targets())
        elif key == "image_OCR":
            keys.extend(_vision_targets())
        else:
            keys.append(key)
    return list(dict.fromkeys(keys))  # dedupe, order-preserving


def resolve(requested: list[str]) -> list[ResolvedAnalyzer]:
    """Enabled analyzers selected by a request (unknown keys are skipped)."""
    installed = installed_analyzers()
    return [installed[key] for key in expand_aliases(requested) if key in installed and installed[key].enabled]


def validate_requested(requested: list[str]) -> list[str]:
    """Human-readable problems with a request's analyzer list (for 422s)."""
    installed = installed_analyzers()
    problems = []
    for key in expand_aliases(requested):
        if key not in installed:
            problems.append(f"unknown analyzer {key!r}")
        elif not installed[key].enabled:
            problems.append(f"analyzer {key!r} is disabled")
    return problems


# --- Execution ----------------------------------------------------------------


def applies_to_message(analyzer: ResolvedAnalyzer, message: Message) -> bool:
    """Whether a media analyzer can enrich this message."""
    if message.media_path is None:
        return False
    if analyzer.input == "audio":
        return "audio" in (message.mime_type or "")
    if analyzer.input == "image":
        return message.message_type == "image"
    return False


def run_text_analyzer(analyzer: ResolvedAnalyzer, text: str) -> list[Finding]:
    if analyzer.type == "builtin":
        spec = BUILTINS[analyzer.key]
        findings = spec.text_fn(text) if spec.text_fn else []
    else:
        findings = http_analyzer.client_for(analyzer.endpoint, analyzer.config).analyze_text(text)
    for finding in findings:
        finding.source = finding.source or analyzer.key
        finding.analyzer_version = analyzer.version
        finding.analyzer_digest = analyzer.image_digest
    return findings


def run_media_analyzer(analyzer: ResolvedAnalyzer, message: Message) -> None:
    if analyzer.type == "builtin":
        spec = BUILTINS[analyzer.key]
        if spec.media_fn is not None:
            spec.media_fn(message)
    else:
        http_analyzer.client_for(analyzer.endpoint, analyzer.config).enrich(message)


def check_status(analyzer: ResolvedAnalyzer) -> AnalyzerStatus:
    if analyzer.type == "builtin":
        status = BUILTINS[analyzer.key].status_fn()
    else:
        status = http_analyzer.client_for(analyzer.endpoint, analyzer.config).healthz()
    # normalize on the registry key: it is what requests and the UI reference
    return AnalyzerStatus(name=analyzer.key, available=status.available, detail=status.detail)


def all_statuses() -> list[AnalyzerStatus]:
    """Live health of every installed analyzer (may be slow: calls out)."""
    statuses = []
    for analyzer in installed_analyzers().values():
        try:
            statuses.append(check_status(analyzer))
        except Exception as exc:  # a broken analyzer must never break the health page
            statuses.append(AnalyzerStatus(name=analyzer.key, available=False, detail=str(exc)))
    return statuses


# --- Builtin seeding ----------------------------------------------------------


def sync_builtin_analyzers() -> None:
    """Idempotent upsert of the builtin rows (operator state is preserved)."""
    from ..resultsdb.engine import session_scope
    from ..resultsdb.models import Analyzer

    now = datetime.now(timezone.utc)
    with session_scope() as session:
        existing = {row.key: row for row in session.query(Analyzer).filter_by(type="builtin").all()}
        for key, spec in BUILTINS.items():
            row = existing.get(key)
            if row is None:
                session.add(
                    Analyzer(
                        key=key,
                        name=spec.name,
                        version=__version__,
                        type="builtin",
                        capabilities=list(spec.capabilities),
                        input=spec.input,
                        trust=spec.trust,
                        config={},
                        enabled=True,
                        installed_at=now,
                        updated_at=now,
                    )
                )
            else:  # refresh spec-owned fields, keep enabled/config (operator state)
                row.name = spec.name
                row.version = __version__
                row.capabilities = list(spec.capabilities)
                row.input = spec.input
                row.trust = spec.trust
                row.updated_at = now
    clear_registry_cache()
