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
from devgodzilla.services.policy import PolicyService
from devgodzilla.services.sprint_integration import SprintIntegrationService
from devgodzilla.services.spec_to_protocol import SpecToProtocolService
from devgodzilla.windmill.client import WindmillClient

router = APIRouter()

def _policy_location(metadata: Optional[dict]) -> Optional[str]:
    if not metadata:
        return None
    if isinstance(metadata.get("location"), str):
        return metadata["location"]
    file_name = metadata.get("file") or metadata.get("path")
    section = metadata.get("section") or metadata.get("heading")
    if file_name and section:
        return f"{file_name}#{section}"
    if file_name:
        return str(file_name)
    if section:
        return str(section)
    return None


def get_sprint_integration(db: Database = Depends(get_db)) -> SprintIntegrationService:
    return SprintIntegrationService(db)


def get_policy_service(
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
) -> PolicyService:
    return PolicyService(ctx, db)


def _workspace_root(run, project) -> Path:
    if run.worktree_path:
        return Path(run.worktree_path).expanduser()
    if project.local_path:
        return Path(project.local_path).expanduser()
    return Path.cwd()


def _protocol_root(run, workspace_root: Path) -> Path:
    if run.protocol_root:
        candidate = Path(run.protocol_root).expanduser()
        if candidate.is_absolute():
            return candidate
        return workspace_root / candidate
    specs = workspace_root / "specs" / run.protocol_name
    protocols = workspace_root / ".protocols" / run.protocol_name
    if specs.exists():
        return specs
    if protocols.exists():
        return protocols
    return specs


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


class ProtocolFromSpecRequest(BaseModel):
    project_id: int
    spec_path: Optional[str] = None
    tasks_path: Optional[str] = None
    protocol_name: Optional[str] = None
    spec_run_id: Optional[int] = None
    overwrite: bool = False


class ProtocolFromSpecResponse(BaseModel):
    success: bool
    protocol: Optional[schemas.ProtocolOut] = None
    protocol_root: Optional[str] = None
    step_count: int = 0
    warnings: List[str] = Field(default_factory=list)
    error: Optional[str] = None


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


@router.post("/protocols/from-spec", response_model=ProtocolFromSpecResponse)
def create_protocol_from_spec(
    request: ProtocolFromSpecRequest,
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """Create a protocol run from SpecKit tasks/spec artifacts."""
    try:
        db.get_project(request.project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")

    service = SpecToProtocolService(ctx, db)
    result = service.create_protocol_from_spec(
        project_id=request.project_id,
        spec_path=request.spec_path,
        tasks_path=request.tasks_path,
        protocol_name=request.protocol_name,
        spec_run_id=request.spec_run_id,
        overwrite=request.overwrite,
    )
    if not result.success:
        return ProtocolFromSpecResponse(
            success=False,
            error=result.error or "Protocol creation failed",
            warnings=result.warnings,
        )

    protocol = db.get_protocol_run(result.protocol_run_id) if result.protocol_run_id else None
    return ProtocolFromSpecResponse(
        success=True,
        protocol=schemas.ProtocolOut.model_validate(protocol) if protocol else None,
        protocol_root=result.protocol_root,
        step_count=result.step_count,
        warnings=result.warnings,
    )

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


@router.get("/protocols/{protocol_id}/steps", response_model=List[schemas.StepOut])
def list_protocol_steps(
    protocol_id: int,
    db: Database = Depends(get_db),
):
    """List steps for a protocol run."""
    try:
        db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")
    return db.list_step_runs(protocol_id)


@router.get("/protocols/{protocol_id}/events", response_model=List[schemas.EventOut])
def list_protocol_events(
    protocol_id: int,
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    category: Optional[List[str]] = Query(None, description="Filter by event category"),
    db: Database = Depends(get_db),
):
    try:
        db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")
    event_types = [event_type] if event_type else None
    return [
        schemas.EventOut.model_validate(e)
        for e in db.list_events(protocol_id, event_types=event_types, categories=category)
    ]


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


@router.post("/protocols/{protocol_id}/actions/retry_latest", response_model=schemas.RetryStepOut)
def retry_latest_step(
    protocol_id: int,
    background_tasks: BackgroundTasks,
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """Retry the most recent failed or blocked step.
    
    Finds the last failed or blocked step in the protocol and retries it.
    Updates the protocol status to running if it was paused or failed.
    """
    try:
        run = db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")
    
    if run.status in ["completed", "cancelled"]:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot retry steps in {run.status} protocol"
        )
    
    # Find the most recent failed or blocked step
    steps = db.list_step_runs(protocol_id)
    target_step = None
    for step in reversed(steps):
        if step.status in ["failed", "blocked"]:
            target_step = step
            break
    
    if not target_step:
        raise HTTPException(
            status_code=404,
            detail="No failed or blocked steps to retry"
        )
    
    # Update step status to pending and increment retry count
    new_retries = (target_step.retries or 0) + 1
    db.update_step_status(
        target_step.id,
        "pending",
        retries=new_retries,
    )
    
    # Update protocol status to running if needed
    if run.status in ["paused", "failed"]:
        db.update_protocol_status(protocol_id, "running")
    
    return schemas.RetryStepOut(
        step_run_id=target_step.id,
        step_name=target_step.step_name,
        message=f"Retrying step '{target_step.step_name}'",
        retries=new_retries,
    )


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

    Aggregates per-step QA verdicts from qa_results.
    """
    try:
        db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")

    steps = db.list_step_runs(protocol_id)
    qa_results = db.list_qa_results(protocol_run_id=protocol_id, limit=1000)
    qa_by_step = {r.step_run_id: r for r in qa_results}

    blocking_issues = sum(1 for r in qa_results if r.verdict in ("fail", "error"))
    warnings = sum(1 for r in qa_results if r.verdict == "warn")

    def to_gate_status(verdict: str | None) -> str:
        if verdict in ("pass", "skip"):
            return "passed"
        if verdict == "warn":
            return "warning"
        if verdict in ("fail", "error"):
            return "failed"
        return "skipped"

    gate_statuses: dict[str, str] = {}
    article_statuses: dict[str, dict[str, str]] = {}

    for qa in qa_results:
        for gate in qa.gate_results or []:
            gate_id = gate.get("gate_id") or ""
            verdict = gate.get("verdict")
            if gate_id:
                current = gate_statuses.get(gate_id, "skipped")
                next_status = to_gate_status(verdict)
                order = {"failed": 3, "warning": 2, "passed": 1, "skipped": 0}
                if order[next_status] > order[current]:
                    gate_statuses[gate_id] = next_status

            if gate_id == "constitutional":
                meta = gate.get("metadata") or {}
                for article in meta.get("article_statuses", []) or []:
                    article_id = str(article.get("article") or "")
                    if not article_id:
                        continue
                    current = article_statuses.get(article_id, {}).get("status", "skipped")
                    next_status = str(article.get("status") or "skipped")
                    order = {"failed": 3, "warning": 2, "passed": 1, "skipped": 0}
                    if order.get(next_status, 0) > order.get(current, 0):
                        article_statuses[article_id] = {
                            "status": next_status,
                            "name": str(article.get("name") or article_id),
                        }

    gates = [
        schemas.GateResultOut(article=gid, name=gid.upper(), status=status, findings=[])
        for gid, status in sorted(gate_statuses.items())
    ]
    for article_id, meta in sorted(article_statuses.items()):
        gates.append(
            schemas.GateResultOut(
                article=article_id,
                name=str(meta.get("name") or article_id),
                status=meta.get("status", "skipped"),
                findings=[],
            )
        )

    # Minimal checklist for now.
    checklist_items = [
        schemas.ChecklistItemOut(
            id="all_steps_qa",
            description="All executed steps have QA verdicts",
            passed=all(s.id in qa_by_step for s in steps) if steps else True,
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
            passed=any(
                any(g.get("gate_id") == "test" for g in (qa.gate_results or []))
                for qa in qa_results
            ),
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


# =============================================================================
# Protocol Policy Endpoints
# =============================================================================

@router.get("/protocols/{protocol_id}/policy/findings", response_model=List[schemas.PolicyFindingOut])
def get_protocol_policy_findings(
    protocol_id: int,
    db: Database = Depends(get_db),
    policy_service: PolicyService = Depends(get_policy_service),
):
    """Get policy violation findings for a protocol."""
    try:
        run = db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")
    
    # Determine repo root for policy evaluation
    project = db.get_project(run.project_id)
    repo_root = None
    if project.local_path:
        try:
            repo_root = Path(project.local_path).expanduser()
        except Exception:
            pass
    
    findings = policy_service.evaluate_protocol(protocol_id, repo_root=repo_root)
    
    return [
        schemas.PolicyFindingOut(
            code=f.code,
            severity=f.severity,
            message=f.message,
            scope=f.scope,
            location=_policy_location(f.metadata),
            suggested_fix=f.suggested_fix,
            metadata=f.metadata,
        )
        for f in findings
    ]


@router.get("/protocols/{protocol_id}/policy/snapshot", response_model=schemas.EffectivePolicyOut)
def get_protocol_policy_snapshot(
    protocol_id: int,
    db: Database = Depends(get_db),
    policy_service: PolicyService = Depends(get_policy_service),
):
    """Get policy snapshot with hash for a protocol.
    
    Returns the effective policy that was (or would be) used for this protocol.
    If the protocol has a recorded policy audit, returns that snapshot.
    Otherwise, resolves the current effective policy for the project.
    """
    try:
        run = db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")
    
    # If protocol has recorded policy audit, return that snapshot
    if run.policy_effective_hash and run.policy_pack_key:
        return schemas.EffectivePolicyOut(
            hash=run.policy_effective_hash,
            policy=run.policy_effective_json or {},
            pack_key=run.policy_pack_key,
            pack_version=run.policy_pack_version or "1.0",
        )
    
    # Otherwise, resolve current effective policy for the project
    project = db.get_project(run.project_id)
    repo_root = None
    if project.local_path:
        try:
            repo_root = Path(project.local_path).expanduser()
        except Exception:
            pass
    
    effective = policy_service.resolve_effective_policy(
        run.project_id,
        repo_root=repo_root,
        include_repo_local=True,
    )
    
    return schemas.EffectivePolicyOut(
        hash=effective.effective_hash,
        policy=effective.policy,
        pack_key=effective.pack_key,
        pack_version=effective.pack_version,
    )


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


# =============================================================================
# Protocol-Sprint Integration Endpoints
# =============================================================================

@router.post("/protocols/{protocol_id}/actions/create-sprint", response_model=schemas.SprintOut)
async def create_sprint_from_protocol(
    protocol_id: int,
    request: schemas.CreateSprintFromProtocolRequest,
    service: SprintIntegrationService = Depends(get_sprint_integration),
):
    """Create a sprint from a protocol run."""
    try:
        return await service.create_sprint_from_protocol(
            protocol_run_id=protocol_id,
            sprint_name=request.sprint_name,
            start_date=request.start_date,
            end_date=request.end_date,
            auto_sync=request.auto_sync,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/protocols/{protocol_id}/sprint", response_model=Optional[schemas.SprintOut])
def get_protocol_sprint(
    protocol_id: int,
    db: Database = Depends(get_db),
):
    """Get the sprint linked to a protocol run."""
    try:
        run = db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol run not found")

    if hasattr(run, "linked_sprint_id") and run.linked_sprint_id:
        try:
            return db.get_sprint(run.linked_sprint_id)
        except KeyError:
            return None

    # Fallback: find sprint by tasks linked to this protocol
    tasks = db.list_tasks(protocol_run_id=protocol_id, limit=1)
    if tasks and tasks[0].sprint_id:
        return db.get_sprint(tasks[0].sprint_id)
    return None


@router.post("/protocols/{protocol_id}/actions/sync-to-sprint", response_model=schemas.SyncResult)
async def sync_protocol_to_sprint(
    protocol_id: int,
    sprint_id: int = Query(..., description="Target sprint ID"),
    service: SprintIntegrationService = Depends(get_sprint_integration),
):
    """Sync protocol steps to an existing sprint as tasks."""
    try:
        tasks = await service.sync_protocol_to_sprint(
            protocol_run_id=protocol_id,
            sprint_id=sprint_id,
            create_missing_tasks=True,
        )
        return schemas.SyncResult(
            sprint_id=sprint_id,
            protocol_run_id=protocol_id,
            tasks_synced=len(tasks),
            task_ids=[t.id for t in tasks],
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
