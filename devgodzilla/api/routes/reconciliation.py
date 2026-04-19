"""
DevGodzilla Reconciliation API Routes

REST endpoints for triggering and monitoring reconciliation operations
that sync DevGodzilla DB state with Windmill job status.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

from devgodzilla.api.dependencies import get_db, get_service_context, get_windmill_client
from devgodzilla.logging import get_logger
from devgodzilla.services.base import ServiceContext
from devgodzilla.db.database import Database
from devgodzilla.services.reconciliation import (
    ReconciliationService,
    ReconciliationReport,
    ReconciliationDetail,
    ProtocolReconciliation,
    StepReconciliation,
    ReconciliationAction,
)
from devgodzilla.windmill.client import WindmillClient

router = APIRouter()
logger = get_logger(__name__)


# Response Models
class ReconciliationDetailOut(BaseModel):
    """API response for a single reconciliation detail."""
    step_run_id: int
    step_name: str
    protocol_run_id: int
    db_status: str
    windmill_status: str
    action: str
    message: Optional[str] = None
    windmill_job_id: Optional[str] = None
    timestamp: str


class ReconciliationReportOut(BaseModel):
    """API response for a full reconciliation report."""
    total_checked: int
    mismatches_found: int
    auto_fixed: int
    requires_manual: int
    details: List[ReconciliationDetailOut] = Field(default_factory=list)
    protocols_checked: int = 0
    timestamp: str
    duration_seconds: Optional[float] = None


class ProtocolReconciliationOut(BaseModel):
    """API response for protocol-level reconciliation."""
    protocol_run_id: int
    protocol_name: str
    protocol_status: str
    steps_checked: int
    mismatches_found: int
    auto_fixed: int
    requires_manual: int
    details: List[ReconciliationDetailOut] = Field(default_factory=list)
    timestamp: str


class StepReconciliationOut(BaseModel):
    """API response for step-level reconciliation."""
    step_run_id: int
    step_name: str
    protocol_run_id: int
    db_status: str
    windmill_status: str
    action: str
    message: Optional[str] = None
    timestamp: str


class ReconciliationRunRequest(BaseModel):
    """Request to trigger a reconciliation run."""
    protocol_run_id: Optional[int] = Field(
        None,
        description="Limit reconciliation to a specific protocol",
    )
    dry_run: bool = Field(
        False,
        description="Report mismatches without applying fixes",
    )
    background: bool = Field(
        False,
        description="Run reconciliation in background",
    )


# Dependency injection
def get_reconciliation_service(
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
    windmill: WindmillClient = Depends(get_windmill_client),
) -> ReconciliationService:
    """Create ReconciliationService with dependencies."""
    return ReconciliationService(ctx, db, windmill)


def _detail_to_out(detail: ReconciliationDetail) -> ReconciliationDetailOut:
    """Convert ReconciliationDetail to API response model."""
    return ReconciliationDetailOut(
        step_run_id=detail.step_run_id,
        step_name=detail.step_name,
        protocol_run_id=detail.protocol_run_id,
        db_status=detail.db_status,
        windmill_status=detail.windmill_status,
        action=detail.action.value,
        message=detail.message,
        windmill_job_id=detail.windmill_job_id,
        timestamp=detail.timestamp,
    )


def _report_to_out(report: ReconciliationReport) -> ReconciliationReportOut:
    """Convert ReconciliationReport to API response model."""
    return ReconciliationReportOut(
        total_checked=report.total_checked,
        mismatches_found=report.mismatches_found,
        auto_fixed=report.auto_fixed,
        requires_manual=report.requires_manual,
        details=[_detail_to_out(d) for d in report.details],
        protocols_checked=report.protocols_checked,
        timestamp=report.timestamp,
        duration_seconds=report.duration_seconds,
    )


def _protocol_reconciliation_to_out(pr: ProtocolReconciliation) -> ProtocolReconciliationOut:
    """Convert ProtocolReconciliation to API response model."""
    return ProtocolReconciliationOut(
        protocol_run_id=pr.protocol_run_id,
        protocol_name=pr.protocol_name,
        protocol_status=pr.protocol_status,
        steps_checked=pr.steps_checked,
        mismatches_found=pr.mismatches_found,
        auto_fixed=pr.auto_fixed,
        requires_manual=pr.requires_manual,
        details=[_detail_to_out(d) for d in pr.details],
        timestamp=pr.timestamp,
    )


def _step_reconciliation_to_out(sr: StepReconciliation) -> StepReconciliationOut:
    """Convert StepReconciliation to API response model."""
    return StepReconciliationOut(
        step_run_id=sr.step_run_id,
        step_name=sr.step_name,
        protocol_run_id=sr.protocol_run_id,
        db_status=sr.db_status,
        windmill_status=sr.windmill_status,
        action=sr.action.value,
        message=sr.message,
        timestamp=sr.timestamp,
    )


# In-memory store for last reconciliation report (simple implementation)
# In production, this would be stored in DB or Redis
_last_report: Optional[ReconciliationReport] = None


@router.post("/reconciliation/run", response_model=ReconciliationReportOut)
async def run_reconciliation(
    request: ReconciliationRunRequest,
    background_tasks: BackgroundTasks,
    service: ReconciliationService = Depends(get_reconciliation_service),
):
    """
    Trigger a reconciliation run to sync DB state with Windmill.
    
    This endpoint:
    - Finds all active (non-terminal) step runs
    - Queries Windmill for the status of each job
    - Updates DB status to match Windmill when safe
    - Returns a detailed report of all changes
    
    Use `dry_run=true` to see what would change without applying fixes.
    Use `background=true` to run in background (returns immediately).
    """
    global _last_report

    async def run_and_store():
        global _last_report
        report = await service.reconcile_runs(
            protocol_run_id=request.protocol_run_id,
            dry_run=request.dry_run,
        )
        _last_report = report

    if request.background:
        background_tasks.add_task(run_and_store)
        # Return placeholder for background runs
        return ReconciliationReportOut(
            total_checked=0,
            mismatches_found=0,
            auto_fixed=0,
            requires_manual=0,
            details=[],
            protocols_checked=0,
            timestamp="pending",
            duration_seconds=None,
        )

    report = await service.reconcile_runs(
        protocol_run_id=request.protocol_run_id,
        dry_run=request.dry_run,
    )
    _last_report = report
    return _report_to_out(report)


@router.get("/reconciliation/status", response_model=Optional[ReconciliationReportOut])
def get_reconciliation_status():
    """
    Get the last reconciliation report.
    
    Returns the most recent reconciliation report, or null if no
    reconciliation has been run yet.
    """
    if _last_report is None:
        return None
    return _report_to_out(_last_report)


@router.get(
    "/reconciliation/protocols/{protocol_run_id}",
    response_model=ProtocolReconciliationOut,
)
async def reconcile_protocol(
    protocol_run_id: int,
    dry_run: bool = Query(False, description="Report mismatches without applying fixes"),
    service: ReconciliationService = Depends(get_reconciliation_service),
    db: Database = Depends(get_db),
):
    """
    Reconcile all steps for a specific protocol.
    
    Args:
        protocol_run_id: Protocol run ID to reconcile
        dry_run: If true, report what would change without applying fixes
    """
    try:
        db.get_protocol_run(protocol_run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")

    result = await service.reconcile_protocol(protocol_run_id, dry_run=dry_run)
    return _protocol_reconciliation_to_out(result)


@router.get(
    "/reconciliation/steps/{step_run_id}",
    response_model=StepReconciliationOut,
)
async def reconcile_step(
    step_run_id: int,
    dry_run: bool = Query(False, description="Report mismatches without applying fixes"),
    service: ReconciliationService = Depends(get_reconciliation_service),
    db: Database = Depends(get_db),
):
    """
    Reconcile a single step run with its Windmill job.
    
    Args:
        step_run_id: Step run ID to reconcile
        dry_run: If true, report what would change without applying fixes
    """
    try:
        db.get_step_run(step_run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Step not found")

    result = await service.reconcile_step(step_run_id, dry_run=dry_run)
    return _step_reconciliation_to_out(result)
