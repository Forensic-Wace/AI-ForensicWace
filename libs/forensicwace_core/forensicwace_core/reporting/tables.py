"""Tabular PDF exports (chat list, GPS locations, blocked contacts, groups)."""

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

from ..config import get_settings
from ..utils.phone import format_phone_number_or_raw

_TABLE_STYLE = TableStyle(
    [
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 11),
        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.black),
        ("ALIGN", (0, 1), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
    ]
)


def _logo_path() -> str | None:
    assets = get_settings().assets_dir
    if assets is None:
        return None
    logo = assets / "img" / "Logo.png"
    return str(logo) if logo.is_file() else None


def _header_and_footer(canvas, doc) -> None:
    canvas.saveState()
    logo = _logo_path()
    if logo:
        canvas.drawImage(logo, A4[0] / 2 - 158, A4[1] - 65, width=300, height=52.5)
    canvas.restoreState()
    canvas.drawCentredString(105 * mm, 20 * mm, f"Page {canvas.getPageNumber()}")
    canvas.line(15 * mm, 25 * mm, 195 * mm, 25 * mm)


def table_pdf(headers: list[str], rows: list[list]) -> bytes:
    """Render a header row plus data rows into an A4 PDF."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    table = Table([headers, *rows], colWidths=[100, 110, 110, 110])
    table.setStyle(_TABLE_STYLE)
    doc.build([table], onFirstPage=_header_and_footer, onLaterPages=_header_and_footer)
    return buffer.getvalue()


def chat_list_pdf(chats: list[dict]) -> bytes:
    rows = [
        [
            c.get("Contact"),
            c.get("UserName"),
            format_phone_number_or_raw(c.get("PhoneNumber") or ""),
            c.get("NumberOfMessages"),
            c.get("MessageDate"),
        ]
        for c in chats
    ]
    return table_pdf(["Contact", "Username", "Phone number", "Number of messages", "Last Message Date"], rows)


def gps_locations_pdf(locations: list[dict]) -> bytes:
    rows = [
        [
            format_phone_number_or_raw(loc.get("Sender") or ""),
            format_phone_number_or_raw(loc.get("Receiver") or ""),
            loc.get("MessageDate"),
            loc.get("Latitude"),
            loc.get("Longitude"),
        ]
        for loc in locations
    ]
    return table_pdf(["Sender", "Receiver", "Date", "Latitude", "Longitude"], rows)


def blocked_contacts_pdf(contacts: list[dict]) -> bytes:
    rows = [
        [c.get("Name") or "Not available", format_phone_number_or_raw(c.get("PhoneNumber") or "")]
        for c in contacts
    ]
    return table_pdf(["Name", "Phone number"], rows)


def group_list_pdf(groups: list[dict]) -> bytes:
    rows = [
        [
            g.get("Group_Name"),
            g.get("Message_Date"),
            g.get("Number_of_Messages"),
            "DISABLED" if g.get("Is_muted") is not None else "ENABLED",
        ]
        for g in groups
    ]
    return table_pdf(["GroupName", "LastMessage", "NumberOfMessages", "NotificationStatus"], rows)
