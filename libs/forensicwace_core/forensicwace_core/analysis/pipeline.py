"""The analysis pipeline: extract messages, enrich media, detect PII/passwords.

Phase 1 runs this in a background thread inside the API service; Phase 3 moves
the exact same entrypoint (``run_analysis``) into queue-driven workers.
"""

import logging
from datetime import datetime
from pathlib import Path

from ..config import get_settings
from ..constants import Platform
from ..resultsdb import repositories
from ..resultsdb.engine import session_scope
from ..resultsdb.models import PII, Password, ProcessStatus, Text
from ..whatsapp import android
from . import analyzers
from .analyzers import speech, vision
from .messages import from_android_rows
from .types import Message

logger = logging.getLogger(__name__)

# Analyzer keys with a special meaning: media enrichment stages.
S2T_KEY = "S2T"
IMAGE_KEY = "image_OCR"


def _extract_messages(process: ProcessStatus) -> list[Message]:
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


def _persist_message(session, process_id: str, message: Message, findings) -> None:
    text_row = Text(
        msg_id=str(message.id),
        process_id=process_id,
        text=message.analysis_text() or "",
        user_id=1,  # single-user until multi-user auth lands
        date=message.timestamp,
    )
    for finding in findings:
        if finding.kind == "password":
            text_row.passwords.append(Password(password=finding.value, source=finding.source))
        else:
            text_row.piis.append(PII(type=finding.entity_type, value=finding.value, source=finding.source))
    session.add(text_row)


def run_analysis(process_id: str) -> None:
    """Execute the analysis for a previously registered process."""
    with session_scope() as session:
        process = repositories.get_process(session, process_id)
        if process is None:
            logger.error("Unknown analysis process %s", process_id)
            return
        requested = [a for a in (process.analyzers or "").split(",") if a]
        text_analyzers = [a for a in requested if a in analyzers.TEXT_ANALYZERS]

        try:
            messages = _extract_messages(process)
        except Exception as exc:
            process.status = "Error"
            process.details = f"Extraction failed: {exc}"
            process.end_time = datetime.now()
            return

        total = len(messages)
        process.status = "Analyzing"
        process.details = f"Analyzing 0 over {total} messages"
        session.commit()

        for index, message in enumerate(messages, start=1):
            try:
                if S2T_KEY in requested and message.media_path and "audio" in (message.mime_type or ""):
                    speech.transcribe(message)
                if IMAGE_KEY in requested and message.media_path and message.message_type == "image":
                    vision.describe(message)

                text = message.analysis_text()
                if text:
                    findings = analyzers.run_text_analyzers(text, text_analyzers)
                    _persist_message(session, process_id, message, findings)
            except Exception:
                logger.exception("Analyzer failure on message %s (process %s)", message.id, process_id)

            process.details = f"Analyzed {index} over {total} messages"
            session.commit()

        process.status = "Finish"
        process.details = f"Analyzed all {total} messages"
        process.end_time = datetime.now()
