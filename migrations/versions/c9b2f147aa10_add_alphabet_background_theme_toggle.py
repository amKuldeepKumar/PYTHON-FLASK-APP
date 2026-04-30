"""add alphabet background theme toggle

Revision ID: c9b2f147aa10
Revises: 66ae1d41a9b9
Create Date: 2026-04-13 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "c9b2f147aa10"
down_revision = "66ae1d41a9b9"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("themes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("alphabet_background_enabled", sa.Boolean(), nullable=True, server_default=sa.false()))

    op.execute("UPDATE themes SET alphabet_background_enabled = 0 WHERE alphabet_background_enabled IS NULL")

    with op.batch_alter_table("themes", schema=None) as batch_op:
        batch_op.alter_column("alphabet_background_enabled", existing_type=sa.Boolean(), nullable=False, server_default=sa.false())


def downgrade():
    with op.batch_alter_table("themes", schema=None) as batch_op:
        batch_op.drop_column("alphabet_background_enabled")
