"""Phone number formatting and vCard parsing helpers."""

import re

_PHONE_PATTERN = re.compile(r"(?:(?:\+)?(\d{1,3})\s*)?(\d{3})\s*(\d{3})\s*(\d{4})")
_VCARD_TEL_PATTERN = re.compile(r"TEL(?:;[^:]*):(\+?\d+(?: \d+)*)")


def format_phone_number(raw: str) -> str | None:
    """Format a phone number as ``[+prefix] xxx xxx xxxx``.

    Returns None when the input does not look like a phone number.
    """
    match = _PHONE_PATTERN.match(raw or "")
    if not match:
        return None
    prefix = f"+{match.group(1)} " if match.group(1) else ""
    return f"{prefix}{match.group(2)} {match.group(3)} {match.group(4)}"


def format_phone_number_or_raw(raw: str) -> str:
    """Like :func:`format_phone_number` but falls back to the raw input."""
    return format_phone_number(raw) or raw


def vcard_phone_numbers(vcard_text: str) -> list[str]:
    """Extract all phone numbers from a vCard payload."""
    return _VCARD_TEL_PATTERN.findall(vcard_text or "")
