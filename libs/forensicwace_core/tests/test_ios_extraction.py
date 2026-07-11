"""iOS analysis extraction: message selection, filters, media resolution."""

import sqlite3
from pathlib import Path

import pytest

from forensicwace_core.analysis.messages import from_ios_rows
from forensicwace_core.constants import IOS_CHATSTORAGE_RELATIVE_PATH, WHATSAPP_IOS_DOMAIN
from forensicwace_core.whatsapp import ios

REPO_ROOT = Path(__file__).parents[3]
FIXTURE_SQL = REPO_ROOT / "schemas" / "whatsapp" / "fixtures" / "ios-chatstorage-z.sql"

AUDIO_FILE_ID = "aa11223344556677889900aabbccddeeff001122"
MANIFEST_SQL = f"""
CREATE TABLE Files (fileID TEXT PRIMARY KEY, domain TEXT, relativePath TEXT, flags INTEGER, file BLOB);
INSERT INTO Files VALUES ('{AUDIO_FILE_ID}', '{WHATSAPP_IOS_DOMAIN}',
                          'Message/Media/390000000001@s.whatsapp.net/a/b/audio1.opus', 1, NULL);
-- The image is referenced by ChatStorage but absent from the backup (flags=0)
INSERT INTO Files VALUES ('bb11223344556677889900aabbccddeeff001122', '{WHATSAPP_IOS_DOMAIN}',
                          'Message/Media/390000000001@s.whatsapp.net/c/d/photo1.jpg', 0, NULL);
"""


def _build_db(path: Path, script: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(script)
    conn.commit()
    conn.close()


@pytest.fixture
def ios_backup_dir(tmp_path: Path) -> Path:
    backup_dir = tmp_path / "00008030-000A11112222333B"
    _build_db(backup_dir.joinpath(*IOS_CHATSTORAGE_RELATIVE_PATH), FIXTURE_SQL.read_text(encoding="utf-8"))
    _build_db(backup_dir / "Manifest.db", MANIFEST_SQL)
    stored_audio = backup_dir / AUDIO_FILE_ID[:2] / AUDIO_FILE_ID
    stored_audio.parent.mkdir(parents=True, exist_ok=True)
    stored_audio.write_bytes(b"OggS fake opus payload")
    return backup_dir


def _chatstorage(backup_dir: Path) -> Path:
    return backup_dir.joinpath(*IOS_CHATSTORAGE_RELATIVE_PATH)


def test_filtered_messages_by_contact_and_group(ios_backup_dir):
    rows = ios.get_filtered_messages(
        _chatstorage(ios_backup_dir), contacts=["390000000001"], groups=["Test Group"]
    )
    assert {r["id"] for r in rows} == {1, 2, 3, 4, 5, 6}
    by_id = {r["id"]: r for r in rows}
    assert by_id[1]["chat_name"] == "Test Contact" and by_id[1]["from_me"] is False
    assert by_id[2]["from_me"] is True  # no ZFROMJID -> sent
    assert by_id[3]["chat_name"] == "Test Group"
    assert by_id[5]["mime_type"] == "audio/ogg; codecs=opus"
    assert by_id[5]["media_local_path"].endswith("audio1.opus")

    # A hostile "phone number" must be treated as data, not SQL
    assert ios.get_filtered_messages(_chatstorage(ios_backup_dir), contacts=["x' OR '1'='1"]) == []


def test_direction_and_type_filters(ios_backup_dir):
    db = _chatstorage(ios_backup_dir)
    only_sent = ios.get_filtered_messages(db, contacts=["390000000001"], include_received=False)
    assert {r["id"] for r in only_sent} == {2, 6}

    audios = ios.get_filtered_messages(db, contacts=["390000000001"], message_types=["audio"])
    assert [r["id"] for r in audios] == [5]


def test_from_ios_rows_resolves_media_through_manifest(ios_backup_dir):
    rows = ios.get_filtered_messages(_chatstorage(ios_backup_dir), contacts=["390000000001"])
    messages = {m.id: m for m in from_ios_rows(rows, ios_backup_dir)}

    audio = messages[5]
    assert audio.message_type == "audio"
    assert audio.media_path is not None and audio.media_path.is_file()
    assert audio.media_path.name == AUDIO_FILE_ID

    image = messages[6]  # in Manifest.db but flags=0: not stored in the backup
    assert image.message_type == "image"
    assert image.media_path is None
    assert image.text == "look at this"

    location = messages[4]  # non-analyzable media types carry no media_path
    assert location.message_type == "location"
    assert location.media_path is None
    assert messages[1].timestamp.year >= 2023


def test_pipeline_extracts_ios_messages(ios_backup_dir, monkeypatch):
    from forensicwace_core.analysis import pipeline
    from forensicwace_core.config import clear_settings_cache
    from forensicwace_core.resultsdb.models import ProcessStatus

    monkeypatch.setenv("FW_IOS_EXTRACTIONS_DIR", str(ios_backup_dir.parent))
    clear_settings_cache()
    try:
        process = ProcessStatus(
            process_id="p-ios",
            OS="ios",
            extraction_name_udid=ios_backup_dir.name,
            db_path=str(_chatstorage(ios_backup_dir)),
            contacts="390000000001",
            groups="Test Group",
            received=1,
            sent=1,
        )
        messages = pipeline.extract_messages(process)
        assert {m.id for m in messages} == {1, 2, 3, 4, 5, 6}
        assert any(m.media_path for m in messages)
    finally:
        clear_settings_cache()
