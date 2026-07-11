"""End-to-end tests of the projects API: upload -> object storage -> hydrate.

Uses the ``file://`` storage backend and a SQLite results database, so the
whole pipeline runs without MinIO or PostgreSQL. TestClient executes FastAPI
background tasks synchronously, making the mirroring step deterministic.
"""

import io
import plistlib
import sqlite3
import zipfile

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from forensicwace_core.config import clear_settings_cache  # noqa: E402
from forensicwace_core.resultsdb.engine import dispose_engine  # noqa: E402
from forensicwace_core.storage import clear_storage_cache  # noqa: E402

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


def _reset_runtime():
    clear_settings_cache()
    clear_storage_cache()
    dispose_engine()


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolated data dir + sqlite results db + file:// object storage."""
    (tmp_path / "data").mkdir()
    monkeypatch.setenv("FW_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FW_DATABASE_URL", f"sqlite:///{(tmp_path / 'results.db').as_posix()}")
    monkeypatch.setenv("FW_S3_ENDPOINT", f"file:///{(tmp_path / 'objects').as_posix()}")
    _reset_runtime()
    yield tmp_path
    _reset_runtime()


@pytest.fixture
def client(env):
    from forensicwace_api.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


def android_zip_bytes() -> bytes:
    db = sqlite3.connect(":memory:")
    db.executescript(ANDROID_FIXTURE_SQL)
    db.commit()
    payload = db.serialize()
    db.close()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("case42/msgstore.db", payload)
        archive.writestr("case42/Media/WhatsApp Images/IMG-1.jpg", b"jpeg-bytes")
    return buffer.getvalue()


def ios_zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("Manifest.db", b"manifest")
        archive.writestr("Manifest.plist", plistlib.dumps({"Lockdown": {"DeviceName": "iPhone test"}}))
        archive.writestr("7c/7c7fba66680ef796b916b067077cc246adacf01d", b"chatstorage")
    return buffer.getvalue()


def create_project(client, name="Case 42") -> str:
    response = client.post("/api/v1/projects", json={"name": name, "description": "test case"})
    assert response.status_code == 201
    return response.json()["id"]


def upload(client, project_id, content=None, platform="android", **form):
    return client.post(
        f"/api/v1/projects/{project_id}/backups",
        files={"file": ("case42.zip", content or android_zip_bytes(), "application/zip")},
        data={"platform": platform, **form},
    )


def test_project_crud(client):
    project_id = create_project(client)

    listed = client.get("/api/v1/projects").json()
    assert [p["id"] for p in listed] == [project_id]
    assert listed[0]["backup_count"] == 0

    detail = client.get(f"/api/v1/projects/{project_id}").json()
    assert detail["name"] == "Case 42"
    assert detail["backups"] == []

    assert client.delete(f"/api/v1/projects/{project_id}").status_code == 204
    assert client.get(f"/api/v1/projects/{project_id}").status_code == 404


def test_upload_android_backup_mirrors_and_hydrates(client, env):
    project_id = create_project(client)
    response = upload(client, project_id)
    assert response.status_code == 202, response.text
    backup_id = response.json()["id"]

    # TestClient ran the background task synchronously -> final state visible
    status = client.get(f"/api/v1/projects/{project_id}/backups/{backup_id}").json()
    assert status["status"] == "stored"
    assert status["hydrated"] is True
    assert status["file_count"] == 2

    # objects mirrored under the project prefix
    bucket = env / "objects" / "forensicwace-evidence"
    assert (bucket / f"projects/{project_id}/android/case42/msgstore.db").is_file()

    # the hydrated copy is a first-class backup for every existing endpoint
    folders = [b["folder"] for b in client.get("/api/v1/backups/android").json()]
    assert folders == ["case42"]
    chats = client.get("/api/v1/backups/android/case42/chats").json()
    assert chats[0]["PhoneNumber"] == "390000000001"


def test_upload_ios_backup(client):
    project_id = create_project(client)
    response = upload(client, project_id, content=ios_zip_bytes(), platform="ios", identifier="00008030-000A")
    assert response.status_code == 202, response.text

    udids = [b["udid"] for b in client.get("/api/v1/backups/ios").json()]
    assert udids == ["00008030-000A"]


def test_upload_without_hydration_then_hydrate(client, env):
    project_id = create_project(client)
    response = upload(client, project_id, auto_hydrate="false")
    backup_id = response.json()["id"]

    status = client.get(f"/api/v1/projects/{project_id}/backups/{backup_id}").json()
    assert status["status"] == "stored"
    assert status["hydrated"] is False
    assert client.get("/api/v1/backups/android").json() == []

    response = client.post(f"/api/v1/projects/{project_id}/backups/{backup_id}/hydrate")
    assert response.status_code == 202
    status = client.get(f"/api/v1/projects/{project_id}/backups/{backup_id}").json()
    assert status["hydrated"] is True
    assert [b["folder"] for b in client.get("/api/v1/backups/android").json()] == ["case42"]


def test_duplicate_identifier_conflicts(client):
    project_id = create_project(client)
    assert upload(client, project_id).status_code == 202
    response = upload(client, project_id)
    assert response.status_code == 409
    assert "already" in response.json()["detail"]


def test_existing_local_extraction_conflicts(client, env):
    (env / "data" / "device_extractions_Android" / "case42").mkdir(parents=True)
    project_id = create_project(client)
    assert upload(client, project_id).status_code == 409


def test_invalid_archive_is_rejected(client, env):
    project_id = create_project(client)
    response = upload(client, project_id, content=b"not a zip at all")
    assert response.status_code == 422
    # nothing recorded, nothing left in staging
    assert client.get(f"/api/v1/projects/{project_id}").json()["backups"] == []
    staging = env / "data" / "staging"
    assert not staging.exists() or list(staging.iterdir()) == []


def test_traversal_identifier_is_rejected(client):
    project_id = create_project(client)
    response = upload(client, project_id, identifier="../evil")
    assert response.status_code == 400


def test_upload_to_unknown_project_is_404(client):
    assert upload(client, "nope").status_code == 404


def test_delete_backup_purges_storage_and_optionally_local(client, env):
    project_id = create_project(client)
    backup_id = upload(client, project_id).json()["id"]
    local_dir = env / "data" / "device_extractions_Android" / "case42"
    assert local_dir.is_dir()

    response = client.delete(f"/api/v1/projects/{project_id}/backups/{backup_id}?purge_local=true")
    assert response.status_code == 204
    assert not local_dir.exists()
    bucket = env / "objects" / "forensicwace-evidence"
    assert not (bucket / f"projects/{project_id}").exists()
    assert client.get(f"/api/v1/projects/{project_id}").json()["backups"] == []


def test_projects_require_object_storage(tmp_path, monkeypatch):
    """DB configured but no FW_S3_ENDPOINT -> uploads answer 503."""
    monkeypatch.setenv("FW_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FW_DATABASE_URL", f"sqlite:///{(tmp_path / 'results.db').as_posix()}")
    monkeypatch.delenv("FW_S3_ENDPOINT", raising=False)
    _reset_runtime()
    from forensicwace_api.main import create_app

    with TestClient(create_app()) as client:
        project_id = create_project(client)
        response = upload(client, project_id)
        assert response.status_code == 503
        assert "FW_S3_ENDPOINT" in response.json()["detail"]
    _reset_runtime()
