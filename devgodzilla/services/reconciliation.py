"""
DevGodzilla Reconciliation Service

Synchronizes DevGodzilla DB state with Windmill job status.
Detects and resolves drift between local database state and Windmill's
actual job execution state.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from devgodzilla.logging import get_logger
from devgodzilla.models.domain import (
    ProtocolRun,
    ProtocolStatus,
    StepRun,
    StepStatus,
)
from devgodzilla.services.base import Service, ServiceContext
from devgodzilla.windmill.client import WindmillClient, JobStatus

logger = get_logger(__name__)


class ReconciliationAction(str, Enum):
    """Actions taken during reconciliation."""
    NO_CHANGE = "no_change"
    AUTO_FIXED = "auto_fixed"
    MANUAL_REQUIRED = "manual_required"
    ERROR = "error"


@dataclass
class ReconciliationDetail:
    """Details for a single reconciliation check."""
    step_run_id: int
    step_name: str
    protocol_run_id: int
    db_status: str
    windmill_status: str
    action: ReconciliationAction
    message: Optional[str] = None
    windmill_job_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ProtocolReconciliation:
    """Reconciliation result for a single protocol."""
    protocol_run_id: int
    protocol_name: str
    protocol_status: str
    steps_checked: int
    mismatches_found: int
    auto_fixed: int
    requires_manual: int
    details: List[ReconciliationDetail] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class StepReconciliation:
    """Reconciliation result for a single step."""
    step_run_id: int
    step_name: str
    protocol_run_id: int
    db_status: str
    windmill_status: str
    action: ReconciliationAction
    message: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ReconciliationReport:
    """
    Summary report of a full reconciliation run.
    
    Attributes:
        total_checked: Total number of step runs checked
        mismatches_found: Number of steps with status drift
        auto_fixed: Number of steps auto-corrected
        requires_manual: Number of steps requiring manual intervention
        details: Per-step reconciliation details
    """
    total_checked: int
    mismatches_found: int
    auto_fixed: int
    requires_manual: int
    details: List[ReconciliationDetail] = field(default_factory=list)
    protocols_checked: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_seconds: Optional[float] = None


# Terminal statuses that indicate a step/job has completed
STEP_TERMINAL_STATUSES = {
    StepStatus.COMPLETED,
    StepStatus.FAILED,
    StepStatus.CANCELLED,
    StepStatus.SKIPPED,
    StepStatus.TIMEOUT,
}

WINDMILL_TERMINAL_STATUSES = {
    JobStatus.COMPLETED,
    JobStatus.FAILED,
    JobStatus.CANCELED,
}


class ReconciliationService(Service):
    """
    Service for reconciling DevGodzilla DB state with Windmill job status.
    
    This service handles:
    - Detecting drift between DB step status and Windmill job status
    - Auto-correcting DB state when safe to do so
    - Flagging cases that require manual intervention
    - Providing audit trail of all reconciliation actions
    
    Example:
        service = ReconciliationService(context, db, windmill_client)
        report = await service.reconcile_runs()
        print(f"Checked {report.total_checked}, fixed {report.auto_fixed}")
    """

    def __init__(
        self,
        context: ServiceContext,
        db,
        windmill: Optional[WindmillClient] = None,
    ) -> None:
        super().__init__(context)
        self.db = db
        self.windmill = windmill

    async def reconcile_runs(
        self,
        *,
        protocol_run_id: Optional[int] = None,
        dry_run: bool = False,
    ) -> ReconciliationReport:
        """
        Reconcile all active step runs with Windmill job status.
        
        Args:
            protocol_run_id: Optional protocol to limit reconciliation to
            dry_run: If True, don't apply fixes, just report what would change
            
        Returns:
            ReconciliationReport with summary and details
        """
        start_time = datetime.now(timezone.utc)
        
        # Get all active (non-terminal) step runs
        active_steps = self._get_active_step_runs(protocol_run_id)
        
        details: List[ReconciliationDetail] = []
        mismatches = 0
        auto_fixed = 0
        requires_manual = 0
        
        for step in active_steps:
            detail = await self._reconcile_step(step, dry_run=dry_run)
            details.append(detail)
            
            if detail.action == ReconciliationAction.AUTO_FIXED:
                auto_fixed += 1
                mismatches += 1
            elif detail.action == ReconciliationAction.MANUAL_REQUIRED:
                requires_manual += 1
                mismatches += 1
            elif detail.action == ReconciliationAction.ERROR:
                requires_manual += 1
                mismatches += 1
        
        protocols_checked = len(set(s.protocol_run_id for s in active_steps if s.protocol_run_id))
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        
        report = ReconciliationReport(
            total_checked=len(active_steps),
            mismatches_found=mismatches,
            auto_fixed=auto_fixed,
            requires_manual=requires_manual,
            details=details,
            protocols_checked=protocols_checked,
            duration_seconds=duration,
        )
        
        self.logger.info(
            "reconciliation_completed",
            extra=self.log_extra(
                total_checked=report.total_checked,
                mismatches_found=report.mismatches_found,
                auto_fixed=report.auto_fixed,
                requires_manual=report.requires_manual,
                dry_run=dry_run,
            ),
        )
        
        return report

    async def reconcile_protocol(
        self,
        protocol_run_id: int,
        *,
        dry_run: bool = False,
    ) -> ProtocolReconciliation:
        """
        Reconcile all steps for a specific protocol.
        
        Args:
            protocol_run_id: Protocol run ID to reconcile
            dry_run: If True, don't apply fixes
            
        Returns:
            ProtocolReconciliation with per-protocol details
        """
        protocol = self.db.get_protocol_run(protocol_run_id)
        steps = self.db.list_step_runs(protocol_run_id)
        
        # Filter to active steps only
        active_steps = [s for s in steps if s.status not in STEP_TERMINAL_STATUSES]
        
        details: List[ReconciliationDetail] = []
        mismatches = 0
        auto_fixed = 0
        requires_manual = 0
        
        for step in active_steps:
            detail = await self._reconcile_step(step, dry_run=dry_run)
            details.append(detail)
            
            if detail.action == ReconciliationAction.AUTO_FIXED:
                auto_fixed += 1
                mismatches += 1
            elif detail.action in (ReconciliationAction.MANUAL_REQUIRED, ReconciliationAction.ERROR):
                requires_manual += 1
                mismatches += 1
        
        return ProtocolReconciliation(
            protocol_run_id=protocol_run_id,
            protocol_name=protocol.protocol_name,
            protocol_status=protocol.status,
            steps_checked=len(active_steps),
            mismatches_found=mismatches,
            auto_fixed=auto_fixed,
            requires_manual=requires_manual,
            details=details,
        )

    async def reconcile_step(
        self,
        step_run_id: int,
        *,
        dry_run: bool = False,
    ) -> StepReconciliation:
        """
        Reconcile a single step run with its Windmill job.
        
        Args:
            step_run_id: Step run ID to reconcile
            dry_run: If True, don't apply fixes
            
        Returns:
            StepReconciliation with details
        """
        step = self.db.get_step_run(step_run_id)
        detail = await self._reconcile_step(step, dry_run=dry_run)
        
        return StepReconciliation(
            step_run_id=step_run_id,
            step_name=step.step_name,
            protocol_run_id=step.protocol_run_id,
            db_status=detail.db_status,
            windmill_status=detail.windmill_status,
            action=detail.action,
            message=detail.message,
        )

    async def _reconcile_step(
        self,
        step: StepRun,
        *,
        dry_run: bool = False,
    ) -> ReconciliationDetail:
        """
        Internal method to reconcile a single step.
        
        Args:
            step: StepRun to reconcile
            dry_run: If True, don't apply fixes
            
        Returns:
            ReconciliationDetail with action taken
        """
        db_status = step.status
        
        if not self.windmill:
            # LOCAL mode reconciliation: check for stuck/timed-out steps
            db_status = step.status

            if db_status not in (StepStatus.RUNNING.value, "running"):
                return ReconciliationDetail(
                    step_run_id=step.id,
                    step_name=step.step_name,
                    protocol_run_id=step.protocol_run_id,
                    db_status=db_status,
                    windmill_status="local_mode",
                    action=ReconciliationAction.NO_CHANGE,
                    message="LOCAL mode: step not in running state, no action needed",
                )

            # Check if step has been running too long (>30 min)
            step_updated = getattr(step, 'updated_at', None)
            if step_updated:
                try:
                    if isinstance(step_updated, str):
                        step_updated = datetime.fromisoformat(step_updated)
                    elapsed = datetime.now(timezone.utc) - step_updated
                    timeout_minutes = 30
                    if elapsed.total_seconds() > timeout_minutes * 60:
                        if not dry_run:
                            self.db.update_step_status(step.id, StepStatus.FAILED.value)
                            try:
                                self.db.append_event(
                                    protocol_run_id=step.protocol_run_id,
                                    step_run_id=step.id,
                                    event_type="reconciliation_local_timeout",
                                    message=f"LOCAL mode: step timed out after {timeout_minutes} min, auto-fixed to failed",
                                    metadata={
                                        "previous_status": db_status,
                                        "new_status": StepStatus.FAILED.value,
                                        "mode": "local",
                                    },
                                )
                            except Exception:
                                pass
                        return ReconciliationDetail(
                            step_run_id=step.id,
                            step_name=step.step_name,
                            protocol_run_id=step.protocol_run_id,
                            db_status=db_status,
                            windmill_status="local_mode",
                            action=ReconciliationAction.AUTO_FIXED,
                            message=f"LOCAL mode: step running >{timeout_minutes} min, auto-fixed to failed",
                        )
                except Exception as exc:
                    self.logger.warning("reconciliation_local_time_parse_error", extra={"step_run_id": step.id, "error": str(exc)})

            return ReconciliationDetail(
                step_run_id=step.id,
                step_name=step.step_name,
                protocol_run_id=step.protocol_run_id,
                db_status=db_status,
                windmill_status="local_mode",
                action=ReconciliationAction.NO_CHANGE,
                message="LOCAL mode: step running normally (no timeout detected)",
            )
        
        # Find Windmill job for this step
        windmill_job_id = await self._find_windmill_job_for_step(step)
        
        if not windmill_job_id:
            # No Windmill job found - step might not have been dispatched yet
            return ReconciliationDetail(
                step_run_id=step.id,
                step_name=step.step_name,
                protocol_run_id=step.protocol_run_id,
                db_status=db_status,
                windmill_status="not_found",
                action=ReconciliationAction.NO_CHANGE,
                message="No Windmill job found for step",
            )
        
        # Query Windmill for job status
        try:
            job_info = self.windmill.get_job(windmill_job_id)
            windmill_status = job_info.status.value
        except Exception as e:
            self.logger.error(
                "reconciliation_windmill_error",
                extra=self.log_extra(
                    step_run_id=step.id,
                    windmill_job_id=windmill_job_id,
                    error=str(e),
                ),
            )
            return ReconciliationDetail(
                step_run_id=step.id,
                step_name=step.step_name,
                protocol_run_id=step.protocol_run_id,
                db_status=db_status,
                windmill_status="error",
                action=ReconciliationAction.ERROR,
                message=f"Failed to query Windmill: {e}",
                windmill_job_id=windmill_job_id,
            )
        
        # Map Windmill status to DB status
        mapped_status = self._map_windmill_status_to_step_status(job_info.status)
        
        # Check if statuses match
        if db_status == mapped_status:
            return ReconciliationDetail(
                step_run_id=step.id,
                step_name=step.step_name,
                protocol_run_id=step.protocol_run_id,
                db_status=db_status,
                windmill_status=windmill_status,
                action=ReconciliationAction.NO_CHANGE,
                windmill_job_id=windmill_job_id,
            )
        
        # Status mismatch detected
        self.logger.warning(
            "reconciliation_mismatch",
            extra=self.log_extra(
                step_run_id=step.id,
                db_status=db_status,
                windmill_status=windmill_status,
                mapped_status=mapped_status,
            ),
        )
        
        # Determine if we can auto-fix
        can_auto_fix = self._can_auto_fix(db_status, mapped_status, job_info.status)
        
        if can_auto_fix and not dry_run:
            # Apply fix
            try:
                self.db.update_step_status(step.id, mapped_status)
                
                # Log the reconciliation action
                self.db.append_event(
                    protocol_run_id=step.protocol_run_id,
                    step_run_id=step.id,
                    event_type="reconciliation_auto_fix",
                    message=f"Auto-fixed status from {db_status} to {mapped_status}",
                    metadata={
                        "windmill_job_id": windmill_job_id,
                        "windmill_status": windmill_status,
                        "previous_status": db_status,
                        "new_status": mapped_status,
                    },
                )
                
                self.logger.info(
                    "reconciliation_auto_fixed",
                    extra=self.log_extra(
                        step_run_id=step.id,
                        previous_status=db_status,
                        new_status=mapped_status,
                        windmill_job_id=windmill_job_id,
                    ),
                )
                
                return ReconciliationDetail(
                    step_run_id=step.id,
                    step_name=step.step_name,
                    protocol_run_id=step.protocol_run_id,
                    db_status=db_status,
                    windmill_status=windmill_status,
                    action=ReconciliationAction.AUTO_FIXED,
                    message=f"Updated status from {db_status} to {mapped_status}",
                    windmill_job_id=windmill_job_id,
                )
            except Exception as e:
                self.logger.error(
                    "reconciliation_fix_failed",
                    extra=self.log_extra(
                        step_run_id=step.id,
                        error=str(e),
                    ),
                )
                return ReconciliationDetail(
                    step_run_id=step.id,
                    step_name=step.step_name,
                    protocol_run_id=step.protocol_run_id,
                    db_status=db_status,
                    windmill_status=windmill_status,
                    action=ReconciliationAction.ERROR,
                    message=f"Failed to apply fix: {e}",
                    windmill_job_id=windmill_job_id,
                )
        elif can_auto_fix and dry_run:
            return ReconciliationDetail(
                step_run_id=step.id,
                step_name=step.step_name,
                protocol_run_id=step.protocol_run_id,
                db_status=db_status,
                windmill_status=windmill_status,
                action=ReconciliationAction.AUTO_FIXED,
                message=f"[DRY RUN] Would update status from {db_status} to {mapped_status}",
                windmill_job_id=windmill_job_id,
            )
        else:
            # Manual intervention required
            return ReconciliationDetail(
                step_run_id=step.id,
                step_name=step.step_name,
                protocol_run_id=step.protocol_run_id,
                db_status=db_status,
                windmill_status=windmill_status,
                action=ReconciliationAction.MANUAL_REQUIRED,
                message=f"Cannot auto-fix: DB={db_status}, Windmill={windmill_status}",
                windmill_job_id=windmill_job_id,
            )

    async def _find_windmill_job_for_step(self, step: StepRun) -> Optional[str]:
        """
        Find the Windmill job ID for a step run.
        
        Looks up job_runs table by step_run_id with windmill_job_id.
        """
        try:
            job_runs = self.db.list_job_runs(step_run_id=step.id, limit=1)
            if job_runs and job_runs[0].windmill_job_id:
                return job_runs[0].windmill_job_id
        except Exception as e:
            self.logger.warning(
                "reconciliation_job_lookup_failed",
                extra=self.log_extra(
                    step_run_id=step.id,
                    error=str(e),
                ),
            )
        return None

    def _get_active_step_runs(
        self,
        protocol_run_id: Optional[int] = None,
    ) -> List[StepRun]:
        """
        Get all active (non-terminal) step runs.
        
        Args:
            protocol_run_id: Optional protocol to filter by
            
        Returns:
            List of active StepRun objects
        """
        if protocol_run_id:
            steps = self.db.list_step_runs(protocol_run_id)
            return [s for s in steps if s.status not in STEP_TERMINAL_STATUSES]
        
        # Get all protocols and their steps
        protocols = self.db.list_all_protocol_runs(limit=500)
        active_steps: List[StepRun] = []
        
        for protocol in protocols:
            # Only check protocols that could have active steps
            if protocol.status in (
                ProtocolStatus.COMPLETED,
                ProtocolStatus.CANCELLED,
                ProtocolStatus.FAILED,
            ):
                continue
            
            steps = self.db.list_step_runs(protocol.id)
            active_steps.extend(
                s for s in steps if s.status not in STEP_TERMINAL_STATUSES
            )
        
        return active_steps

    def _map_windmill_status_to_step_status(self, job_status: JobStatus) -> str:
        """Map Windmill JobStatus to StepStatus."""
        mapping = {
            JobStatus.QUEUED: StepStatus.PENDING,
            JobStatus.RUNNING: StepStatus.RUNNING,
            JobStatus.COMPLETED: StepStatus.COMPLETED,
            JobStatus.FAILED: StepStatus.FAILED,
            JobStatus.CANCELED: StepStatus.CANCELLED,
        }
        return mapping.get(job_status, StepStatus.PENDING)

    def _can_auto_fix(
        self,
        db_status: str,
        mapped_status: str,
        windmill_status: JobStatus,
    ) -> bool:
        """
        Determine if we can safely auto-fix the status mismatch.
        
        Rules:
        - Can always update to terminal status from non-terminal
        - Can update from PENDING to RUNNING if Windmill shows RUNNING
        - Cannot update from terminal to non-terminal
        - Cannot update from COMPLETED to FAILED
        """
        # Never auto-fix if DB already shows terminal
        if db_status in STEP_TERMINAL_STATUSES:
            return False
        
        # Can always update non-terminal to terminal
        if mapped_status in STEP_TERMINAL_STATUSES:
            return True
        
        # Can update PENDING to RUNNING
        if db_status == StepStatus.PENDING and mapped_status == StepStatus.RUNNING:
            return True
        
        # Can update to NEEDS_QA (from RUNNING when Windmill shows COMPLETED)
        if db_status == StepStatus.RUNNING and mapped_status == StepStatus.COMPLETED:
            return True
        
        return False
