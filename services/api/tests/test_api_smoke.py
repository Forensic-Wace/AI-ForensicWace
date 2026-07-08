import sqlite3

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from forensicwace_core.config import clear_settings_cache  # noqa: E402

ANDROID_FIXTURE_SQL = """
CREATE TABLE jid (_id INTEGER PRIMARY KEY, user TEXT, server TEXT, raw_string TEXT);
CREATE TABLE chat_view (_id INTEGER PRIMARY KEY, jid_row_id INTEGER, subject TEXT,
                        raw_string_jid TEXT, last_message_row_id INTEGER);
CREATE TABLE message (_id INTEGER PRIMARY KEY, chat_row_id INTEGER, from_me INTEGER,
                      timestamp INTEGER, message_type INTEGER, text_data TEXT);
INSERT INTO jid VALUES (1, '390000000001', 's.whatsapp.net', '390000000001@s.whatsapp.net');
INSERT INTO chat_view VALUES (1, 1, NULL, '390000000001@s.whatsapp.net', 1);
INSERT INTO message VALUES (1, 1, 0, 1700000000000, 0, 'hi');
"""


@pytest.fixture
def client(tmp_path, monkeypatch):
    ios_dir = tmp_path / "ios"
    android_dir = tmp_path / "android"
    ios_dir.mkdir()
    (android_dir / "extraction_test").mkdir(parents=True)

    db = sqlite3.connect(android_dir / "extraction_test" / "msgstore.db")
    db.executescript(ANDROID_FIXTURE_SQL)
    db.commit()
    db.close()

    monkeypatch.setenv("FW_IOS_EXTRACTIONS_DIR", str(ios_dir))
    monkeypatch.setenv("FW_ANDROID_EXTRACTIONS_DIR", str(android_dir))
    clear_settings_cache()

    from forensicwace_api.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
    clear_settings_cache()


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_openapi_schema_is_served(client):
    assert client.get("/openapi.json").status_code == 200


def test_list_backups(client):
    assert client.get("/api/v1/backups/ios").json() == []
    androids = client.get("/api/v1/backups/android").json()
    assert len(androids) == 1
    assert androids[0]["folder"] == "extraction_test"


def test_android_chat_endpoints(client):
    chats = client.get("/api/v1/backups/android/extraction_test/chats").json()
    assert chats[0]["PhoneNumber"] == "390000000001"

    private = client.get("/api/v1/backups/android/extraction_test/chats/390000000001/messages").json()
    assert private["counters"]["TotalMessages"] == 1
    assert private["messages"][0]["text_data"] == "hi"


def test_unknown_backup_is_404(client):
    assert client.get("/api/v1/backups/android/nope/chats").status_code == 404


def test_traversal_identifier_is_rejected(client):
    response = client.get("/api/v1/backups/android/..%2F..%2Fetc/chats")
    assert response.status_code in (400, 404)


def test_android_blocked_contacts_not_implemented(client):
    assert client.get("/api/v1/backups/android/extraction_test/blocked-contacts").status_code == 501
