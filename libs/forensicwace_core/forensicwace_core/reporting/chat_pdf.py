"""Chat transcript PDF: WhatsApp-style bubbles, one renderer for private and
group chats (the legacy code had two near-identical 300-line copies).
"""

from dataclasses import dataclass
from io import BytesIO

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdf_canvas

from ..config import get_settings
from ..constants import DATABASE_OWNER, DELETED_MESSAGE_TEXT, INFO_NOT_AVAILABLE, IosMessageType
from ..utils.phone import format_phone_number_or_raw
from ..utils.timeconv import format_utc, receipt_read_datetime, receipt_sent_datetime, seconds_to_mmss

LEFT_MARGIN = 50
RIGHT_MARGIN = 50
TOP_MARGIN = 100
BOTTOM_MARGIN = 100
BOX_RADIUS = 20
LINE_WRAP = 85

OWNER_COLOR = HexColor("#DCF8C6")
CONTACT_COLOR = HexColor("#C6E9F9")
TEXT_COLOR = HexColor("#000000")


@dataclass
class _Bubble:
    icon: str | None  # icon base name under assets/img/icons
    label: str | None  # short text shown next to the icon
    lines: list[str]  # wrapped free-text lines (text messages only)


def _wrap_text(text: str) -> list[str]:
    lines, line = [], ""
    for word in (text or "").split():
        if len(line + word) > LINE_WRAP:
            lines.append(line)
            line = word + " "
        else:
            line += word + " "
    lines.append(line)
    return lines


def _bubble_for(message: dict, contact_name_key: str) -> _Bubble:
    mtype = message.get("ZMESSAGETYPE")
    duration = seconds_to_mmss(message.get("duration"))
    by_type = {
        IosMessageType.IMAGE: _Bubble("Camera", None, []),
        IosMessageType.VIDEO: _Bubble("Video", duration, []),
        IosMessageType.AUDIO: _Bubble("Mic", duration, []),
        IosMessageType.CONTACT: _Bubble("Contact", message.get(contact_name_key) or "", []),
        IosMessageType.POSITION: _Bubble("Position", f"{message.get('latitude')} , {message.get('longitude')}", []),
        IosMessageType.GROUP_EVENT: _Bubble("Group", None, []),
        IosMessageType.URL: _Bubble("Link", None, []),
        IosMessageType.FILE: _Bubble("Doc", message.get("text") if message.get("text") != "None" else None, []),
        IosMessageType.GIF: _Bubble("Gif", "GIF", []),
        IosMessageType.DELETED: _Bubble("Bin", DELETED_MESSAGE_TEXT, []),
        IosMessageType.STICKER: _Bubble("Sticker", "Sticker", []),
        IosMessageType.ONE_TIME_IMAGE: _Bubble("OneTime", "Image", []),
        IosMessageType.ONE_TIME_VIDEO: _Bubble("OneTime", duration, []),
        IosMessageType.POLL: _Bubble("Poll", "Poll", []),
    }
    if mtype in by_type:
        return by_type[mtype]
    return _Bubble(None, None, _wrap_text(message.get("text") or ""))


class _ChatCanvas:
    """Keeps track of the cursor and handles page breaks with logo/footer."""

    def __init__(self, buffer: BytesIO):
        self.canvas = pdf_canvas.Canvas(buffer, pagesize=A4)
        self.y = A4[1] - TOP_MARGIN
        assets = get_settings().assets_dir
        self.logo = str(assets / "img" / "Logo.png") if assets and (assets / "img" / "Logo.png").is_file() else None
        self.icons_dir = assets / "img" / "icons" if assets else None
        self._decorate_page()

    def _decorate_page(self) -> None:
        if self.logo:
            self.canvas.drawImage(self.logo, A4[0] / 2 - 150, A4[1] - 65, width=300, height=52.5)
        self.canvas.drawCentredString(105 * mm, 20 * mm, f"Page {self.canvas.getPageNumber()}")
        self.canvas.line(15 * mm, 25 * mm, 195 * mm, 25 * mm)

    def ensure_space(self, extra_offset: int = 0) -> None:
        if self.y < BOTTOM_MARGIN:
            self.canvas.showPage()
            self.y = A4[1] - TOP_MARGIN - extra_offset
            self._decorate_page()

    def draw_icon(self, name: str, is_owner: bool, x: float, y: float) -> None:
        if self.icons_dir is None:
            return
        icon = self.icons_dir / f"{name}{'User' if is_owner else 'Num'}.png"
        if icon.is_file():
            self.canvas.drawImage(str(icon), x, y, width=12, height=12)


def chat_transcript_pdf(messages: list[dict], contact_name_key: str = "contactName") -> bytes:
    """Render extracted iOS chat messages (private or group) as a PDF transcript.

    ``contact_name_key`` is the row key holding the sender's display name
    ('contactName' for private chats, group rows use it for members too but
    fall back to ZPARTNERNAME when absent).
    """
    buffer = BytesIO()
    page = _ChatCanvas(buffer)
    c = page.canvas
    previous_sender = object()

    for message in messages:
        page.ensure_space()

        bubble = _bubble_for(message, contact_name_key)
        is_owner = message.get("user") is None

        # Sender header when the speaker changes
        if previous_sender != message.get("user"):
            c.setFillColor(OWNER_COLOR if is_owner else CONTACT_COLOR)
            if is_owner:
                header = DATABASE_OWNER
            else:
                display_name = message.get(contact_name_key) or message.get("ZPARTNERNAME") or "Name not available"
                header = f"{display_name} - ({format_phone_number_or_raw(message['user'])})"
            c.setFillColor(TEXT_COLOR)
            c.drawString(LEFT_MARGIN, page.y, header)
            page.y -= 50
        else:
            page.y -= 30

        # Bubble geometry
        label = bubble.label or ""
        if bubble.lines:
            content_width = max(c.stringWidth(line, "Helvetica", 12) for line in bubble.lines)
            box_width = content_width + 40
        else:
            content_width = c.stringWidth(label, "Helvetica", 12)
            box_width = content_width + 52
        box_width = min(box_width, A4[0] - LEFT_MARGIN - RIGHT_MARGIN)
        box_height = 40 + max(0, len(bubble.lines) - 1) * 18
        page.y -= max(0, len(bubble.lines) - 1) * 18
        page.ensure_space(extra_offset=len(bubble.lines) * 35)

        c.setFillColor(OWNER_COLOR if is_owner else CONTACT_COLOR)
        c.roundRect(LEFT_MARGIN, page.y, box_width, box_height, BOX_RADIUS, stroke=0, fill=1)
        c.setFillColor(TEXT_COLOR)

        text_y = page.y + box_height / 2 - 6
        if bubble.icon:
            page.draw_icon(bubble.icon, is_owner, LEFT_MARGIN + 14, page.y + box_height / 2 - 7)
            if bubble.label:
                c.drawString(LEFT_MARGIN + 32, text_y, bubble.label)
            page.y -= 16
        else:
            y = text_y + (len(bubble.lines) - 1) * 8
            for line in bubble.lines:
                c.drawString(LEFT_MARGIN + 20, y, line)
                y -= 16
            page.y -= 16

        # Delivery metadata under the bubble
        c.setFont("Helvetica", 8)
        if is_owner:
            sent = format_utc(receipt_sent_datetime(message.get("dateTimeInfos"))) or INFO_NOT_AVAILABLE
            read = format_utc(receipt_read_datetime(message.get("dateTimeInfos"))) or INFO_NOT_AVAILABLE
            c.drawString(LEFT_MARGIN, page.y, f"Send date: {sent}")
            page.y -= 12
            c.drawString(LEFT_MARGIN, page.y, f"Reading date: {read}")
        else:
            c.drawString(LEFT_MARGIN, page.y, f"Send date: {message.get('receiveDateTime')} UTC")
        c.setFont("Helvetica", 12)
        page.y -= 26

        previous_sender = message.get("user")

    c.save()
    return buffer.getvalue()
