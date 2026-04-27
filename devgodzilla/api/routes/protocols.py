from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

from devgodzilla.api import schemas
from devgodzilla.api.run_context import enrich_runs_with_agile_context
from devgodzilla.api.dependencies import get_db, get_service_context, get_windmill_client
from devgodzilla.logging import get_logger
from devgodzilla.services.base import ServiceContext
from devgodzilla.db.database import Database
from devgodzilla.models.domain import ProtocolStatus, StepStatus
from devgodzilla.speckit_metadata import extract_spec_run_id
from devgodzilla.services.execution import ExecutionService
from devgodzilla.services.clarifier import ClarifierService
from devgodzilla.services.orchestrator import OrchestratorMode, OrchestratorService
from devgodzilla.services.planning import PlanningService
from devgodzilla.services.policy import PolicyService
from devgodzilla.services.priority import sort_by_priority
from devgodzilla.services.sprint_integration import SprintIntegrationService
from devgodzilla.services.spec_to_protocol import SpecToProtocolService
from devgodzilla.windmill.client import WindmillClient, WindmillConfig
from devgodzilla.services.workspace_paths import WorkspacePathError, resolve_protocol_root, resolve_workspace_root

router = APIRouter()
logger = get_logger(__name__)

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
    try:
        return resolve_workspace_root(run, project)
    except WorkspacePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _protocol_root(run, workspace_root: Path) -> Path:
    return resolve_protocol_root(run, workspace_root)


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


def _next_runnable_step_id(db: Database, protocol_id: int) -> Optional[int]:
    steps = db.list_step_runs(protocol_id)
    completed_ids = {step.id for step in steps if step.status == StepStatus.COMPLETED}
    pending_steps = [step for step in steps if step.status == StepStatus.PENDING]
    for step in sort_by_priority(pending_steps, priority_attr="priority"):
        depends_on = step.depends_on or []
        if all(dep in completed_ids for dep in depends_on):
            return step.id
    return None


def _build_orchestrator(ctx: ServiceContext, db: Database) -> OrchestratorService:
    windmill_client = None
    mode = OrchestratorMode.LOCAL
    if getattr(ctx.config, "windmill_enabled", False):
        windmill_client = WindmillClient(
            WindmillConfig(
                base_url=ctx.config.windmill_url or "http://localhost:8000",
                token=ctx.config.windmill_token or "",
                workspace=getattr(ctx.config, "windmill_workspace", "devgodzilla"),
            )
        )
        mode = OrchestratorMode.WINDMILL
    return OrchestratorService(context=ctx, db=db, windmill_client=windmill_client, mode=mode)


class ProjectProtocolCreate(schemas.ProtocolCreateBase):
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
    task_cycle: bool = False
    owner_agent: Optional[str] = None
    helper_agents: List[str] = Field(default_factory=list)
    allow_helper_agents: bool = False


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
    if request.template_source is not None or request.template_config is not None:
        db.update_protocol_template(
            run.id,
            template_source=request.template_source,
            template_config=request.template_config,
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
        protocol_name=protocol.protocol_name,
        status="pending",
        base_branch=protocol.base_branch,
        description=protocol.description,
    )
    if protocol.template_source is not None or protocol.template_config is not None:
        db.update_protocol_template(
            run.id,
            template_config=protocol.template_config,
            template_source=protocol.template_source,
        )
    
    # If using planning service, we should trigger plan_protocol in background
    # But for now, we just return the pending run. The CLI triggers planning explicitly.
    # We could add an option 'plan: bool = False' to trigger it.
    
    return db.get_protocol_run(run.id)


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

    if result.protocol_run_id and request.task_cycle:
        from devgodzilla.services.task_cycle import TaskCycleService

        TaskCycleService(ctx, db).seed_task_cycle_metadata(
            result.protocol_run_id,
            owner_agent=request.owner_agent,
            helper_agents=request.helper_agents if (request.allow_helper_agents or request.helper_agents) else [],
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


# Response models for new endpoints
class ProtocolSpecOut(BaseModel):
    spec_run_id: Optional[int] = None
    spec_hash: Optional[str] = None
    validation_status: Optional[str] = None
    validated_at: Optional[str] = None
    spec: Dict[str, Any] = Field(default_factory=dict)


class OpenPRRequest(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    draft: bool = False


class OpenPRResponse(BaseModel):
    pr_url: Optional[str] = None
    pr_number: Optional[int] = None
    message: str
    status: str = "created"


@router.get("/protocols/{protocol_id}/spec", response_model=ProtocolSpecOut)
def get_protocol_spec(
    protocol_id: int,
    db: Database = Depends(get_db),
):
    """Get spec associated with a protocol run from speckit_metadata."""
    try:
        run = db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")
    
    meta = run.speckit_metadata or {}
    return ProtocolSpecOut(
        spec_run_id=extract_spec_run_id(meta),
        spec_hash=meta.get("spec_hash"),
        validation_status=meta.get("validation_status"),
        validated_at=meta.get("validated_at"),
        spec=meta.get("spec", {}),
    )


@router.get("/protocols/{protocol_id}/runs", response_model=List[schemas.JobRunOut])
def list_protocol_runs(
    protocol_id: int,
    status: Optional[str] = None,
    job_type: Optional[str] = None,
    limit: int = 200,
    db: Database = Depends(get_db),
):
    """List job runs for a specific protocol."""
    try:
        db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")
    
    runs = db.list_job_runs(
        protocol_run_id=protocol_id,
        status=status,
        job_type=job_type,
        limit=limit,
    )
    return [schemas.JobRunOut.model_validate(r) for r in enrich_runs_with_agile_context(db, runs)]


@router.post("/protocols/{protocol_id}/actions/open_pr", response_model=OpenPRResponse)
def open_protocol_pr(
    protocol_id: int,
    request: OpenPRRequest = OpenPRRequest(),
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """Open a pull request for a completed protocol.
    
    Creates a PR from the protocol's worktree branch to the base branch.
    Only works for protocols in 'completed' or 'running' status.
    """
    try:
        run = db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")
    
    if run.status not in ["completed", "running"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot open PR for protocol in '{run.status}' state. Protocol must be completed or running."
        )
    
    project = db.get_project(run.project_id)
    
    # Determine branch name from worktree or protocol name
    branch_name = None
    if run.worktree_path:
        # Extract branch name from worktree path or use protocol_name
        branch_name = run.protocol_name
    
    if not branch_name:
        return OpenPRResponse(
            pr_url=None,
            pr_number=None,
            message="No branch associated with this protocol",
            status="error",
        )
    
    # Get git provider from context if available
    git_provider = getattr(ctx, 'git_provider', None)
    
    if git_provider:
        try:
            # Attempt to create PR via git provider
            pr_info = git_provider.create_pull_request(
                repo_path=project.local_path,
                title=request.title or f"[Protocol] {run.protocol_name}",
                body=request.body or run.summary or "",
                head_branch=branch_name,
                base_branch=run.base_branch,
                draft=request.draft,
            )
            return OpenPRResponse(
                pr_url=pr_info.get("url"),
                pr_number=pr_info.get("number"),
                message="Pull request created successfully",
                status="created",
            )
        except Exception as exc:
            return OpenPRResponse(
                pr_url=None,
                pr_number=None,
                message=f"Failed to create PR: {str(exc)}",
                status="error",
            )

    # Fallback to local git service for standard GitHub/GitLab repositories.
    try:
        from devgodzilla.services.git import GitService

        worktree = Path(run.worktree_path or project.local_path or "").expanduser()
        if not worktree.exists():
            return OpenPRResponse(
                pr_url=None,
                pr_number=None,
                message="PR creation not available - repository worktree is missing.",
                status="error",
            )

        github_token = ((project.secrets or {}).get("github_token") or "").strip() or None
        git_service = GitService(ctx)
        branch_pushed = git_service.push_and_open_pr(
            worktree,
            run.protocol_name,
            run.base_branch,
            protocol_run_id=run.id,
            project_id=project.id,
            github_token=github_token,
        )
        if not branch_pushed:
            return OpenPRResponse(
                pr_url=None,
                pr_number=None,
                message="Failed to push branch or create pull request.",
                status="error",
            )

        pr_url = None
        if project.git_url and "github.com" in project.git_url:
            owner_repo = project.git_url.split("github.com/", 1)[-1].replace(".git", "").strip("/")
            if owner_repo:
                pr_url = f"https://github.com/{owner_repo}/compare/{run.base_branch}...{run.protocol_name}"

        return OpenPRResponse(
            pr_url=pr_url,
            pr_number=None,
            message="Pull request created or compare view prepared",
            status="created",
        )
    except Exception as exc:
        return OpenPRResponse(
            pr_url=None,
            pr_number=None,
            message=f"PR creation failed: {exc}",
            status="error",
        )


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
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """
    Execute the next runnable step for a protocol.

    Returns the selected `step_run_id` after dispatching it for execution.
    """
    try:
        run = db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")

    if run.status in [ProtocolStatus.CANCELLED, ProtocolStatus.COMPLETED]:
        return schemas.NextStepOut(step_run_id=None)

    step_run_id = _next_runnable_step_id(db, protocol_id)
    if step_run_id is None:
        return schemas.NextStepOut(step_run_id=None)

    if getattr(ctx.config, "windmill_enabled", False):
        orchestrator = _build_orchestrator(ctx, db)
        result = orchestrator.run_step(step_run_id)
        if not result.success:
            raise HTTPException(status_code=400, detail=result.error or "Failed to run next step")
        return schemas.NextStepOut(step_run_id=step_run_id)

    execution = ExecutionService(ctx, db)
    execution.execute_step(step_run_id)
    return schemas.NextStepOut(step_run_id=step_run_id)


@router.get("/protocols/{protocol_id}/next-step", response_model=schemas.NextStepOut)
def preview_next_step(
    protocol_id: int,
    db: Database = Depends(get_db),
):
    """Preview the next runnable step without executing it."""
    try:
        run = db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")

    if run.status in [ProtocolStatus.CANCELLED, ProtocolStatus.COMPLETED]:
        return schemas.NextStepOut(step_run_id=None)

    return schemas.NextStepOut(step_run_id=_next_runnable_step_id(db, protocol_id))


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
                    created_at=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
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
    db: Database = Depends(get_db),
    ctx: ServiceContext = Depends(get_service_context),
):
    """Answer a clarification scoped to a protocol."""
    try:
        db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")
    
    clarifier = ClarifierService(ctx, db)
    run = db.get_protocol_run(protocol_id)
    try:
        updated = clarifier.answer(
            project_id=run.project_id,
            protocol_run_id=protocol_id,
            key=key,
            answer=answer.answer,
            answered_by=answer.answered_by,
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
    
    project = db.get_project(run.project_id)
    repo_root = None
    try:
        repo_root = resolve_workspace_root(run, project)
    except Exception:
        if project.local_path:
            try:
                repo_root = Path(project.local_path).expanduser()
            except Exception:
                repo_root = None

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

    # Fallback: find sprint by tasks linked to this protocol. Database.list_tasks
    # is intentionally narrow across backends, so filter protocol linkage here.
    tasks = db.list_tasks(project_id=run.project_id, limit=500)
    for task in tasks:
        if task.protocol_run_id != protocol_id or not task.sprint_id:
            continue
        try:
            return db.get_sprint(task.sprint_id)
        except KeyError:
            continue
    return None


@router.post("/protocols/{protocol_id}/actions/sync-to-sprint", response_model=schemas.SyncResult)
async def sync_protocol_to_sprint(
    protocol_id: int,
    request: schemas.SyncProtocolToSprintRequest,
    service: SprintIntegrationService = Depends(get_sprint_integration),
):
    """Persist the protocol->sprint link and sync protocol steps into that sprint."""
    try:
        await service.link_protocol_to_sprint(
            protocol_run_id=protocol_id,
            sprint_id=request.sprint_id,
        )
        tasks = await service.sync_protocol_to_sprint(
            protocol_run_id=protocol_id,
            sprint_id=request.sprint_id,
            create_missing_tasks=True,
        )
        return schemas.SyncResult(
            sprint_id=request.sprint_id,
            protocol_run_id=protocol_id,
            tasks_synced=len(tasks),
            task_ids=[t.id for t in tasks],
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
