"""Analyzer registry API: seeding, CRUD, submit validation, provenance."""

import sqlite3
from datetime import datetime

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from forensicwace_core.analysis import registry  # noqa: E402
from forensicwace_core.analysis.contract import AnalyzerManifest  # noqa: E402
from forensicwace_core.config import clear_settings_cache  # noqa: E402
from forensicwace_core.resultsdb.engine import dispose_engine  # noqa: E402

ANDROID_FIXTURE_SQL = """
CREATE TABLE jid (_id INTEGER PRIMARY KEY, user TEXT, server TEXT, raw_string TEXT);
CREATE TABLE chat_view (_id INTEGER PRIMARY KEY, jid_row_id INTEGER, subject TEXT,
                        raw_string_jid TEXT, last_message_row_id INTEGER);
CREATE TABLE message (_id INTEGER PRIMARY KEY, chat_row_id INTEGER, from_me INTEGER,
                      timestamp INTEGER, message_type INTEGER, text_data TEXT);
CREATE TABLE message_media (message_row_id INTEGER, file_path TEXT, file_size INTEGER,
                            media_caption TEXT, mime_type TEXT);
INSERT INTO jid VALUES (1, '390000000001', 's.whatsapp.net', '390000000001@s.whatsapp.net');
INSERT INTO chat_view VALUES (1, 1, NULL, '390000000001@s.whatsapp.net', 1);
INSERT INTO message VALUES (1, 1, 0, 1700000000000, 0, 'la mia password è hunter2');
"""

EXTERNAL_MANIFEST = AnalyzerManifest.model_validate(
    {
        "contract": "fw-analyzer/1",
        "key": "ext_detector",
        "name": "External detector",
        "version": "2.1.0",
        "capabilities": ["password"],
        "input": "text",
        "trust": "local",
    }
)


def _reset_runtime():
    clear_settings_cache()
    registry.clear_registry_cache()
    dispose_engine()


@pytest.fixture
def client(tmp_path, monkeypatch):
    android_dir = tmp_path / "android"
    backup = android_dir / "extraction_test"
    backup.mkdir(parents=True)
    db = sqlite3.connect(backup / "msgstore.db")
    db.executescript(ANDROID_FIXTURE_SQL)
    db.commit()
    db.close()

    monkeypatch.setenv("FW_ANDROID_EXTRACTIONS_DIR", str(android_dir))
    monkeypatch.setenv("FW_IOS_EXTRACTIONS_DIR", str(tmp_path / "ios"))
    monkeypatch.setenv("FW_DATABASE_URL", f"sqlite:///{(tmp_path / 'results.db').as_posix()}")
    monkeypatch.delenv("FW_BROKER_URL", raising=False)
    _reset_runtime()

    from forensicwace_api.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
    _reset_runtime()


@pytest.fixture
def fake_manifest(monkeypatch):
    """Registration fetches the manifest from the endpoint; stub the network."""
    from forensicwace_core.analysis.analyzers.http_analyzer import HttpAnalyzer

    monkeypatch.setattr(HttpAnalyzer, "manifest", lambda self: EXTERNAL_MANIFEST)


def test_builtins_seeded_on_startup(client):
    analyzers = client.get("/api/v1/analyzers").json()
    keys = {a["key"] for a in analyzers}
    assert {"presidio", "whisper", "tesseract", "microsoft_vision"} <= keys
    assert all(a["type"] == "builtin" and a["enabled"] for a in analyzers)
    # text analyzers listed first for the UI
    assert analyzers[0]["input"] == "text"


def test_register_update_uninstall_http_analyzer(client, fake_manifest):
    created = client.post("/api/v1/analyzers", json={"endpoint": "http://ext:9009/"})
    assert created.status_code == 201, created.text
    assert created.json()["key"] == "ext_detector"
    assert created.json()["endpoint"] == "http://ext:9009"  # trailing slash stripped

    # duplicate registration conflicts
    assert client.post("/api/v1/analyzers", json={"endpoint": "http://ext:9009"}).status_code == 409

    listed = {a["key"]: a for a in client.get("/api/v1/analyzers").json()}
    assert listed["ext_detector"]["type"] == "http"

    updated = client.patch("/api/v1/analyzers/ext_detector", json={"enabled": False, "config": {"x": 1}})
    assert updated.json()["enabled"] is False
    assert updated.json()["config"] == {"x": 1}

    assert client.delete("/api/v1/analyzers/ext_detector").status_code == 204
    assert "ext_detector" not in {a["key"] for a in client.get("/api/v1/analyzers").json()}


def test_unreachable_endpoint_is_502(client):
    response = client.post("/api/v1/analyzers", json={"endpoint": "http://127.0.0.1:1"})
    assert response.status_code == 502


def test_builtin_cannot_be_uninstalled_but_can_be_disabled(client):
    assert client.delete("/api/v1/analyzers/presidio").status_code == 409
    assert client.patch("/api/v1/analyzers/presidio", json={"enabled": False}).json()["enabled"] is False


def test_submit_rejects_unknown_or_disabled_analyzers(client):
    body = {
        "platform": "android",
        "backup_id": "extraction_test",
        "contacts": ["390000000001"],
        "analyzers": ["nope"],
    }
    response = client.post("/api/v1/analyses", json=body)
    assert response.status_code == 422
    assert "unknown analyzer 'nope'" in response.json()["detail"]

    client.patch("/api/v1/analyzers/presidio", json={"enabled": False})
    response = client.post("/api/v1/analyses", json={**body, "analyzers": ["presidio"]})
    assert response.status_code == 422
    assert "disabled" in response.json()["detail"]


def test_analysis_with_http_analyzer_persists_provenance(client, fake_manifest, monkeypatch):
    """Full loop: register external analyzer -> analysis -> findings carry
    version + digest. The analyzer HTTP call is stubbed at the client layer."""
    from forensicwace_core.analysis.analyzers import http_analyzer as http_mod
    from forensicwace_core.analysis.types import Finding

    client.post("/api/v1/analyzers", json={"endpoint": "http://ext:9009"})

    class StubClient:
        def analyze_text(self, text):
            if "hunter2" in text:
                return [Finding(kind="password", value="hunter2", source="")]
            return []

    monkeypatch.setattr(http_mod, "client_for", lambda endpoint, config: StubClient())

    submitted = client.post(
        "/api/v1/analyses",
        json={
            "platform": "android",
            "backup_id": "extraction_test",
            "contacts": ["390000000001"],
            "message_types": ["text"],
            "analyzers": ["ext_detector"],
        },
    )
    assert submitted.status_code == 202, submitted.text
    process_id = submitted.json()["process_id"]

    # no broker configured -> daemon-thread executor; wait for completion
    import time

    for _ in range(50):
        process = client.get(f"/api/v1/analyses/{process_id}").json()
        if process["status"] in ("Finish", "Error"):
            break
        time.sleep(0.1)
    assert process["status"] == "Finish", process

    results = client.get(f"/api/v1/analyses/{process_id}/results").json()
    passwords = [p for r in results for p in r["passwords"]]
    assert passwords[0]["value"] == "hunter2"
    assert passwords[0]["source"] == "ext_detector"
    assert passwords[0]["analyzer_version"] == "2.1.0"
