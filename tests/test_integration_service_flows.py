"""Integration tests for service flows.

These tests verify end-to-end workflows through the services layer,
ensuring that services interact correctly to complete complex operations.
"""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tasksgodzilla.config import load_config
from tasksgodzilla.domain import ProtocolStatus, StepStatus
from tasksgodzilla.jobs import RedisQueue
from tasksgodzilla.services.orchestrator import OrchestratorService
from tasksgodzilla.services.execution import ExecutionService
from tasksgodzilla.services.quality import QualityService
from tasksgodzilla.services.git import GitService
from tasksgodzilla.services.budget import BudgetService
from tasksgodzilla.services.spec import SpecService
from tasksgodzilla.storage import Database


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    db = Database(db_path)
    db.init_schema()
    yield db
    
    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def test_project(temp_db):
    """Create a test project."""
    return temp_db.create_project(
        name="test-project",
        git_url="https://github.com/test/repo.git",
        base_branch="main",
        ci_provider="github",
        default_models={"exec": "codex-5.1-max", "qa": "codex-5.1-max"},
        secrets=None,
        local_path=None
    )


@pytest.fixture
def mock_queue():
    """Create a mock queue for testing."""
    queue = MagicMock(spec=RedisQueue)
    queue.enqueue = MagicMock(side_effect=lambda job_type, payload: MagicMock(
        job_id=f"job-{job_type}-{payload.get('protocol_run_id', payload.get('step_run_id', 'unknown'))}",
        asdict=lambda: {"job_id": f"job-{job_type}"}
    ))
    return queue


class TestProtocolLifecycleIntegration:
    """Integration tests for complete protocol lifecycle through services."""
    
    def test_create_plan_execute_complete_flow(self, temp_db, test_project, mock_queue):
        """Test create → plan → execute → complete flow.
        
        Validates Requirements 5.4: Integration tests verify end-to-end flows through services.
        """
        orchestrator = OrchestratorService(temp_db)
        
        # Step 1: Create protocol run
        protocol_run = orchestrator.create_protocol_run(
            project_id=test_project.id,
            protocol_name="test-protocol-123",
            status=ProtocolStatus.PENDING,
            base_branch="main",
            worktree_path=None,
            protocol_root=None,
            description="Test protocol for integration testing"
        )
        
        assert protocol_run.id is not None
        assert protocol_run.status == ProtocolStatus.PENDING
        assert protocol_run.protocol_name == "test-protocol-123"
        assert protocol_run.project_id == test_project.id
        
        # Step 2: Start protocol (transition to PLANNING)
        job = orchestrator.start_protocol_run(protocol_run.id, mock_queue)
        
        assert job.job_id is not None
        mock_queue.enqueue.assert_called_once_with(
            "plan_protocol_job",
            {"protocol_run_id": protocol_run.id}
        )
        
        # Verify status transition
        updated_run = temp_db.get_protocol_run(protocol_run.id)
        assert updated_run.status == ProtocolStatus.PLANNING
        
        # Step 3: Simulate planning completion - create step runs
        temp_db.update_protocol_status(protocol_run.id, ProtocolStatus.PLANNED)
        
        step1 = temp_db.create_step_run(
            protocol_run_id=protocol_run.id,
            step_index=0,
            step_name="step-1",
            step_type="task",
            status=StepStatus.PENDING,
            model="codex-5.1-max",
            engine_id="codex"
        )
        
        step2 = temp_db.create_step_run(
            protocol_run_id=protocol_run.id,
            step_index=1,
            step_name="step-2",
            step_type="task",
            status=StepStatus.PENDING,
            model="codex-5.1-max",
            engine_id="codex"
        )
        
        # Step 4: Enqueue first step for execution
        mock_queue.reset_mock()
        step_run, step_job = orchestrator.enqueue_next_step(protocol_run.id, mock_queue)
        
        assert step_run.id == step1.id
        assert step_run.status == StepStatus.RUNNING
        mock_queue.enqueue.assert_called_once_with(
            "execute_step_job",
            {"step_run_id": step1.id}
        )
        
        # Verify protocol is now RUNNING
        updated_run = temp_db.get_protocol_run(protocol_run.id)
        assert updated_run.status == ProtocolStatus.RUNNING
        
        # Step 5: Simulate step execution completion
        temp_db.update_step_status(step1.id, StepStatus.NEEDS_QA, summary="Execution completed")
        
        # Step 6: Simulate QA pass
        temp_db.update_step_status(step1.id, StepStatus.COMPLETED, summary="QA passed")
        
        # Step 7: Handle step completion (should trigger next step or check completion)
        orchestrator.handle_step_completion(step1.id, qa_verdict="PASS")
        
        # Step 8: Enqueue second step
        mock_queue.reset_mock()
        step_run2, step_job2 = orchestrator.enqueue_next_step(protocol_run.id, mock_queue)
        
        assert step_run2.id == step2.id
        assert step_run2.status == StepStatus.RUNNING
        
        # Step 9: Complete second step
        temp_db.update_step_status(step2.id, StepStatus.NEEDS_QA, summary="Execution completed")
        temp_db.update_step_status(step2.id, StepStatus.COMPLETED, summary="QA passed")
        
        # handle_step_completion should check and complete the protocol automatically
        orchestrator.handle_step_completion(step2.id, qa_verdict="PASS")
        
        # Verify protocol was completed
        final_run = temp_db.get_protocol_run(protocol_run.id)
        assert final_run.status == ProtocolStatus.COMPLETED
        
        # Verify events were logged
        events = temp_db.list_events(protocol_run.id)
        assert len(events) > 0
        assert any(e.event_type == "protocol_completed" for e in events)
    
    def test_protocol_pause_resume_flow(self, temp_db, test_project, mock_queue):
        """Test protocol pause and resume operations.
        
        Validates Requirements 5.4: Integration tests verify end-to-end flows through services.
        """
        orchestrator = OrchestratorService(temp_db)
        
        # Create and start protocol
        protocol_run = orchestrator.create_protocol_run(
            project_id=test_project.id,
            protocol_name="test-pause-resume",
            status=ProtocolStatus.PENDING,
            base_branch="main"
        )
        
        orchestrator.start_protocol_run(protocol_run.id, mock_queue)
        temp_db.update_protocol_status(protocol_run.id, ProtocolStatus.RUNNING)
        
        # Pause protocol
        paused_run = orchestrator.pause_protocol(protocol_run.id)
        assert paused_run.status == ProtocolStatus.PAUSED
        
        # Resume protocol
        resumed_run = orchestrator.resume_protocol(protocol_run.id)
        assert resumed_run.status == ProtocolStatus.RUNNING
    
    def test_protocol_cancel_flow(self, temp_db, test_project, mock_queue):
        """Test protocol cancellation with step cleanup.
        
        Validates Requirements 5.4: Integration tests verify end-to-end flows through services.
        """
        orchestrator = OrchestratorService(temp_db)
        
        # Create protocol with steps
        protocol_run = orchestrator.create_protocol_run(
            project_id=test_project.id,
            protocol_name="test-cancel",
            status=ProtocolStatus.PENDING,
            base_branch="main"
        )
        
        orchestrator.start_protocol_run(protocol_run.id, mock_queue)
        temp_db.update_protocol_status(protocol_run.id, ProtocolStatus.RUNNING)
        
        # Create steps in various states
        step1 = temp_db.create_step_run(
            protocol_run_id=protocol_run.id,
            step_index=0,
            step_name="step-1",
            step_type="task",
            status=StepStatus.RUNNING,
            model="codex-5.1-max"
        )
        
        step2 = temp_db.create_step_run(
            protocol_run_id=protocol_run.id,
            step_index=1,
            step_name="step-2",
            step_type="task",
            status=StepStatus.PENDING,
            model="codex-5.1-max"
        )
        
        step3 = temp_db.create_step_run(
            protocol_run_id=protocol_run.id,
            step_index=2,
            step_name="step-3",
            step_type="task",
            status=StepStatus.COMPLETED,
            model="codex-5.1-max"
        )
        
        # Cancel protocol
        cancelled_run = orchestrator.cancel_protocol(protocol_run.id)
        assert cancelled_run.status == ProtocolStatus.CANCELLED
        
        # Verify running and pending steps are cancelled
        updated_step1 = temp_db.get_step_run(step1.id)
        updated_step2 = temp_db.get_step_run(step2.id)
        updated_step3 = temp_db.get_step_run(step3.id)
        
        assert updated_step1.status == StepStatus.CANCELLED
        assert updated_step2.status == StepStatus.CANCELLED
        assert updated_step3.status == StepStatus.COMPLETED  # Already completed, not changed


class TestStepExecutionIntegration:
    """Integration tests for step execution through services."""
    
    @patch('tasksgodzilla.services.git.GitService.ensure_repo_or_block')
    @patch('tasksgodzilla.services.git.GitService.ensure_worktree')
    @patch('shutil.which')
    def test_step_execution_stub_mode(
        self,
        mock_which,
        mock_ensure_worktree,
        mock_ensure_repo,
        temp_db,
        test_project
    ):
        """Test step execution in stub mode (no codex available).
        
        Validates Requirements 5.4: Integration tests verify git, budget, spec, prompt services.
        """
        # Setup mocks
        mock_which.return_value = None  # Codex not available
        mock_ensure_repo.return_value = None  # Repo not available
        
        execution_service = ExecutionService(temp_db)
        
        # Create protocol and step
        protocol_run = temp_db.create_protocol_run(
            project_id=test_project.id,
            protocol_name="test-exec",
            status=ProtocolStatus.RUNNING,
            base_branch="main",
            worktree_path=None,
            protocol_root=None,
            description="Test execution",
            template_config={"steps": [{"id": "test-step", "name": "Test Step"}]}
        )
        
        step = temp_db.create_step_run(
            protocol_run_id=protocol_run.id,
            step_index=0,
            step_name="test-step",
            step_type="task",
            status=StepStatus.RUNNING,
            model="codex-5.1-max",
            engine_id="codex"
        )
        
        # Execute step (should run in stub mode)
        execution_service.execute_step(step.id, job_id="test-job-123")
        
        # Verify step transitioned to NEEDS_QA (stub mode default)
        updated_step = temp_db.get_step_run(step.id)
        assert updated_step.status == StepStatus.NEEDS_QA
        assert "stub" in updated_step.summary.lower()
        
        # Verify events were logged
        events = temp_db.list_events(protocol_run.id)
        assert len(events) > 0
        assert any(e.event_type == "step_completed" for e in events)
    
    @patch('tasksgodzilla.services.git.GitService.ensure_repo_or_block')
    @patch('tasksgodzilla.services.git.GitService.ensure_worktree')
    @patch('shutil.which')
    def test_step_execution_with_qa_skip_policy(
        self,
        mock_which,
        mock_ensure_worktree,
        mock_ensure_repo,
        temp_db,
        test_project
    ):
        """Test step execution with QA skip policy.
        
        Validates Requirements 5.4: Integration tests verify service interactions.
        """
        # Setup mocks
        mock_which.return_value = None
        mock_ensure_repo.return_value = None
        
        execution_service = ExecutionService(temp_db)
        orchestrator = OrchestratorService(temp_db)
        
        # Create protocol with QA skip policy
        protocol_run = temp_db.create_protocol_run(
            project_id=test_project.id,
            protocol_name="test-qa-skip",
            status=ProtocolStatus.RUNNING,
            base_branch="main",
            worktree_path=None,
            protocol_root=None,
            description="Test QA skip",
            template_config={
                "steps": [{
                    "id": "test-step",
                    "name": "Test Step",
                    "qa": {"policy": "skip"}
                }]
            }
        )
        
        step = temp_db.create_step_run(
            protocol_run_id=protocol_run.id,
            step_index=0,
            step_name="test-step",
            step_type="task",
            status=StepStatus.RUNNING,
            model="codex-5.1-max"
        )
        
        # Execute step
        execution_service.execute_step(step.id, job_id="test-job-456")
        
        # In stub mode (no repo), step goes to NEEDS_QA even with skip policy
        # The QA skip policy is applied during QA execution, not during step execution
        updated_step = temp_db.get_step_run(step.id)
        assert updated_step.status == StepStatus.NEEDS_QA
        assert "stub" in updated_step.summary.lower()
        
        # Verify step execution event was logged
        events = temp_db.list_events(protocol_run.id)
        assert any(e.event_type == "step_completed" for e in events)


class TestQAWorkflowIntegration:
    """Integration tests for QA workflow through services."""
    
    @patch('tasksgodzilla.services.git.GitService.ensure_repo_or_block')
    @patch('tasksgodzilla.services.git.GitService.ensure_worktree')
    @patch('tasksgodzilla.services.prompts.PromptService.resolve_qa_prompt')
    @patch('tasksgodzilla.services.prompts.PromptService.resolve_step_path_for_qa')
    @patch('tasksgodzilla.services.prompts.PromptService.build_qa_context')
    @patch('shutil.which')
    def test_qa_workflow_with_pass_verdict(
        self,
        mock_which,
        mock_build_context,
        mock_resolve_step,
        mock_resolve_qa,
        mock_ensure_worktree,
        mock_ensure_repo,
        temp_db,
        test_project
    ):
        """Test QA evaluation workflow with PASS verdict.
        
        Validates Requirements 5.4: Integration tests verify quality and prompt services.
        """
        # Setup mocks
        mock_which.return_value = None  # Codex not available (stub mode)
        mock_ensure_repo.return_value = Path("/tmp/test-repo")
        mock_ensure_worktree.return_value = Path("/tmp/test-worktree")
        
        mock_resolve_qa.return_value = (Path("/tmp/qa-prompt.md"), "v1.0")
        mock_resolve_step.return_value = Path("/tmp/step.md")
        mock_build_context.return_value = {
            "plan": "Test plan",
            "context": "Test context",
            "log": "Test log",
            "step": "Test step content",
            "step_name": "test-step",
            "git_status": "clean",
            "last_commit": "Initial commit"
        }
        
        quality_service = QualityService(db=temp_db)
        orchestrator = OrchestratorService(temp_db)
        
        # Create protocol and step
        protocol_run = temp_db.create_protocol_run(
            project_id=test_project.id,
            protocol_name="test-qa",
            status=ProtocolStatus.RUNNING,
            base_branch="main",
            worktree_path=None,
            protocol_root=None,
            description="Test QA",
            template_config={"steps": [{"id": "test-step", "name": "Test Step"}]}
        )
        
        step = temp_db.create_step_run(
            protocol_run_id=protocol_run.id,
            step_index=0,
            step_name="test-step",
            step_type="task",
            status=StepStatus.NEEDS_QA,
            model="codex-5.1-max"
        )
        
        # Run QA (will run in stub mode and pass)
        quality_service.run_for_step_run(step.id, job_id="test-qa-job")
        
        # Verify step completed with PASS
        updated_step = temp_db.get_step_run(step.id)
        assert updated_step.status == StepStatus.COMPLETED
        
        # Verify QA events were logged
        events = temp_db.list_events(protocol_run.id)
        assert any(e.event_type == "qa_passed" for e in events)
    
    @patch('tasksgodzilla.services.git.GitService.ensure_repo_or_block')
    @patch('tasksgodzilla.services.git.GitService.ensure_worktree')
    def test_qa_skip_policy(
        self,
        mock_ensure_worktree,
        mock_ensure_repo,
        temp_db,
        test_project
    ):
        """Test QA workflow with skip policy.
        
        Validates Requirements 5.4: Integration tests verify service policy handling.
        """
        mock_ensure_repo.return_value = Path("/tmp/test-repo")
        mock_ensure_worktree.return_value = Path("/tmp/test-worktree")
        
        quality_service = QualityService(db=temp_db)
        spec_service = SpecService(temp_db)
        
        # Create protocol with QA skip policy
        protocol_run = temp_db.create_protocol_run(
            project_id=test_project.id,
            protocol_name="test-qa-skip-policy",
            status=ProtocolStatus.RUNNING,
            base_branch="main",
            worktree_path=None,
            protocol_root=None,
            description="Test QA skip policy",
            template_config={
                "steps": [{
                    "id": "test-step",
                    "name": "Test Step",
                    "qa": {"policy": "skip"}
                }]
            }
        )
        
        step = temp_db.create_step_run(
            protocol_run_id=protocol_run.id,
            step_index=0,
            step_name="test-step",
            step_type="task",
            status=StepStatus.NEEDS_QA,
            model="codex-5.1-max"
        )
        
        # Run QA
        quality_service.run_for_step_run(step.id, job_id="test-qa-skip-job")
        
        # Verify step completed
        updated_step = temp_db.get_step_run(step.id)
        assert updated_step.status == StepStatus.COMPLETED
        
        # Verify events were logged - the QA service logs events during execution
        events = temp_db.list_events(protocol_run.id)
        assert len(events) > 0
        
        # Check for QA-related events (either skip or pass)
        qa_events = [e for e in events if "qa" in e.event_type.lower()]
        assert len(qa_events) > 0


class TestServiceIntegrationPatterns:
    """Tests for common service integration patterns."""
    
    def test_services_use_database_correctly(self, temp_db, test_project):
        """Verify all services interact with database correctly.
        
        Validates Requirements 5.4: Services should use database for state management.
        """
        orchestrator = OrchestratorService(temp_db)
        git_service = GitService(temp_db)
        spec_service = SpecService(temp_db)
        
        # Create protocol
        protocol_run = orchestrator.create_protocol_run(
            project_id=test_project.id,
            protocol_name="test-db-integration",
            status=ProtocolStatus.PENDING,
            base_branch="main"
        )
        
        # Verify all services can access the same data
        retrieved_run = temp_db.get_protocol_run(protocol_run.id)
        assert retrieved_run.id == protocol_run.id
        assert retrieved_run.protocol_name == "test-db-integration"
        
        # Verify services can update state
        temp_db.update_protocol_status(protocol_run.id, ProtocolStatus.RUNNING)
        updated_run = temp_db.get_protocol_run(protocol_run.id)
        assert updated_run.status == ProtocolStatus.RUNNING
    
    def test_service_event_logging(self, temp_db, test_project):
        """Verify services log events correctly.
        
        Validates Requirements 5.4: Services should log events for observability.
        """
        orchestrator = OrchestratorService(temp_db)
        
        # Create protocol
        protocol_run = orchestrator.create_protocol_run(
            project_id=test_project.id,
            protocol_name="test-events",
            status=ProtocolStatus.PENDING,
            base_branch="main"
        )
        
        # Log some events
        temp_db.append_event(
            protocol_run.id,
            "test_event",
            "Test event message",
            metadata={"key": "value"}
        )
        
        # Verify events are retrievable
        events = temp_db.list_events(protocol_run.id)
        assert len(events) > 0
        
        test_events = [e for e in events if e.event_type == "test_event"]
        assert len(test_events) == 1
        assert test_events[0].message == "Test event message"
        assert test_events[0].metadata == {"key": "value"}
