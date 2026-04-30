"""phase4 security policy and audit hashing

Revision ID: b4f4c2d9e001
Revises: a1f3c9b2d410
Create Date: 2026-03-17 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "b4f4c2d9e001"
down_revision = "a1f3c9b2d410"
branch_labels = None
depends_on = None


def _get_columns(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = inspect(bind)
    return {col["name"] for col in inspector.get_columns(table_name)}


def _get_indexes(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = inspect(bind)
    return {idx["name"] for idx in inspector.get_indexes(table_name)}


def upgrade():
    existing_columns = _get_columns("audit_logs")
    existing_indexes = _get_indexes("audit_logs")

    with op.batch_alter_table("audit_logs") as batch_op:
        if "prev_hash" not in existing_columns:
            batch_op.add_column(sa.Column("prev_hash", sa.String(length=64), nullable=True))

        if "row_hash" not in existing_columns:
            batch_op.add_column(sa.Column("row_hash", sa.String(length=64), nullable=True))

        # Backward compatibility in case an older model/migration used event_hash
        if "event_hash" not in existing_columns and "row_hash" not in existing_columns:
            batch_op.add_column(sa.Column("event_hash", sa.String(length=64), nullable=True))

        prev_hash_index_name = "ix_audit_logs_prev_hash"
        event_hash_index_name = "ix_audit_logs_event_hash"
        row_hash_index_name = "ix_audit_logs_row_hash"

        if "prev_hash" in _get_columns("audit_logs") and prev_hash_index_name not in existing_indexes:
            batch_op.create_index(prev_hash_index_name, ["prev_hash"], unique=False)

        # Prefer row_hash going forward; support event_hash only if that column exists
        refreshed_columns = _get_columns("audit_logs")
        refreshed_indexes = _get_indexes("audit_logs")

        if "row_hash" in refreshed_columns and row_hash_index_name not in refreshed_indexes:
            batch_op.create_index(row_hash_index_name, ["row_hash"], unique=False)
        elif "event_hash" in refreshed_columns and event_hash_index_name not in refreshed_indexes:
            batch_op.create_index(event_hash_index_name, ["event_hash"], unique=False)


def downgrade():
    existing_columns = _get_columns("audit_logs")
    existing_indexes = _get_indexes("audit_logs")

    with op.batch_alter_table("audit_logs") as batch_op:
        if "ix_audit_logs_row_hash" in existing_indexes:
            batch_op.drop_index("ix_audit_logs_row_hash")

        if "ix_audit_logs_event_hash" in existing_indexes:
            batch_op.drop_index("ix_audit_logs_event_hash")

        if "ix_audit_logs_prev_hash" in existing_indexes:
            batch_op.drop_index("ix_audit_logs_prev_hash")

        if "row_hash" in existing_columns:
            batch_op.drop_column("row_hash")

        if "event_hash" in existing_columns:
            batch_op.drop_column("event_hash")

        if "prev_hash" in existing_columns:
            batch_op.drop_column("prev_hash")