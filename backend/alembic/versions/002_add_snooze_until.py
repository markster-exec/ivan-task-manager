"""Add snooze_until column to tasks table.

Revision ID: 002
Revises: 001
Create Date: 2026-01-31
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("snooze_until", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "snooze_until")
