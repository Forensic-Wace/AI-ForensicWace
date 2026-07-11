"""Conversion of raw extraction rows into normalized :class:`Message` objects."""

from datetime import datetime
from pathlib import Path

from ..constants import ANDROID_MESSAGE_TYPES, IOS_MESSAGE_TYPES
from ..whatsapp.ios import find_media_file
from .types import Message


def from_android_rows(rows: list[dict], backup_dir: Path) -> list[Message]:
    """Map rows produced by ``whatsapp.android.get_filtered_messages``.

    Media paths in msgstore.db are relative to the extraction folder; they are
    resolved against the backup directory and kept only when the logical type
    supports downstream analysis (image OCR/caption, audio transcription).
    """
    messages = []
    for row in rows:
        logical_type = ANDROID_MESSAGE_TYPES.get(row["message_type"], "unknown")
        media_path = None
        if row.get("file_path"):
            candidate = (backup_dir / row["file_path"]).resolve()
            # The media file referenced by the DB may be absent from the extraction.
            if candidate.is_file():
                media_path = candidate

        mime_type = row.get("mime_type") or ""
        is_audio = "audio" in mime_type
        messages.append(
            Message(
                id=row["id"],
                chat_id=row["chat_id"],
                chat_name=row.get("chat_name"),
                sent=row["from_me"],
                timestamp=datetime.fromtimestamp(row["timestamp"] / 1000),
                message_type=logical_type,
                text=row.get("text"),
                media_path=media_path if (logical_type == "image" or is_audio) else None,
                mime_type=row.get("mime_type"),
                media_caption=row.get("media_caption"),
            )
        )
    return messages


def from_ios_rows(rows: list[dict], backup_dir: Path) -> list[Message]:
    """Map rows produced by ``whatsapp.ios.get_filtered_messages``.

    iOS media paths are logical (``Media/...`` relative to the WhatsApp
    ``Message/`` folder); the actual file lives under a hashed name resolved
    through Manifest.db, and only when the backup contains it.
    """
    messages = []
    for row in rows:
        logical_type = IOS_MESSAGE_TYPES.get(row["message_type"], "unknown")
        mime_type = row.get("mime_type") or ""
        is_audio = logical_type == "audio" or "audio" in mime_type

        media_path = None
        if row.get("media_local_path") and (logical_type == "image" or is_audio):
            media_path = find_media_file(backup_dir, relative_path=row["media_local_path"])

        messages.append(
            Message(
                id=row["id"],
                chat_id=row["chat_id"],
                chat_name=row.get("chat_name"),
                sent=row["from_me"],
                timestamp=datetime.fromtimestamp(row["timestamp"]),
                message_type=logical_type,
                text=row.get("text"),
                media_path=media_path,
                mime_type=row.get("mime_type"),
                media_caption=None,
            )
        )
    return messages
