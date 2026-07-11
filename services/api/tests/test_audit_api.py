"""Audit trail: events recorded, admin-only access."""

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


def login(client, username="admin", password="correct-horse-battery"):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


def test_actions_land_on_the_trail(client):
    assert login(client, password="wrong").status_code == 401
    assert login(client).status_code == 200
    client.post("/api/v1/users", json={"username": "ada", "password": "analyst-pw-1", "role": "analyst"})
    client.post("/api/v1/projects", json={"name": "Case 42", "description": ""})
    assert client.post("/api/v1/auth/logout").status_code == 204

    login(client)
    entries = client.get("/api/v1/audit").json()
    actions = [e["action"] for e in entries]
    # newest first
    assert actions[0] == "auth.login"
    for expected in ("auth.login_failed", "auth.login", "user.created", "project.created", "auth.logout"):
        assert expected in actions, actions

    failed = next(e for e in entries if e["action"] == "auth.login_failed")
    assert failed["resource"] == "admin" and failed["username"] is None
    created = next(e for e in entries if e["action"] == "user.created")
    assert created["username"] == "admin" and created["resource"] == "ada"

    filtered = client.get("/api/v1/audit?action=project.created").json()
    assert {e["action"] for e in filtered} == {"project.created"}
    assert filtered[0]["resource"] == "Case 42"


def test_audit_is_admin_only(client):
    login(client)
    client.post("/api/v1/users", json={"username": "ada", "password": "analyst-pw-1", "role": "analyst"})
    client.cookies.clear()
    login(client, "ada", "analyst-pw-1")
    assert client.get("/api/v1/audit").status_code == 403
