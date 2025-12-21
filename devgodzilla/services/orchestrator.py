"""
DevGodzilla Orchestrator Service

High-level protocol and step orchestration.
Manages lifecycle of protocol runs and coordinates with Windmill for execution.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from devgodzilla.logging import get_logger
from devgodzilla.models.domain import (
    ProtocolRun,
    ProtocolStatus,
    StepRun,
    StepStatus,
)
from devgodzilla.services.base import Service, ServiceContext
from devgodzilla.services.events import get_event_bus, ProtocolStarted, ProtocolCompleted, StepStarted, StepCompleted
from devgodzilla.windmill.client import WindmillClient, JobStatus
from devgodzilla.windmill.flow_generator import DAGBuilder, FlowGenerator

logger = get_logger(__name__)


class OrchestratorMode(str, Enum):
    """Orchestrator execution mode."""
    WINDMILL = "windmill"  # Use Windmill for job execution
    LOCAL = "local"        # Run jobs in-process (for testing)


@dataclass
class OrchestratorResult:
    """Result from an orchestrator operation."""
    success: bool
    message: Optional[str] = None
    job_id: Optional[str] = None
    flow_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class OrchestratorService(Service):
    """
    Service for high-level protocol and step orchestration.
    
    Manages the complete lifecycle of protocol runs:
    - Creating and starting protocols
    - Converting task DAGs to Windmill flows
    - Tracking step execution status
    - Handling pauses, resumes, and cancellations
    
    Example:
        orchestrator = OrchestratorService(context, db, windmill_client)
        
        # Create and start a protocol
        run = orchestrator.create_protocol_run(project_id=1, protocol_name="feature-auth")
        result = orchestrator.start_protocol_run(run.id)
        
        # Check status
        status = orchestrator.get_protocol_status(run.id)
    """

    def __init__(
        self,
        context: ServiceContext,
        db,
        windmill_client: Optional[WindmillClient] = None,
        *,
        mode: OrchestratorMode = OrchestratorMode.WINDMILL,
        planning_service=None,
        execution_service=None,
        quality_service=None,
        git_service=None,
    ) -> None:
        super().__init__(context)
        self.db = db
        self.windmill = windmill_client
        self.mode = mode
        self.planning_service = planning_service
        self.execution_service = execution_service
        self.quality_service = quality_service
        self.git_service = git_service
        self._flow_generator = FlowGenerator()
        self._dag_builder = DAGBuilder()

    # Protocol Lifecycle
    def create_protocol_run(
        self,
        project_id: int,
        protocol_name: str,
        *,
        base_branch: Optional[str] = None,
        worktree_path: Optional[str] = None,
        protocol_root: Optional[str] = None,
        description: Optional[str] = None,
        template_config: Optional[dict] = None,
    ) -> ProtocolRun:
        """
        Create a new protocol run.
        
        Args:
            project_id: Project ID
            protocol_name: Name of the protocol
            base_branch: Base branch (defaults to project default)
            worktree_path: Optional worktree path
            protocol_root: Optional protocol root directory
            description: Optional description
            template_config: Optional template configuration
            
        Returns:
            Created ProtocolRun
        """
        project = self.db.get_project(project_id)
        branch = base_branch or project.base_branch
        
        run = self.db.create_protocol_run(
            project_id=project_id,
            protocol_name=protocol_name,
            status=ProtocolStatus.PENDING,
            base_branch=branch,
            worktree_path=worktree_path,
            protocol_root=protocol_root,
            description=description,
        )
        
        if template_config:
            self.db.update_protocol_template(run.id, template_config=template_config)
            run = self.db.get_protocol_run(run.id)
        
        self.logger.info(
            "protocol_run_created",
            extra=self.log_extra(
                protocol_run_id=run.id,
                project_id=project_id,
                protocol_name=protocol_name,
            ),
        )
        
        return run

    def start_protocol_run(self, protocol_run_id: int) -> OrchestratorResult:
        """
        Start a protocol run.
        
        Transitions to PLANNING and triggers the planning phase.
        
        Args:
            protocol_run_id: Protocol run ID
            
        Returns:
            OrchestratorResult with job/flow details
        """
        run = self.db.get_protocol_run(protocol_run_id)
        
        if run.status not in (ProtocolStatus.PENDING, ProtocolStatus.PAUSED):
            return OrchestratorResult(
                success=False,
                error=f"Cannot start protocol in status {run.status}",
            )
        
        # Update status
        self.db.update_protocol_status(protocol_run_id, ProtocolStatus.PLANNING)
        
        # Emit event
        event_bus = get_event_bus()
        event_bus.publish(ProtocolStarted(
            protocol_run_id=protocol_run_id,
            protocol_name=run.protocol_name,
        ))
        
        self.logger.info(
            "protocol_run_started",
            extra=self.log_extra(protocol_run_id=protocol_run_id),
        )
        
        # Trigger planning
        if self.mode == OrchestratorMode.WINDMILL and self.windmill:
            job_id = self.windmill.run_script(
                "u/devgodzilla/protocol_plan_and_wait",
                {"protocol_run_id": protocol_run_id},
            )
            try:
                self.db.create_job_run(
                    run_id=str(uuid.uuid4()),
                    job_type="protocol_plan_and_wait",
                    status="queued",
                    project_id=run.project_id,
                    protocol_run_id=protocol_run_id,
                    windmill_job_id=job_id,
                )
            except Exception as exc:
                self.logger.error(
                    "job_run_persist_failed",
                    extra=self.log_extra(
                        protocol_run_id=protocol_run_id,
                        job_type="protocol_plan_and_wait",
                        job_id=job_id,
                        error=str(exc),
                    ),
                )
            return OrchestratorResult(success=True, job_id=job_id)
        elif self.planning_service:
            # Local mode - run planning directly
            result = self.planning_service.plan_protocol(protocol_run_id)
            return OrchestratorResult(
                success=result.success,
                error=result.error,
            )
        
        return OrchestratorResult(success=True)

    def create_flow_from_steps(self, protocol_run_id: int) -> OrchestratorResult:
        """
        Create a Windmill flow from protocol steps.
        
        Converts step runs to a DAG and generates a Windmill flow definition.
        
        Args:
            protocol_run_id: Protocol run ID
            
        Returns:
            OrchestratorResult with flow_id
        """
        if not self.windmill:
            return OrchestratorResult(
                success=False,
                error="Windmill client not configured",
            )
        
        run = self.db.get_protocol_run(protocol_run_id)
        steps = self.db.list_step_runs(protocol_run_id)
        
        if not steps:
            return OrchestratorResult(
                success=False,
                error="No steps found for protocol",
            )
        
        # Build DAG
        step_data = [
            {
                "id": s.id,
                "step_name": s.step_name,
                "description": s.step_name,
                "depends_on": s.depends_on,
                "assigned_agent": s.assigned_agent,
                "parallel": True,
            }
            for s in steps
        ]
        dag = self._dag_builder.build_from_steps(step_data)
        
        # Check for cycles
        cycles = self._dag_builder.detect_cycles(dag)
        if cycles:
            return OrchestratorResult(
                success=False,
                error=f"Cycle detected in task dependencies: {cycles[0]}",
            )
        
        # Generate flow
        flow_def = self._flow_generator.generate(dag, protocol_run_id)
        
        # Create flow in Windmill
        flow_path = f"f/devgodzilla/protocol-{protocol_run_id}"
        self.windmill.create_flow(
            flow_path,
            flow_def,
            summary=f"Protocol {run.protocol_name}",
            description=run.description or "",
        )
        
        # Store flow ID
        self.db.update_protocol_windmill(protocol_run_id, windmill_flow_id=flow_path)
        
        self.logger.info(
            "flow_created",
            extra=self.log_extra(protocol_run_id=protocol_run_id, flow_path=flow_path),
        )
        
        return OrchestratorResult(success=True, flow_id=flow_path, data={"flow_definition": flow_def})

    def run_protocol_flow(self, protocol_run_id: int) -> OrchestratorResult:
        """
        Run the Windmill flow for a protocol.
        
        Args:
            protocol_run_id: Protocol run ID
            
        Returns:
            OrchestratorResult with job_id
        """
        if not self.windmill:
            return OrchestratorResult(
                success=False,
                error="Windmill client not configured",
            )
        
        run = self.db.get_protocol_run(protocol_run_id)
        if not run.windmill_flow_id:
            return OrchestratorResult(
                success=False,
                error="No Windmill flow created for protocol",
            )
        
        # Update status
        self.db.update_protocol_status(protocol_run_id, ProtocolStatus.RUNNING)
        
        # Run flow
        job_id = self.windmill.run_flow(
            run.windmill_flow_id,
            {"protocol_run_id": protocol_run_id},
        )
        try:
            self.db.create_job_run(
                run_id=str(uuid.uuid4()),
                job_type="run_flow",
                status="queued",
                project_id=run.project_id,
                protocol_run_id=protocol_run_id,
                windmill_job_id=job_id,
                params={"flow_id": run.windmill_flow_id},
            )
        except Exception as exc:
            self.logger.error(
                "job_run_persist_failed",
                extra=self.log_extra(
                    protocol_run_id=protocol_run_id,
                    job_type="run_flow",
                    job_id=job_id,
                    error=str(exc),
                ),
            )
        
        self.logger.info(
            "protocol_flow_started",
            extra=self.log_extra(
                protocol_run_id=protocol_run_id,
                flow_id=run.windmill_flow_id,
                job_id=job_id,
            ),
        )
        
        return OrchestratorResult(success=True, job_id=job_id, flow_id=run.windmill_flow_id)

    # Step Operations
    def run_step(self, step_run_id: int) -> OrchestratorResult:
        """
        Execute a single step.
        
        Args:
            step_run_id: Step run ID
            
        Returns:
            OrchestratorResult with job_id
        """
        step = self.db.get_step_run(step_run_id)
        
        if step.status not in (StepStatus.PENDING, StepStatus.FAILED, StepStatus.BLOCKED):
            return OrchestratorResult(
                success=False,
                error=f"Cannot run step in status {step.status}",
            )
        
        # Update status
        self.db.update_step_status(step_run_id, StepStatus.RUNNING)
        
        # Emit event
        event_bus = get_event_bus()
        event_bus.publish(StepStarted(
            step_run_id=step_run_id,
            step_name=step.step_name,
        ))
        
        if self.mode == OrchestratorMode.WINDMILL and self.windmill:
            job_id = self.windmill.run_script(
                "u/devgodzilla/step_execute_api",
                {"step_run_id": step_run_id},
            )
            try:
                self.db.create_job_run(
                    run_id=str(uuid.uuid4()),
                    job_type="execute_step",
                    status="queued",
                    project_id=self.db.get_protocol_run(step.protocol_run_id).project_id,
                    protocol_run_id=step.protocol_run_id,
                    step_run_id=step_run_id,
                    windmill_job_id=job_id,
                    params={},
                )
            except Exception as exc:
                self.logger.error(
                    "job_run_persist_failed",
                    extra=self.log_extra(
                        protocol_run_id=step.protocol_run_id,
                        step_run_id=step_run_id,
                        job_type="execute_step",
                        job_id=job_id,
                        error=str(exc),
                    ),
                )
            return OrchestratorResult(success=True, job_id=job_id)
        elif self.execution_service:
            # Local mode
            result = self.execution_service.execute_step(step_run_id)
            return OrchestratorResult(
                success=result.get("success", False),
                error=result.get("error"),
            )
        
        return OrchestratorResult(success=True)

    def run_step_qa(self, step_run_id: int) -> OrchestratorResult:
        """
        Run QA validation for a step.
        
        Args:
            step_run_id: Step run ID
            
        Returns:
            OrchestratorResult with job_id
        """
        step = self.db.get_step_run(step_run_id)
        
        # Update status
        self.db.update_step_status(step_run_id, StepStatus.NEEDS_QA)
        
        if self.mode == OrchestratorMode.WINDMILL and self.windmill:
            job_id = self.windmill.run_script(
                "u/devgodzilla/step_run_qa_api",
                {"step_run_id": step_run_id},
            )
            try:
                self.db.create_job_run(
                    run_id=str(uuid.uuid4()),
                    job_type="run_qa",
                    status="queued",
                    project_id=self.db.get_protocol_run(step.protocol_run_id).project_id,
                    protocol_run_id=step.protocol_run_id,
                    step_run_id=step_run_id,
                    windmill_job_id=job_id,
                )
            except Exception as exc:
                self.logger.error(
                    "job_run_persist_failed",
                    extra=self.log_extra(
                        protocol_run_id=step.protocol_run_id,
                        step_run_id=step_run_id,
                        job_type="run_qa",
                        job_id=job_id,
                        error=str(exc),
                    ),
                )
            return OrchestratorResult(success=True, job_id=job_id)
        elif self.quality_service:
            # Local mode
            result = self.quality_service.validate_step(step_run_id)
            return OrchestratorResult(
                success=result.passed,
                error=result.error if not result.passed else None,
            )
        
        return OrchestratorResult(success=True)

    def enqueue_next_step(self, protocol_run_id: int) -> OrchestratorResult:
        """
        Find and run the next available step.
        
        Selects a step with status PENDING whose dependencies are satisfied.
        
        Args:
            protocol_run_id: Protocol run ID
            
        Returns:
            OrchestratorResult with step details
        """
        steps = self.db.list_step_runs(protocol_run_id)
        completed_ids = {s.id for s in steps if s.status == StepStatus.COMPLETED}
        
        for step in steps:
            if step.status != StepStatus.PENDING:
                continue
            
            # Check dependencies
            deps_satisfied = all(dep in completed_ids for dep in (step.depends_on or []))
            if deps_satisfied:
                return self.run_step(step.id)

        if self.check_and_complete_protocol(protocol_run_id):
            return OrchestratorResult(
                success=True,
                message="Protocol completed",
                data={"completed": True},
            )

        return OrchestratorResult(
            success=False,
            error="No runnable steps found",
        )

    def retry_step(self, step_run_id: int) -> OrchestratorResult:
        """
        Retry a failed, blocked, or timed out step.
        
        Args:
            step_run_id: Step run ID
            
        Returns:
            OrchestratorResult
        """
        step = self.db.get_step_run(step_run_id)
        
        if step.status not in (StepStatus.FAILED, StepStatus.BLOCKED, StepStatus.TIMEOUT):
            return OrchestratorResult(
                success=False,
                error=f"Cannot retry step in status {step.status}",
            )
        
        # Increment retry count
        self.db.update_step_status(
            step_run_id,
            StepStatus.PENDING,
            retries=(step.retries or 0) + 1,
        )
        
        return self.run_step(step_run_id)

    # Protocol Control
    def pause_protocol(self, protocol_run_id: int) -> OrchestratorResult:
        """Pause a running protocol."""
        run = self.db.get_protocol_run(protocol_run_id)
        
        terminal = {ProtocolStatus.COMPLETED, ProtocolStatus.CANCELLED, ProtocolStatus.FAILED}
        if run.status in terminal:
            return OrchestratorResult(
                success=False,
                error=f"Cannot pause protocol in status {run.status}",
            )
        
        self.db.update_protocol_status(protocol_run_id, ProtocolStatus.PAUSED)
        
        self.logger.info(
            "protocol_paused",
            extra=self.log_extra(protocol_run_id=protocol_run_id),
        )
        
        return OrchestratorResult(success=True)

    def resume_protocol(self, protocol_run_id: int) -> OrchestratorResult:
        """Resume a paused protocol."""
        run = self.db.get_protocol_run(protocol_run_id)
        
        if run.status != ProtocolStatus.PAUSED:
            return OrchestratorResult(
                success=False,
                error=f"Cannot resume protocol in status {run.status}",
            )
        
        self.db.update_protocol_status(protocol_run_id, ProtocolStatus.RUNNING)
        
        self.logger.info(
            "protocol_resumed",
            extra=self.log_extra(protocol_run_id=protocol_run_id),
        )
        
        # Enqueue next step
        return self.enqueue_next_step(protocol_run_id)

    def cancel_protocol(self, protocol_run_id: int) -> OrchestratorResult:
        """Cancel a protocol and mark in-flight steps as cancelled."""
        run = self.db.get_protocol_run(protocol_run_id)
        
        terminal = {ProtocolStatus.COMPLETED, ProtocolStatus.CANCELLED, ProtocolStatus.FAILED}
        if run.status in terminal:
            return OrchestratorResult(
                success=False,
                error=f"Cannot cancel protocol in status {run.status}",
            )
        
        # Cancel running steps
        steps = self.db.list_step_runs(protocol_run_id)
        for step in steps:
            if step.status == StepStatus.RUNNING:
                self.db.update_step_status(step.id, StepStatus.CANCELLED)
        
        self.db.update_protocol_status(protocol_run_id, ProtocolStatus.CANCELLED)
        
        # Emit event - cancellation is not a failure, just a completion
        event_bus = get_event_bus()
        event_bus.publish(ProtocolCompleted(
            protocol_run_id=protocol_run_id,
        ))

        self.logger.info(
            "protocol_cancelled",
            extra=self.log_extra(protocol_run_id=protocol_run_id),
        )

        return OrchestratorResult(success=True)

    def check_and_complete_protocol(self, protocol_run_id: int) -> bool:
        """
        Check if all steps are complete and mark protocol as completed.
        
        Returns True if protocol was transitioned to completed.
        """
        steps = self.db.list_step_runs(protocol_run_id)
        
        if not steps:
            return False
        
        terminal = {StepStatus.COMPLETED, StepStatus.CANCELLED, StepStatus.SKIPPED, StepStatus.FAILED, StepStatus.TIMEOUT}
        all_terminal = all(s.status in terminal for s in steps)
        
        if not all_terminal:
            return False
        
        # Check if any failed
        any_failed = any(s.status == StepStatus.FAILED for s in steps)
        
        new_status = ProtocolStatus.FAILED if any_failed else ProtocolStatus.COMPLETED
        self.db.update_protocol_status(protocol_run_id, new_status)
        
        # Emit appropriate event
        event_bus = get_event_bus()
        if any_failed:
            from devgodzilla.services.events import ProtocolFailed
            event_bus.publish(ProtocolFailed(
                protocol_run_id=protocol_run_id,
                error="One or more steps failed",
            ))
        else:
            event_bus.publish(ProtocolCompleted(
                protocol_run_id=protocol_run_id,
            ))

        self.logger.info(
            "protocol_completed",
            extra=self.log_extra(
                protocol_run_id=protocol_run_id,
                status=new_status,
            ),
        )

        return True

    def _find_runnable_step(self, steps: List[StepRun]) -> Optional[StepRun]:
        completed_ids = {s.id for s in steps if s.status == StepStatus.COMPLETED}
        for step in steps:
            if step.status != StepStatus.PENDING:
                continue
            deps_satisfied = all(dep in completed_ids for dep in (step.depends_on or []))
            if deps_satisfied:
                return step
        return None

    def recover_stuck_protocols(
        self,
        *,
        limit: int = 200,
        resume: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Attempt to recover protocols stuck in RUNNING without active steps.

        This will:
        - complete protocols with all terminal steps
        - mark protocols blocked when failed/blocked steps exist
        - optionally enqueue the next runnable step
        """
        recovered: List[Dict[str, Any]] = []
        runs = self.db.list_all_protocol_runs(limit=limit)
        for run in runs:
            if run.status != ProtocolStatus.RUNNING:
                continue

            steps = self.db.list_step_runs(run.id)
            if not steps:
                continue

            in_flight = any(
                s.status in (StepStatus.RUNNING, StepStatus.NEEDS_QA)
                for s in steps
            )
            if in_flight:
                continue

            if self.check_and_complete_protocol(run.id):
                recovered.append(
                    {"protocol_run_id": run.id, "action": "completed"}
                )
                self.logger.info(
                    "protocol_recovered_completed",
                    extra=self.log_extra(protocol_run_id=run.id),
                )
                continue

            if any(
                s.status in (StepStatus.FAILED, StepStatus.TIMEOUT, StepStatus.BLOCKED)
                for s in steps
            ):
                self.db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
                recovered.append(
                    {"protocol_run_id": run.id, "action": "blocked_failed_step"}
                )
                self.logger.warning(
                    "protocol_recovered_blocked",
                    extra=self.log_extra(protocol_run_id=run.id),
                )
                continue

            runnable = self._find_runnable_step(steps)
            if runnable and resume:
                result = self.run_step(runnable.id)
                recovered.append(
                    {
                        "protocol_run_id": run.id,
                        "action": "enqueued_step",
                        "step_run_id": runnable.id,
                        "success": result.success,
                    }
                )
                self.logger.info(
                    "protocol_recovered_enqueued_step",
                    extra=self.log_extra(
                        protocol_run_id=run.id,
                        step_run_id=runnable.id,
                        success=result.success,
                        error=result.error,
                    ),
                )
                if not result.success:
                    self.db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
                continue

            self.db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
            recovered.append(
                {"protocol_run_id": run.id, "action": "blocked_no_runnable"}
            )
            self.logger.warning(
                "protocol_recovered_blocked",
                extra=self.log_extra(protocol_run_id=run.id, reason="no_runnable_steps"),
            )

        if recovered:
            self.logger.info(
                "protocol_recovery_summary",
                extra=self.log_extra(recovered_count=len(recovered)),
            )
        else:
            self.logger.info("protocol_recovery_noop", extra=self.log_extra())

        return recovered

    # PR Operations
    def open_protocol_pr(self, protocol_run_id: int) -> OrchestratorResult:
        """
        Open a PR/MR for a completed protocol.
        
        Args:
            protocol_run_id: Protocol run ID
            
        Returns:
            OrchestratorResult with PR details
        """
        if not self.git_service:
            return OrchestratorResult(
                success=False,
                error="Git service not configured",
            )
        
        run = self.db.get_protocol_run(protocol_run_id)
        project = self.db.get_project(run.project_id)

        worktree_path = run.worktree_path or project.local_path
        if not worktree_path:
            return OrchestratorResult(success=False, error="Project has no local_path/worktree_path configured")

        head_branch = self.git_service.get_branch_name(run.protocol_name)
        pr_info = self.git_service.open_pr(
            Path(worktree_path).expanduser(),
            run.protocol_name,
            run.base_branch or project.base_branch or "main",
            head_branch=head_branch,
            title=f"[DevGodzilla] {run.protocol_name}",
            description=run.description or "Automated changes from DevGodzilla",
        )
        if not pr_info.get("success"):
            return OrchestratorResult(success=False, error="Failed to open PR/MR")
        
        self.logger.info(
            "protocol_pr_opened",
            extra=self.log_extra(
                protocol_run_id=protocol_run_id,
                pr_url=pr_info.get("url"),
            ),
        )
        
        return OrchestratorResult(
            success=True,
            message=pr_info.get("url"),
        )
