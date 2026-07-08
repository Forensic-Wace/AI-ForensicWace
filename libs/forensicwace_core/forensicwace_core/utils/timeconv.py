"""Time conversions and WhatsApp receipt-info decoding.

iOS WhatsApp stores timestamps as seconds since 2001-01-01 UTC (Apple epoch)
and per-message delivery/read receipts as a protobuf blob in
``ZWAMESSAGEINFO.ZRECEIPTINFO``.
"""

import binascii
from datetime import datetime, timezone

APPLE_EPOCH_OFFSET = 978307200  # 2001-01-01T00:00:00Z in Unix seconds


def from_apple_time(seconds: float) -> datetime:
    return datetime.fromtimestamp(seconds + APPLE_EPOCH_OFFSET, timezone.utc)


def from_unix_time(seconds: float) -> datetime:
    return datetime.fromtimestamp(seconds, timezone.utc)


def _parse_receipt_fields(blob: bytes):
    from protobuf_decoder.protobuf_decoder import Parser

    hex_data = binascii.hexlify(blob).decode()
    return Parser().parse(hex_data).results


def receipt_sent_datetime(blob: bytes | None) -> datetime | None:
    """Decode the send timestamp (field 3) from a receipt-info blob."""
    if blob is None:
        return None
    try:
        for result in _parse_receipt_fields(blob):
            if result.field == 3:
                return datetime.fromtimestamp(result.data, tz=timezone.utc)
    except Exception:
        return None
    return None


def receipt_read_datetime(blob: bytes | None) -> datetime | None:
    """Decode the read timestamp (field 3 + field 2.5 offset) from a receipt-info blob."""
    if blob is None:
        return None
    try:
        sent_ts = None
        read_offset = None
        for result in _parse_receipt_fields(blob):
            if result.field == 3:
                sent_ts = result.data
            elif result.field == 2:
                for sub in result.data.results:
                    if sub.field == 5:
                        read_offset = sub.data
                        break
        if sent_ts is None or read_offset is None:
            return None
        return datetime.fromtimestamp(int(sent_ts) + int(read_offset), tz=timezone.utc)
    except Exception:
        return None


def format_utc(dt: datetime | None) -> str | None:
    return dt.strftime("%Y-%m-%d %H:%M:%S %Z") if dt else None


def seconds_to_mmss(seconds: int | None) -> str:
    seconds = int(seconds or 0)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"
