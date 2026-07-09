"""WhatsApp data extraction from iOS ``ChatStorage.sqlite``.

Extraction SQL is resolved through the schema registry: the database is
fingerprinted and the matching query pack (schemas/whatsapp/ios/...) provides
the statements. Manifest.db lookups are iOS-backup plumbing, not WhatsApp
schema, so they stay in :mod:`manifest_queries`.
"""

from pathlib import Path

from ..backups.ios import chatstorage_path, manifest_db_path
from ..constants import IOS_MESSAGE_TYPE_FILTERS, WHATSAPP_IOS_DOMAIN, Platform
from ..schema_registry import SchemaMatch, resolve
from . import manifest_queries
from .sqlite import query_dicts


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
