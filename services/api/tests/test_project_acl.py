"""Per-project ACL: case visibility, sharing, owner/admin management rights."""

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from forensicwace_core.config import clear_settings_cache  # noqa: E402
from forensicwace_core.resultsdb.engine import dispose_engine  # noqa: E402
from forensicwace_core.storage import clear_storage_cache  # noqa: E402


def _reset_runtime():
    clear_settings_cache()
    clear_storage_cache()
    dispose_engine()


@pytest.fixture
def client(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    monkeypatch.setenv("FW_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FW_DATABASE_URL", f"sqlite:///{(tmp_path / 'results.db').as_posix()}")
    monkeypatch.setenv("FW_S3_ENDPOINT", f"file:///{(tmp_path / 'objects').as_posix()}")
    monkeypatch.delenv("FW_AUTH_DISABLED", raising=False)
    monkeypatch.setenv("FW_JWT_SECRET", "test-secret-not-for-production-0123456789")
    monkeypatch.setenv("FW_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("FW_ADMIN_PASSWORD", "correct-horse-battery")
    _reset_runtime()

    from forensicwace_api.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
    _reset_runtime()


def login(client, username, password="analyst-pw-1"):
    client.cookies.clear()
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "correct-horse-battery" if username == "admin" else password},
    )
    assert response.status_code == 200, response.text


@pytest.fixture
def case(client):
    """Two analysts; 'ada' owns a case."""
    login(client, "admin")
    for name in ("ada", "bob"):
        assert client.post(
            "/api/v1/users", json={"username": name, "password": "analyst-pw-1", "role": "analyst"}
        ).status_code == 201
    login(client, "ada")
    project = client.post("/api/v1/projects", json={"name": "Case 42", "description": ""}).json()
    return project


def test_cases_are_private_until_shared(client, case):
    login(client, "bob")
    assert client.get("/api/v1/projects").json() == []
    # existence is hidden, not just forbidden
    assert client.get(f"/api/v1/projects/{case['id']}").status_code == 404
    assert client.post(f"/api/v1/projects/{case['id']}/members", json={"username": "bob"}).status_code == 404

    login(client, "admin")
    assert [p["name"] for p in client.get("/api/v1/projects").json()] == ["Case 42"]
    detail = client.get(f"/api/v1/projects/{case['id']}").json()
    assert detail["owner"] == "ada" and detail["can_manage"] is True


def test_sharing_grants_and_revokes_access(client, case):
    login(client, "ada")
    assert client.post(f"/api/v1/projects/{case['id']}/members", json={"username": "bob"}).status_code == 201
    # idempotence guards
    assert client.post(f"/api/v1/projects/{case['id']}/members", json={"username": "bob"}).status_code == 409
    assert client.post(f"/api/v1/projects/{case['id']}/members", json={"username": "ada"}).status_code == 409
    assert client.post(f"/api/v1/projects/{case['id']}/members", json={"username": "ghost"}).status_code == 404

    login(client, "bob")
    detail = client.get(f"/api/v1/projects/{case['id']}").json()
    assert detail["name"] == "Case 42" and detail["can_manage"] is False
    assert [m["username"] for m in detail["members"]] == ["bob"]
    # members can look, not manage
    assert client.delete(f"/api/v1/projects/{case['id']}").status_code == 403
    assert client.post(f"/api/v1/projects/{case['id']}/members", json={"username": "admin"}).status_code == 403

    login(client, "ada")
    bob_id = next(m["user_id"] for m in client.get(f"/api/v1/projects/{case['id']}").json()["members"])
    assert client.delete(f"/api/v1/projects/{case['id']}/members/{bob_id}").status_code == 204

    login(client, "bob")
    assert client.get(f"/api/v1/projects/{case['id']}").status_code == 404


def test_sharing_lands_on_the_audit_trail(client, case):
    login(client, "ada")
    client.post(f"/api/v1/projects/{case['id']}/members", json={"username": "bob"})
    login(client, "admin")
    actions = [e["action"] for e in client.get("/api/v1/audit?action=project.shared").json()]
    assert actions == ["project.shared"]


def test_legacy_unowned_projects_stay_visible(client, case):
    from forensicwace_core.resultsdb.engine import session_scope
    from forensicwace_core.resultsdb.models import Project

    with session_scope() as session:
        session.add(Project(id="legacy-1", name="Pre-ACL case", created_by=None))

    login(client, "bob")
    assert [p["name"] for p in client.get("/api/v1/projects").json()] == ["Pre-ACL case"]
