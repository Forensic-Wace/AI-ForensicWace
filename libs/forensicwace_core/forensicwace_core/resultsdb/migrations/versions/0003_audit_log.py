"""Append-only audit trail (chain of custody for operator actions).

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "audit_log" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("resource", sa.String(length=255), nullable=True),
        sa.Column("detail", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_at", "audit_log", ["at"], unique=False)
    op.create_index("ix_audit_log_action", "audit_log", ["action"], unique=False)


def downgrade() -> None:
    op.drop_table("audit_log")
