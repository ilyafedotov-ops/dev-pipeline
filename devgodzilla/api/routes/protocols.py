from typing import Any, Dict, List, Optional
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

from devgodzilla.api import schemas
from devgodzilla.api.dependencies import get_db, get_service_context, get_windmill_client
from devgodzilla.services.base import ServiceContext
from devgodzilla.db.database import Database
from devgodzilla.services.orchestrator import OrchestratorMode, OrchestratorService
from devgodzilla.services.planning import PlanningService
from devgodzilla.windmill.client import WindmillClient

router = APIRouter()


def _workspace_root(run, project) -> Path:
    if run.worktree_path:
        return Path(run.worktree_path).expanduser()
    if project.local_path:
        return Path(project.local_path).expanduser()
    return Path.cwd()


def _protocol_root(run, workspace_root: Path) -> Path:
    if run.protocol_root:
        return Path(run.protocol_root).expanduser()
    protocols = workspace_root / ".protocols" / run.protocol_name
    specify = workspace_root / ".specify" / "specs" / run.protocol_name
    if protocols.exists():
        return protocols
    if specify.exists():
        return specify
    return protocols


def _artifact_type_from_name(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".log") or "log" in lower:
        return "log"
    if lower.endswith(".diff") or lower.endswith(".patch"):
        return "diff"
    if lower.endswith(".md") and ("report" in lower or "qa" in lower):
        return "report"
    if lower.endswith(".json"):
        return "json"
    if lower.endswith(".txt") or lower.endswith(".md"):
        return "text"
    return "file"


class ProjectProtocolCreate(BaseModel):
    protocol_name: str = Field(..., min_length=1)
    description: Optional[str] = None
    base_branch: str = "main"
    auto_start: bool = False


class CreateFlowRequest(BaseModel):
    tasks_path: Optional[str] = None


@router.get("/projects/{project_id}/protocols", response_model=List[schemas.ProtocolOut])
def list_project_protocols(
    project_id: int,
    limit: int = 200,
    db: Database = Depends(get_db),
):
    try:
        db.get_project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    limit = max(1, min(int(limit), 500))
    return db.list_protocol_runs(project_id)[:limit]


@router.post("/projects/{project_id}/protocols", response_model=schemas.ProtocolOut)
def create_project_protocol(
    project_id: int,
    request: ProjectProtocolCreate,
    background_tasks: BackgroundTasks,
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    try:
        db.get_project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    run = db.create_protocol_run(
        project_id=project_id,
        protocol_name=request.protocol_name,
        status="pending",
        base_branch=request.base_branch,
        description=request.description,
    )
    if request.auto_start:
        def run_planning() -> None:
            service = PlanningService(ctx, db)
            service.plan_protocol(run.id)

        db.update_protocol_status(run.id, "planning")
        background_tasks.add_task(run_planning)
    return db.get_protocol_run(run.id)

@router.post("/protocols", response_model=schemas.ProtocolOut)
def create_protocol(
    protocol: schemas.ProtocolCreate,
    background_tasks: BackgroundTasks,
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db)
):
    """Create a new protocol run."""
    # Create the run record
    run = db.create_protocol_run(
        project_id=protocol.project_id,
        protocol_name=protocol.name,
        status="pending",
        base_branch=protocol.branch_name or "main",
        description=protocol.description,
    )
    
    # If using planning service, we should trigger plan_protocol in background
    # But for now, we just return the pending run. The CLI triggers planning explicitly.
    # We could add an option 'plan: bool = False' to trigger it.
    
    return run

@router.get("/protocols", response_model=List[schemas.ProtocolOut])
def list_protocols(
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 20,
    db: Database = Depends(get_db)
):
    """List protocol runs."""
    limit = max(1, min(int(limit), 500))
    if project_id is None:
        runs = db.list_all_protocol_runs(limit=limit)
    else:
        runs = db.list_protocol_runs(project_id=project_id)[:limit]

    if status:
        runs = [r for r in runs if r.status == status]
    return runs[:limit]

@router.get("/protocols/{protocol_id}", response_model=schemas.ProtocolOut)
def get_protocol(
    protocol_id: int,
    db: Database = Depends(get_db)
):
    """Get a protocol run by ID."""
    try:
        return db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Protocol {protocol_id} not found")


@router.get("/protocols/{protocol_id}/events", response_model=List[schemas.EventOut])
def list_protocol_events(
    protocol_id: int,
    db: Database = Depends(get_db),
):
    try:
        db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")
    return [schemas.EventOut.model_validate(e) for e in db.list_events(protocol_id)]


@router.get("/protocols/{protocol_id}/flow")
def get_protocol_flow(
    protocol_id: int,
    db: Database = Depends(get_db),
):
    try:
        run = db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")
    return {"windmill_flow_id": run.windmill_flow_id}


@router.post("/protocols/{protocol_id}/flow")
def create_protocol_flow(
    protocol_id: int,
    _request: CreateFlowRequest,
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
    windmill: WindmillClient = Depends(get_windmill_client),
):
    try:
        db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")

    orchestrator = OrchestratorService(
        context=ctx,
        db=db,
        windmill_client=windmill,
        mode=OrchestratorMode.WINDMILL,
    )
    result = orchestrator.create_flow_from_steps(protocol_id)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error or "Failed to create flow")
    return {
        "windmill_flow_id": result.flow_id,
        "flow_definition": (result.data or {}).get("flow_definition"),
    }

@router.post("/protocols/{protocol_id}/actions/start", response_model=schemas.ProtocolOut)
def start_protocol(
    protocol_id: int,
    background_tasks: BackgroundTasks,
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db)
):
    """Start planning/execution for a protocol."""
    try:
        run = db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")
        
    if run.status not in ["pending", "planned"]:
        raise HTTPException(status_code=400, detail=f"Cannot start protocol in {run.status} state")
        
    # Update status to planning
    db.update_protocol_status(protocol_id, "planning")
    
    # Trigger planning service in background
    def run_planning():
        service = PlanningService(ctx, db)
        service.plan_protocol(protocol_id)
        
    background_tasks.add_task(run_planning)
    
    return db.get_protocol_run(protocol_id)

@router.post("/protocols/{protocol_id}/actions/run_next_step", response_model=schemas.NextStepOut)
def run_next_step(
    protocol_id: int,
    db: Database = Depends(get_db),
):
    """
    Select the next runnable step for a protocol.

    This does not execute the step; it only returns the next step_run_id whose
    dependencies are satisfied and whose status is pending.
    """
    try:
        run = db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")

    if run.status in ["cancelled", "completed"]:
        return schemas.NextStepOut(step_run_id=None)

    steps = db.list_step_runs(protocol_id)
    completed_ids = {s.id for s in steps if s.status == "completed"}

    for step in steps:
        if step.status != "pending":
            continue
        depends_on = step.depends_on or []
        if all(dep in completed_ids for dep in depends_on):
            return schemas.NextStepOut(step_run_id=step.id)

    return schemas.NextStepOut(step_run_id=None)


@router.post("/protocols/{protocol_id}/actions/pause", response_model=schemas.ProtocolOut)
def pause_protocol(
    protocol_id: int,
    db: Database = Depends(get_db),
):
    """Pause a running protocol."""
    try:
        run = db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")

    if run.status != "running":
        raise HTTPException(status_code=400, detail=f"Cannot pause protocol in {run.status} state")

    db.update_protocol_status(protocol_id, "paused")
    return db.get_protocol_run(protocol_id)


@router.post("/protocols/{protocol_id}/actions/resume", response_model=schemas.ProtocolOut)
def resume_protocol(
    protocol_id: int,
    db: Database = Depends(get_db),
):
    """Resume a paused protocol."""
    try:
        run = db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")

    if run.status != "paused":
        raise HTTPException(status_code=400, detail=f"Cannot resume protocol in {run.status} state")

    db.update_protocol_status(protocol_id, "running")
    return db.get_protocol_run(protocol_id)


@router.post("/protocols/{protocol_id}/actions/cancel", response_model=schemas.ProtocolOut)
def cancel_protocol(
    protocol_id: int,
    db: Database = Depends(get_db),
):
    """Cancel a protocol."""
    try:
        run = db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")

    if run.status in ["completed", "cancelled"]:
        return run

    db.update_protocol_status(protocol_id, "cancelled")
    return db.get_protocol_run(protocol_id)


@router.get("/protocols/{protocol_id}/artifacts", response_model=List[schemas.ProtocolArtifactOut])
def list_protocol_artifacts(
    protocol_id: int,
    limit: int = 200,
    db: Database = Depends(get_db),
):
    """List artifacts across all steps for a protocol (aggregated)."""
    limit = max(1, min(int(limit), 500))
    try:
        run = db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")

    project = db.get_project(run.project_id)
    root = _protocol_root(run, _workspace_root(run, project))

    items: List[schemas.ProtocolArtifactOut] = []
    for step in db.list_step_runs(protocol_id):
        artifacts_dir = root / ".devgodzilla" / "steps" / str(step.id) / "artifacts"
        if not artifacts_dir.exists():
            continue
        for p in artifacts_dir.iterdir():
            if not p.is_file():
                continue
            stat = p.stat()
            items.append(
                schemas.ProtocolArtifactOut(
                    id=f"{step.id}:{p.name}",
                    type=_artifact_type_from_name(p.name),
                    name=p.name,
                    size=stat.st_size,
                    created_at=None,
                    step_run_id=step.id,
                    step_name=step.step_name,
                )
            )

    # Sort by file mtime desc (best-effort)
    def _mtime(item: schemas.ProtocolArtifactOut) -> float:
        try:
            step_id_str, filename = item.id.split(":", 1)
            p = root / ".devgodzilla" / "steps" / step_id_str / "artifacts" / filename
            return p.stat().st_mtime
        except Exception:
            return 0.0

    items.sort(key=_mtime, reverse=True)
    return items[:limit]


@router.get("/protocols/{protocol_id}/quality", response_model=schemas.QualitySummaryOut)
def get_protocol_quality(
    protocol_id: int,
    db: Database = Depends(get_db),
):
    """
    Lightweight protocol quality summary for the Windmill React app.

    Aggregates per-step QA verdicts (persisted in step.runtime_state["qa_verdict"]).
    """
    try:
        db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")

    steps = db.list_step_runs(protocol_id)
    qa_verdicts = []
    for s in steps:
        state = s.runtime_state or {}
        verdict = (state.get("qa_verdict") or {}).get("verdict")
        qa_verdicts.append((s, verdict))

    blocking_issues = sum(1 for _, v in qa_verdicts if v in ("fail", "error"))
    warnings = sum(1 for _, v in qa_verdicts if v == "warn")

    def to_gate_status(verdict: str | None) -> str:
        if verdict in ("pass", "skip"):
            return "passed"
        if verdict == "warn":
            return "warning"
        if verdict in ("fail", "error"):
            return "failed"
        return "skipped"

    # Aggregate gate statuses across all steps (lint/type/test in current implementation).
    gate_ids = ["lint", "type", "test"]
    gate_statuses: dict[str, str] = {gid: "skipped" for gid in gate_ids}
    for step, _ in qa_verdicts:
        qa = (step.runtime_state or {}).get("qa_verdict") or {}
        for g in qa.get("gates", []) or []:
            gid = g.get("gate_id")
            if gid not in gate_statuses:
                continue
            v = g.get("verdict")
            current = gate_statuses[gid]
            next_status = to_gate_status(v)
            # Worst status wins: failed > warning > passed > skipped
            order = {"failed": 3, "warning": 2, "passed": 1, "skipped": 0}
            if order[next_status] > order[current]:
                gate_statuses[gid] = next_status

    gates = [
        schemas.GateResultOut(article=gid, name=gid.upper(), status=gate_statuses[gid], findings=[])
        for gid in gate_ids
    ]

    # Minimal checklist for now.
    checklist_items = [
        schemas.ChecklistItemOut(
            id="all_steps_qa",
            description="All executed steps have QA verdicts",
            passed=all(v is not None for _, v in qa_verdicts) if steps else True,
            required=False,
        ),
        schemas.ChecklistItemOut(
            id="no_blocking",
            description="No blocking QA failures",
            passed=blocking_issues == 0,
            required=True,
        ),
        schemas.ChecklistItemOut(
            id="tests_run",
            description="Test gate executed at least once",
            passed=any((s.runtime_state or {}).get("qa_verdict") for s, _ in qa_verdicts),
            required=False,
        ),
    ]
    passed = sum(1 for i in checklist_items if i.passed)
    total = len(checklist_items)
    score = passed / total if total else 1.0

    overall_status = "failed" if blocking_issues > 0 else "warning" if warnings > 0 else "passed"

    return schemas.QualitySummaryOut(
        protocol_run_id=protocol_id,
        score=score,
        gates=gates,
        checklist=schemas.ChecklistResultOut(passed=passed, total=total, items=checklist_items),
        overall_status=overall_status,
        blocking_issues=blocking_issues,
        warnings=warnings,
    )


@router.get("/protocols/{protocol_id}/quality/gates")
def get_protocol_quality_gates(
    protocol_id: int,
    db: Database = Depends(get_db),
):
    summary = get_protocol_quality(protocol_id, db)
    return {"gates": summary.gates}


@router.get("/protocols/{protocol_id}/feedback", response_model=schemas.FeedbackListOut)
def list_protocol_feedback(
    protocol_id: int,
    db: Database = Depends(get_db),
):
    """
    Feedback feed for the Windmill React app.

    For now, this is derived from clarifications (open/answered) tied to the protocol.
    """
    try:
        db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")

    clarifications = db.list_clarifications(protocol_run_id=protocol_id, limit=500)
    events: list[schemas.FeedbackEventOut] = []
    for c in clarifications:
        action = "clarification_created" if c.status == "open" else "clarification_answered"
        events.append(
            schemas.FeedbackEventOut(
                id=str(c.id),
                action_taken=action,
                created_at=c.created_at,
                resolved=c.status == "answered",
                clarification=schemas.ClarificationOut.model_validate(c),
            )
        )
    return schemas.FeedbackListOut(events=events)

@router.get("/protocols/{protocol_id}/clarifications", response_model=List[schemas.ClarificationOut])
def list_protocol_clarifications(
    protocol_id: int,
    status: Optional[str] = None,
    limit: int = 100,
    db: Database = Depends(get_db)
):
    """List clarifications scoped to a protocol."""
    try:
        db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")
    
    return db.list_clarifications(
        protocol_run_id=protocol_id,
        status=status,
        limit=limit
    )

@router.post("/protocols/{protocol_id}/clarifications/{key}", response_model=schemas.ClarificationOut)
def answer_protocol_clarification(
    protocol_id: int,
    key: str,
    answer: schemas.ClarificationAnswer,
    db: Database = Depends(get_db)
):
    """Answer a clarification scoped to a protocol."""
    try:
        db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")
    
    # Construct scope for protocol-level clarification
    scope = f"protocol:{protocol_id}"
    
    # Store answer as structured JSON
    payload = {"text": answer.answer}
    
    try:
        updated = db.answer_clarification(
            scope=scope,
            key=key,
            answer=payload,
            answered_by=answer.answered_by,
            status="answered",
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Clarification not found")

    return updated


@router.post("/protocols/{protocol_id}/feedback")
def submit_protocol_feedback(
    protocol_id: int,
    feedback: schemas.FeedbackRequest,
    db: Database = Depends(get_db),
    ctx: ServiceContext = Depends(get_service_context)
):
    """
    Submit feedback for a protocol.

    Supports multiple actions:
    - "clarify": Create a clarification request
    - "approve": Mark protocol as approved
    - "reject": Mark protocol as rejected
    - "retry": Retry failed protocol
    """
    try:
        protocol = db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")

    action = feedback.action.lower()

    if action == "clarify":
        # Create a clarification
        scope = f"protocol:{protocol_id}"
        key = feedback.metadata.get("key", "user_feedback") if feedback.metadata else "user_feedback"

        clarification = db.create_clarification(
            scope=scope,
            key=key,
            question=feedback.message or "User feedback requested",
            context=feedback.metadata or {},
            status="open"
        )

        return {
            "status": "clarification_created",
            "clarification_id": clarification.id,
            "message": "Clarification request created"
        }

    elif action == "approve":
        # Mark protocol as approved/completed
        db.update_protocol_run(protocol_id, status="completed", summary=feedback.message)
        return {
            "status": "approved",
            "message": "Protocol marked as approved"
        }

    elif action == "reject":
        # Mark protocol as rejected/failed
        db.update_protocol_run(protocol_id, status="failed", summary=feedback.message)
        return {
            "status": "rejected",
            "message": "Protocol marked as rejected"
        }

    elif action == "retry":
        # Reset protocol to retry
        db.update_protocol_run(protocol_id, status="pending")
        return {
            "status": "retry_scheduled",
            "message": "Protocol reset for retry"
        }

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown action: {action}. Supported actions: clarify, approve, reject, retry"
        )
