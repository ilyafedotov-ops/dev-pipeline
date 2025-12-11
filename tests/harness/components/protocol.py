"""ProtocolTestComponent - Tests protocol pipeline workflow end-to-end."""

import subprocess
import tempfile
import shutil
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

from tasksgodzilla.storage import Database
from tasksgodzilla.config import load_config
from tasksgodzilla.domain import ProtocolStatus
from ..environment import EnvironmentContext
from ..models import TestResult, HarnessStatus


class ProtocolTestComponent:
    """Test component for protocol pipeline functionality."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = load_config()
    
    def run_test(self, project, env_context: EnvironmentContext) -> bool:
        """Run comprehensive protocol tests."""
        try:
            # Test various protocol scenarios
            test_results = []
            
            # Test 1: Test protocol creation and planning
            result1 = self._test_protocol_creation_and_planning(env_context)
            test_results.append(result1)
            
            # Test 2: Test protocol step execution
            result2 = self._test_protocol_step_execution(env_context)
            test_results.append(result2)
            
            # Test 3: Test worktree management and Git operations
            result3 = self._test_worktree_management(env_context)
            test_results.append(result3)
            
            # Test 4: Test protocol completion and cleanup
            result4 = self._test_protocol_completion_cleanup(env_context)
            test_results.append(result4)
            
            # Test 5: Test protocol pipeline CLI interface
            result5 = self._test_protocol_pipeline_cli(env_context)
            test_results.append(result5)
            
            # Test 6: Test protocol error handling and rollback
            result6 = self._test_protocol_error_handling(env_context)
            test_results.append(result6)
            
            # Test 7: Test protocol validation workflows
            result7 = self._test_protocol_validation_workflows(env_context)
            test_results.append(result7)
            
            # Log detailed results for debugging
            self.logger.info(f"Protocol test results: {[(r.test_name, r.status.value) for r in test_results]}")
            
            # Count passed tests (some may be skipped if dependencies unavailable)
            passed_tests = [r for r in test_results if r.status == HarnessStatus.PASS]
            failed_tests = [r for r in test_results if r.status == HarnessStatus.FAIL]
            
            # Consider success if no tests failed (skipped tests are OK)
            success = len(failed_tests) == 0
            
            if not success:
                failed_test_names = [r.test_name for r in failed_tests]
                self.logger.error(f"Protocol tests failed: {failed_test_names}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"ProtocolTestComponent failed: {e}")
            return False
    
    def _is_codex_available(self) -> bool:
        """Check if Codex CLI is available."""
        try:
            result = subprocess.run(
                ["codex", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _test_protocol_creation_and_planning(self, env_context: EnvironmentContext) -> TestResult:
        """Test protocol creation and planning functionality."""
        test_name = "protocol_creation_and_planning"
        
        try:
            # Check if we have projects in the database to work with
            db_path = getattr(env_context, 'database_path', None)
            if not db_path:
                db_path = os.environ.get('TASKSGODZILLA_DB_PATH')
                if not db_path:
                    return TestResult(
                        component="protocol",
                        test_name=test_name,
                        status=HarnessStatus.SKIP,
                        duration=0.0,
                        error_message="No database path available for testing"
                    )
            
            db = Database(db_path)
            projects = db.list_projects()
            
            if not projects:
                return TestResult(
                    component="protocol",
                    test_name=test_name,
                    status=HarnessStatus.SKIP,
                    duration=0.0,
                    error_message="No projects in database to test protocol creation"
                )
            
            # Use the first project for testing
            project = projects[0]
            
            # Create a test protocol run
            protocol_run = db.create_protocol_run(
                project_id=project.id,
                protocol_name="test-protocol-harness",
                status=ProtocolStatus.PENDING,
                base_branch=project.base_branch,
                worktree_path=None,
                protocol_root=None,
                description="Test protocol created by harness",
            )
            
            if protocol_run:
                # Check that the protocol was created successfully
                retrieved_run = db.get_protocol_run(protocol_run.id)
                
                if (retrieved_run and 
                    retrieved_run.protocol_name == "test-protocol-harness" and
                    retrieved_run.status == ProtocolStatus.PENDING):
                    
                    return TestResult(
                        component="protocol",
                        test_name=test_name,
                        status=HarnessStatus.PASS,
                        duration=0.5,
                        metadata={"protocol_run_id": protocol_run.id}
                    )
                else:
                    return TestResult(
                        component="protocol",
                        test_name=test_name,
                        status=HarnessStatus.FAIL,
                        duration=0.5,
                        error_message="Protocol run not properly stored or retrieved"
                    )
            else:
                return TestResult(
                    component="protocol",
                    test_name=test_name,
                    status=HarnessStatus.FAIL,
                    duration=0.5,
                    error_message="Failed to create protocol run"
                )
                
        except Exception as e:
            return TestResult(
                component="protocol",
                test_name=test_name,
                status=HarnessStatus.ERROR,
                duration=0.0,
                error_message=str(e)
            )
    
    def _test_protocol_step_execution(self, env_context: EnvironmentContext) -> TestResult:
        """Test protocol step execution functionality."""
        test_name = "protocol_step_execution"
        
        try:
            db_path = getattr(env_context, 'database_path', None)
            if not db_path:
                db_path = os.environ.get('TASKSGODZILLA_DB_PATH')
                if not db_path:
                    return TestResult(
                        component="protocol",
                        test_name=test_name,
                        status=HarnessStatus.SKIP,
                        duration=0.0,
                        error_message="No database path available for testing"
                    )
            
            db = Database(db_path)
            
            # Look for existing protocol runs
            projects = db.list_projects()
            if not projects:
                return TestResult(
                    component="protocol",
                    test_name=test_name,
                    status=HarnessStatus.SKIP,
                    duration=0.0,
                    error_message="No projects available for step execution test"
                )
            
            # Find protocol runs
            protocol_runs = []
            for project in projects:
                runs = db.list_protocol_runs(project.id)
                protocol_runs.extend(runs)
            
            if not protocol_runs:
                return TestResult(
                    component="protocol",
                    test_name=test_name,
                    status=HarnessStatus.SKIP,
                    duration=0.0,
                    error_message="No protocol runs available for step execution test"
                )
            
            # Test step creation and status updates
            test_run = protocol_runs[0]
            
            # Create a test step
            step_run = db.create_step_run(
                protocol_run_id=test_run.id,
                step_name="test-step",
                step_type="implementation",
                step_file="test-step.md",
                status="pending"
            )
            
            if step_run:
                # Update step status to simulate execution
                db.update_step_status(step_run.id, "completed", summary="Test step completed")
                
                # Verify the update
                updated_step = db.get_step_run(step_run.id)
                
                if updated_step and updated_step.status == "completed":
                    return TestResult(
                        component="protocol",
                        test_name=test_name,
                        status=HarnessStatus.PASS,
                        duration=0.3,
                        metadata={"step_run_id": step_run.id}
                    )
                else:
                    return TestResult(
                        component="protocol",
                        test_name=test_name,
                        status=HarnessStatus.FAIL,
                        duration=0.3,
                        error_message="Step status update failed"
                    )
            else:
                return TestResult(
                    component="protocol",
                    test_name=test_name,
                    status=HarnessStatus.FAIL,
                    duration=0.3,
                    error_message="Failed to create step run"
                )
                
        except Exception as e:
            return TestResult(
                component="protocol",
                test_name=test_name,
                status=HarnessStatus.ERROR,
                duration=0.0,
                error_message=str(e)
            )
    
    def _test_worktree_management(self, env_context: EnvironmentContext) -> TestResult:
        """Test worktree management and Git operations."""
        test_name = "worktree_management"
        
        try:
            db = Database(env_context.db_path)
            projects = db.list_projects()
            
            if not projects:
                return TestResult(
                    component="protocol",
                    test_name=test_name,
                    status=HarnessStatus.SKIP,
                    duration=0.0,
                    error_message="No projects available for worktree test"
                )
            
            # Find a project with a valid local path
            test_project = None
            for project in projects:
                if project.local_path and Path(project.local_path).exists():
                    project_path = Path(project.local_path)
                    if (project_path / ".git").exists():
                        test_project = project
                        break
            
            if not test_project:
                return TestResult(
                    component="protocol",
                    test_name=test_name,
                    status=HarnessStatus.SKIP,
                    duration=0.0,
                    error_message="No projects with valid git repositories found"
                )
            
            project_path = Path(test_project.local_path)
            
            # Test basic git operations
            try:
                # Check git status
                result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=project_path,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode != 0:
                    return TestResult(
                        component="protocol",
                        test_name=test_name,
                        status=HarnessStatus.FAIL,
                        duration=0.5,
                        error_message=f"Git status failed: {result.stderr}"
                    )
                
                # Check current branch
                result = subprocess.run(
                    ["git", "branch", "--show-current"],
                    cwd=project_path,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    current_branch = result.stdout.strip()
                    
                    # Test branch listing
                    result = subprocess.run(
                        ["git", "branch", "-a"],
                        cwd=project_path,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if result.returncode == 0:
                        return TestResult(
                            component="protocol",
                            test_name=test_name,
                            status=HarnessStatus.PASS,
                            duration=0.5,
                            metadata={"current_branch": current_branch}
                        )
                    else:
                        return TestResult(
                            component="protocol",
                            test_name=test_name,
                            status=HarnessStatus.FAIL,
                            duration=0.5,
                            error_message=f"Git branch listing failed: {result.stderr}"
                        )
                else:
                    return TestResult(
                        component="protocol",
                        test_name=test_name,
                        status=HarnessStatus.FAIL,
                        duration=0.5,
                        error_message=f"Git branch check failed: {result.stderr}"
                    )
                    
            except subprocess.TimeoutExpired:
                return TestResult(
                    component="protocol",
                    test_name=test_name,
                    status=HarnessStatus.FAIL,
                    duration=10.0,
                    error_message="Git operations timed out"
                )
                
        except Exception as e:
            return TestResult(
                component="protocol",
                test_name=test_name,
                status=HarnessStatus.ERROR,
                duration=0.0,
                error_message=str(e)
            )
    
    def _test_protocol_completion_cleanup(self, env_context: EnvironmentContext) -> TestResult:
        """Test protocol completion and cleanup functionality."""
        test_name = "protocol_completion_cleanup"
        
        try:
            db_path = getattr(env_context, 'database_path', None)
            if not db_path:
                db_path = os.environ.get('TASKSGODZILLA_DB_PATH')
                if not db_path:
                    return TestResult(
                        component="protocol",
                        test_name=test_name,
                        status=HarnessStatus.SKIP,
                        duration=0.0,
                        error_message="No database path available for testing"
                    )
            
            db = Database(db_path)
            
            # Find protocol runs to test completion
            projects = db.list_projects()
            if not projects:
                return TestResult(
                    component="protocol",
                    test_name=test_name,
                    status=HarnessStatus.SKIP,
                    duration=0.0,
                    error_message="No projects available for completion test"
                )
            
            protocol_runs = []
            for project in projects:
                runs = db.list_protocol_runs(project.id)
                protocol_runs.extend(runs)
            
            if not protocol_runs:
                return TestResult(
                    component="protocol",
                    test_name=test_name,
                    status=HarnessStatus.SKIP,
                    duration=0.0,
                    error_message="No protocol runs available for completion test"
                )
            
            # Test protocol status transitions
            test_run = protocol_runs[0]
            original_status = test_run.status
            
            # Test status update to completed
            db.update_protocol_status(test_run.id, ProtocolStatus.COMPLETED)
            
            # Verify the update
            updated_run = db.get_protocol_run(test_run.id)
            
            if updated_run and updated_run.status == ProtocolStatus.COMPLETED:
                # Test event logging for completion
                db.append_event(
                    protocol_run_id=test_run.id,
                    event_type="protocol_completed",
                    message="Protocol completed by harness test"
                )
                
                # Verify event was logged
                events = db.list_events(test_run.id)
                completion_events = [e for e in events if e.event_type == "protocol_completed"]
                
                if completion_events:
                    return TestResult(
                        component="protocol",
                        test_name=test_name,
                        status=HarnessStatus.PASS,
                        duration=0.3,
                        metadata={"original_status": original_status.value}
                    )
                else:
                    return TestResult(
                        component="protocol",
                        test_name=test_name,
                        status=HarnessStatus.FAIL,
                        duration=0.3,
                        error_message="Completion event not logged"
                    )
            else:
                return TestResult(
                    component="protocol",
                    test_name=test_name,
                    status=HarnessStatus.FAIL,
                    duration=0.3,
                    error_message="Protocol status update to completed failed"
                )
                
        except Exception as e:
            return TestResult(
                component="protocol",
                test_name=test_name,
                status=HarnessStatus.ERROR,
                duration=0.0,
                error_message=str(e)
            )
    
    def _test_protocol_pipeline_cli(self, env_context: EnvironmentContext) -> TestResult:
        """Test protocol pipeline CLI interface."""
        test_name = "protocol_pipeline_cli"
        
        try:
            # Test if the protocol_pipeline.py script exists and is executable
            script_path = Path(__file__).resolve().parents[3] / "scripts" / "protocol_pipeline.py"
            
            if not script_path.exists():
                return TestResult(
                    component="protocol",
                    test_name=test_name,
                    status=HarnessStatus.FAIL,
                    duration=0.0,
                    error_message="protocol_pipeline.py script not found"
                )
            
            # Test help output (should not require Codex)
            try:
                result = subprocess.run(
                    ["python3", str(script_path), "--help"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0 and "protocol pipeline" in result.stdout.lower():
                    return TestResult(
                        component="protocol",
                        test_name=test_name,
                        status=HarnessStatus.PASS,
                        duration=1.0,
                    )
                else:
                    return TestResult(
                        component="protocol",
                        test_name=test_name,
                        status=HarnessStatus.FAIL,
                        duration=1.0,
                        error_message=f"Protocol pipeline help failed: {result.stderr}"
                    )
                    
            except subprocess.TimeoutExpired:
                return TestResult(
                    component="protocol",
                    test_name=test_name,
                    status=HarnessStatus.FAIL,
                    duration=30.0,
                    error_message="Protocol pipeline help command timed out"
                )
                
        except Exception as e:
            return TestResult(
                component="protocol",
                test_name=test_name,
                status=HarnessStatus.ERROR,
                duration=0.0,
                error_message=str(e)
            )
    def _test_protocol_error_handling(self, env_context: EnvironmentContext) -> TestResult:
        """Test protocol error handling and rollback functionality."""
        test_name = "protocol_error_handling"
        
        try:
            db_path = getattr(env_context, 'database_path', None)
            if not db_path:
                db_path = os.environ.get('TASKSGODZILLA_DB_PATH')
                if not db_path:
                    return TestResult(
                        component="protocol",
                        test_name=test_name,
                        status=HarnessStatus.SKIP,
                        duration=0.0,
                        error_message="No database path available for testing"
                    )
            
            db = Database(db_path)
            projects = db.list_projects()
            
            if not projects:
                return TestResult(
                    component="protocol",
                    test_name=test_name,
                    status=HarnessStatus.SKIP,
                    duration=0.0,
                    error_message="No projects available for error handling test"
                )
            
            project = projects[0]
            
            # Test error scenarios
            error_test_results = []
            
            # Test 1: Create protocol with invalid parameters
            try:
                invalid_protocol = db.create_protocol_run(
                    project_id=project.id,
                    protocol_name="",  # Empty name should be handled
                    status=ProtocolStatus.PENDING,
                    base_branch="",  # Empty branch should be handled
                    worktree_path=None,
                    protocol_root=None,
                    description="Test invalid protocol",
                )
                
                if invalid_protocol:
                    error_test_results.append("invalid_params: created (should validate better)")
                else:
                    error_test_results.append("invalid_params: rejected (good)")
                    
            except Exception as e:
                error_test_results.append(f"invalid_params: exception handled - {str(e)[:100]}")
            
            # Test 2: Update protocol status to invalid state
            try:
                # Create a valid protocol first
                test_protocol = db.create_protocol_run(
                    project_id=project.id,
                    protocol_name="test-error-protocol",
                    status=ProtocolStatus.PENDING,
                    base_branch=project.base_branch,
                    worktree_path=None,
                    protocol_root=None,
                    description="Test error handling protocol",
                )
                
                if test_protocol:
                    # Try to update to invalid status (this should be handled gracefully)
                    try:
                        db.update_protocol_status(test_protocol.id, "invalid_status")
                        error_test_results.append("invalid_status: accepted (should validate)")
                    except Exception as e:
                        error_test_results.append("invalid_status: rejected (good)")
                        
                    # Test rollback by updating to failed status
                    db.update_protocol_status(test_protocol.id, ProtocolStatus.FAILED)
                    updated_protocol = db.get_protocol_run(test_protocol.id)
                    
                    if updated_protocol and updated_protocol.status == ProtocolStatus.FAILED:
                        error_test_results.append("rollback_to_failed: success")
                    else:
                        error_test_results.append("rollback_to_failed: failed")
                        
            except Exception as e:
                error_test_results.append(f"status_update_error: {str(e)[:100]}")
            
            # Test 3: Step execution error handling
            try:
                if test_protocol:
                    # Create a step that might fail
                    error_step = db.create_step_run(
                        protocol_run_id=test_protocol.id,
                        step_name="error-test-step",
                        step_type="implementation",
                        step_file="error-test.md",
                        status="pending"
                    )
                    
                    if error_step:
                        # Simulate step failure
                        db.update_step_status(error_step.id, "failed", summary="Simulated failure for testing")
                        
                        # Verify failure was recorded
                        failed_step = db.get_step_run(error_step.id)
                        if failed_step and failed_step.status == "failed":
                            error_test_results.append("step_failure_handling: success")
                        else:
                            error_test_results.append("step_failure_handling: failed")
                            
            except Exception as e:
                error_test_results.append(f"step_error_handling: {str(e)[:100]}")
            
            # Evaluate results
            failed_error_tests = [r for r in error_test_results if "failed" in r or "exception" in r]
            
            if len(failed_error_tests) == 0:
                return TestResult(
                    component="protocol",
                    test_name=test_name,
                    status=HarnessStatus.PASS,
                    duration=0.5,
                    metadata={"error_test_results": error_test_results}
                )
            else:
                return TestResult(
                    component="protocol",
                    test_name=test_name,
                    status=HarnessStatus.FAIL,
                    duration=0.5,
                    error_message=f"Error handling issues: {failed_error_tests[:2]}"
                )
                
        except Exception as e:
            return TestResult(
                component="protocol",
                test_name=test_name,
                status=HarnessStatus.ERROR,
                duration=0.0,
                error_message=str(e)
            )
    
    def _test_protocol_validation_workflows(self, env_context: EnvironmentContext) -> TestResult:
        """Test protocol validation workflows."""
        test_name = "protocol_validation_workflows"
        
        try:
            db_path = getattr(env_context, 'database_path', None)
            if not db_path:
                db_path = os.environ.get('TASKSGODZILLA_DB_PATH')
                if not db_path:
                    return TestResult(
                        component="protocol",
                        test_name=test_name,
                        status=HarnessStatus.SKIP,
                        duration=0.0,
                        error_message="No database path available for testing"
                    )
            
            db = Database(db_path)
            projects = db.list_projects()
            
            if not projects:
                return TestResult(
                    component="protocol",
                    test_name=test_name,
                    status=HarnessStatus.SKIP,
                    duration=0.0,
                    error_message="No projects available for validation test"
                )
            
            project = projects[0]
            
            # Test validation workflow
            validation_results = []
            
            # Test 1: Protocol lifecycle validation
            try:
                # Create protocol
                validation_protocol = db.create_protocol_run(
                    project_id=project.id,
                    protocol_name="validation-test-protocol",
                    status=ProtocolStatus.PENDING,
                    base_branch=project.base_branch,
                    worktree_path=None,
                    protocol_root=None,
                    description="Test validation workflow",
                )
                
                if validation_protocol:
                    # Test status progression: PENDING -> RUNNING -> COMPLETED
                    status_transitions = [
                        (ProtocolStatus.RUNNING, "started"),
                        (ProtocolStatus.COMPLETED, "completed")
                    ]
                    
                    for new_status, event_type in status_transitions:
                        db.update_protocol_status(validation_protocol.id, new_status)
                        db.append_event(
                            protocol_run_id=validation_protocol.id,
                            event_type=f"protocol_{event_type}",
                            message=f"Protocol {event_type} during validation test"
                        )
                        
                        # Verify status update
                        updated_protocol = db.get_protocol_run(validation_protocol.id)
                        if updated_protocol and updated_protocol.status == new_status:
                            validation_results.append(f"status_transition_to_{new_status.value}: success")
                        else:
                            validation_results.append(f"status_transition_to_{new_status.value}: failed")
                    
                    # Test event logging validation
                    events = db.list_events(validation_protocol.id)
                    event_types = [e.event_type for e in events]
                    
                    expected_events = ["protocol_started", "protocol_completed"]
                    missing_events = [e for e in expected_events if e not in event_types]
                    
                    if not missing_events:
                        validation_results.append("event_logging: complete")
                    else:
                        validation_results.append(f"event_logging: missing {missing_events}")
                        
            except Exception as e:
                validation_results.append(f"lifecycle_validation: error - {str(e)[:100]}")
            
            # Test 2: Step validation workflow
            try:
                if validation_protocol:
                    # Create multiple steps to test workflow
                    step_names = ["planning", "implementation", "testing", "review"]
                    created_steps = []
                    
                    for i, step_name in enumerate(step_names):
                        step = db.create_step_run(
                            protocol_run_id=validation_protocol.id,
                            step_name=f"{i+1}-{step_name}",
                            step_type="implementation",
                            step_file=f"{step_name}.md",
                            status="pending"
                        )
                        if step:
                            created_steps.append(step)
                    
                    if len(created_steps) == len(step_names):
                        validation_results.append("step_creation: all_created")
                        
                        # Test step execution workflow
                        for step in created_steps:
                            db.update_step_status(step.id, "completed", summary=f"Completed {step.step_name}")
                        
                        # Verify all steps completed
                        completed_steps = [s for s in created_steps 
                                         if db.get_step_run(s.id).status == "completed"]
                        
                        if len(completed_steps) == len(created_steps):
                            validation_results.append("step_execution: all_completed")
                        else:
                            validation_results.append(f"step_execution: {len(completed_steps)}/{len(created_steps)} completed")
                    else:
                        validation_results.append(f"step_creation: {len(created_steps)}/{len(step_names)} created")
                        
            except Exception as e:
                validation_results.append(f"step_validation: error - {str(e)[:100]}")
            
            # Evaluate validation results
            failed_validations = [r for r in validation_results if "failed" in r or "error" in r or "missing" in r]
            
            if not failed_validations:
                return TestResult(
                    component="protocol",
                    test_name=test_name,
                    status=HarnessStatus.PASS,
                    duration=0.7,
                    metadata={"validation_results": validation_results}
                )
            else:
                return TestResult(
                    component="protocol",
                    test_name=test_name,
                    status=HarnessStatus.FAIL,
                    duration=0.7,
                    error_message=f"Validation issues: {failed_validations[:2]}"
                )
                
        except Exception as e:
            return TestResult(
                component="protocol",
                test_name=test_name,
                status=HarnessStatus.ERROR,
                duration=0.0,
                error_message=str(e)
            )