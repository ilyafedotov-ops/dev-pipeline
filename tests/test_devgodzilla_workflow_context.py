from __future__ import annotations

from pathlib import Path

import pytest

from devgodzilla.config import load_config
from devgodzilla.db.database import SQLiteDatabase
from devgodzilla.services.base import ServiceContext
from devgodzilla.services.clarifier import ClarifierService
from devgodzilla.services.workflow_context import build_workflow_prompt_context


@pytest.fixture
def db(tmp_path: Path):
    db_path = tmp_path / "test.db"
    db = SQLiteDatabase(db_path)
    db.init_schema()
    return db


@pytest.fixture
def context():
    return ServiceContext(config=load_config())


@pytest.fixture
def sample_project(db: SQLiteDatabase):
    return db.create_project(
        name="Workflow Context Demo",
        git_url="https://github.com/example/demo.git",
        base_branch="main",
        policy_pack_key="default",
        policy_pack_version="1.0",
    )


def test_workflow_prompt_context_includes_policy_and_answered_clarifications(
    context: ServiceContext,
    db: SQLiteDatabase,
    sample_project,
    tmp_path: Path,
) -> None:
    db.upsert_clarification(
        scope=f"project:{sample_project.id}",
        project_id=sample_project.id,
        key="deployment_window",
        question="Which deployment window should we use?",
        applies_to="onboarding",
        blocking=True,
    )
    db.answer_clarification(
        scope=f"project:{sample_project.id}",
        key="deployment_window",
        answer={"text": "Use the weekday evening release window."},
        answered_by="owner",
        status="answered",
    )
    db.upsert_clarification(
        scope=f"project:{sample_project.id}",
        project_id=sample_project.id,
        key="execution_note",
        question="Do we need a canary rollout?",
        applies_to="execution",
        blocking=False,
        recommended={"value": "Yes, for production-facing changes."},
    )

    prompt_context = build_workflow_prompt_context(
        context,
        db,
        project_id=sample_project.id,
        repo_root=tmp_path,
        stage="execution",
    )

    assert "## Effective Policy" in prompt_context.rendered
    assert "Resolved Clarifications" in prompt_context.rendered
    assert "Use the weekday evening release window." in prompt_context.rendered
    assert "Do we need a canary rollout?" in prompt_context.rendered
    assert "deployment_window" in prompt_context.rendered


def test_has_blocking_open_for_stage_respects_stage_filter(
    context: ServiceContext,
    db: SQLiteDatabase,
    sample_project,
) -> None:
    clarifier = ClarifierService(context, db)
    db.upsert_clarification(
        scope=f"project:{sample_project.id}",
        project_id=sample_project.id,
        key="execution_gate",
        question="Who approves production execution?",
        applies_to="execution",
        blocking=True,
    )
    db.upsert_clarification(
        scope=f"project:{sample_project.id}",
        project_id=sample_project.id,
        key="planning_only",
        question="What planning branch should be used?",
        applies_to="planning",
        blocking=True,
    )

    assert clarifier.has_blocking_open_for_stage(project_id=sample_project.id, stage="execution") is True
    assert clarifier.has_blocking_open_for_stage(project_id=sample_project.id, stage="checklist") is False
