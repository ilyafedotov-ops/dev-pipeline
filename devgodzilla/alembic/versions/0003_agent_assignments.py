"""Add agent assignments and overrides

Revision ID: 0003
Revises: 0002
Create Date: 2024-01-01 00:00:02.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    json_type = sa.Text() if is_sqlite else sa.dialects.postgresql.JSONB()
    timestamp_type = sa.DateTime() if is_sqlite else sa.TIMESTAMP()
    boolean_type = sa.Integer() if is_sqlite else sa.Boolean()

    op.create_table(
        "agent_assignments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("process_key", sa.Text(), nullable=False),
        sa.Column("agent_id", sa.Text(), nullable=True),
        sa.Column("prompt_id", sa.Text(), nullable=True),
        sa.Column("model_override", sa.Text(), nullable=True),
        sa.Column("enabled", boolean_type, nullable=True, server_default=sa.text("1" if is_sqlite else "true")),
        sa.Column("metadata", json_type, nullable=True),
        sa.Column("created_at", timestamp_type, server_default=sa.func.now()),
        sa.Column("updated_at", timestamp_type, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "process_key", name="uq_agent_assignments_project_process"),
    )
    op.create_index("idx_agent_assignments_project", "agent_assignments", ["project_id", "process_key"])

    op.create_table(
        "agent_overrides",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("agent_id", sa.Text(), nullable=False),
        sa.Column("overrides", json_type, nullable=True),
        sa.Column("created_at", timestamp_type, server_default=sa.func.now()),
        sa.Column("updated_at", timestamp_type, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "agent_id", name="uq_agent_overrides_project_agent"),
    )
    op.create_index("idx_agent_overrides_project", "agent_overrides", ["project_id"])

    op.create_table(
        "agent_assignment_settings",
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), primary_key=True),
        sa.Column("inherit_global", boolean_type, nullable=True, server_default=sa.text("1" if is_sqlite else "true")),
        sa.Column("created_at", timestamp_type, server_default=sa.func.now()),
        sa.Column("updated_at", timestamp_type, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("agent_assignment_settings")
    op.drop_index("idx_agent_overrides_project", table_name="agent_overrides")
    op.drop_table("agent_overrides")
    op.drop_index("idx_agent_assignments_project", table_name="agent_assignments")
    op.drop_table("agent_assignments")
