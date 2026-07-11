"""WhatsApp data extraction from iOS ``ChatStorage.sqlite``.

Extraction SQL is resolved through the schema registry: the database is
fingerprinted and the matching query pack (schemas/whatsapp/ios/...) provides
the statements. Manifest.db lookups are iOS-backup plumbing, not WhatsApp
schema, so they stay in :mod:`manifest_queries`.
"""

from datetime import datetime
from pathlib import Path

from ..backups.ios import chatstorage_path, manifest_db_path
from ..constants import IOS_MESSAGE_TYPE_FILTERS, IOS_TYPE_CODES, WHATSAPP_IOS_DOMAIN, Platform
from ..schema_registry import SchemaMatch, resolve
from ..utils.timeconv import APPLE_EPOCH_OFFSET
from . import ios_queries as q
from . import manifest_queries
from .sqlite import open_readonly, query_dicts


def schema_match(backup_dir: Path) -> SchemaMatch:
    return resolve(chatstorage_path(backup_dir), Platform.IOS)


def get_chat_list(backup_dir: Path) -> list[dict]:
    return query_dicts(chatstorage_path(backup_dir), schema_match(backup_dir).sql("chat_list"))


def get_private_chat(backup_dir: Path, phone_number: str) -> tuple[dict, list[dict]]:
    """Counters and messages for the 1:1 chat with the given phone number.

    Matching uses the last 10 digits, consistent with how WhatsApp JIDs embed
    the number without country-code normalization.
    """
    db = chatstorage_path(backup_dir)
    pack = schema_match(backup_dir)
    params = {"jid_pattern": f"%{phone_number[-10:]}%"}
    counters = query_dicts(db, pack.sql("private_chat_counters"), params)
    messages = query_dicts(db, pack.sql("private_chat_messages"), params)
    return counters[0] if counters else {}, messages


def get_group_list(backup_dir: Path) -> list[dict]:
    return query_dicts(chatstorage_path(backup_dir), schema_match(backup_dir).sql("group_list"))


def get_group_chat(backup_dir: Path, group_name: str) -> tuple[dict, list[dict]]:
    db = chatstorage_path(backup_dir)
    pack = schema_match(backup_dir)
    params = {"group_pattern": group_name}
    counters = query_dicts(db, pack.sql("group_chat_counters"), params)
    messages = query_dicts(db, pack.sql("group_chat_messages"), params)
    return counters[0] if counters else {}, messages


def get_gps_locations(backup_dir: Path) -> list[dict]:
    return query_dicts(chatstorage_path(backup_dir), schema_match(backup_dir).sql("gps_locations"))


def get_blocked_contacts(backup_dir: Path) -> list[dict]:
    return query_dicts(chatstorage_path(backup_dir), schema_match(backup_dir).sql("blocked_contacts"))


def filter_messages_by_type(messages: list[dict], type_filter: str | None) -> list[dict]:
    """Restrict messages to a media-type filter key (see IOS_MESSAGE_TYPE_FILTERS)."""
    if not type_filter:
        return messages
    allowed = IOS_MESSAGE_TYPE_FILTERS.get(type_filter)
    if allowed is None:
        return messages
    return [m for m in messages if m.get("ZMESSAGETYPE") in allowed]


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

    Each returned row has: chat_name, id, chat_id, from_me, timestamp (Unix
    seconds), message_type (raw ZMESSAGETYPE code), text, media_local_path
    (relative to ``Message/`` in the backup manifest), mime_type.

    Sent messages carry no ZFROMJID in this schema generation, so direction is
    derived from its presence.
    """
    contacts = [c for c in (contacts or []) if c]
    groups = [g for g in (groups or []) if g]

    conn = open_readonly(db_path)
    try:
        chat_names: dict[int, str] = {}
        for contact in contacts:
            for row in conn.execute(q.PRIVATE_SESSION_BY_JID, (f"%{contact[-10:]}%",)):
                chat_names[row["Z_PK"]] = row["ZPARTNERNAME"]
        if groups:
            sql = q.GROUP_SESSIONS_BY_NAME.format(placeholders=_in_clause(len(groups)))
            for row in conn.execute(sql, groups):
                chat_names[row["Z_PK"]] = row["ZPARTNERNAME"]

        if not chat_names:
            return []

        chat_ids = list(chat_names)
        sql = q.MESSAGES_BASE.format(placeholders=_in_clause(len(chat_ids)))
        params: list = list(chat_ids)

        if date_from is not None and date_to is not None:
            sql += " AND m.ZMESSAGEDATE >= ? AND m.ZMESSAGEDATE <= ?"
            params += [date_from.timestamp() - APPLE_EPOCH_OFFSET, date_to.timestamp() - APPLE_EPOCH_OFFSET]

        if include_received and not include_sent:
            sql += " AND m.ZFROMJID IS NOT NULL"
        elif include_sent and not include_received:
            sql += " AND m.ZFROMJID IS NULL"

        type_codes = [code for t in (message_types or []) for code in IOS_TYPE_CODES.get(t, ())]
        if type_codes:
            sql += f" AND m.ZMESSAGETYPE IN ({_in_clause(len(type_codes))})"
            params += type_codes

        sql += " ORDER BY m.ZCHATSESSION, m.ZMESSAGEDATE"

        results = []
        for row in conn.execute(sql, params):
            media_meta = row["media_meta"]
            results.append(
                {
                    "chat_name": chat_names.get(row["chat_id"]),
                    "id": row["id"],
                    "chat_id": row["chat_id"],
                    "from_me": row["from_jid"] is None,
                    "timestamp": (row["message_date"] or 0) + APPLE_EPOCH_OFFSET,
                    "message_type": row["message_type"],
                    "text": row["text"],
                    "media_local_path": row["media_local_path"],
                    # ZVCARDSTRING holds the MIME type on media items; on
                    # contact-card messages it holds the vCard itself.
                    "mime_type": media_meta if media_meta and "/" in media_meta and "\n" not in media_meta else None,
                }
            )
        return results
    finally:
        conn.close()


def find_media_file(backup_dir: Path, relative_path: str | None = None, profile_of: str | None = None) -> Path | None:
    """Locate a media file inside the hashed iOS backup layout via Manifest.db.

    Exactly one of ``relative_path`` (chat media, relative to ``Message/``) or
    ``profile_of`` (phone number / 'Photo' for the owner picture) must be given.
    Returns the on-disk path of the stored file, or None when not present.
    """
    if (relative_path is None) == (profile_of is None):
        raise ValueError("Pass exactly one of relative_path or profile_of")

    if relative_path is not None:
        sql, pattern = manifest_queries.CHAT_MEDIA, f"Message/{relative_path}"
    else:
        sql, pattern = manifest_queries.PROFILE_PIC, f"Media/Profile/%{profile_of}%"

    rows = query_dicts(manifest_db_path(backup_dir), sql, {"domain": WHATSAPP_IOS_DOMAIN, "path_pattern": pattern})
    for row in rows:
        # flags == 1 marks an actual file present in the backup
        if row["relativePath"] and row["flags"] == 1:
            file_id = row["fileID"]
            path = backup_dir / file_id[:2] / file_id
            if path.is_file():
                return path
    return None
