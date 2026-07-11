"""Baseline: the full schema as of marketplace phase 7A (frozen).

Adopts pre-Alembic databases: every ``create_table`` is guarded on
existence, and columns that the old ``init_db`` reconciliation used to add
late are back-filled on tables that already existed. A fresh database gets
the whole schema; a legacy one is patched up to exactly this state.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _ensure_columns(table: str, columns: list[sa.Column]) -> None:
    """Late-added columns for databases that predate them (all nullable)."""
    present = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}
    for column in columns:
        if column.name not in present:
            op.add_column(table, column)


def upgrade() -> None:
    existing = _existing_tables()

    if "users" not in existing:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("surname", sa.String(), nullable=False),
            sa.Column("address", sa.String(), nullable=True),
            sa.Column("comment", sa.String(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)

    if "PIIs" not in existing:
        op.create_table(
            "PIIs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("type", sa.String(), nullable=True),
            sa.Column("value", sa.String(), nullable=True),
            sa.Column("source", sa.String(), nullable=False),
            sa.Column("analyzer_version", sa.String(length=50), nullable=True),
            sa.Column("analyzer_digest", sa.String(length=120), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_PIIs_id"), "PIIs", ["id"], unique=False)
        op.create_index(op.f("ix_PIIs_type"), "PIIs", ["type"], unique=False)
    else:
        _ensure_columns("PIIs", [
            sa.Column("analyzer_version", sa.String(length=50), nullable=True),
            sa.Column("analyzer_digest", sa.String(length=120), nullable=True),
        ])

    if "passwords" not in existing:
        op.create_table(
            "passwords",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("password", sa.String(), nullable=True),
            sa.Column("source", sa.String(), nullable=False),
            sa.Column("analyzer_version", sa.String(length=50), nullable=True),
            sa.Column("analyzer_digest", sa.String(length=120), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_passwords_id"), "passwords", ["id"], unique=False)
        op.create_index(op.f("ix_passwords_password"), "passwords", ["password"], unique=False)
    else:
        _ensure_columns("passwords", [
            sa.Column("analyzer_version", sa.String(length=50), nullable=True),
            sa.Column("analyzer_digest", sa.String(length=120), nullable=True),
        ])

    if "texts" not in existing:
        op.create_table(
            "texts",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("process_id", sa.String(), nullable=False),
            sa.Column("msg_id", sa.String(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("text", sa.String(), nullable=False),
            sa.Column("date", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_texts_id"), "texts", ["id"], unique=False)
        op.create_index(op.f("ix_texts_process_id"), "texts", ["process_id"], unique=False)

    if "text_password" not in existing:
        op.create_table(
            "text_password",
            sa.Column("text", sa.Integer(), nullable=True),
            sa.Column("password", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["password"], ["passwords.id"]),
            sa.ForeignKeyConstraint(["text"], ["texts.id"]),
        )

    if "text_pii" not in existing:
        op.create_table(
            "text_pii",
            sa.Column("text", sa.Integer(), nullable=True),
            sa.Column("PIIs", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["PIIs"], ["PIIs.id"]),
            sa.ForeignKeyConstraint(["text"], ["texts.id"]),
        )

    if "process_status" not in existing:
        op.create_table(
            "process_status",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("process_id", sa.String(length=128), nullable=False),
            sa.Column("OS", sa.String(length=50), nullable=True),
            sa.Column("extraction_name_udid", sa.String(length=255), nullable=True),
            sa.Column("db_path", sa.String(), nullable=True),
            sa.Column("start_time", sa.DateTime(), nullable=True),
            sa.Column("end_time", sa.DateTime(), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=True),
            sa.Column("details", sa.String(), nullable=True),
            sa.Column("date_to", sa.DateTime(), nullable=True),
            sa.Column("date_from", sa.DateTime(), nullable=True),
            sa.Column("received", sa.Boolean(), nullable=True),
            sa.Column("sent", sa.Boolean(), nullable=True),
            sa.Column("contacts", sa.String(), nullable=True),
            sa.Column("groups", sa.String(), nullable=True),
            sa.Column("msg_type", sa.String(), nullable=True),
            sa.Column("analyzers", sa.String(), nullable=True),
            sa.Column("total_messages", sa.Integer(), nullable=True),
            sa.Column("analyzed_messages", sa.Integer(), nullable=True),
            sa.Column("failed_messages", sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_process_status_process_id"), "process_status", ["process_id"], unique=True)
    else:
        _ensure_columns("process_status", [
            sa.Column("total_messages", sa.Integer(), nullable=True),
            sa.Column("analyzed_messages", sa.Integer(), nullable=True),
            sa.Column("failed_messages", sa.Integer(), nullable=True),
        ])

    if "projects" not in existing:
        op.create_table(
            "projects",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    if "project_backups" not in existing:
        op.create_table(
            "project_backups",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("platform", sa.String(length=10), nullable=False),
            sa.Column("identifier", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("detail", sa.String(), nullable=True),
            sa.Column("object_prefix", sa.String(), nullable=False),
            sa.Column("original_filename", sa.String(length=255), nullable=True),
            sa.Column("size_bytes", sa.BigInteger(), nullable=True),
            sa.Column("file_count", sa.Integer(), nullable=True),
            sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("platform", "identifier", name="uq_project_backups_identity"),
        )
        op.create_index(op.f("ix_project_backups_project_id"), "project_backups", ["project_id"], unique=False)

    if "analyzers" not in existing:
        op.create_table(
            "analyzers",
            sa.Column("key", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("version", sa.String(length=50), nullable=False),
            sa.Column("type", sa.String(length=10), nullable=False),
            sa.Column("capabilities", sa.JSON(), nullable=False),
            sa.Column("input", sa.String(length=10), nullable=False),
            sa.Column("trust", sa.String(length=10), nullable=False),
            sa.Column("endpoint", sa.String(), nullable=True),
            sa.Column("image", sa.String(), nullable=True),
            sa.Column("image_digest", sa.String(length=120), nullable=True),
            sa.Column("config", sa.JSON(), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("installed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("key"),
        )


def downgrade() -> None:
    raise NotImplementedError("The baseline cannot be downgraded")
