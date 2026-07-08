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
    """Create all tables. Called once at service startup."""
    from . import models  # noqa: F401 — register mappings

    Base.metadata.create_all(get_engine())


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
