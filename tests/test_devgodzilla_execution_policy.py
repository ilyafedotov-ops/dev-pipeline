"""
Tests for policy gating in ExecutionService.
"""

from unittest.mock import Mock

import pytest

from devgodzilla.models.domain import ProtocolStatus, StepStatus
from devgodzilla.services.base import ServiceContext
from devgodzilla.services.execution import ExecutionService
from devgodzilla.services.policy import EffectivePolicy, Finding


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
        "devgodzilla.services.execution.ClarifierService.has_blocking_open",
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


def test_execute_step_blocks_on_policy_findings(service_context, monkeypatch):
    db, step, run, project = _build_execution_db()

    monkeypatch.setattr(
        "devgodzilla.services.execution.ClarifierService.has_blocking_open",
        lambda *args, **kwargs: False,
    )

    effective = EffectivePolicy(
        policy={},
        effective_hash="hash",
        pack_key="default",
        pack_version="1.0",
    )
    monkeypatch.setattr(
        "devgodzilla.services.execution.PolicyService.resolve_effective_policy",
        lambda *args, **kwargs: effective,
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
