"""Android chat data endpoints.

Feature parity with the legacy platform: chat list, private chat, group list
and GPS locations. Blocked contacts live in ``wa.db`` and were never wired up;
they return 501 until the schema registry phase adds support.
"""

from pathlib import Path

from fastapi import APIRouter, Query

from forensicwace_core.backups.android import resolve_db_path
from forensicwace_core.config import get_settings
from forensicwace_core.whatsapp import android

from ..schemas import PrivateChatOut

router = APIRouter(prefix="/backups/android/{folder}", tags=["android"])

_DB_QUERY = Query(default="msgstore.db", description="Database file name inside the extraction folder")


def _db_path(folder: str, db: str) -> Path:
    return resolve_db_path(get_settings().android_dir, folder, db)


@router.get("/chats")
def chat_list(folder: str, db: str = _DB_QUERY) -> list[dict]:
    return android.get_chat_list(_db_path(folder, db))


@router.get("/chats/{phone_number}/messages", response_model=PrivateChatOut)
def private_chat(folder: str, phone_number: str, db: str = _DB_QUERY):
    counters, messages = android.get_private_chat(_db_path(folder, db), phone_number)
    return PrivateChatOut(counters=counters, messages=messages)


@router.get("/groups")
def group_list(folder: str, db: str = _DB_QUERY) -> list[dict]:
    return android.get_group_list(_db_path(folder, db))


@router.get("/gps-locations")
def gps_locations(folder: str, db: str = _DB_QUERY) -> list[dict]:
    return android.get_gps_locations(_db_path(folder, db))


@router.get("/blocked-contacts")
def blocked_contacts(folder: str, db: str = _DB_QUERY) -> list[dict]:
    # Whether this works is decided by the matched query pack: on the modern
    # Android schema it raises UnsupportedCapabilityError (block list lives in
    # wa.db), which the API maps to a 501 with the descriptor id.
    return android.get_blocked_contacts(_db_path(folder, db))
