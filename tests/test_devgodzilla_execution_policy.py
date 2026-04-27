"""
Tests for policy gating in ExecutionService.
"""

from pathlib import Path
from unittest.mock import Mock

import pytest

from devgodzilla.models.domain import ProtocolStatus, StepStatus
from types import SimpleNamespace

from devgodzilla.engines.interface import EngineResult
from devgodzilla.services.base import ServiceContext
from devgodzilla.services.execution import ExecutionService, StepResolution
from devgodzilla.services.policy import EffectivePolicy, Finding
from devgodzilla.services.workflow_context import WorkflowPromptContext


@pytest.fixture
def service_context():
    config = Mock()
    config.engine_defaults = {}
    return ServiceContext(config=config)


def _build_execution_db():
    db = Mock()

    step = Mock()
    step.id = 10
    step.protocol_run_id = 20
    step.step_name = "step-1"
    step.engine_id = None
    step.model = None
    step.assigned_agent = None

    run = Mock()
    run.id = 20
    run.project_id = 30
    run.protocol_name = "demo"
    run.worktree_path = None
    run.protocol_root = None

    project = Mock()
    project.id = 30
    project.local_path = "/tmp/repo"
    project.policy_enforcement_mode = "block"

    db.get_step_run.return_value = step
    db.get_protocol_run.return_value = run
    db.get_project.return_value = project

    return db, step, run, project


def test_execute_step_blocks_on_clarifications(service_context, monkeypatch):
    db, step, run, _project = _build_execution_db()

    monkeypatch.setattr(
        "devgodzilla.services.execution.resolve_workspace_root",
        lambda *args, **kwargs: Path("/tmp"),
    )
    effective = EffectivePolicy(
        policy={},
        effective_hash="hash",
        pack_key="default",
        pack_version="1.0",
    )
    monkeypatch.setattr(
        "devgodzilla.services.execution.build_workflow_prompt_context",
        lambda *args, **kwargs: WorkflowPromptContext(
            effective_policy=effective,
            policy_context="",
            answered_clarifications=[],
            open_clarifications=[],
            blocking_open_clarifications=[],
            rendered="",
        ),
    )
    monkeypatch.setattr(
        "devgodzilla.services.execution.ClarifierService.has_blocking_open_for_stage",
        lambda *args, **kwargs: True,
    )

    service = ExecutionService(context=service_context, db=db)
    result = service.execute_step(step.id)

    assert result.success is False
    assert result.error == "Blocked on clarifications"
    db.update_step_status.assert_called_with(
        step.id,
        StepStatus.BLOCKED,
        summary="Blocked on clarifications",
    )
    db.update_protocol_status.assert_called_with(run.id, ProtocolStatus.BLOCKED)


def test_execute_step_blocks_on_policy_findings(service_context, monkeypatch, tmp_path):
    db, step, run, project = _build_execution_db()
    project.local_path = str(tmp_path)

    monkeypatch.setattr(
        "devgodzilla.services.execution.ClarifierService.has_blocking_open_for_stage",
        lambda *args, **kwargs: False,
    )

    effective = EffectivePolicy(
        policy={},
        effective_hash="hash",
        pack_key="default",
        pack_version="1.0",
    )
    monkeypatch.setattr(
        "devgodzilla.services.execution.build_workflow_prompt_context",
        lambda *args, **kwargs: WorkflowPromptContext(
            effective_policy=effective,
            policy_context="",
            answered_clarifications=[],
            open_clarifications=[],
            blocking_open_clarifications=[],
            rendered="",
        ),
    )
    finding = Finding(
        code="policy.step.file_missing",
        severity="warning",
        message="Missing step file",
        scope="step",
    )
    monkeypatch.setattr(
        "devgodzilla.services.execution.PolicyService.evaluate_step",
        lambda *args, **kwargs: [finding],
    )

    service = ExecutionService(context=service_context, db=db)
    result = service.execute_step(step.id)

    assert result.success is False
    assert result.error == "Blocked by policy findings"
    db.update_step_status.assert_called_with(
        step.id,
        StepStatus.BLOCKED,
        summary="Blocked by policy findings",
    )
    db.update_protocol_status.assert_called_with(run.id, ProtocolStatus.BLOCKED)

    assert db.append_event.called
    event_calls = [call.kwargs for call in db.append_event.call_args_list]
    assert any(call.get("event_type") == "policy_finding" for call in event_calls)


def test_handle_result_fails_on_fatal_opencode_stderr(service_context, monkeypatch, tmp_path):
    db, step, run, project = _build_execution_db()
    project.local_path = str(tmp_path)
    run.worktree_path = str(tmp_path)
    run.protocol_root = "_runtime"
    (tmp_path / "_runtime").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "devgodzilla.services.execution.get_event_bus",
        lambda: Mock(publish=Mock()),
    )

    service = ExecutionService(context=service_context, db=db)
    engine = SimpleNamespace(metadata=SimpleNamespace(id="opencode"))
    resolution = StepResolution(
        engine_id="opencode",
        model="zai-coding-plan/glm-5",
        prompt_text="",
        prompt_path=None,
        prompt_version=None,
        workdir=tmp_path,
        protocol_root=tmp_path / "_runtime",
        workspace_root=tmp_path,
    )
    result = service._handle_result(
        step,
        run,
        engine,
        EngineResult(
            success=True,
            stdout="",
            stderr="ProviderModelNotFoundError\\nModel not found: zai-coding-plan/glm-5.",
            exit_code=0,
            duration_seconds=0.1,
        ),
        resolution,
    )

    assert result.success is False
    assert result.error == "opencode execution failed: ProviderModelNotFoundError"
    db.update_step_status.assert_any_call(
        step.id,
        StepStatus.FAILED,
        summary="opencode execution failed: ProviderModelNotFoundError",
    )
    assert db.update_protocol_status.call_args_list[-1].args == (run.id, ProtocolStatus.BLOCKED)


def test_build_prompt_includes_task_cycle_context_pack(service_context, tmp_path):
    db, step, run, project = _build_execution_db()
    project.local_path = str(tmp_path)
    run.worktree_path = str(tmp_path)
    protocol_root = tmp_path / "specs" / "demo" / "_runtime"
    protocol_root.mkdir(parents=True, exist_ok=True)
    (protocol_root / "plan.md").write_text("# Plan\nDo the thing\n", encoding="utf-8")
    (protocol_root / "step-1.md").write_text("# Task\nImplement feature\n", encoding="utf-8")
    context_dir = tmp_path / ".devgodzilla" / "task-cycle" / "protocols" / str(run.id) / "work-items" / str(step.id)
    context_dir.mkdir(parents=True, exist_ok=True)
    (context_dir / "context_pack.json").write_text(
        """
        {
          "goal": "Implement feature",
          "test_commands": ["pytest -q", "pnpm test"]
        }
        """.strip(),
        encoding="utf-8",
    )

    service = ExecutionService(context=service_context, db=db)
    prompt = service._build_prompt(
        step,
        protocol_root,
        tmp_path,
        step_prompt_path=protocol_root / "step-1.md",
        workflow_context="",
    )

    assert "# ContextPack (machine-readable handoff)" in prompt
    assert '"goal": "Implement feature"' in prompt
    assert "# Exact Test Commands" in prompt
    assert "`pytest -q`" in prompt


def test_build_prompt_includes_task_cycle_helper_summary(service_context, tmp_path):
    db, step, run, project = _build_execution_db()
    project.local_path = str(tmp_path)
    run.worktree_path = str(tmp_path)
    protocol_root = tmp_path / "specs" / "demo" / "_runtime"
    protocol_root.mkdir(parents=True, exist_ok=True)
    (protocol_root / "step-1.md").write_text("# Task\nImplement feature\n", encoding="utf-8")
    helpers_dir = (
        tmp_path
        / ".devgodzilla"
        / "task-cycle"
        / "protocols"
        / str(run.id)
        / "work-items"
        / str(step.id)
        / "helpers"
    )
    helpers_dir.mkdir(parents=True, exist_ok=True)
    (helpers_dir / "helper_summary.json").write_text(
        """
        {
          "helpers": [
            {
              "helper_agent": "trace",
              "status": "completed",
              "summary": "trace findings for owner"
            }
          ]
        }
        """.strip(),
        encoding="utf-8",
    )

    service = ExecutionService(context=service_context, db=db)
    prompt = service._build_prompt(
        step,
        protocol_root,
        tmp_path,
        step_prompt_path=protocol_root / "step-1.md",
        workflow_context="",
    )

    assert "# Helper Subtask Findings" in prompt
    assert '"helper_agent": "trace"' in prompt
