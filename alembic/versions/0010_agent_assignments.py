"""Add agent assignments and overrides tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "0010_agent_assignments"
down_revision = "0009_add_linked_task_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())
    created_assignments = False
    created_overrides = False

    if "agent_assignments" not in existing_tables:
        op.create_table(
            "agent_assignments",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
            sa.Column("process_key", sa.Text(), nullable=False),
            sa.Column("agent_id", sa.Text(), nullable=True),
            sa.Column("prompt_id", sa.Text(), nullable=True),
            sa.Column("model_override", sa.Text(), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=True, server_default=sa.text("true")),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint("project_id", "process_key", name="uq_agent_assignments_project_process"),
        )
        created_assignments = True
    if created_assignments or "agent_assignments" in existing_tables:
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("agent_assignments")}
        if "idx_agent_assignments_project" not in existing_indexes:
            op.create_index("idx_agent_assignments_project", "agent_assignments", ["project_id", "process_key"])

    if "agent_overrides" not in existing_tables:
        op.create_table(
            "agent_overrides",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
            sa.Column("agent_id", sa.Text(), nullable=False),
            sa.Column("overrides", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint("project_id", "agent_id", name="uq_agent_overrides_project_agent"),
        )
        created_overrides = True
    if created_overrides or "agent_overrides" in existing_tables:
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("agent_overrides")}
        if "idx_agent_overrides_project" not in existing_indexes:
            op.create_index("idx_agent_overrides_project", "agent_overrides", ["project_id"])

    if "agent_assignment_settings" not in existing_tables:
        op.create_table(
            "agent_assignment_settings",
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), primary_key=True),
            sa.Column("inherit_global", sa.Boolean(), nullable=True, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table("agent_assignment_settings")
    op.drop_index("idx_agent_overrides_project", table_name="agent_overrides")
    op.drop_table("agent_overrides")
    op.drop_index("idx_agent_assignments_project", table_name="agent_assignments")
    op.drop_table("agent_assignments")
