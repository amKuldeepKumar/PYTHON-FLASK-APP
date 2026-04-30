"""add premium alphabet controls

Revision ID: e4f1b2a0d9c3
Revises: c9b2f147aa10
Create Date: 2026-04-13 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "e4f1b2a0d9c3"
down_revision = "c9b2f147aa10"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("themes", sa.Column("alphabet_trails_enabled", sa.Boolean(), nullable=True, server_default=sa.true()))
    op.add_column("themes", sa.Column("alphabet_rotation_depth", sa.Integer(), nullable=True, server_default="60"))
    op.add_column("themes", sa.Column("alphabet_speed", sa.Integer(), nullable=True, server_default="100"))


def downgrade():
    op.drop_column("themes", "alphabet_speed")
    op.drop_column("themes", "alphabet_rotation_depth")
    op.drop_column("themes", "alphabet_trails_enabled")
