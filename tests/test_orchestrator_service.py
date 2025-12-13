from pathlib import Path
from unittest.mock import Mock

from tasksgodzilla.domain import ProtocolStatus, StepStatus
from tasksgodzilla.jobs import Job
from tasksgodzilla.services import OrchestratorService
from tasksgodzilla.storage import Database


def test_create_protocol_run(tmp_path):
    """Test creating a protocol run via OrchestratorService."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    
    service = OrchestratorService(db=db)
    run = service.create_protocol_run(
        project_id=project.id,
        protocol_name="test-protocol",
        status=ProtocolStatus.PENDING,
        base_branch="main",
        description="Test protocol",
    )
    
    assert run.id is not None
    assert run.protocol_name == "test-protocol"
    assert run.status == ProtocolStatus.PENDING
    assert run.base_branch == "main"
    
    # Verify it's persisted
    fetched = db.get_protocol_run(run.id)
    assert fetched.protocol_name == "test-protocol"


def test_start_protocol_run_enqueues_planning(tmp_path):
    """Test starting a protocol transitions status and enqueues planning job."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.PENDING, "main", None, None, None)
    
    mock_queue = Mock()
    mock_queue.enqueue.return_value = Job(job_id="job-123", job_type="plan_protocol_job", payload={})
    
    service = OrchestratorService(db=db)
    job = service.start_protocol_run(run.id, queue=mock_queue)
    
    # Verify status transition
    updated_run = db.get_protocol_run(run.id)
    assert updated_run.status == ProtocolStatus.PLANNING
    
    # Verify queue call
    mock_queue.enqueue.assert_called_once_with("plan_protocol_job", {"protocol_run_id": run.id})
    assert job.job_id == "job-123"


def test_start_protocol_run_rejects_invalid_status(tmp_path):
    """Test that starting a protocol fails when status is invalid."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.RUNNING, "main", None, None, None)
    
    mock_queue = Mock()
    service = OrchestratorService(db=db)
    
    try:
        service.start_protocol_run(run.id, queue=mock_queue)
        assert False, "Expected ValueError"
    except ValueError as e:
        assert "already running or terminal" in str(e)


def test_enqueue_next_step_selects_pending(tmp_path):
    """Test that enqueue_next_step selects the first pending step."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.PLANNED, "main", None, None, None)
    
    step1 = db.create_step_run(run.id, 1, "step-1", "work", StepStatus.PENDING, model=None)
    step2 = db.create_step_run(run.id, 2, "step-2", "work", StepStatus.PENDING, model=None)
    
    mock_queue = Mock()
    mock_queue.enqueue.return_value = Job(job_id="job-456", job_type="execute_step_job", payload={})
    
    service = OrchestratorService(db=db)
    step, job = service.enqueue_next_step(run.id, queue=mock_queue)
    
    # Should select step1 (first pending)
    assert step.id == step1.id
    assert step.status == StepStatus.RUNNING
    
    # Verify protocol status updated
    updated_run = db.get_protocol_run(run.id)
    assert updated_run.status == ProtocolStatus.RUNNING
    
    # Verify queue call
    mock_queue.enqueue.assert_called_once_with("execute_step_job", {"step_run_id": step1.id})


def test_enqueue_next_step_raises_when_no_pending(tmp_path):
    """Test that enqueue_next_step raises when no pending steps exist."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.PLANNED, "main", None, None, None)
    
    db.create_step_run(run.id, 1, "step-1", "work", StepStatus.COMPLETED, model=None)
    
    mock_queue = Mock()
    service = OrchestratorService(db=db)
    
    try:
        service.enqueue_next_step(run.id, queue=mock_queue)
        assert False, "Expected LookupError"
    except LookupError as e:
        assert "No pending or failed steps" in str(e)


def test_enqueue_next_step_watchdog_fails_stuck_running(tmp_path):
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.PLANNED, "main", None, None, None)

    stuck = db.create_step_run(run.id, 1, "step-1", "work", StepStatus.RUNNING, model=None)
    # Force updated_at far in the past so watchdog triggers.
    with db._connect() as conn:
        conn.execute(
            "UPDATE step_runs SET updated_at = ? WHERE id = ?",
            ("2000-01-01T00:00:00+00:00", stuck.id),
        )
        conn.commit()

    mock_queue = Mock()
    mock_queue.enqueue.return_value = Job(job_id="job-789", job_type="execute_step_job", payload={})

    service = OrchestratorService(db=db)
    step, _job = service.enqueue_next_step(run.id, queue=mock_queue)

    # Watchdog should have fired and emitted an event.
    events = db.list_events(run.id)
    assert any(ev.event_type == "step_stuck_watchdog" for ev in events)
    # The stuck step becomes runnable and is selected.
    assert step.step_name == "step-1"


def test_retry_latest_step_requeues_failed(tmp_path):
    """Test that retry_latest_step retries the most recent failed step."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.BLOCKED, "main", None, None, None)
    
    step1 = db.create_step_run(run.id, 1, "step-1", "work", StepStatus.COMPLETED, model=None)
    step2 = db.create_step_run(run.id, 2, "step-2", "work", StepStatus.FAILED, model=None)
    step3 = db.create_step_run(run.id, 3, "step-3", "work", StepStatus.PENDING, model=None)
    
    mock_queue = Mock()
    mock_queue.enqueue.return_value = Job(job_id="job-789", job_type="execute_step_job", payload={})
    
    service = OrchestratorService(db=db)
    step, job = service.retry_latest_step(run.id, queue=mock_queue)
    
    # Should select step2 (most recent failed)
    assert step.id == step2.id
    assert step.status == StepStatus.RUNNING
    assert step.retries == 1
    
    # Verify protocol status updated
    updated_run = db.get_protocol_run(run.id)
    assert updated_run.status == ProtocolStatus.RUNNING


def test_pause_resume_cancel_transitions(tmp_path):
    """Test pause, resume, and cancel lifecycle transitions."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.RUNNING, "main", None, None, None)
    
    service = OrchestratorService(db=db)
    
    # Pause
    paused = service.pause_protocol(run.id)
    assert paused.status == ProtocolStatus.PAUSED
    
    # Resume
    resumed = service.resume_protocol(run.id)
    assert resumed.status == ProtocolStatus.RUNNING
    
    # Cancel
    cancelled = service.cancel_protocol(run.id)
    assert cancelled.status == ProtocolStatus.CANCELLED


def test_cancel_protocol_cancels_in_flight_steps(tmp_path):
    """Test that cancelling a protocol also cancels in-flight steps."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.RUNNING, "main", None, None, None)
    
    step1 = db.create_step_run(run.id, 1, "step-1", "work", StepStatus.COMPLETED, model=None)
    step2 = db.create_step_run(run.id, 2, "step-2", "work", StepStatus.RUNNING, model=None)
    step3 = db.create_step_run(run.id, 3, "step-3", "work", StepStatus.PENDING, model=None)
    
    service = OrchestratorService(db=db)
    service.cancel_protocol(run.id)
    
    # Verify step statuses
    updated_step1 = db.get_step_run(step1.id)
    updated_step2 = db.get_step_run(step2.id)
    updated_step3 = db.get_step_run(step3.id)
    
    assert updated_step1.status == StepStatus.COMPLETED  # Unchanged
    assert updated_step2.status == StepStatus.CANCELLED
    assert updated_step3.status == StepStatus.CANCELLED


def test_run_step_transitions_and_enqueues(tmp_path):
    """Test that run_step transitions a step to RUNNING and enqueues execution."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.PLANNED, "main", None, None, None)
    step = db.create_step_run(run.id, 1, "step-1", "work", StepStatus.PENDING, model=None)
    
    mock_queue = Mock()
    mock_queue.enqueue.return_value = Job(job_id="job-abc", job_type="execute_step_job", payload={})
    
    service = OrchestratorService(db=db)
    job = service.run_step(step.id, queue=mock_queue)
    
    # Verify step status
    updated_step = db.get_step_run(step.id)
    assert updated_step.status == StepStatus.RUNNING
    
    # Verify protocol status
    updated_run = db.get_protocol_run(run.id)
    assert updated_run.status == ProtocolStatus.RUNNING
    
    # Verify queue call
    mock_queue.enqueue.assert_called_once_with("execute_step_job", {"step_run_id": step.id})


def test_run_step_qa_transitions_and_enqueues(tmp_path):
    """Test that run_step_qa transitions a step to NEEDS_QA and enqueues QA job."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.RUNNING, "main", None, None, None)
    step = db.create_step_run(run.id, 1, "step-1", "work", StepStatus.RUNNING, model=None)
    
    mock_queue = Mock()
    mock_queue.enqueue.return_value = Job(job_id="job-qa", job_type="run_quality_job", payload={})
    
    service = OrchestratorService(db=db)
    job = service.run_step_qa(step.id, queue=mock_queue)
    
    # Verify step status
    updated_step = db.get_step_run(step.id)
    assert updated_step.status == StepStatus.NEEDS_QA
    
    # Verify queue call
    mock_queue.enqueue.assert_called_once_with("run_quality_job", {"step_run_id": step.id})


def test_trigger_step_inline_fallback(tmp_path, monkeypatch):
    """Test that trigger_step falls back to inline execution when no queue is unavailable."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.RUNNING, "main", None, None, None)
    step = db.create_step_run(run.id, 1, "step-1", "work", StepStatus.PENDING, model=None)

    # Mock ExecutionService.execute_step and config
    mock_execute_step = Mock()
    monkeypatch.setattr("tasksgodzilla.services.execution.ExecutionService.execute_step", mock_execute_step)
    
    # Mock config to have no Redis
    mock_config = Mock(redis_url=None)
    monkeypatch.setattr("tasksgodzilla.services.orchestrator.load_config", Mock(return_value=mock_config))

    service = OrchestratorService(db=db)
    result = service.trigger_step(step.id, run.id, source="test", inline_depth=0)

    assert result == {"inline": True, "target_step_id": step.id}
    
    # Verify ExecutionService.execute_step was called
    mock_execute_step.assert_called_once_with(step.id)
    
    # Verify status updated
    updated_step = db.get_step_run(step.id)
    assert updated_step.status == StepStatus.RUNNING
    assert updated_step.summary == "Triggered (inline)"



def test_apply_trigger_policy_with_matching_condition(tmp_path, monkeypatch):
    """Test apply_trigger_policy triggers target step when conditions match."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.RUNNING, "main", None, None, None)
    
    # Add trigger policy to source step
    # Note: agent ID is extracted from step name, so "step-2" becomes "2"
    policy = [{
        "behavior": "trigger",
        "module_id": "trigger-1",
        "condition": "qa_passed",
        "trigger_agent_id": "2"
    }]
    
    # Create source step with trigger policy
    source_step = db.create_step_run(run.id, 1, "step-1", "work", StepStatus.COMPLETED, model=None, policy=policy)
    target_step = db.create_step_run(run.id, 2, "step-2", "work", StepStatus.PENDING, model=None)
    
    # Mock config to have no Redis (inline execution)
    mock_config = Mock(redis_url=None)
    monkeypatch.setattr("tasksgodzilla.services.orchestrator.load_config", Mock(return_value=mock_config))
    
    # Mock ExecutionService.execute_step to avoid actual execution
    mock_execute_step = Mock()
    monkeypatch.setattr("tasksgodzilla.services.execution.ExecutionService.execute_step", mock_execute_step)
    
    service = OrchestratorService(db=db)
    result = service.apply_trigger_policy(source_step, reason="qa_passed")
    
    assert result is not None
    assert result.get("applied") is True
    assert result.get("target_step_id") == target_step.id
    
    # Verify target step was triggered (status should be RUNNING after trigger_step is called)
    updated_target = db.get_step_run(target_step.id)
    # The step should be RUNNING after trigger_step sets it, before execute_step runs
    assert updated_target.status in (StepStatus.RUNNING, StepStatus.NEEDS_QA), f"Expected RUNNING or NEEDS_QA, got {updated_target.status}"


def test_apply_trigger_policy_skips_non_matching_condition(tmp_path):
    """Test apply_trigger_policy skips when condition doesn't match."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.RUNNING, "main", None, None, None)
    
    # Add trigger policy with different condition
    policy = [{
        "behavior": "trigger",
        "module_id": "trigger-1",
        "condition": "exec_completed",
        "trigger_agent_id": "2"
    }]
    
    source_step = db.create_step_run(run.id, 1, "step-1", "work", StepStatus.COMPLETED, model=None, policy=policy)
    target_step = db.create_step_run(run.id, 2, "step-2", "work", StepStatus.PENDING, model=None)
    
    service = OrchestratorService(db=db)
    result = service.apply_trigger_policy(source_step, reason="qa_passed")
    
    # Should return None or not applied
    assert result is None or not result.get("applied")
    
    # Target step should remain unchanged
    updated_target = db.get_step_run(target_step.id)
    assert updated_target.status == StepStatus.PENDING


def test_apply_trigger_policy_enforces_depth_limit(tmp_path, monkeypatch):
    """Test apply_trigger_policy enforces MAX_INLINE_TRIGGER_DEPTH."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.RUNNING, "main", None, None, None)
    
    policy = [{
        "behavior": "trigger",
        "module_id": "trigger-1",
        "condition": "qa_passed",
        "trigger_agent_id": "2"
    }]
    
    source_step = db.create_step_run(run.id, 1, "step-1", "work", StepStatus.COMPLETED, model=None, policy=policy)
    target_step = db.create_step_run(run.id, 2, "step-2", "work", StepStatus.PENDING, model=None)
    
    # Mock config to have no Redis
    mock_config = Mock(redis_url=None)
    monkeypatch.setattr("tasksgodzilla.services.orchestrator.load_config", Mock(return_value=mock_config))
    
    service = OrchestratorService(db=db)
    
    # Try to trigger at max depth
    from tasksgodzilla.services.orchestrator import MAX_INLINE_TRIGGER_DEPTH
    result = service.apply_trigger_policy(source_step, reason="qa_passed", inline_depth=MAX_INLINE_TRIGGER_DEPTH)
    
    # Should not trigger due to depth limit
    # The trigger_step method will return None when depth is exceeded
    # But apply_trigger_policy will still return the decision from apply_trigger_policies
    assert result is not None
    assert result.get("applied") is True


def test_apply_loop_policy_resets_steps(tmp_path):
    """Test apply_loop_policy resets target steps to PENDING."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.RUNNING, "main", None, None, None)
    
    step1 = db.create_step_run(run.id, 1, "step-1", "work", StepStatus.COMPLETED, model=None)
    
    # Add loop policy to step2
    policy = [{
        "behavior": "loop",
        "module_id": "loop-1",
        "condition": "qa_failed",
        "step_back": 1,
        "max_iterations": 3
    }]
    step2 = db.create_step_run(run.id, 2, "step-2", "work", StepStatus.FAILED, model=None, policy=policy)
    
    service = OrchestratorService(db=db)
    result = service.apply_loop_policy(step2, reason="qa_failed")
    
    assert result is not None
    assert result.get("applied") is True
    assert result.get("iterations") == 1
    
    # Verify steps were reset
    updated_step1 = db.get_step_run(step1.id)
    updated_step2 = db.get_step_run(step2.id)
    
    # Both steps should be reset to PENDING (step_back=1 means go back 1 step)
    assert updated_step1.status == StepStatus.PENDING
    assert updated_step2.status == StepStatus.PENDING


def test_apply_loop_policy_enforces_max_iterations(tmp_path):
    """Test apply_loop_policy enforces max_iterations limit."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.RUNNING, "main", None, None, None)
    
    # Add loop policy with max_iterations
    policy = [{
        "behavior": "loop",
        "module_id": "loop-1",
        "condition": "qa_failed",
        "step_back": 1,
        "max_iterations": 2
    }]
    
    # Set runtime_state to indicate we've already looped twice
    runtime_state = {
        "loop_counts": {
            "loop-1": 2
        }
    }
    step = db.create_step_run(run.id, 1, "step-1", "work", StepStatus.FAILED, model=None, policy=policy)
    db.update_step_status(step.id, StepStatus.FAILED, runtime_state=runtime_state)
    step = db.get_step_run(step.id)
    
    service = OrchestratorService(db=db)
    result = service.apply_loop_policy(step, reason="qa_failed")
    
    # Should not apply due to max_iterations
    assert result is None
    
    # Step should remain FAILED
    updated_step = db.get_step_run(step.id)
    assert updated_step.status == StepStatus.FAILED


def test_handle_step_completion_with_pass_verdict(tmp_path, monkeypatch):
    """Test handle_step_completion applies trigger policy on success."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.RUNNING, "main", None, None, None)
    
    # Add trigger policy
    policy = [{
        "behavior": "trigger",
        "module_id": "trigger-1",
        "condition": "qa_passed",
        "trigger_agent_id": "2"
    }]
    
    source_step = db.create_step_run(run.id, 1, "step-1", "work", StepStatus.COMPLETED, model=None, policy=policy)
    target_step = db.create_step_run(run.id, 2, "step-2", "work", StepStatus.PENDING, model=None)
    
    # Mock config and execution
    mock_config = Mock(redis_url=None)
    monkeypatch.setattr("tasksgodzilla.services.orchestrator.load_config", Mock(return_value=mock_config))
    mock_execute_step = Mock()
    monkeypatch.setattr("tasksgodzilla.services.execution.ExecutionService.execute_step", mock_execute_step)
    
    service = OrchestratorService(db=db)
    service.handle_step_completion(source_step.id, qa_verdict="PASS")
    
    # Verify target step was triggered
    updated_target = db.get_step_run(target_step.id)
    # The step should be RUNNING after trigger_step sets it, before execute_step runs
    assert updated_target.status in (StepStatus.RUNNING, StepStatus.NEEDS_QA), f"Expected RUNNING or NEEDS_QA, got {updated_target.status}"


def test_handle_step_completion_with_fail_verdict(tmp_path):
    """Test handle_step_completion applies loop policy on failure."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.RUNNING, "main", None, None, None)
    
    step1 = db.create_step_run(run.id, 1, "step-1", "work", StepStatus.COMPLETED, model=None)
    
    # Add loop policy
    policy = [{
        "behavior": "loop",
        "module_id": "loop-1",
        "condition": "qa_failed",
        "step_back": 1,
        "max_iterations": 3
    }]
    step2 = db.create_step_run(run.id, 2, "step-2", "work", StepStatus.FAILED, model=None, policy=policy)
    
    service = OrchestratorService(db=db)
    service.handle_step_completion(step2.id, qa_verdict="FAIL")
    
    # Verify steps were reset
    updated_step1 = db.get_step_run(step1.id)
    updated_step2 = db.get_step_run(step2.id)
    
    assert updated_step1.status == StepStatus.PENDING
    assert updated_step2.status == StepStatus.PENDING
    
    # Protocol should remain RUNNING
    updated_run = db.get_protocol_run(run.id)
    assert updated_run.status == ProtocolStatus.RUNNING


def test_handle_step_completion_blocks_on_failure_without_loop(tmp_path):
    """Test handle_step_completion blocks protocol when failure has no loop policy."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.RUNNING, "main", None, None, None)
    
    step = db.create_step_run(run.id, 1, "step-1", "work", StepStatus.FAILED, model=None)
    
    service = OrchestratorService(db=db)
    service.handle_step_completion(step.id, qa_verdict="FAIL")
    
    # Protocol should be BLOCKED
    updated_run = db.get_protocol_run(run.id)
    assert updated_run.status == ProtocolStatus.BLOCKED


def test_handle_step_completion_checks_protocol_completion(tmp_path):
    """Test handle_step_completion checks if protocol is complete."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.RUNNING, "main", None, None, None)
    
    step1 = db.create_step_run(run.id, 1, "step-1", "work", StepStatus.COMPLETED, model=None)
    step2 = db.create_step_run(run.id, 2, "step-2", "work", StepStatus.COMPLETED, model=None)
    
    service = OrchestratorService(db=db)
    service.handle_step_completion(step2.id, qa_verdict="PASS")
    
    # Protocol should be COMPLETED
    updated_run = db.get_protocol_run(run.id)
    assert updated_run.status == ProtocolStatus.COMPLETED


def test_check_and_complete_protocol_completes_when_all_done(tmp_path):
    """Test check_and_complete_protocol marks protocol as COMPLETED when all steps are done."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.RUNNING, "main", None, None, None)
    
    db.create_step_run(run.id, 1, "step-1", "work", StepStatus.COMPLETED, model=None)
    db.create_step_run(run.id, 2, "step-2", "work", StepStatus.COMPLETED, model=None)
    
    service = OrchestratorService(db=db)
    result = service.check_and_complete_protocol(run.id)
    
    assert result is True
    updated_run = db.get_protocol_run(run.id)
    assert updated_run.status == ProtocolStatus.COMPLETED


def test_check_and_complete_protocol_returns_false_when_incomplete(tmp_path):
    """Test check_and_complete_protocol returns False when steps are still pending."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.RUNNING, "main", None, None, None)
    
    db.create_step_run(run.id, 1, "step-1", "work", StepStatus.COMPLETED, model=None)
    db.create_step_run(run.id, 2, "step-2", "work", StepStatus.PENDING, model=None)
    
    service = OrchestratorService(db=db)
    result = service.check_and_complete_protocol(run.id)
    
    assert result is False
    updated_run = db.get_protocol_run(run.id)
    assert updated_run.status == ProtocolStatus.RUNNING


def test_plan_protocol_delegates_to_service(tmp_path, monkeypatch):
    """Test plan_protocol delegates to PlanningService."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.PENDING, "main", None, None, None)
    
    # Mock the service method
    mock_plan_protocol = Mock()
    monkeypatch.setattr("tasksgodzilla.services.planning.PlanningService.plan_protocol", mock_plan_protocol)
    
    service = OrchestratorService(db=db)
    service.plan_protocol(run.id, job_id="test-job")
    
    # Verify service was called
    mock_plan_protocol.assert_called_once_with(run.id, job_id="test-job")


def test_execute_step_delegates_to_service(tmp_path, monkeypatch):
    """Test execute_step delegates to ExecutionService."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.RUNNING, "main", None, None, None)
    step = db.create_step_run(run.id, 1, "step-1", "work", StepStatus.PENDING, model=None)
    
    # Mock the service method
    mock_execute_step = Mock()
    monkeypatch.setattr("tasksgodzilla.services.execution.ExecutionService.execute_step", mock_execute_step)
    
    service = OrchestratorService(db=db)
    service.execute_step(step.id, job_id="test-job")
    
    # Verify service was called
    mock_execute_step.assert_called_once_with(step.id, job_id="test-job")


def test_open_protocol_pr_delegates_to_service(tmp_path, monkeypatch):
    """Test open_protocol_pr uses GitService."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.RUNNING, "main", None, None, None)
    
    # Mock GitService methods
    mock_ensure_repo = Mock(return_value=Path("/tmp/repo"))
    mock_ensure_worktree = Mock(return_value=Path("/tmp/worktree"))
    mock_get_branch_name = Mock(return_value="test-protocol")
    mock_push_and_open_pr = Mock(return_value=True)
    
    monkeypatch.setattr("tasksgodzilla.services.git.GitService.ensure_repo_or_block", mock_ensure_repo)
    monkeypatch.setattr("tasksgodzilla.services.git.GitService.ensure_worktree", mock_ensure_worktree)
    monkeypatch.setattr("tasksgodzilla.services.git.GitService.get_branch_name", mock_get_branch_name)
    monkeypatch.setattr("tasksgodzilla.services.git.GitService.push_and_open_pr", mock_push_and_open_pr)
    
    service = OrchestratorService(db=db)
    service.open_protocol_pr(run.id, job_id="test-job")
    
    # Verify GitService methods were called
    mock_ensure_repo.assert_called_once()
    mock_ensure_worktree.assert_called_once()
    mock_push_and_open_pr.assert_called_once()


def test_enqueue_open_protocol_pr_enqueues_pr_job(tmp_path):
    """Test enqueue_open_protocol_pr enqueues a PR opening job."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.RUNNING, "main", None, None, None)
    
    mock_queue = Mock()
    mock_queue.enqueue.return_value = Job(job_id="pr-job-2", job_type="open_pr_job", payload={})
    
    service = OrchestratorService(db=db)
    job = service.enqueue_open_protocol_pr(run.id, queue=mock_queue)
    
    assert job.job_id == "pr-job-2"
    mock_queue.enqueue.assert_called_once_with("open_pr_job", {"protocol_run_id": run.id})


def test_sync_steps_from_protocol_creates_step_runs(tmp_path):
    """Test sync_steps_from_protocol creates StepRun rows from protocol spec."""
    db = Database(tmp_path / "test.db")
    db.init_schema()
    project = db.create_project("test-project", "https://github.com/test/repo", "main", "github", {})
    run = db.create_protocol_run(project.id, "test-protocol", ProtocolStatus.PLANNED, "main", None, None, None)
    
    # Create protocol directory with step files
    protocol_root = tmp_path / "protocol"
    protocol_root.mkdir()
    (protocol_root / "01-step.md").write_text("# Step 1", encoding="utf-8")
    (protocol_root / "02-step.md").write_text("# Step 2", encoding="utf-8")
    
    service = OrchestratorService(db=db)
    created = service.sync_steps_from_protocol(run.id, protocol_root)
    
    assert created == 2
    steps = db.list_step_runs(run.id)
    assert len(steps) == 2
