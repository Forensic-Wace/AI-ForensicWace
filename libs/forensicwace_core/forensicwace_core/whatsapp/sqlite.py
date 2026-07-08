"""Read-only access to WhatsApp evidence SQLite databases.

Evidence must never be modified: connections are opened with
``mode=ro&immutable=1`` so SQLite cannot create journal/WAL files either.
"""

import sqlite3
from pathlib import Path

from ..exceptions import ExtractionError


def open_readonly(db_path: Path | str) -> sqlite3.Connection:
    uri = f"{Path(db_path).resolve().as_uri()}?mode=ro&immutable=1"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        raise ExtractionError(f"Cannot open evidence database {db_path}: {exc}") from exc
    conn.row_factory = sqlite3.Row
    return conn


def query_dicts(db_path: Path | str, sql: str, params: dict | tuple = ()) -> list[dict]:
    """Run a single parameterized query and return the rows as dicts."""
    conn = open_readonly(db_path)
    try:
        cursor = conn.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as exc:
        raise ExtractionError(f"Query failed on {db_path}: {exc}") from exc
    finally:
        conn.close()
