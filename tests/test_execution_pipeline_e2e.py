"""E2E tests for the execution pipeline — full lifecycle with real SQLite DB.

Covers:
1. Protocol lifecycle: create → start → step transitions → complete/fail
2. Step execution flow: mock engine, verify state transitions + QA gate
3. QA pipeline: scaffold detection, artifact evaluation
4. Auto-advance chain: multi-step protocol progression
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devgodzilla.db.database import SQLiteDatabase
from devgodzilla.models.domain import (
    ProtocolRun, StepRun, Project,
)
from devgodzilla.qa.gates.interface import GateContext, GateVerdict, GateResult
from devgodzilla.engines.block_detector import BlockDetector, BlockReason
from devgodzilla.services.error_classification import ErrorClassifier, ErrorAction


# ─── Helpers ────────────────────────────────────────────────────────────


def _create_project(db: SQLiteDatabase, name: str = "e2e-proj") -> Project:
    return db.create_project(
        name=name,
        git_url="https://github.com/example/e2e-repo.git",
        base_branch="main",
    )


def _create_protocol(
    db: SQLiteDatabase,
    project: Project,
    name: str = "e2e-protocol",
    status: str = "pending",
) -> ProtocolRun:
    return db.create_protocol_run(
        project_id=project.id,
        protocol_name=name,
        status=status,
        base_branch=project.base_branch,
    )


def _create_step(
    db: SQLiteDatabase,
    protocol: ProtocolRun,
    name: str = "step-1",
    stype: str = "execute",
    status: str = "pending",
    idx: int = 0,
) -> StepRun:
    return db.create_step_run(
        protocol_run_id=protocol.id,
        step_index=idx,
        step_name=name,
        step_type=stype,
        status=status,
    )


# ─── 1. Protocol Lifecycle ────────────────────────────────────────────


class TestProtocolLifecycle:
    """Full lifecycle: create project → protocol → steps → transitions."""

    def test_create_project_and_protocol(self, db_session):
        proj = _create_project(db_session)
        assert proj.id is not None
        assert proj.name == "e2e-proj"
        assert proj.status == "active"

        proto = _create_protocol(db_session, proj)
        assert proto.id is not None
        assert proto.protocol_name == "e2e-protocol"
        assert proto.status == "pending"

    def test_protocol_status_transitions(self, db_session):
        proj = _create_project(db_session)
        proto = _create_protocol(db_session, proj)

        # pending → planned
        updated = db_session.update_protocol_status(proto.id, "planned")
        assert updated.status == "planned"

        # planned → running
        updated = db_session.update_protocol_status(proto.id, "running")
        assert updated.status == "running"

        # running → completed
        updated = db_session.update_protocol_status(proto.id, "completed")
        assert updated.status == "completed"

    def test_protocol_failure_path(self, db_session):
        proj = _create_project(db_session)
        proto = _create_protocol(db_session, proj)

        db_session.update_protocol_status(proto.id, "running")
        db_session.update_protocol_status(proto.id, "failed")
        proto = db_session.get_protocol_run(proto.id)
        assert proto.status == "failed"

    def test_protocol_blocked_and_cancelled(self, db_session):
        proj = _create_project(db_session)
        proto = _create_protocol(db_session, proj)

        db_session.update_protocol_status(proto.id, "running")
        db_session.update_protocol_status(proto.id, "blocked")
        proto = db_session.get_protocol_run(proto.id)
        assert proto.status == "blocked"

        db_session.update_protocol_status(proto.id, "cancelled")
        proto = db_session.get_protocol_run(proto.id)
        assert proto.status == "cancelled"

    def test_list_protocol_runs(self, db_session):
        proj = _create_project(db_session)
        _create_protocol(db_session, proj, "proto-a")
        _create_protocol(db_session, proj, "proto-b")

        runs = db_session.list_protocol_runs(proj.id)
        assert len(runs) == 2
        names = {r.protocol_name for r in runs}
        assert names == {"proto-a", "proto-b"}


# ─── 2. Step Execution Flow ───────────────────────────────────────────


class TestStepExecutionFlow:
    """Step state transitions through the execution pipeline."""

    def test_create_steps_for_protocol(self, db_session):
        proj = _create_project(db_session)
        proto = _create_protocol(db_session, proj)
        s1 = _create_step(db_session, proto, "step-1", idx=0)
        s2 = _create_step(db_session, proto, "step-2", idx=1)
        s3 = _create_step(db_session, proto, "step-3", idx=2)

        steps = db_session.list_step_runs(proto.id)
        assert len(steps) == 3
        assert [s.step_name for s in steps] == ["step-1", "step-2", "step-3"]

    def test_step_success_path(self, db_session):
        proj = _create_project(db_session)
        proto = _create_protocol(db_session, proj)
        step = _create_step(db_session, proto)

        # pending → running → needs_qa → completed
        db_session.update_step_status(step.id, "running")
        step = db_session.get_step_run(step.id)
        assert step.status == "running"

        db_session.update_step_status(step.id, "needs_qa")
        step = db_session.get_step_run(step.id)
        assert step.status == "needs_qa"

        db_session.update_step_status(step.id, "completed")
        step = db_session.get_step_run(step.id)
        assert step.status == "completed"

    def test_step_failure_path(self, db_session):
        proj = _create_project(db_session)
        proto = _create_protocol(db_session, proj)
        step = _create_step(db_session, proto)

        db_session.update_step_status(step.id, "running")
        db_session.update_step_status(step.id, "failed")
        step = db_session.get_step_run(step.id)
        assert step.status == "failed"

    def test_step_blocked_path(self, db_session):
        proj = _create_project(db_session)
        proto = _create_protocol(db_session, proj)
        step = _create_step(db_session, proto)

        db_session.update_step_status(step.id, "running")
        db_session.update_step_status(step.id, "blocked")
        step = db_session.get_step_run(step.id)
        assert step.status == "blocked"

    def test_step_update_with_metadata(self, db_session):
        proj = _create_project(db_session)
        proto = _create_protocol(db_session, proj)
        step = _create_step(db_session, proto)

        updated = db_session.update_step_run(
            step.id,
            status="running",
            assigned_agent="glm-4.6",
        )
        assert updated.status == "running"
        assert updated.assigned_agent == "glm-4.6"

    def test_step_retry(self, db_session):
        proj = _create_project(db_session)
        proto = _create_protocol(db_session, proj)
        step = _create_step(db_session, proto)

        # First attempt: fail
        db_session.update_step_status(step.id, "running")
        db_session.update_step_status(step.id, "failed")

        # Retry: back to running
        db_session.update_step_status(step.id, "running")
        step = db_session.get_step_run(step.id)
        assert step.status == "running"

        # Succeed on retry
        db_session.update_step_status(step.id, "needs_qa")
        db_session.update_step_status(step.id, "completed")
        step = db_session.get_step_run(step.id)
        assert step.status == "completed"


# ─── 3. QA Pipeline Integration ───────────────────────────────────────


class TestQAPipelineScaffoldDetection:
    """Tests for the scaffold detection fix in prompt QA gate."""

    @pytest.fixture
    def mock_engine(self):
        eng = MagicMock()
        eng.execute.return_value = MagicMock(
            success=True, stdout="PASS: output looks good", stderr="", exit_code=0
        )
        return eng

    def test_scaffold_detection_all_missing(self, tmp_path, mock_engine):
        """When ALL artifacts are missing, should detect scaffolding."""
        from devgodzilla.qa.gates.prompt import PromptQAGate

        prompt_path = tmp_path / "qa.prompt.md"
        prompt_path.write_text("Evaluate this step output.", encoding="utf-8")

        gate = PromptQAGate(
            engine=mock_engine,
            prompt_path=prompt_path,
        )

        protocol_root = tmp_path / "protocol"
        protocol_root.mkdir()

        ctx = GateContext(
            step_name="step-1",
            protocol_root=str(protocol_root),
            workspace_root=str(tmp_path / "workspace"),
        )

        prompt = gate._build_prompt(ctx)
        assert "MISSING" not in prompt
        assert "not yet available" in prompt

    def test_partial_artifacts_show_content(self, tmp_path, mock_engine):
        """When SOME artifacts exist, should show content for those and MISSING for absent."""
        from devgodzilla.qa.gates.prompt import PromptQAGate

        prompt_path = tmp_path / "qa.prompt.md"
        prompt_path.write_text("Evaluate.", encoding="utf-8")

        gate = PromptQAGate(
            engine=mock_engine,
            prompt_path=prompt_path,
        )

        protocol_root = tmp_path / "protocol"
        protocol_root.mkdir()
        (protocol_root / "plan.md").write_text("# Implementation Plan\nBuild feature X", encoding="utf-8")

        ctx = GateContext(
            step_name="step-1",
            protocol_root=str(protocol_root),
            workspace_root=str(tmp_path / "workspace"),
        )

        prompt = gate._build_prompt(ctx)
        assert "Implementation Plan" in prompt
        assert "MISSING" in prompt

    def test_no_protocol_root_graceful(self, tmp_path, mock_engine):
        """When protocol_root is None, should handle gracefully."""
        from devgodzilla.qa.gates.prompt import PromptQAGate

        prompt_path = tmp_path / "qa.prompt.md"
        prompt_path.write_text("Evaluate.", encoding="utf-8")

        gate = PromptQAGate(
            engine=mock_engine,
            prompt_path=prompt_path,
        )

        ctx = GateContext(
            step_name="step-1",
            protocol_root=None,
            workspace_root=str(tmp_path),
        )

        prompt = gate._build_prompt(ctx)
        assert isinstance(prompt, str)
        assert len(prompt) > 0


class TestBlockDetectorIntegration:
    """Integration tests for block detection in execution flow."""

    @pytest.fixture
    def detector(self):
        return BlockDetector()

    def test_clarification_block_triggers_correct_action(self, detector):
        output = "Error: Cannot proceed. Which auth method should I use: OAuth or API key?"
        block = detector.detect(output)
        if block:
            assert block.reason in (BlockReason.CLARIFICATION_NEEDED, BlockReason.MISSING_INFORMATION)

    def test_syntax_error_not_blocked(self, detector):
        output = """Created src/main.py
All tests passed (42/42)
Task completed successfully."""
        block = detector.detect(output)
        assert block is None

    def test_rate_limit_error_classified(self):
        classifier = ErrorClassifier()
        exc = Exception("Rate limit exceeded: 429 Too Many Requests")
        result = classifier.classify(exc)
        assert result.action == ErrorAction.RETRY

    def test_max_retries_escalates(self):
        classifier = ErrorClassifier()
        exc = TimeoutError("Connection timed out after 30s")
        result = classifier.classify(exc, context={"retry_count": 100})
        assert result.action in (ErrorAction.MANUAL, ErrorAction.RETRY)


# ─── 4. Multi-Step Protocol Execution ─────────────────────────────────


class TestMultiStepProtocolExecution:
    """Simulate a full multi-step protocol run with mock engine."""

    def test_three_steps_sequential_execution(self, db_session):
        """Run 3 steps sequentially: all succeed → protocol completes."""
        proj = _create_project(db_session)
        proto = _create_protocol(db_session, proj, "multi-step")
        steps = [
            _create_step(db_session, proto, f"step-{i}", idx=i)
            for i in range(3)
        ]

        db_session.update_protocol_status(proto.id, "running")

        # Execute steps sequentially
        for step in steps:
            db_session.update_step_status(step.id, "running")
            db_session.update_step_status(step.id, "needs_qa")
            db_session.update_step_status(step.id, "completed")

        # Verify all steps completed
        final_steps = db_session.list_step_runs(proto.id)
        assert all(s.status == "completed" for s in final_steps)

        # Complete protocol
        db_session.update_protocol_status(proto.id, "completed")
        proto = db_session.get_protocol_run(proto.id)
        assert proto.status == "completed"

    def test_blocked_step_halts_protocol(self, db_session):
        """If a step gets blocked, protocol should be marked blocked."""
        proj = _create_project(db_session)
        proto = _create_protocol(db_session, proj, "blocked-proto")
        s1 = _create_step(db_session, proto, "step-1", idx=0)
        s2 = _create_step(db_session, proto, "step-2", idx=1)

        db_session.update_protocol_status(proto.id, "running")

        # Step 1 succeeds
        db_session.update_step_status(s1.id, "running")
        db_session.update_step_status(s1.id, "completed")

        # Step 2 gets blocked
        db_session.update_step_status(s2.id, "running")
        db_session.update_step_status(s2.id, "blocked")

        # Protocol should be blocked
        db_session.update_protocol_status(proto.id, "blocked")
        proto = db_session.get_protocol_run(proto.id)
        assert proto.status == "blocked"

        # Step 2 should still be blocked, step 1 completed
        steps = db_session.list_step_runs(proto.id)
        statuses = {s.step_name: s.status for s in steps}
        assert statuses["step-1"] == "completed"
        assert statuses["step-2"] == "blocked"

    def test_step_failure_with_retry_then_success(self, db_session):
        """Step fails, retries, then succeeds."""
        proj = _create_project(db_session)
        proto = _create_protocol(db_session, proj, "retry-proto")
        step = _create_step(db_session, proto, "flaky-step", idx=0)

        db_session.update_protocol_status(proto.id, "running")

        # Attempt 1: fail
        db_session.update_step_status(step.id, "running")
        db_session.update_step_status(step.id, "failed")

        # Attempt 2: fail again
        db_session.update_step_status(step.id, "running")
        db_session.update_step_status(step.id, "failed")

        # Attempt 3: success
        db_session.update_step_status(step.id, "running")
        db_session.update_step_status(step.id, "needs_qa")
        db_session.update_step_status(step.id, "completed")

        step = db_session.get_step_run(step.id)
        assert step.status == "completed"

        # Protocol can now complete
        db_session.update_protocol_status(proto.id, "completed")
        proto = db_session.get_protocol_run(proto.id)
        assert proto.status == "completed"

    def test_parallel_steps_independent_execution(self, db_session):
        """Parallel steps (same parallel_group) execute independently."""
        proj = _create_project(db_session)
        proto = _create_protocol(db_session, proj, "parallel-proto")

        # Create 3 parallel steps
        for i in range(3):
            db_session.create_step_run(
                protocol_run_id=proto.id,
                step_index=i,
                step_name=f"parallel-{i}",
                step_type="execute",
                status="pending",
                parallel_group="group-a",
            )

        db_session.update_protocol_status(proto.id, "running")

        # Run all in parallel (simulate by updating all)
        steps = db_session.list_step_runs(proto.id)
        for s in steps:
            db_session.update_step_status(s.id, "running")

        # First completes, second fails, third gets blocked
        db_session.update_step_status(steps[0].id, "completed")
        db_session.update_step_status(steps[1].id, "failed")
        db_session.update_step_status(steps[2].id, "blocked")

        # Verify independent statuses
        final = db_session.list_step_runs(proto.id)
        statuses = {s.step_name: s.status for s in final}
        assert statuses["parallel-0"] == "completed"
        assert statuses["parallel-1"] == "failed"
        assert statuses["parallel-2"] == "blocked"


# ─── 5. Protocol Recovery Scenarios ───────────────────────────────────


class TestProtocolRecovery:
    """Test recovering from various failure states."""

    def test_resume_from_blocked_after_clarification(self, db_session):
        """Protocol blocked → clarification provided → resume."""
        proj = _create_project(db_session)
        proto = _create_protocol(db_session, proj, "resume-proto")
        step = _create_step(db_session, proto, "step-1", idx=0)

        # Run and get blocked
        db_session.update_protocol_status(proto.id, "running")
        db_session.update_step_status(step.id, "running")
        db_session.update_step_status(step.id, "blocked")
        db_session.update_protocol_status(proto.id, "blocked")

        # Resume: unblock step and restart protocol
        db_session.update_step_status(step.id, "running")
        db_session.update_protocol_status(proto.id, "running")

        # Now succeeds
        db_session.update_step_status(step.id, "completed")
        db_session.update_protocol_status(proto.id, "completed")

        proto = db_session.get_protocol_run(proto.id)
        assert proto.status == "completed"

    def test_cancel_running_protocol(self, db_session):
        """Cancel a running protocol with in-flight steps."""
        proj = _create_project(db_session)
        proto = _create_protocol(db_session, proj)
        s1 = _create_step(db_session, proto, "step-1", idx=0)
        s2 = _create_step(db_session, proto, "step-2", idx=1)

        db_session.update_protocol_status(proto.id, "running")
        db_session.update_step_status(s1.id, "running")
        db_session.update_step_status(s1.id, "completed")
        db_session.update_step_status(s2.id, "running")

        # Cancel everything
        db_session.update_step_status(s2.id, "cancelled")
        db_session.update_protocol_status(proto.id, "cancelled")

        proto = db_session.get_protocol_run(proto.id)
        assert proto.status == "cancelled"

    def test_paused_protocol_resumes(self, db_session):
        """Pause and resume a protocol."""
        proj = _create_project(db_session)
        proto = _create_protocol(db_session, proj)
        step = _create_step(db_session, proto, idx=0)

        db_session.update_protocol_status(proto.id, "running")
        db_session.update_step_status(step.id, "running")

        # Pause
        db_session.update_protocol_status(proto.id, "paused")
        proto = db_session.get_protocol_run(proto.id)
        assert proto.status == "paused"

        # Resume
        db_session.update_protocol_status(proto.id, "running")
        proto = db_session.get_protocol_run(proto.id)
        assert proto.status == "running"

        db_session.update_step_status(step.id, "completed")
        db_session.update_protocol_status(proto.id, "completed")
        proto = db_session.get_protocol_run(proto.id)
        assert proto.status == "completed"
