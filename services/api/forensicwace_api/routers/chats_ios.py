"""iOS chat data endpoints (extraction + signed PDF exports + media)."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from forensicwace_core.backups.ios import resolve_backup_dir
from forensicwace_core.config import get_settings
from forensicwace_core.constants import IOS_MESSAGE_TYPE_FILTERS
from forensicwace_core.reporting import chat_pdf, tables, timestamping
from forensicwace_core.whatsapp import ios

from ..schemas import PrivateChatOut

router = APIRouter(prefix="/backups/ios/{udid}", tags=["ios"])

_TYPE_FILTER_QUERY = Query(default=None, description=f"One of: {', '.join(IOS_MESSAGE_TYPE_FILTERS)}")


def _backup_dir(udid: str) -> Path:
    return resolve_backup_dir(get_settings().ios_dir, udid)


def _zip_response(zip_path: Path) -> FileResponse:
    return FileResponse(zip_path, media_type="application/zip", filename=zip_path.name)


@router.get("/chats")
def chat_list(udid: str) -> list[dict]:
    return ios.get_chat_list(_backup_dir(udid))


@router.get("/chats/{phone_number}/messages", response_model=PrivateChatOut)
def private_chat(udid: str, phone_number: str, type_filter: str | None = _TYPE_FILTER_QUERY):
    counters, messages = ios.get_private_chat(_backup_dir(udid), phone_number)
    return PrivateChatOut(counters=counters, messages=ios.filter_messages_by_type(messages, type_filter))


@router.get("/groups")
def group_list(udid: str) -> list[dict]:
    return ios.get_group_list(_backup_dir(udid))


@router.get("/groups/{group_name}/messages", response_model=PrivateChatOut)
def group_chat(udid: str, group_name: str, type_filter: str | None = _TYPE_FILTER_QUERY):
    counters, messages = ios.get_group_chat(_backup_dir(udid), group_name)
    return PrivateChatOut(counters=counters, messages=ios.filter_messages_by_type(messages, type_filter))


@router.get("/gps-locations")
def gps_locations(udid: str) -> list[dict]:
    return ios.get_gps_locations(_backup_dir(udid))


@router.get("/blocked-contacts")
def blocked_contacts(udid: str) -> list[dict]:
    return ios.get_blocked_contacts(_backup_dir(udid))


@router.get("/media")
def media(udid: str, relative_path: str | None = None, profile_of: str | None = None):
    """Serve a media file or profile picture from the hashed backup layout."""
    if (relative_path is None) == (profile_of is None):
        raise HTTPException(status_code=400, detail="Pass exactly one of relative_path or profile_of")
    path = ios.find_media_file(_backup_dir(udid), relative_path=relative_path, profile_of=profile_of)
    if path is None:
        raise HTTPException(status_code=404, detail="Media file not found in backup")
    return FileResponse(path)


# --- Signed PDF exports -----------------------------------------------------


@router.get("/exports/chat-list")
def export_chat_list(udid: str):
    pdf = tables.chat_list_pdf(ios.get_chat_list(_backup_dir(udid)))
    return _zip_response(timestamping.sign_and_zip(pdf, f"{udid}-ChatList"))


@router.get("/exports/gps-locations")
def export_gps_locations(udid: str):
    pdf = tables.gps_locations_pdf(ios.get_gps_locations(_backup_dir(udid)))
    return _zip_response(timestamping.sign_and_zip(pdf, f"{udid}-GpsLocations"))


@router.get("/exports/blocked-contacts")
def export_blocked_contacts(udid: str):
    pdf = tables.blocked_contacts_pdf(ios.get_blocked_contacts(_backup_dir(udid)))
    return _zip_response(timestamping.sign_and_zip(pdf, f"{udid}-BlockedContacts"))


@router.get("/exports/group-list")
def export_group_list(udid: str):
    pdf = tables.group_list_pdf(ios.get_group_list(_backup_dir(udid)))
    return _zip_response(timestamping.sign_and_zip(pdf, f"{udid}-GroupList"))


@router.get("/exports/chats/{phone_number}")
def export_private_chat(udid: str, phone_number: str):
    _, messages = ios.get_private_chat(_backup_dir(udid), phone_number)
    pdf = chat_pdf.chat_transcript_pdf(messages, contact_name_key="contactName")
    return _zip_response(timestamping.sign_and_zip(pdf, f"{udid}-PrivateChat-{phone_number}"))


@router.get("/exports/groups/{group_name}")
def export_group_chat(udid: str, group_name: str):
    _, messages = ios.get_group_chat(_backup_dir(udid), group_name)
    pdf = chat_pdf.chat_transcript_pdf(messages, contact_name_key="contactName")
    safe_name = "".join(group_name.split())
    return _zip_response(timestamping.sign_and_zip(pdf, f"{udid}-GroupChat-{safe_name}"))
