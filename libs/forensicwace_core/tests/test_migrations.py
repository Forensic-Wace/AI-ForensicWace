"""Alembic wiring: fresh databases and adoption of pre-Alembic ones."""

import sqlite3

import pytest

pytest.importorskip("alembic")

from forensicwace_core.config import clear_settings_cache  # noqa: E402
from forensicwace_core.resultsdb.engine import dispose_engine, init_db  # noqa: E402

EXPECTED_TABLES = {
    "PIIs", "alembic_version", "analyzers", "passwords", "process_status",
    "project_backups", "projects", "text_password", "text_pii", "texts", "users",
}

# Schema shape of a phase-5-era deployment: no projects/analyzers tables,
# no provenance columns on findings.
LEGACY_SQL = """
CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, surname TEXT NOT NULL, address TEXT, comment TEXT);
CREATE TABLE texts (id INTEGER PRIMARY KEY, process_id TEXT NOT NULL, msg_id TEXT NOT NULL, user_id INTEGER,
                    text TEXT NOT NULL, date DATETIME);
CREATE TABLE passwords (id INTEGER PRIMARY KEY, password TEXT, source TEXT NOT NULL);
CREATE TABLE PIIs (id INTEGER PRIMARY KEY, type TEXT, value TEXT, source TEXT NOT NULL);
CREATE TABLE text_password (text INTEGER, password INTEGER);
CREATE TABLE text_pii (text INTEGER, PIIs INTEGER);
CREATE TABLE process_status (id INTEGER PRIMARY KEY, process_id TEXT NOT NULL, OS TEXT, status TEXT);
INSERT INTO passwords VALUES (1, 'legacy-pw', 'legacy');
"""


@pytest.fixture
def use_db(tmp_path, monkeypatch):
    def _use(name: str):
        monkeypatch.setenv("FW_DATABASE_URL", f"sqlite:///{(tmp_path / name).as_posix()}")
        clear_settings_cache()
        dispose_engine()
        return tmp_path / name

    yield _use
    clear_settings_cache()
    dispose_engine()


def _tables(db_path) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_fresh_database_gets_full_schema(use_db):
    db_path = use_db("fresh.db")
    init_db()
    assert EXPECTED_TABLES <= _tables(db_path)


def test_init_db_is_idempotent(use_db):
    use_db("twice.db")
    init_db()
    init_db()  # second run must be a no-op, not an error


def test_legacy_database_is_adopted(use_db):
    db_path = use_db("legacy.db")
    with sqlite3.connect(db_path) as conn:
        conn.executescript(LEGACY_SQL)

    init_db()

    assert EXPECTED_TABLES <= _tables(db_path)
    with sqlite3.connect(db_path) as conn:
        columns = {r[1] for r in conn.execute("PRAGMA table_info(passwords)")}
        assert {"analyzer_version", "analyzer_digest"} <= columns
        assert conn.execute("SELECT password FROM passwords").fetchone() == ("legacy-pw",)
        counters = {r[1] for r in conn.execute("PRAGMA table_info(process_status)")}
        assert {"total_messages", "analyzed_messages", "failed_messages"} <= counters
