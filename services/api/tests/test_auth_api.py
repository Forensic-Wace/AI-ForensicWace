"""Authentication and RBAC: login, cookies, roles, revocation."""

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from forensicwace_core.analysis import registry  # noqa: E402
from forensicwace_core.config import clear_settings_cache  # noqa: E402
from forensicwace_core.resultsdb.engine import dispose_engine  # noqa: E402


def _reset_runtime():
    clear_settings_cache()
    registry.clear_registry_cache()
    dispose_engine()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """API with authentication ENABLED and a bootstrap admin."""
    monkeypatch.setenv("FW_DATABASE_URL", f"sqlite:///{(tmp_path / 'results.db').as_posix()}")
    monkeypatch.setenv("FW_IOS_EXTRACTIONS_DIR", str(tmp_path / "ios"))
    monkeypatch.setenv("FW_ANDROID_EXTRACTIONS_DIR", str(tmp_path / "android"))
    monkeypatch.delenv("FW_AUTH_DISABLED", raising=False)
    monkeypatch.setenv("FW_JWT_SECRET", "test-secret-not-for-production-0123456789")
    monkeypatch.setenv("FW_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("FW_ADMIN_PASSWORD", "correct-horse-battery")
    _reset_runtime()

    from forensicwace_api.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
    _reset_runtime()

    from forensicwace_api import auth

    auth._failures.clear()


def login(client, username="admin", password="correct-horse-battery"):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


def test_everything_requires_a_session(client):
    assert client.get("/api/v1/backups/android").status_code == 401
    assert client.get("/api/v1/analyzers").status_code == 401
    assert client.get("/api/v1/projects").status_code == 401
    # probes stay public
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 200


def test_login_sets_cookie_and_unlocks_the_api(client):
    assert login(client, password="wrong").status_code == 401

    response = login(client)
    assert response.status_code == 200
    assert response.json()["role"] == "admin"
    assert "fw_session" in response.cookies

    assert client.get("/api/v1/auth/me").json()["username"] == "admin"
    assert client.get("/api/v1/backups/android").status_code == 200

    assert client.post("/api/v1/auth/logout").status_code == 204
    client.cookies.clear()
    assert client.get("/api/v1/backups/android").status_code == 401


def test_login_rate_limit(client):
    for _ in range(5):
        assert login(client, password="wrong").status_code == 401
    assert login(client, password="wrong").status_code == 429
    # the throttle also blocks a now-correct password until the window expires
    assert login(client).status_code == 429


def test_analyst_cannot_manage_users_or_analyzers(client):
    login(client)
    created = client.post("/api/v1/users", json={"username": "ada", "password": "analyst-pw-1", "role": "analyst"})
    assert created.status_code == 201

    client.cookies.clear()
    assert login(client, "ada", "analyst-pw-1").status_code == 200
    # read access is fine
    assert client.get("/api/v1/analyzers").status_code == 200
    # writes are admin-only
    assert client.post("/api/v1/analyzers", json={"endpoint": "http://x"}).status_code == 403
    assert client.delete("/api/v1/analyzers/presidio").status_code == 403
    assert client.get("/api/v1/users").status_code == 403


def test_disabling_a_user_revokes_the_session(client):
    login(client)
    user_id = client.post(
        "/api/v1/users", json={"username": "eve", "password": "analyst-pw-2", "role": "analyst"}
    ).json()["id"]
    admin_cookies = dict(client.cookies)

    client.cookies.clear()
    login(client, "eve", "analyst-pw-2")
    assert client.get("/api/v1/auth/me").status_code == 200
    eve_cookies = dict(client.cookies)

    client.cookies.clear()
    client.cookies.update(admin_cookies)
    assert client.patch(f"/api/v1/users/{user_id}", json={"is_active": False}).json()["is_active"] is False

    client.cookies.clear()
    client.cookies.update(eve_cookies)
    assert client.get("/api/v1/auth/me").status_code == 401
    assert login(client, "eve", "analyst-pw-2").status_code == 401


def test_admin_cannot_disable_own_account(client):
    login(client)
    admin_id = client.get("/api/v1/auth/me").json()["id"]
    assert client.patch(f"/api/v1/users/{admin_id}", json={"is_active": False}).status_code == 409
    assert client.patch(f"/api/v1/users/{admin_id}", json={"role": "analyst"}).status_code == 409


def test_password_reset_revokes_old_sessions(client):
    login(client)
    user_id = client.post(
        "/api/v1/users", json={"username": "bob", "password": "analyst-pw-3", "role": "analyst"}
    ).json()["id"]
    admin_cookies = dict(client.cookies)

    client.cookies.clear()
    login(client, "bob", "analyst-pw-3")
    bob_cookies = dict(client.cookies)

    client.cookies.clear()
    client.cookies.update(admin_cookies)
    client.patch(f"/api/v1/users/{user_id}", json={"password": "new-password-9"})

    client.cookies.clear()
    client.cookies.update(bob_cookies)
    assert client.get("/api/v1/auth/me").status_code == 401
    assert login(client, "bob", "new-password-9").status_code == 200


def test_analysis_records_the_operator(client, tmp_path):
    import sqlite3

    backup = tmp_path / "android" / "extraction_test"
    backup.mkdir(parents=True)
    db = sqlite3.connect(backup / "msgstore.db")
    db.executescript("""
        CREATE TABLE jid (_id INTEGER PRIMARY KEY, user TEXT, server TEXT, raw_string TEXT);
        CREATE TABLE chat_view (_id INTEGER PRIMARY KEY, jid_row_id INTEGER, subject TEXT,
                                raw_string_jid TEXT, last_message_row_id INTEGER);
        CREATE TABLE message (_id INTEGER PRIMARY KEY, chat_row_id INTEGER, from_me INTEGER,
                              timestamp INTEGER, message_type INTEGER, text_data TEXT);
        CREATE TABLE message_media (message_row_id INTEGER, file_path TEXT, file_size INTEGER,
                                    media_caption TEXT, mime_type TEXT);
        INSERT INTO jid VALUES (1, '390000000001', 's.whatsapp.net', '390000000001@s.whatsapp.net');
        INSERT INTO chat_view VALUES (1, 1, NULL, '390000000001@s.whatsapp.net', 1);
        INSERT INTO message VALUES (1, 1, 0, 1700000000000, 0, 'ciao');
    """)
    db.commit()
    db.close()

    admin_id = login(client).json()["id"]
    submitted = client.post(
        "/api/v1/analyses",
        json={"platform": "android", "backup_id": "extraction_test",
              "contacts": ["390000000001"], "analyzers": []},
    )
    assert submitted.status_code == 202

    from forensicwace_core.resultsdb.engine import session_scope
    from forensicwace_core.resultsdb.models import ProcessStatus

    with session_scope() as session:
        process = session.query(ProcessStatus).filter_by(process_id=submitted.json()["process_id"]).first()
        assert process.created_by == admin_id


def test_api_docs_require_a_session(client):
    assert client.get("/docs").status_code == 401
    assert client.get("/openapi.json").status_code == 401
    login(client)
    assert client.get("/docs").status_code == 200
    assert "/api/v1/auth/login" in client.get("/openapi.json").json()["paths"]
