from datetime import datetime
from pathlib import Path

from forensicwace_core.analysis.types import Message


def test_message_roundtrip():
    message = Message(
        id=42,
        chat_id=1,
        chat_name="390000000001",
        sent=False,
        timestamp=datetime(2024, 5, 1, 12, 30),
        message_type="image",
        text="hello",
        media_path=Path("/data/media/img.jpg"),
        mime_type="image/jpeg",
    )
    restored = Message.from_dict(message.to_dict())
    assert restored == message


def test_payload_is_json_safe():
    import json

    message = Message(
        id="a1",
        chat_id=None,
        chat_name=None,
        sent=True,
        timestamp=datetime(2024, 5, 1),
        message_type="text",
        text="ciao",
    )
    json.dumps(message.to_dict())  # must not raise
