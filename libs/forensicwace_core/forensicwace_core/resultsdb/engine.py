"""Results-database engine and session management.

The engine is created lazily from ``FW_DATABASE_URL`` so that importing the
library (or running extraction-only features) never requires PostgreSQL.
Sessions are short-lived and thread-local safe: always use ``session_scope``.
"""

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from ..config import get_settings
from ..exceptions import ConfigurationError

Base = declarative_base()

_engine = None
_session_factory = None


def get_engine():
    global _engine, _session_factory
    if _engine is None:
        url = get_settings().database_url
        if not url:
            raise ConfigurationError("FW_DATABASE_URL is not configured")
        _engine = create_engine(url, pool_pre_ping=True, future=True)
        _session_factory = sessionmaker(bind=_engine, autocommit=False, autoflush=False, future=True)
    return _engine


def dispose_engine() -> None:
    """Tear down the engine (used by tests and reconfiguration)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def init_db() -> None:
    """Create all tables and reconcile late-added columns.

    The column reconciliation is a stopgap until Alembic migrations land: it
    adds missing nullable/counter columns to pre-existing databases.
    """
    from sqlalchemy import inspect, text

    from . import models  # noqa: F401 — register mappings

    engine = get_engine()
    Base.metadata.create_all(engine)

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            existing = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name not in existing:
                    ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column.type.compile(engine.dialect)}'
                    conn.execute(text(ddl))


@contextmanager
def session_scope():
    """Provide a transactional session: commit on success, rollback on error."""
    get_engine()
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
