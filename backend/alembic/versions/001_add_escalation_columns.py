"""Add escalation tracking columns to tasks table.

Revision ID: 001
Revises:
Create Date: 2026-01-31
"""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("escalation_level", sa.Integer(), default=0))
    op.add_column("tasks", sa.Column("last_notified_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "last_notified_at")
    op.drop_column("tasks", "escalation_level")
