"""The analysis pipeline: extract messages, enrich media, detect PII/passwords.

The building blocks are executor-agnostic: ``extract_messages`` and
``process_message`` are called by the Celery workers (one task per message)
and by the in-process thread fallback (``run_analysis``) alike. Progress is
tracked in the ``process_status`` table with atomic counters, so any number of
concurrent workers can report safely.
"""

import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import update

from ..config import get_settings
from ..constants import Platform
from ..resultsdb import repositories
from ..resultsdb.engine import session_scope
from ..resultsdb.models import PII, Password, ProcessStatus, Text
from ..whatsapp import android
from . import registry
from .messages import from_android_rows
from .types import Message

logger = logging.getLogger(__name__)


def extract_messages(process: ProcessStatus) -> list[Message]:
    """Extract the messages selected by an analysis request."""
    if process.OS == Platform.ANDROID:
        backup_dir = get_settings().android_dir / process.extraction_name_udid
        rows = android.get_filtered_messages(
            Path(process.db_path),
            date_from=process.date_from,
            date_to=process.date_to,
            include_received=bool(process.received),
            include_sent=bool(process.sent),
            contacts=(process.contacts or "").split(","),
            groups=(process.groups or "").split(","),
            message_types=[t for t in (process.msg_type or "").split(",") if t],
        )
        return from_android_rows(rows, backup_dir)
    # iOS analysis was never implemented in the legacy platform either; the
    # request is accepted but yields no messages until the iOS path lands.
    logger.warning("Analysis for platform %s is not implemented yet", process.OS)
    return []


def needs_media_stage(message: Message, requested: list[str]) -> bool:
    """True when the message must pass through audio/image enrichment first."""
    return any(registry.applies_to_message(a, message) for a in registry.resolve(requested) if a.is_media)


def enrich_media(message: Message, requested: list[str]) -> Message:
    """Run the requested media analyzers, storing their output on the message."""
    for analyzer in registry.resolve(requested):
        if analyzer.is_media and registry.applies_to_message(analyzer, message):
            registry.run_media_analyzer(analyzer, message)
    return message


def analyze_and_persist(message: Message, process_id: str, requested: list[str]) -> None:
    """Run the text analyzers on one message and store text + findings.

    Idempotent per (process_id, msg_id): an earlier row from a retried task is
    replaced instead of duplicated.
    """
    text = message.analysis_text()
    if not text:
        return

    findings = []
    for analyzer in registry.resolve(requested):
        if analyzer.input == "text":
            findings.extend(registry.run_text_analyzer(analyzer, text))

    with session_scope() as session:
        stale = (
            session.query(Text)
            .filter(Text.process_id == process_id, Text.msg_id == str(message.id))
            .all()
        )
        for row in stale:
            session.delete(row)

        text_row = Text(
            msg_id=str(message.id),
            process_id=process_id,
            text=text,
            user_id=1,  # single-user until multi-user auth lands
            date=message.timestamp,
        )
        for finding in findings:
            if finding.kind == "password":
                text_row.passwords.append(
                    Password(
                        password=finding.value,
                        source=finding.source,
                        analyzer_version=finding.analyzer_version,
                        analyzer_digest=finding.analyzer_digest,
                    )
                )
            else:
                text_row.piis.append(
                    PII(
                        type=finding.entity_type,
                        value=finding.value,
                        source=finding.source,
                        analyzer_version=finding.analyzer_version,
                        analyzer_digest=finding.analyzer_digest,
                    )
                )
        session.add(text_row)


# --- Progress tracking -------------------------------------------------------


def start_processing(process_id: str, total: int) -> None:
    with session_scope() as session:
        session.execute(
            update(ProcessStatus)
            .where(ProcessStatus.process_id == process_id)
            .values(
                status="Analyzing",
                total_messages=total,
                analyzed_messages=0,
                failed_messages=0,
                details=f"Analyzing 0 over {total} messages",
            )
        )


def record_message_done(process_id: str, failed: bool = False) -> None:
    """Atomically bump the progress counters and finalize when complete."""
    counter = ProcessStatus.failed_messages if failed else ProcessStatus.analyzed_messages
    column = "failed_messages" if failed else "analyzed_messages"
    with session_scope() as session:
        session.execute(
            update(ProcessStatus).where(ProcessStatus.process_id == process_id).values({column: counter + 1})
        )
        session.commit()

        process = repositories.get_process(session, process_id)
        if process is None:
            return
        done = (process.analyzed_messages or 0) + (process.failed_messages or 0)
        total = process.total_messages or 0
        if done >= total:
            process.status = "Finish"
            process.details = _summary(process.analyzed_messages or 0, process.failed_messages or 0, total)
            process.end_time = datetime.now()
        else:
            process.details = f"Analyzed {done} over {total} messages" + (
                f" ({process.failed_messages} failed)" if process.failed_messages else ""
            )


def mark_process_error(process_id: str, reason: str) -> None:
    with session_scope() as session:
        session.execute(
            update(ProcessStatus)
            .where(ProcessStatus.process_id == process_id)
            .values(status="Error", details=reason[:500], end_time=datetime.now())
        )


def finish_empty(process_id: str) -> None:
    with session_scope() as session:
        session.execute(
            update(ProcessStatus)
            .where(ProcessStatus.process_id == process_id)
            .values(status="Finish", details="No messages matched the request", end_time=datetime.now())
        )


def _summary(analyzed: int, failed: int, total: int) -> str:
    summary = f"Analyzed {analyzed} of {total} messages"
    if failed:
        summary += f" — {failed} failed after retries (see dead-letter queue)"
    return summary


# --- In-process fallback executor -----------------------------------------------


def process_message(message: Message, process_id: str, requested: list[str]) -> None:
    """Full per-message pipeline (media enrichment + text analysis)."""
    enrich_media(message, requested)
    analyze_and_persist(message, process_id, requested)


def run_analysis(process_id: str) -> None:
    """Synchronous executor used when no message broker is configured."""
    with session_scope() as session:
        process = repositories.get_process(session, process_id)
        if process is None:
            logger.error("Unknown analysis process %s", process_id)
            return
        requested = [a for a in (process.analyzers or "").split(",") if a]
        try:
            messages = extract_messages(process)
        except Exception as exc:
            logger.exception("Extraction failed for process %s", process_id)
            process.status = "Error"
            process.details = f"Extraction failed: {exc}"
            process.end_time = datetime.now()
            return

    if not messages:
        finish_empty(process_id)
        return

    start_processing(process_id, len(messages))
    for message in messages:
        try:
            process_message(message, process_id, requested)
            record_message_done(process_id)
        except Exception:
            logger.exception("Analyzer failure on message %s (process %s)", message.id, process_id)
            record_message_done(process_id, failed=True)
