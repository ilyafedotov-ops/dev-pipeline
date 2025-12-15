"""Initial DevGodzilla schema

Revision ID: 0001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

This migration creates the initial DevGodzilla schema with:
- Projects table with constitution tracking
- Protocol runs with Windmill integration
- Step runs with DAG support (depends_on, parallel_group)
- Events table
- Job runs (renamed from codex_runs)
- Run artifacts
- Policy packs
- Clarifications
- Feedback events (new for DevGodzilla)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Detect dialect for conditional syntax
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    is_postgres = bind.dialect.name == "postgresql"
    
    # Use appropriate types based on dialect
    json_type = sa.Text() if is_sqlite else sa.dialects.postgresql.JSONB()
    timestamp_type = sa.DateTime() if is_sqlite else sa.TIMESTAMP()
    boolean_type = sa.Integer() if is_sqlite else sa.Boolean()
    
    # Projects table
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("git_url", sa.Text(), nullable=False),
        sa.Column("base_branch", sa.Text(), nullable=False),
        sa.Column("local_path", sa.Text(), nullable=True),
        sa.Column("ci_provider", sa.Text(), nullable=True),
        sa.Column("project_classification", sa.Text(), nullable=True),
        sa.Column("secrets", json_type, nullable=True),
        sa.Column("default_models", json_type, nullable=True),
        # Policy configuration
        sa.Column("policy_pack_key", sa.Text(), nullable=True),
        sa.Column("policy_pack_version", sa.Text(), nullable=True),
        sa.Column("policy_overrides", json_type, nullable=True),
        sa.Column("policy_repo_local_enabled", boolean_type, nullable=True),
        sa.Column("policy_effective_hash", sa.Text(), nullable=True),
        sa.Column("policy_enforcement_mode", sa.Text(), nullable=True),
        # Constitution tracking (new for DevGodzilla)
        sa.Column("constitution_version", sa.Text(), nullable=True),
        sa.Column("constitution_hash", sa.Text(), nullable=True),
        # Timestamps
        sa.Column("created_at", timestamp_type, server_default=sa.func.now()),
        sa.Column("updated_at", timestamp_type, server_default=sa.func.now()),
    )

    # Policy packs table
    op.create_table(
        "policy_packs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("pack", json_type, nullable=False),
        sa.Column("created_at", timestamp_type, server_default=sa.func.now()),
        sa.Column("updated_at", timestamp_type, server_default=sa.func.now()),
        sa.UniqueConstraint("key", "version", name="uq_policy_packs_key_version"),
    )

    # Protocol runs table
    op.create_table(
        "protocol_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("protocol_name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("base_branch", sa.Text(), nullable=False),
        sa.Column("worktree_path", sa.Text(), nullable=True),
        sa.Column("protocol_root", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("template_config", json_type, nullable=True),
        sa.Column("template_source", json_type, nullable=True),
        # Policy audit
        sa.Column("policy_pack_key", sa.Text(), nullable=True),
        sa.Column("policy_pack_version", sa.Text(), nullable=True),
        sa.Column("policy_effective_hash", sa.Text(), nullable=True),
        sa.Column("policy_effective_json", json_type, nullable=True),
        # Windmill integration (new for DevGodzilla)
        sa.Column("windmill_flow_id", sa.Text(), nullable=True),
        sa.Column("speckit_metadata", json_type, nullable=True),
        # Timestamps
        sa.Column("created_at", timestamp_type, server_default=sa.func.now()),
        sa.Column("updated_at", timestamp_type, server_default=sa.func.now()),
    )

    # Step runs table
    op.create_table(
        "step_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("protocol_run_id", sa.Integer(), sa.ForeignKey("protocol_runs.id"), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("step_name", sa.Text(), nullable=False),
        sa.Column("step_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("retries", sa.Integer(), server_default="0"),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("engine_id", sa.Text(), nullable=True),
        sa.Column("policy", json_type, nullable=True),
        sa.Column("runtime_state", json_type, nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        # DAG support (new for DevGodzilla)
        sa.Column("depends_on", json_type, server_default="[]"),
        sa.Column("parallel_group", sa.Text(), nullable=True),
        # Agent assignment (new for DevGodzilla)
        sa.Column("assigned_agent", sa.Text(), nullable=True),
        # Timestamps
        sa.Column("created_at", timestamp_type, server_default=sa.func.now()),
        sa.Column("updated_at", timestamp_type, server_default=sa.func.now()),
    )

    # Events table
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("protocol_run_id", sa.Integer(), sa.ForeignKey("protocol_runs.id"), nullable=False),
        sa.Column("step_run_id", sa.Integer(), sa.ForeignKey("step_runs.id"), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metadata", json_type, nullable=True),
        sa.Column("created_at", timestamp_type, server_default=sa.func.now()),
    )

    # Job runs table (renamed from codex_runs for multi-agent support)
    op.create_table(
        "job_runs",
        sa.Column("run_id", sa.Text(), primary_key=True),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("run_kind", sa.Text(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("protocol_run_id", sa.Integer(), nullable=True),
        sa.Column("step_run_id", sa.Integer(), nullable=True),
        sa.Column("queue", sa.Text(), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=True),
        sa.Column("worker_id", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.Text(), nullable=True),
        sa.Column("params", json_type, nullable=True),
        sa.Column("result", json_type, nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("log_path", sa.Text(), nullable=True),
        sa.Column("cost_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_cents", sa.Integer(), nullable=True),
        # Windmill integration (new for DevGodzilla)
        sa.Column("windmill_job_id", sa.Text(), nullable=True),
        # Timestamps
        sa.Column("created_at", timestamp_type, server_default=sa.func.now()),
        sa.Column("updated_at", timestamp_type, server_default=sa.func.now()),
        sa.Column("started_at", timestamp_type, nullable=True),
        sa.Column("finished_at", timestamp_type, nullable=True),
    )

    # Run artifacts table
    op.create_table(
        "run_artifacts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=True),
        sa.Column("bytes", sa.Integer(), nullable=True),
        sa.Column("created_at", timestamp_type, server_default=sa.func.now()),
        sa.UniqueConstraint("run_id", "name", name="uq_run_artifacts_run_name"),
    )

    # Clarifications table
    op.create_table(
        "clarifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("protocol_run_id", sa.Integer(), sa.ForeignKey("protocol_runs.id"), nullable=True),
        sa.Column("step_run_id", sa.Integer(), sa.ForeignKey("step_runs.id"), nullable=True),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("recommended", json_type, nullable=True),
        sa.Column("options", json_type, nullable=True),
        sa.Column("applies_to", sa.Text(), nullable=True),
        sa.Column("blocking", boolean_type, server_default="0" if is_sqlite else "false"),
        sa.Column("answer", json_type, nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("answered_at", timestamp_type, nullable=True),
        sa.Column("answered_by", sa.Text(), nullable=True),
        sa.Column("created_at", timestamp_type, server_default=sa.func.now()),
        sa.Column("updated_at", timestamp_type, server_default=sa.func.now()),
        sa.UniqueConstraint("scope", "key", name="uq_clarifications_scope_key"),
    )

    # Feedback events table (new for DevGodzilla)
    op.create_table(
        "feedback_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("protocol_run_id", sa.Integer(), sa.ForeignKey("protocol_runs.id"), nullable=False),
        sa.Column("step_run_id", sa.Integer(), sa.ForeignKey("step_runs.id"), nullable=True),
        sa.Column("error_type", sa.Text(), nullable=False),
        sa.Column("action_taken", sa.Text(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("context", json_type, nullable=True),
        sa.Column("created_at", timestamp_type, server_default=sa.func.now()),
    )

    # Create indexes
    op.create_index("idx_job_runs_job_status", "job_runs", ["job_type", "status", "created_at"])
    op.create_index("idx_job_runs_project", "job_runs", ["project_id", "created_at"])
    op.create_index("idx_job_runs_protocol", "job_runs", ["protocol_run_id", "created_at"])
    op.create_index("idx_job_runs_step", "job_runs", ["step_run_id", "created_at"])
    op.create_index("idx_run_artifacts_run_id", "run_artifacts", ["run_id", "created_at"])
    op.create_index("idx_clarifications_project", "clarifications", ["project_id", "status", "created_at"])
    op.create_index("idx_clarifications_protocol", "clarifications", ["protocol_run_id", "status", "created_at"])
    op.create_index("idx_clarifications_step", "clarifications", ["step_run_id", "status", "created_at"])
    op.create_index("idx_feedback_events_protocol", "feedback_events", ["protocol_run_id", "created_at"])


def downgrade() -> None:
    # Drop indexes
    op.drop_index("idx_feedback_events_protocol")
    op.drop_index("idx_clarifications_step")
    op.drop_index("idx_clarifications_protocol")
    op.drop_index("idx_clarifications_project")
    op.drop_index("idx_run_artifacts_run_id")
    op.drop_index("idx_job_runs_step")
    op.drop_index("idx_job_runs_protocol")
    op.drop_index("idx_job_runs_project")
    op.drop_index("idx_job_runs_job_status")
    
    # Drop tables in reverse order
    op.drop_table("feedback_events")
    op.drop_table("clarifications")
    op.drop_table("run_artifacts")
    op.drop_table("job_runs")
    op.drop_table("events")
    op.drop_table("step_runs")
    op.drop_table("protocol_runs")
    op.drop_table("policy_packs")
    op.drop_table("projects")
