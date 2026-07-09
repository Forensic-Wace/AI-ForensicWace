"""WhatsApp data extraction from Android ``msgstore.db``.

Extraction SQL is resolved through the schema registry: the database is
fingerprinted and the matching query pack (schemas/whatsapp/android/...)
provides the statements. The analysis message selection is assembled
dynamically (IN clauses sized on the request) and stays in
:mod:`android_queries`.
"""

from datetime import datetime
from pathlib import Path

from ..constants import ANDROID_TYPE_CODES, Platform
from ..schema_registry import SchemaMatch, resolve
from . import android_queries as q
from .sqlite import open_readonly, query_dicts


def schema_match(db_path: Path) -> SchemaMatch:
    return resolve(db_path, Platform.ANDROID)


def get_chat_list(db_path: Path) -> list[dict]:
    return query_dicts(db_path, schema_match(db_path).sql("chat_list"))


def get_private_chat(db_path: Path, phone_number: str) -> tuple[dict, list[dict]]:
    """Counters and messages for the 1:1 chat matching the last 10 digits."""
    pack = schema_match(db_path)
    params = {"phone_pattern": f"%{phone_number[-10:]}%"}
    counters = query_dicts(db_path, pack.sql("private_chat_counters"), params)
    messages = query_dicts(db_path, pack.sql("private_chat_messages"), params)
    return counters[0] if counters else {}, messages


def get_group_list(db_path: Path) -> list[dict]:
    return query_dicts(db_path, schema_match(db_path).sql("group_list"))


def get_gps_locations(db_path: Path) -> list[dict]:
    return query_dicts(db_path, schema_match(db_path).sql("gps_locations"))


def get_blocked_contacts(db_path: Path) -> list[dict]:
    """Raises UnsupportedCapabilityError on schema generations that keep the
    block list in a companion database (wa.db)."""
    return query_dicts(db_path, schema_match(db_path).sql("blocked_contacts"))


def _in_clause(count: int) -> str:
    return ", ".join("?" for _ in range(count))


def get_filtered_messages(
    db_path: Path,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    include_received: bool = True,
    include_sent: bool = True,
    contacts: list[str] | None = None,
    groups: list[str] | None = None,
    message_types: list[str] | None = None,
) -> list[dict]:
    """Messages selected for AI analysis, joined with their media metadata.

    Each returned row has: chat_name, id, chat_id, from_me, timestamp (ms),
    message_type (raw code), text, file_path, file_size, media_caption, mime_type.
    """
    contacts = [c for c in (contacts or []) if c]
    groups = [g for g in (groups or []) if g]

    conn = open_readonly(db_path)
    try:
        chat_names: dict[int, str] = {}
        if contacts:
            sql = q.CHATS_BY_CONTACTS.format(placeholders=_in_clause(len(contacts)))
            for row in conn.execute(sql, contacts):
                chat_names[row["_id"]] = row["user"]
        if groups:
            sql = q.CHATS_BY_GROUP_SUBJECTS.format(placeholders=_in_clause(len(groups)))
            for row in conn.execute(sql, groups):
                chat_names[row["_id"]] = row["subject"]

        if not chat_names:
            return []

        chat_ids = list(chat_names)
        sql = (
            "SELECT _id, chat_row_id, from_me, timestamp, message_type, text_data "
            f"FROM message WHERE chat_row_id IN ({_in_clause(len(chat_ids))})"
        )
        params: list = list(chat_ids)

        if date_from is not None and date_to is not None:
            sql += " AND timestamp >= ? AND timestamp <= ?"
            params += [date_from.timestamp() * 1000, date_to.timestamp() * 1000]

        if include_received and not include_sent:
            sql += " AND from_me = 0"
        elif include_sent and not include_received:
            sql += " AND from_me = 1"

        type_codes = [code for t in (message_types or []) for code in ANDROID_TYPE_CODES.get(t, ())]
        if type_codes:
            sql += f" AND message_type IN ({_in_clause(len(type_codes))})"
            params += type_codes

        sql += " ORDER BY chat_row_id, timestamp"

        results = []
        for row in conn.execute(sql, params):
            media = conn.execute(q.MESSAGE_MEDIA, {"message_id": row["_id"]}).fetchone()
            results.append(
                {
                    "chat_name": chat_names.get(row["chat_row_id"]),
                    "id": row["_id"],
                    "chat_id": row["chat_row_id"],
                    "from_me": bool(row["from_me"]),
                    "timestamp": row["timestamp"],
                    "message_type": row["message_type"],
                    "text": row["text_data"],
                    "file_path": media["file_path"] if media else None,
                    "file_size": media["file_size"] if media else None,
                    "media_caption": media["media_caption"] if media else None,
                    "mime_type": media["mime_type"] if media else None,
                }
            )
        return results
    finally:
        conn.close()
