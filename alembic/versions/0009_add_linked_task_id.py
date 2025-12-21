"""Add linked_task_id to step_runs

Revision ID: 0009
Revises: 0008
Create Date: 2025-12-20 20:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0009_add_linked_task_id"
down_revision = "0008_add_spec_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add linked_task_id column to step_runs table."""
    try:
        op.add_column(
            "step_runs",
            sa.Column("linked_task_id", sa.Integer(), sa.ForeignKey("tasks.id"), nullable=True)
        )
    except Exception:
        # Column may already exist if manually added
        pass


def downgrade() -> None:
    """Remove linked_task_id column from step_runs table."""
    try:
        op.drop_column("step_runs", "linked_task_id")
    except Exception:
        pass
