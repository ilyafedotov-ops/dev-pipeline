from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from tasksgodzilla.logging import get_logger
from tasksgodzilla.storage import BaseDatabase
from tasksgodzilla.domain import ProtocolRun, ProtocolStatus, StepRun, StepStatus
from tasksgodzilla.jobs import BaseQueue, Job, RedisQueue
from tasksgodzilla.config import load_config

log = get_logger(__name__)

MAX_INLINE_TRIGGER_DEPTH = 3


@dataclass
class OrchestratorService:
    """Service for high-level protocol and step orchestration.
    
    This service manages the complete lifecycle of protocol runs and step executions,
    including state transitions, policy evaluation, and completion handling.
    
    Responsibilities:
    - Create and manage protocol runs
    - Transition protocols through lifecycle states (PENDING → PLANNING → RUNNING → COMPLETED)
    - Enqueue and manage step execution jobs
    - Apply trigger policies to start dependent steps
    - Apply loop policies to retry failed steps
    - Handle step completion and determine next actions
    - Check and mark protocol completion
    - Manage protocol pause/resume/cancel operations
    - Coordinate PR/MR creation for protocols
    
    Protocol Lifecycle:
    PENDING → PLANNING → RUNNING → COMPLETED/FAILED/BLOCKED/CANCELLED
    
    Step Lifecycle:
    PENDING → RUNNING → NEEDS_QA → COMPLETED/FAILED/BLOCKED/CANCELLED
    
    Policy System:
    - Trigger policies: Automatically start dependent steps when conditions are met
    - Loop policies: Retry steps when failures occur within iteration limits
    - Inline triggers: Execute steps immediately when depth limit not exceeded
    
    Usage:
        orchestrator = OrchestratorService(db)
        
        # Create and start protocol
        run = orchestrator.create_protocol_run(
            project_id=1,
            protocol_name="feature-123",
            status="pending",
            base_branch="main"
        )
        job = orchestrator.start_protocol_run(run.id, queue)
        
        # Enqueue next step
        step, job = orchestrator.enqueue_next_step(run.id, queue)
        
        # Handle step completion with policies
        orchestrator.handle_step_completion(
            step_run_id=step.id,
            qa_verdict="PASS"
        )
        
        # Check if protocol is complete
        completed = orchestrator.check_and_complete_protocol(run.id)
    """

    db: BaseDatabase

    def create_protocol_run(
        self,
        project_id: int,
        protocol_name: str,
        status: str,
        base_branch: str,
        *,
        worktree_path: Optional[str] = None,
        protocol_root: Optional[str] = None,
        description: Optional[str] = None,
        template_config: Optional[dict] = None,
        template_source: Optional[dict] = None,
    ) -> ProtocolRun:
        """Create a new ProtocolRun row.

        This is a thin wrapper over `BaseDatabase.create_protocol_run` so that
        API/CLI layers can depend on the orchestrator service instead of the DB
        interface directly.
        """
        run = self.db.create_protocol_run(
            project_id=project_id,
            protocol_name=protocol_name,
            status=status,
            base_branch=base_branch,
            worktree_path=worktree_path,
            protocol_root=protocol_root,
            description=description,
            template_config=template_config,
            template_source=template_source,
        )
        log.info(
            "orchestrator_protocol_created",
            extra={"protocol_run_id": run.id, "project_id": project_id, "protocol_name": protocol_name},
        )
        return run

    def start_protocol_run(self, protocol_run_id: int, queue: BaseQueue) -> Job:
        """Transition a protocol to PLANNING and enqueue the planning job.

        Raises ValueError when the protocol is not a state that can be started.
        """
        run = self.db.get_protocol_run(protocol_run_id)
        if run.status not in (ProtocolStatus.PENDING, ProtocolStatus.PLANNED, ProtocolStatus.PAUSED):
            raise ValueError("Protocol already running or terminal")
        self.db.update_protocol_status(protocol_run_id, ProtocolStatus.PLANNING, expected_status=run.status)
        job = queue.enqueue("plan_protocol_job", {"protocol_run_id": protocol_run_id})
        log.info(
            "orchestrator_plan_enqueued",
            extra={"protocol_run_id": protocol_run_id, "job_id": job.job_id},
        )
        return job

    def enqueue_next_step(self, protocol_run_id: int, queue: BaseQueue) -> Tuple[StepRun, Job]:
        """Select the next runnable step, mark it running, and enqueue execution.

        Returns the updated StepRun and Job. Raises LookupError when no suitable
        step exists, and ValueError when the step state changes concurrently.
        """
        steps = self.db.list_step_runs(protocol_run_id)
        target = next(
            (s for s in steps if s.status in (StepStatus.PENDING, StepStatus.BLOCKED, StepStatus.FAILED)),
            None,
        )
        if not target:
            raise LookupError("No pending or failed steps to run")
        step = self.db.update_step_status(target.id, StepStatus.RUNNING, expected_status=target.status)
        self.db.update_protocol_status(protocol_run_id, ProtocolStatus.RUNNING)
        job = queue.enqueue("execute_step_job", {"step_run_id": step.id})
        log.info(
            "orchestrator_step_enqueued",
            extra={"protocol_run_id": protocol_run_id, "step_run_id": step.id, "job_id": job.job_id},
        )
        return step, job

    def retry_latest_step(self, protocol_run_id: int, queue: BaseQueue) -> Tuple[StepRun, Job]:
        """Retry the most recent failed or blocked step and enqueue execution.

        Returns the updated StepRun and Job. Raises LookupError when no suitable
        step exists, and ValueError when the step state changes concurrently.
        """
        steps = self.db.list_step_runs(protocol_run_id)
        target = next(
            (s for s in reversed(steps) if s.status in (StepStatus.FAILED, StepStatus.BLOCKED)),
            None,
        )
        if not target:
            raise LookupError("No failed or blocked steps to retry")
        step = self.db.update_step_status(
            target.id,
            StepStatus.RUNNING,
            retries=target.retries + 1,
            expected_status=target.status,
        )
        self.db.update_protocol_status(protocol_run_id, ProtocolStatus.RUNNING)
        job = queue.enqueue("execute_step_job", {"step_run_id": step.id})
        log.info(
            "orchestrator_step_retry_enqueued",
            extra={"protocol_run_id": protocol_run_id, "step_run_id": step.id, "job_id": job.job_id, "retries": step.retries},
        )
        return step, job

    def plan_protocol(self, protocol_run_id: int, job_id: Optional[str] = None) -> None:
        """Plan a protocol run by delegating to the Codex worker."""
        from tasksgodzilla.workers.codex_worker import handle_plan_protocol
        log.info("orchestrator_plan_protocol", extra={"protocol_run_id": protocol_run_id, "job_id": job_id})
        handle_plan_protocol(protocol_run_id, self.db, job_id=job_id)

    def execute_step(self, step_run_id: int, job_id: Optional[str] = None) -> None:
        """Execute a single step via the existing worker implementation."""
        from tasksgodzilla.workers.codex_worker import handle_execute_step
        log.info("orchestrator_execute_step", extra={"step_run_id": step_run_id, "job_id": job_id})
        handle_execute_step(step_run_id, self.db, job_id=job_id)

    def run_step(self, step_run_id: int, queue: BaseQueue) -> Job:
        """Transition a step to RUNNING and enqueue execution."""
        step = self.db.get_step_run(step_run_id)
        if step.status not in (StepStatus.PENDING, StepStatus.BLOCKED, StepStatus.FAILED):
            raise ValueError("Step already running or completed")
        step = self.db.update_step_status(step.id, StepStatus.RUNNING, expected_status=step.status)
        self.db.update_protocol_status(step.protocol_run_id, ProtocolStatus.RUNNING)
        job = queue.enqueue("execute_step_job", {"step_run_id": step.id})
        log.info(
            "orchestrator_step_run_enqueued",
            extra={"protocol_run_id": step.protocol_run_id, "step_run_id": step.id, "job_id": job.job_id},
        )
        return job

    def run_step_qa(self, step_run_id: int, queue: BaseQueue) -> Job:
        """Transition a step to NEEDS_QA and enqueue a QA job."""
        step = self.db.get_step_run(step_run_id)
        if step.status in (StepStatus.COMPLETED, StepStatus.CANCELLED):
            raise ValueError("Step already completed or cancelled")
        step = self.db.update_step_status(step.id, StepStatus.NEEDS_QA, expected_status=step.status)
        job = queue.enqueue("run_quality_job", {"step_run_id": step.id})
        log.info(
            "orchestrator_step_qa_enqueued",
            extra={"protocol_run_id": step.protocol_run_id, "step_run_id": step.id, "job_id": job.job_id},
        )
        return job

    def pause_protocol(self, protocol_run_id: int) -> ProtocolRun:
        """Pause a protocol run when it is not terminal."""
        run = self.db.get_protocol_run(protocol_run_id)
        if run.status in (ProtocolStatus.CANCELLED, ProtocolStatus.COMPLETED, ProtocolStatus.FAILED):
            raise ValueError("Protocol already terminal")
        return self.db.update_protocol_status(protocol_run_id, ProtocolStatus.PAUSED, expected_status=run.status)

    def resume_protocol(self, protocol_run_id: int) -> ProtocolRun:
        """Resume a paused protocol run."""
        run = self.db.get_protocol_run(protocol_run_id)
        if run.status != ProtocolStatus.PAUSED:
            raise ValueError("Protocol is not paused")
        return self.db.update_protocol_status(protocol_run_id, ProtocolStatus.RUNNING, expected_status=run.status)

    def cancel_protocol(self, protocol_run_id: int) -> ProtocolRun:
        """Cancel a protocol and mark in-flight steps as cancelled when appropriate."""
        run = self.db.get_protocol_run(protocol_run_id)
        if run.status == ProtocolStatus.CANCELLED:
            return run
        updated = self.db.update_protocol_status(protocol_run_id, ProtocolStatus.CANCELLED, expected_status=run.status)
        steps = self.db.list_step_runs(protocol_run_id)
        for step in steps:
            if step.status in (StepStatus.PENDING, StepStatus.RUNNING, StepStatus.NEEDS_QA):
                try:
                    self.db.update_step_status(
                        step.id,
                        StepStatus.CANCELLED,
                        summary="Cancelled with protocol",
                        expected_status=step.status,
                    )
                except Exception:
                    continue
        return updated

    def open_protocol_pr(self, protocol_run_id: int, job_id: Optional[str] = None) -> None:
        """Open PR/MR for a protocol using the existing worker implementation."""
        from tasksgodzilla.workers.codex_worker import handle_open_pr
        handle_open_pr(protocol_run_id, self.db, job_id=job_id)

    def enqueue_open_protocol_pr(self, protocol_run_id: int, queue: BaseQueue) -> Job:
        """Enqueue an open_pr job for the protocol."""
        job = queue.enqueue("open_pr_job", {"protocol_run_id": protocol_run_id})
        log.info(
            "orchestrator_open_pr_enqueued",
            extra={"protocol_run_id": protocol_run_id, "job_id": job.job_id},
        )
        return job

    def sync_steps_from_protocol(self, protocol_run_id: int, protocol_root: Path) -> int:
        """Ensure StepRun rows exist for each protocol step file."""
        from tasksgodzilla.services.spec import SpecService
        spec_service = SpecService(self.db)
        return spec_service.sync_step_runs_from_protocol(protocol_root, protocol_run_id)

    def check_and_complete_protocol(self, protocol_run_id: int) -> bool:
        """Mark protocol as completed if all steps are in terminal state.
        
        Returns True if the protocol was transitioned to completed.
        """
        run = self.db.get_protocol_run(protocol_run_id)
        if run.status in (ProtocolStatus.COMPLETED, ProtocolStatus.CANCELLED, ProtocolStatus.FAILED, ProtocolStatus.BLOCKED):
            return False

        steps = self.db.list_step_runs(protocol_run_id)
        if not steps:
            return False

        terminal = {StepStatus.COMPLETED, StepStatus.CANCELLED}
        if any(step.status not in terminal for step in steps):
            return False

        self.db.update_protocol_status(protocol_run_id, ProtocolStatus.COMPLETED)
        self.db.append_event(protocol_run_id, "protocol_completed", "All steps completed; protocol closed.")
        log.info("protocol_completed", extra={"protocol_run_id": run.id, "project_id": run.project_id})
        return True

    def apply_trigger_policy(
        self,
        step: StepRun,
        reason: str = "qa_passed",
        inline_depth: int = 0
    ) -> Optional[dict]:
        """Apply trigger policies to a step and enqueue target steps.
        
        Evaluates trigger policies attached to the step and triggers target steps
        based on policy configuration. Handles inline vs queued triggers and enforces
        MAX_INLINE_TRIGGER_DEPTH.
        
        Args:
            step: The step run to evaluate policies for
            reason: The reason for triggering (e.g., "qa_passed", "exec_completed")
            inline_depth: Current inline trigger depth for recursion control
            
        Returns:
            Dict with trigger details if a policy was applied, None otherwise
        """
        from tasksgodzilla.codemachine.policy_runtime import apply_trigger_policies
        
        trigger_decision = apply_trigger_policies(step, self.db, reason=reason)
        if not trigger_decision or not trigger_decision.get("applied"):
            return None
            
        target_step_id = trigger_decision.get("target_step_id")
        if not target_step_id:
            return trigger_decision
            
        # Trigger the target step
        self.trigger_step(
            target_step_id,
            step.protocol_run_id,
            source=reason,
            inline_depth=inline_depth
        )
        
        return trigger_decision

    def apply_loop_policy(
        self,
        step: StepRun,
        reason: str = "qa_failed"
    ) -> Optional[dict]:
        """Apply loop policies to a step and reset step status when conditions are met.
        
        Evaluates loop policies attached to the step and resets target steps to PENDING
        when loop conditions are met. Updates runtime_state with loop counts and enforces
        max_iterations limits.
        
        Args:
            step: The step run to evaluate policies for
            reason: The reason for looping (e.g., "qa_failed", "exec_failed")
            
        Returns:
            Dict with loop details if a policy was applied, None otherwise
        """
        from tasksgodzilla.codemachine.policy_runtime import apply_loop_policies
        
        return apply_loop_policies(step, self.db, reason=reason)

    def handle_step_completion(
        self,
        step_run_id: int,
        qa_verdict: Optional[str] = None
    ) -> None:
        """Handle step completion workflow including policies and protocol completion.
        
        Applies trigger and loop policies based on the step outcome, checks if the
        protocol is complete, and updates statuses appropriately.
        
        Args:
            step_run_id: The ID of the step that completed
            qa_verdict: Optional QA verdict ("PASS" or "FAIL")
        """
        step = self.db.get_step_run(step_run_id)
        
        # Determine the reason based on step status and QA verdict
        if qa_verdict == "FAIL" or step.status == StepStatus.FAILED:
            reason = "qa_failed" if qa_verdict == "FAIL" else "exec_failed"
            
            # Apply loop policy for failures
            loop_decision = self.apply_loop_policy(step, reason=reason)
            if loop_decision and loop_decision.get("applied"):
                self.db.update_protocol_status(step.protocol_run_id, ProtocolStatus.RUNNING)
                return
                
            # Apply trigger policy even on failure
            trigger_decision = self.apply_trigger_policy(step, reason=reason)
            if trigger_decision and trigger_decision.get("applied"):
                self.db.update_protocol_status(step.protocol_run_id, ProtocolStatus.RUNNING)
            else:
                self.db.update_protocol_status(step.protocol_run_id, ProtocolStatus.BLOCKED)
                
        elif qa_verdict == "PASS" or step.status == StepStatus.COMPLETED:
            reason = "qa_passed" if qa_verdict == "PASS" else "exec_completed"
            
            # Apply trigger policy for success
            trigger_decision = self.apply_trigger_policy(step, reason=reason)
            if trigger_decision and trigger_decision.get("applied"):
                self.db.update_protocol_status(step.protocol_run_id, ProtocolStatus.RUNNING)
                
            # Check if protocol is complete
            self.check_and_complete_protocol(step.protocol_run_id)
            
        elif step.status == StepStatus.NEEDS_QA:
            # Step completed execution but needs QA
            reason = "exec_completed"
            trigger_decision = self.apply_trigger_policy(step, reason=reason)
            if trigger_decision and trigger_decision.get("applied"):
                self.db.update_protocol_status(step.protocol_run_id, ProtocolStatus.RUNNING)

    def trigger_step(
        self,
        step_run_id: int,
        protocol_run_id: int,
        source: str,
        inline_depth: int = 0
    ) -> Optional[dict]:
        """Trigger execution of a step, either via queue or inline fallback."""
        from tasksgodzilla.workers.codex_worker import handle_execute_step
        from tasksgodzilla.spec import get_step_spec

        config = load_config()
        if inline_depth >= MAX_INLINE_TRIGGER_DEPTH:
            self.db.append_event(
                protocol_run_id,
                "trigger_inline_depth_exceeded",
                f"Inline trigger depth exceeded ({inline_depth}/{MAX_INLINE_TRIGGER_DEPTH}).",
                step_run_id=step_run_id,
                metadata={"target_step_id": step_run_id, "source": source, "inline_depth": inline_depth},
            )
            return None

        queue = None
        if config.redis_url:
            try:
                queue = RedisQueue(config.redis_url)
                job = queue.enqueue("execute_step_job", {"step_run_id": step_run_id})
                self.db.append_event(
                    protocol_run_id,
                    "trigger_enqueued",
                    "Triggered step enqueued for execution.",
                    step_run_id=step_run_id,
                    metadata={"job_id": job.job_id, "target_step_id": step_run_id, "source": source, "inline_depth": inline_depth},
                )
                return job.asdict()
            except Exception as exc:  # pragma: no cover - best effort
                self.db.append_event(
                    protocol_run_id,
                    "trigger_enqueue_failed",
                    f"Failed to enqueue triggered step: {exc}",
                    step_run_id=step_run_id,
                    metadata={"target_step_id": step_run_id, "source": source, "inline_depth": inline_depth},
                )
                return None

        target: Optional[StepRun] = None
        target_qa_skip = False
        try:
            target = self.db.get_step_run(step_run_id)
            try:
                run = self.db.get_protocol_run(protocol_run_id)
                target_spec = get_step_spec(run.template_config, target.step_name) or {}
                target_qa_skip = (target_spec.get("qa") or {}).get("policy") == "skip"
            except Exception:
                target_qa_skip = False
        except Exception:
            target = None

        if queue is None and target_qa_skip:
            self.db.append_event(
                protocol_run_id,
                "trigger_pending",
                "Triggered step pending; no queue configured.",
                step_run_id=step_run_id,
                metadata={"target_step_id": step_run_id, "source": source, "inline_depth": inline_depth},
            )
            return None

        # Inline fallback for dev/local without Redis.
        try:
            target = target or self.db.get_step_run(step_run_id)
            merged_state = dict(target.runtime_state or {})
            merged_state["inline_trigger_depth"] = inline_depth
            self.db.update_step_status(step_run_id, StepStatus.RUNNING, summary="Triggered (inline)", runtime_state=merged_state)
            self.db.append_event(
                protocol_run_id,
                "trigger_executed_inline",
                "Triggered step executed inline (no queue configured).",
                step_run_id=step_run_id,
                metadata={"target_step_id": step_run_id, "source": source, "inline_depth": inline_depth},
            )
            handle_execute_step(step_run_id, self.db)
            return {"inline": True, "target_step_id": step_run_id}
        except Exception as exc:  # pragma: no cover - best effort
            self.db.append_event(
                protocol_run_id,
                "trigger_inline_failed",
                f"Inline trigger failed: {exc}",
                step_run_id=step_run_id,
                metadata={"target_step_id": step_run_id, "source": source, "inline_depth": inline_depth},
            )
            try:
                self.db.update_step_status(step_run_id, StepStatus.FAILED, summary=f"Trigger inline failed: {exc}")
            except Exception:
                pass
            return None

