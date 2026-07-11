"""Auth: login columns on users, created_by provenance on work items.

Guarded like the baseline so databases created by any prior state upgrade
cleanly. Legacy ``users`` rows (analysis subjects, no ``username``) keep
working: login-capable accounts are the rows where ``username`` is set.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

USERS_COLUMNS = [
    sa.Column("username", sa.String(length=64), nullable=True),
    sa.Column("password_hash", sa.String(length=255), nullable=True),
    sa.Column("role", sa.String(length=10), nullable=True),
    sa.Column("is_active", sa.Boolean(), nullable=True),
    sa.Column("token_version", sa.Integer(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
]

CREATED_BY_TABLES = ("process_status", "projects", "project_backups")


def _ensure_column(table: str, column: sa.Column) -> None:
    inspector = sa.inspect(op.get_bind())
    if column.name not in {c["name"] for c in inspector.get_columns(table)}:
        op.add_column(table, column)


def upgrade() -> None:
    for column in USERS_COLUMNS:
        _ensure_column("users", column)

    inspector = sa.inspect(op.get_bind())
    if "ix_users_username" not in {i["name"] for i in inspector.get_indexes("users")}:
        op.create_index("ix_users_username", "users", ["username"], unique=True)

    for table in CREATED_BY_TABLES:
        _ensure_column(table, sa.Column("created_by", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    with op.batch_alter_table("users") as batch:
        for column in USERS_COLUMNS:
            batch.drop_column(column.name)
    for table in CREATED_BY_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_column("created_by")
