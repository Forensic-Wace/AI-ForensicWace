"""End-to-end pipeline test: Celery eager mode + SQLite results DB + synthetic
msgstore fixture. No broker, no network, no real data."""

import sqlite3
import uuid
from datetime import datetime

import pytest

pytest.importorskip("celery")

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
INSERT INTO message VALUES (1, 1, 0, 1700000000000, 0, 'first message');
INSERT INTO message VALUES (2, 1, 1, 1700000100000, 0, 'second message');
"""


@pytest.fixture
def env(tmp_path, monkeypatch):
    android_dir = tmp_path / "android"
    backup = android_dir / "extraction_test"
    backup.mkdir(parents=True)
    db = sqlite3.connect(backup / "msgstore.db")
    db.executescript(ANDROID_FIXTURE_SQL)
    db.commit()
    db.close()

    monkeypatch.setenv("FW_ANDROID_EXTRACTIONS_DIR", str(android_dir))
    monkeypatch.setenv("FW_DATABASE_URL", f"sqlite:///{tmp_path / 'results.db'}")
    monkeypatch.delenv("FW_BROKER_URL", raising=False)
    clear_settings_cache()
    dispose_engine()
    yield {"db_path": backup / "msgstore.db"}
    clear_settings_cache()
    dispose_engine()


def test_full_pipeline_eager(env):
    from forensicwace_worker.celery_app import app
    from forensicwace_worker.tasks import start_analysis

    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = True

    from forensicwace_core.resultsdb import repositories
    from forensicwace_core.resultsdb.engine import init_db, session_scope
    from forensicwace_core.resultsdb.models import ProcessStatus

    init_db()
    process_id = str(uuid.uuid4())
    with session_scope() as session:
        session.add(
            ProcessStatus(
                process_id=process_id,
                OS="android",
                extraction_name_udid="extraction_test",
                db_path=str(env["db_path"]),
                start_time=datetime.now(),
                status="Started",
                received=True,
                sent=True,
                contacts="390000000001",
                groups="",
                msg_type="text",
                analyzers="",  # no external analyzers: text persistence only
            )
        )

    start_analysis.apply(args=[process_id]).get()

    with session_scope() as session:
        process = repositories.get_process(session, process_id)
        assert process.status == "Finish"
        assert process.total_messages == 2
        assert process.analyzed_messages == 2
        assert process.failed_messages == 0

        texts = repositories.get_texts_by_process(session, process_id)
        assert sorted(t.text for t in texts) == ["first message", "second message"]


def test_retry_idempotency(env):
    """Re-running the text stage for the same message must not duplicate rows."""
    from forensicwace_core.analysis.pipeline import analyze_and_persist
    from forensicwace_core.analysis.types import Message
    from forensicwace_core.resultsdb import repositories
    from forensicwace_core.resultsdb.engine import init_db, session_scope

    init_db()
    message = Message(
        id=7,
        chat_id=1,
        chat_name="x",
        sent=False,
        timestamp=datetime(2024, 1, 1),
        message_type="text",
        text="same message",
    )
    analyze_and_persist(message, "proc-1", [])
    analyze_and_persist(message, "proc-1", [])  # simulated redelivery

    with session_scope() as session:
        texts = repositories.get_texts_by_process(session, "proc-1")
        assert len(texts) == 1
