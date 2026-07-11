"""Alembic environment.

Invoked two ways:
- programmatically by ``engine.init_db()`` at service startup, which passes
  the live engine through ``config.attributes["connection"]``;
- from the CLI (``alembic -c libs/forensicwace_core/alembic.ini ...``), where
  the engine is built from ``FW_DATABASE_URL`` like everywhere else.
"""

from alembic import context

from forensicwace_core.resultsdb import models  # noqa: F401 — register mappings
from forensicwace_core.resultsdb.engine import Base, get_engine

target_metadata = Base.metadata


def run_migrations_online() -> None:
    connectable = context.config.attributes.get("connection") or get_engine()
    with connectable.connect() as connection:
        if connection.dialect.name == "postgresql":
            # serialize concurrent replicas racing to migrate at startup;
            # the xact lock is released when the migration transaction ends
            connection.exec_driver_sql("SELECT pg_advisory_xact_lock(429154)")
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
