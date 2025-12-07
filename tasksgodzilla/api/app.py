import time
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
import json

from fastapi import Depends, FastAPI, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from tasksgodzilla import jobs
from tasksgodzilla.config import load_config
from tasksgodzilla.domain import ProtocolStatus, StepStatus
from tasksgodzilla.codemachine import ConfigError, config_to_template_payload, load_codemachine_config
from tasksgodzilla.logging import log_extra, setup_logging, json_logging_from_env
from tasksgodzilla.metrics import metrics
from tasksgodzilla.storage import BaseDatabase, create_database
from tasksgodzilla.worker_runtime import BackgroundWorker, RQWorkerThread
from tasksgodzilla.worker_runtime import drain_once
from tasksgodzilla.health import check_db
from tasksgodzilla.workers.state import maybe_complete_protocol
from tasksgodzilla.workers import codemachine_worker
from tasksgodzilla.spec import PROTOCOL_SPEC_KEY, SPEC_META_KEY, protocol_spec_hash
from hmac import compare_digest
import hmac
import hashlib

from . import schemas
from tasksgodzilla.git_utils import delete_remote_branch, list_remote_branches, resolve_project_repo_path
from tasksgodzilla.project_setup import local_repo_dir

logger = setup_logging(json_output=json_logging_from_env())
auth_scheme = HTTPBearer(auto_error=False)

ONBOARDING_STAGE_DEFS = [
    {"key": "resolve", "name": "Resolve/Clone"},
    {"key": "discovery", "name": "Discovery"},
    {"key": "assets", "name": "Assets"},
    {"key": "git", "name": "Git Config"},
    {"key": "clarifications", "name": "Clarifications"},
]

ONBOARDING_EVENT_STAGE = {
    "setup_started": ("resolve", "running"),
    "setup_pending_clone": ("resolve", "blocked"),
    "setup_cloned": ("resolve", "completed"),
    "setup_local_path_recorded": ("resolve", "completed"),
    "setup_discovery_started": ("discovery", "running"),
    "setup_discovery_skipped": ("discovery", "skipped"),
    "setup_discovery_completed": ("discovery", "completed"),
    "setup_discovery_warning": ("discovery", "warning"),
    "setup_assets": ("assets", "completed"),
    "setup_warning": ("assets", "warning"),
    "setup_git_remote": ("git", "completed"),
    "setup_git_identity": ("git", "completed"),
    "setup_clarifications": ("clarifications", "running"),
    "setup_blocked": ("clarifications", "blocked"),
    "setup_completed": ("clarifications", "completed"),
}

STAGE_RANK = {"pending": 0, "running": 1, "skipped": 1, "warning": 2, "blocked": 2, "completed": 3, "failed": 3}


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config()
    logger.setLevel(config.log_level.upper())
    logger.info("Starting API", extra={"request_id": "-", "env": config.environment})
    db = create_database(db_path=config.db_path, db_url=config.db_url, pool_size=config.db_pool_size)
    db.init_schema()
    queue = jobs.create_queue(config.redis_url)
    try:
        # Fail fast if Redis is unreachable
        queue.stats()
    except Exception as exc:  # pragma: no cover - runtime guard
        logger.error("Redis unavailable at startup", extra={"error": str(exc)})
        raise
    app.state.config = config  # type: ignore[attr-defined]
    app.state.db = db  # type: ignore[attr-defined]
    app.state.queue = queue  # type: ignore[attr-defined]
    app.state.metrics = metrics  # type: ignore[attr-defined]
    worker = None
    spec_audit_stop: Optional[threading.Event] = None
    spec_audit_thread: Optional[threading.Thread] = None
    if config.spec_audit_interval_seconds:
        spec_audit_stop = threading.Event()
        interval_default = max(30, int(config.spec_audit_interval_seconds))
        next_runs: dict[int, float] = {}

        def _spec_audit_cron() -> None:
            while not spec_audit_stop.is_set():
                now = time.time()
                try:
                    projects = db.list_projects()
                    for proj in projects:
                        secrets = proj.secrets or {}
                        interval = secrets.get("spec_audit_interval_seconds") or interval_default
                        try:
                            interval = int(interval)
                        except Exception:
                            interval = interval_default
                        if interval < 30:
                            interval = 30
                        last_next = next_runs.get(proj.id, 0)
                        if now >= last_next:
                            queue.enqueue(
                                "spec_audit_job",
                                {
                                    "project_id": proj.id,
                                    "protocol_id": None,
                                    "backfill_missing": True,
                                },
                            )
                            next_runs[proj.id] = now + interval
                except Exception as exc:  # pragma: no cover - best effort
                    logger.warning("Spec audit cron failed to enqueue", extra={"error": str(exc)})
                spec_audit_stop.wait(5)

        spec_audit_thread = threading.Thread(target=_spec_audit_cron, daemon=True)
        spec_audit_thread.start()
    if isinstance(queue, jobs.RedisQueue) and queue.is_fakeredis:
        worker = RQWorkerThread(queue)
        app.state.worker = worker  # type: ignore[attr-defined]
        worker.start()
    try:
        yield
    finally:
        if worker:
            worker.stop()
        if spec_audit_stop:
            spec_audit_stop.set()
        if spec_audit_thread:
            spec_audit_thread.join(timeout=2)
        logger.info("Shutting down API", extra={"request_id": "-"})


app = FastAPI(title="TasksGodzilla Orchestrator API", version="0.1.0", lifespan=lifespan)
frontend_dir = Path(__file__).resolve().parent / "frontend"
if frontend_dir.exists():
    app.mount("/console/static", StaticFiles(directory=frontend_dir), name="console-static")


def get_db(request: Request) -> BaseDatabase:
    return request.app.state.db  # type: ignore[attr-defined]


def get_queue(request: Request) -> jobs.BaseQueue:
    return request.app.state.queue  # type: ignore[attr-defined]


def get_worker(request: Request) -> RQWorkerThread:
    return request.app.state.worker  # type: ignore[attr-defined]


def get_protocol_project(protocol_run_id: int, db: BaseDatabase) -> int:
    run = db.get_protocol_run(protocol_run_id)
    return run.project_id


def get_step_project(step_run_id: int, db: BaseDatabase) -> int:
    step = db.get_step_run(step_run_id)
    return get_protocol_project(step.protocol_run_id, db)


def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
) -> None:
    config = request.app.state.config  # type: ignore[attr-defined]
    token = getattr(config, "api_token", None)
    if not token:
        return
    if credentials is None or credentials.scheme.lower() != "bearer" or credentials.credentials != token:
        raise HTTPException(status_code=401, detail="Unauthorized")


def require_project_access(project_id: int, request: Request, db: BaseDatabase) -> None:
    """Optional per-project token check (secrets.api_token)."""
    try:
        project = db.get_project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    secrets = project.secrets or {}
    project_token = secrets.get("api_token")
    if not project_token:
        return
    header_token = request.headers.get("X-Project-Token")
    if header_token != project_token:
        raise HTTPException(status_code=401, detail="Project access denied")


def verify_signature(secret: str, body: bytes, signature_header: str) -> bool:
    if not signature_header:
        return False
    if signature_header.startswith("sha256="):
        signature = signature_header.split("sha256=", 1)[1]
    else:
        signature = signature_header
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return compare_digest(digest, signature)


def record_event(
    db: BaseDatabase,
    protocol_run_id: int,
    event_type: str,
    message: str,
    *,
    request: Optional[Request] = None,
    step_run_id: Optional[int] = None,
    metadata: Optional[dict] = None,
):
    request_id = getattr(request.state, "request_id", None) if request else None
    meta = dict(metadata or {})
    try:
        run = db.get_protocol_run(protocol_run_id)
        spec_hash = _spec_hash_from_template(run.template_config)
        if spec_hash and "spec_hash" not in meta:
            meta["spec_hash"] = spec_hash
    except Exception:  # pragma: no cover - defensive guard
        pass
    return db.append_event(
        protocol_run_id=protocol_run_id,
        event_type=event_type,
        message=message,
        step_run_id=step_run_id,
        metadata=meta,
        request_id=request_id,
    )


def _protocol_out(run, db: Optional[BaseDatabase] = None) -> schemas.ProtocolRunOut:
    data = dict(run.__dict__)
    spec_hash = _spec_hash_from_template(data.get("template_config"))
    data["spec_hash"] = spec_hash
    summary = _spec_validation_summary(run.id, db=db) if db else {"status": None, "validated_at": None}
    data["spec_validation_status"] = summary.get("status")
    data["spec_validated_at"] = summary.get("validated_at")
    return schemas.ProtocolRunOut(**data)


def _spec_hash_from_template(template_config: Optional[dict]) -> Optional[str]:
    if isinstance(template_config, dict):
        spec = template_config.get(PROTOCOL_SPEC_KEY)
        if spec:
            return protocol_spec_hash(spec)
    return None


def _onboarding_stages_from_events(events: list[schemas.EventOut]) -> list[schemas.OnboardingStage]:
    stages = {d["key"]: schemas.OnboardingStage(key=d["key"], name=d["name"], status="pending") for d in ONBOARDING_STAGE_DEFS}
    sorted_events = sorted(events, key=lambda e: e.created_at)
    for ev in sorted_events:
        stage_meta = ONBOARDING_EVENT_STAGE.get(ev.event_type)
        if not stage_meta:
            continue
        stage_key, status = stage_meta
        current = stages.get(stage_key)
        if current is None:
            continue
        current_rank = STAGE_RANK.get(current.status, 0)
        incoming_rank = STAGE_RANK.get(status, 0)
        if incoming_rank >= current_rank:
            stages[stage_key] = schemas.OnboardingStage(
                key=stage_key,
                name=current.name,
                status=status,
                event_type=ev.event_type,
                message=ev.message,
                created_at=ev.created_at,
                metadata=ev.metadata,
            )
    return [stages[key] for key in stages]


def _onboarding_summary(project, db: BaseDatabase) -> schemas.OnboardingSummary:
    protocol_name = f"setup-{project.id}"
    run = None
    try:
        run = db.find_protocol_run_by_name(protocol_name)
    except Exception:
        run = None
    status = run.status if run else "pending"
    try:
        events = db.list_events(run.id) if run else []
    except Exception:
        events = []
    ev_out = [schemas.EventOut(**e.__dict__) for e in events]
    last_event = ev_out[-1] if ev_out else None
    stages = _onboarding_stages_from_events(ev_out)
    workspace_path = project.local_path or str(local_repo_dir(project.git_url, project.name, project_id=project.id))
    return schemas.OnboardingSummary(
        project_id=project.id,
        protocol_run_id=run.id if run else None,
        status=status,
        workspace_path=workspace_path,
        last_event=last_event,
        stages=stages,
        events=ev_out,
    )


def _spec_validation_summary(protocol_run_id: int, db: BaseDatabase) -> dict:
    run = db.get_protocol_run(protocol_run_id)
    status = None
    errors: list[str] = []
    validated_at = None
    template = run.template_config or {}
    if isinstance(template, dict):
        meta = template.get(SPEC_META_KEY) or {}
        if meta:
            status = meta.get("status")
            errors = meta.get("errors") or []
            validated_at = meta.get("validated_at")
            return {"status": status, "errors": errors or None, "validated_at": validated_at}

    events = db.list_events(protocol_run_id)
    for ev in events:
        if ev.event_type == "spec_validation_error":
            status = "invalid"
            ev_errors = []
            if isinstance(ev.metadata, dict):
                meta_errs = ev.metadata.get("errors")
                if isinstance(meta_errs, list):
                    ev_errors.extend(str(e) for e in meta_errs)
            errors = ev_errors or errors
            validated_at = ev.created_at if not validated_at else validated_at
            break
        if isinstance(ev.metadata, dict) and ev.metadata.get("spec_validated"):
            status = status or "valid"
            validated_at = ev.created_at
            if errors:
                break
    return {"status": status, "errors": errors or None, "validated_at": validated_at}


@app.post("/specs/audit", response_model=schemas.ActionResponse, dependencies=[Depends(require_auth)])
def enqueue_spec_audit(
    payload: schemas.SpecAuditRequest,
    queue: jobs.BaseQueue = Depends(get_queue),
    db: BaseDatabase = Depends(get_db),
    request: Request = None,  # type: ignore
) -> schemas.ActionResponse:
    if payload.project_id:
        require_project_access(payload.project_id, request, db)
    job_payload = {
        "project_id": payload.project_id,
        "protocol_id": payload.protocol_id,
        "backfill_missing": payload.backfill,
        "interval_override": payload.interval_seconds,
    }
    job = queue.enqueue("spec_audit_job", job_payload).asdict()
    return schemas.ActionResponse(message="Spec audit enqueued.", job=job)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id  # type: ignore[attr-defined]
    metrics.inc_request()
    start = time.time()
    response = await call_next(request)
    duration_s = (time.time() - start)
    metrics.observe_request(request.url.path, request.method, str(response.status_code), duration_s)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request",
        extra={
            **log_extra(
                request_id=request_id,
                protocol_run_id=request.headers.get("X-Protocol-Run-ID"),
                step_run_id=request.headers.get("X-Step-Run-ID"),
            ),
            "path": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
            "duration_ms": f"{duration_s * 1000:.2f}",
            "client": request.client.host if request.client else None,
        },
    )
    return response


@app.get("/", response_class=HTMLResponse)
@app.get("/console", response_class=HTMLResponse)
def console() -> HTMLResponse:
    if not frontend_dir.exists():
        raise HTTPException(status_code=404, detail="Console assets not available")
    html = (frontend_dir / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)


@app.get("/health", response_model=schemas.Health)
def health() -> schemas.Health:
    db_status = check_db(app.state.db)  # type: ignore[attr-defined]
    status = "ok" if db_status.status == "ok" else "degraded"
    return schemas.Health(status=status)


@app.get("/metrics")
def metrics_endpoint():
    data = metrics.to_prometheus()
    from fastapi import Response

    return Response(content=data, media_type="text/plain; version=0.0.4")


@app.post("/projects", response_model=schemas.ProjectOut, dependencies=[Depends(require_auth)])
def create_project(
    payload: schemas.ProjectCreate,
    db: BaseDatabase = Depends(get_db),
    queue: jobs.BaseQueue = Depends(get_queue),
    request: Request = None,
) -> schemas.ProjectOut:
    project = db.create_project(
        name=payload.name,
        git_url=payload.git_url,
        local_path=payload.local_path,
        base_branch=payload.base_branch,
        ci_provider=payload.ci_provider,
        default_models=payload.default_models,
        secrets=payload.secrets,
    )
    # Kick off onboarding so the console can show progress immediately.
    setup_run = db.create_protocol_run(
        project_id=project.id,
        protocol_name=f"setup-{project.id}",
        status=ProtocolStatus.PENDING,
        base_branch=project.base_branch,
        worktree_path=None,
        protocol_root=None,
        description="Project setup and bootstrap",
    )
    record_event(
        db,
        protocol_run_id=setup_run.id,
        event_type="setup_enqueued",
        message="Project setup enqueued.",
        request=request,
    )
    queue.enqueue("project_setup_job", {"project_id": project.id, "protocol_run_id": setup_run.id})
    return schemas.ProjectOut(**project.__dict__)


@app.get("/projects", response_model=list[schemas.ProjectOut], dependencies=[Depends(require_auth)])
def list_projects(db: BaseDatabase = Depends(get_db)) -> list[schemas.ProjectOut]:
    projects = db.list_projects()
    return [schemas.ProjectOut(**p.__dict__) for p in projects]


@app.get("/projects/{project_id}", response_model=schemas.ProjectOut, dependencies=[Depends(require_auth)])
def get_project(project_id: int, db: BaseDatabase = Depends(get_db), request: Request = None) -> schemas.ProjectOut:
    if request:
        require_project_access(project_id, request, db)
    try:
        project = db.get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return schemas.ProjectOut(**project.__dict__)


@app.get("/projects/{project_id}/branches", response_model=schemas.BranchListResponse, dependencies=[Depends(require_auth)])
def list_branches(project_id: int, db: BaseDatabase = Depends(get_db), request: Request = None) -> schemas.BranchListResponse:
    if request:
        require_project_access(project_id, request, db)
    try:
        project = db.get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        repo_root = resolve_project_repo_path(project.git_url, project.name, project.local_path, project_id=project.id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    branches = list_remote_branches(repo_root)
    record_event(db, protocol_run_id=0, event_type="branches_listed", message="Listed remote branches.", metadata={"project_id": project.id, "branches": branches}, request=request)
    return schemas.BranchListResponse(branches=branches)


@app.post("/projects/{project_id}/branches/{branch:path}/delete", dependencies=[Depends(require_auth)])
def delete_branch(
    project_id: int,
    branch: str,
    payload: schemas.BranchDeleteRequest,
    db: BaseDatabase = Depends(get_db),
    request: Request = None,
):
    if request:
        require_project_access(project_id, request, db)
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="confirm=true required to delete a remote branch")
    try:
        project = db.get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        repo_root = resolve_project_repo_path(project.git_url, project.name, project.local_path, project_id=project.id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    try:
        delete_remote_branch(repo_root, branch)
    except Exception as exc:
        record_event(
            db,
            protocol_run_id=0,
            event_type="branch_delete_failed",
            message=f"Failed to delete remote branch {branch}: {exc}",
            metadata={"project_id": project.id, "branch": branch},
            request=request,
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    record_event(
        db,
        protocol_run_id=0,
        event_type="branch_deleted",
        message=f"Deleted remote branch {branch}.",
        metadata={"project_id": project.id, "branch": branch},
        request=request,
    )
    return {"deleted": True, "branch": branch}


@app.post("/projects/{project_id}/protocols", response_model=schemas.ProtocolRunOut, dependencies=[Depends(require_auth)])
def create_protocol_run(
    project_id: int,
    payload: schemas.ProtocolRunCreate,
    db: BaseDatabase = Depends(get_db),
    request: Request = None,
) -> schemas.ProtocolRunOut:
    if request:
        require_project_access(project_id, request, db)
    try:
        db.get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    run = db.create_protocol_run(
        project_id=project_id,
        protocol_name=payload.protocol_name,
        status=payload.status,
        base_branch=payload.base_branch,
        worktree_path=payload.worktree_path,
        protocol_root=payload.protocol_root,
        description=payload.description,
        template_config=payload.template_config,
        template_source=payload.template_source,
    )
    return _protocol_out(run, db=db)


@app.get("/protocols/{protocol_run_id}/spec", response_model=schemas.ProtocolSpecOut, dependencies=[Depends(require_auth)])
def get_protocol_spec(
    protocol_run_id: int,
    db: BaseDatabase = Depends(get_db),
    request: Request = None,
) -> schemas.ProtocolSpecOut:
    if request:
        project_id = get_protocol_project(protocol_run_id, db)
        require_project_access(project_id, request, db)
    try:
        run = db.get_protocol_run(protocol_run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    template = run.template_config or {}
    spec = template.get(PROTOCOL_SPEC_KEY) if isinstance(template, dict) else None
    summary = _spec_validation_summary(run.id, db)
    return schemas.ProtocolSpecOut(
        protocol_run_id=run.id,
        protocol_name=run.protocol_name,
        project_id=run.project_id,
        spec=spec,
        spec_hash=_spec_hash_from_template(template),
        validation_status=summary["status"],
        validation_errors=summary["errors"],
        validated_at=summary["validated_at"],
    )


@app.post("/projects/{project_id}/codemachine/import", response_model=schemas.CodeMachineImportResponse, dependencies=[Depends(require_auth)])
def import_codemachine(
    project_id: int,
    payload: schemas.CodeMachineImportRequest,
    db: BaseDatabase = Depends(get_db),
    queue: jobs.BaseQueue = Depends(get_queue),
    request: Request = None,
) -> schemas.CodeMachineImportResponse:
    if request:
        require_project_access(project_id, request, db)
    try:
        project = db.get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    status = ProtocolStatus.PLANNING if payload.enqueue else ProtocolStatus.PLANNED
    run = db.create_protocol_run(
        project_id=project.id,
        protocol_name=payload.protocol_name,
        status=status,
        base_branch=payload.base_branch,
        worktree_path=payload.workspace_path,
        protocol_root=str(Path(payload.workspace_path) / ".codemachine"),
        description=payload.description,
        template_config=None,
        template_source=None,
    )

    if payload.enqueue:
        job = queue.enqueue(
            "codemachine_import_job",
            {
                "project_id": project.id,
                "protocol_run_id": run.id,
                "workspace_path": payload.workspace_path,
            },
        ).asdict()
        record_event(
            db,
            protocol_run_id=run.id,
            event_type="codemachine_import_enqueued",
            message="CodeMachine import enqueued.",
            metadata={"job_id": job["job_id"], "workspace": payload.workspace_path},
            request=request,
        )
        return schemas.CodeMachineImportResponse(
            protocol_run=_protocol_out(run, db=db),
            job=job,
            message="Enqueued CodeMachine import job.",
        )

    try:
        codemachine_worker.import_codemachine_workspace(project.id, run.id, payload.workspace_path, db)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    run = db.get_protocol_run(run.id)
    return schemas.CodeMachineImportResponse(
        protocol_run=_protocol_out(run, db=db),
        message="Imported CodeMachine workspace.",
        job=None,
    )


@app.get("/projects/{project_id}/protocols", response_model=list[schemas.ProtocolRunOut], dependencies=[Depends(require_auth)])
def list_protocol_runs(project_id: int, db: BaseDatabase = Depends(get_db), request: Request = None) -> list[schemas.ProtocolRunOut]:
    if request:
        require_project_access(project_id, request, db)
    runs = db.list_protocol_runs(project_id)
    return [_protocol_out(r, db=db) for r in runs]


@app.get("/protocols/{protocol_run_id}", response_model=schemas.ProtocolRunOut, dependencies=[Depends(require_auth)])
def get_protocol(protocol_run_id: int, db: BaseDatabase = Depends(get_db), request: Request = None) -> schemas.ProtocolRunOut:
    if request:
        project_id = get_protocol_project(protocol_run_id, db)
        require_project_access(project_id, request, db)
    try:
        run = db.get_protocol_run(protocol_run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _protocol_out(run, db=db)


@app.post("/protocols/{protocol_run_id}/actions/start", response_model=schemas.ActionResponse, dependencies=[Depends(require_auth)])
def start_protocol(
    protocol_run_id: int,
    db: BaseDatabase = Depends(get_db),
    queue: jobs.BaseQueue = Depends(get_queue),
    request: Request = None,
) -> schemas.ActionResponse:
    if request:
        project_id = get_protocol_project(protocol_run_id, db)
        require_project_access(project_id, request, db)
    try:
        run = db.get_protocol_run(protocol_run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if run.status not in (ProtocolStatus.PENDING, ProtocolStatus.PLANNED, ProtocolStatus.PAUSED):
        raise HTTPException(status_code=409, detail="Protocol already running or terminal")
    try:
        db.update_protocol_status(protocol_run_id, ProtocolStatus.PLANNING, expected_status=run.status)
    except ValueError:
        raise HTTPException(status_code=409, detail="Protocol state changed; retry")
    job = queue.enqueue("plan_protocol_job", {"protocol_run_id": protocol_run_id}).asdict()
    record_event(
        db,
        protocol_run_id,
        "planning_enqueued",
        "Planning job enqueued.",
        metadata={"job_id": job["job_id"], "spec_hash": _spec_hash_from_template(run.template_config)},
        request=request,
    )
    return schemas.ActionResponse(message="Protocol planning enqueued", job=job)


@app.post("/protocols/{protocol_run_id}/actions/pause", response_model=schemas.ProtocolRunOut, dependencies=[Depends(require_auth)])
def pause_protocol(
    protocol_run_id: int,
    db: BaseDatabase = Depends(get_db),
    request: Request = None,
) -> schemas.ProtocolRunOut:
    if request:
        project_id = get_protocol_project(protocol_run_id, db)
        require_project_access(project_id, request, db)
    try:
        run = db.get_protocol_run(protocol_run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if run.status in (ProtocolStatus.CANCELLED, ProtocolStatus.COMPLETED, ProtocolStatus.FAILED):
        raise HTTPException(status_code=409, detail="Protocol already terminal")
    try:
        run = db.update_protocol_status(protocol_run_id, ProtocolStatus.PAUSED, expected_status=run.status)
    except ValueError:
        raise HTTPException(status_code=409, detail="Protocol state changed; retry")
    record_event(db, protocol_run_id, "paused", "Protocol paused by user.", request=request)
    return _protocol_out(run, db=db)


@app.post("/protocols/{protocol_run_id}/actions/resume", response_model=schemas.ProtocolRunOut, dependencies=[Depends(require_auth)])
def resume_protocol(
    protocol_run_id: int,
    db: BaseDatabase = Depends(get_db),
    request: Request = None,
) -> schemas.ProtocolRunOut:
    if request:
        project_id = get_protocol_project(protocol_run_id, db)
        require_project_access(project_id, request, db)
    try:
        run = db.get_protocol_run(protocol_run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if run.status != ProtocolStatus.PAUSED:
        raise HTTPException(status_code=409, detail="Protocol is not paused")
    try:
        run = db.update_protocol_status(protocol_run_id, ProtocolStatus.RUNNING, expected_status=run.status)
    except ValueError:
        raise HTTPException(status_code=409, detail="Protocol state changed; retry")
    record_event(db, protocol_run_id, "resumed", "Protocol resumed by user.", request=request)
    return _protocol_out(run, db=db)


@app.post("/protocols/{protocol_run_id}/actions/cancel", response_model=schemas.ProtocolRunOut, dependencies=[Depends(require_auth)])
def cancel_protocol(
    protocol_run_id: int,
    db: BaseDatabase = Depends(get_db),
    request: Request = None,
) -> schemas.ProtocolRunOut:
    if request:
        project_id = get_protocol_project(protocol_run_id, db)
        require_project_access(project_id, request, db)
    try:
        run = db.get_protocol_run(protocol_run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if run.status == ProtocolStatus.CANCELLED:
        return _protocol_out(run, db=db)
    try:
        run = db.update_protocol_status(protocol_run_id, ProtocolStatus.CANCELLED, expected_status=run.status)
    except ValueError:
        raise HTTPException(status_code=409, detail="Protocol state changed; retry")
    steps = db.list_step_runs(protocol_run_id)
    for step in steps:
        if step.status in (StepStatus.PENDING, StepStatus.RUNNING, StepStatus.NEEDS_QA):
            db.update_step_status(step.id, StepStatus.CANCELLED, summary="Cancelled with protocol", expected_status=step.status)
    record_event(db, protocol_run_id, "cancelled", "Protocol cancelled by user.", request=request)
    return _protocol_out(run, db=db)


@app.post("/protocols/{protocol_run_id}/actions/run_next_step", response_model=schemas.ActionResponse, dependencies=[Depends(require_auth)])
def run_next_step(
    protocol_run_id: int,
    db: BaseDatabase = Depends(get_db),
    queue: jobs.BaseQueue = Depends(get_queue),
    request: Request = None,
) -> schemas.ActionResponse:
    if request:
        project_id = get_protocol_project(protocol_run_id, db)
        require_project_access(project_id, request, db)
    steps = db.list_step_runs(protocol_run_id)
    target = next((s for s in steps if s.status in (StepStatus.PENDING, StepStatus.BLOCKED, StepStatus.FAILED)), None)
    if not target:
        raise HTTPException(status_code=404, detail="No pending or failed steps to run")
    try:
        step = db.update_step_status(target.id, StepStatus.RUNNING, expected_status=target.status)
    except ValueError:
        raise HTTPException(status_code=409, detail="Step state changed; retry")
    db.update_protocol_status(protocol_run_id, ProtocolStatus.RUNNING)
    job = queue.enqueue("execute_step_job", {"step_run_id": step.id}).asdict()
    record_event(
        db,
        protocol_run_id,
        "step_enqueued",
        f"Step {step.step_name} enqueued for execution.",
        step_run_id=step.id,
        metadata={"job_id": job["job_id"]},
        request=request,
    )
    return schemas.ActionResponse(message=f"Step {step.step_name} enqueued", job=job)


@app.post("/protocols/{protocol_run_id}/actions/retry_latest", response_model=schemas.ActionResponse, dependencies=[Depends(require_auth)])
def retry_latest_step(
    protocol_run_id: int,
    db: BaseDatabase = Depends(get_db),
    queue: jobs.BaseQueue = Depends(get_queue),
    request: Request = None,
) -> schemas.ActionResponse:
    if request:
        project_id = get_protocol_project(protocol_run_id, db)
        require_project_access(project_id, request, db)
    steps = db.list_step_runs(protocol_run_id)
    target = next((s for s in reversed(steps) if s.status in (StepStatus.FAILED, StepStatus.BLOCKED)), None)
    if not target:
        raise HTTPException(status_code=404, detail="No failed or blocked steps to retry")
    try:
        step = db.update_step_status(
            target.id,
            StepStatus.RUNNING,
            retries=target.retries + 1,
            expected_status=target.status,
        )
    except ValueError:
        raise HTTPException(status_code=409, detail="Step state changed; retry")
    db.update_protocol_status(protocol_run_id, ProtocolStatus.RUNNING)
    job = queue.enqueue("execute_step_job", {"step_run_id": step.id}).asdict()
    record_event(
        db,
        protocol_run_id,
        "step_retry_enqueued",
        f"Retrying {step.step_name}.",
        step_run_id=step.id,
        metadata={"job_id": job["job_id"], "retries": step.retries},
        request=request,
    )
    return schemas.ActionResponse(message=f"Retrying {step.step_name}", job=job)


@app.post("/protocols/{protocol_run_id}/steps", response_model=schemas.StepRunOut, dependencies=[Depends(require_auth)])
def create_step(
    protocol_run_id: int,
    payload: schemas.StepRunCreate,
    db: BaseDatabase = Depends(get_db),
    request: Request = None,
) -> schemas.StepRunOut:
    try:
        db.get_protocol_run(protocol_run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if request:
        project_id = get_protocol_project(protocol_run_id, db)
        require_project_access(project_id, request, db)
    step = db.create_step_run(
        protocol_run_id=protocol_run_id,
        step_index=payload.step_index,
        step_name=payload.step_name,
        step_type=payload.step_type,
        status=payload.status,
        model=payload.model,
        engine_id=payload.engine_id,
        summary=payload.summary,
        policy=payload.policy,
    )
    return schemas.StepRunOut(**step.__dict__)


@app.get("/protocols/{protocol_run_id}/steps", response_model=list[schemas.StepRunOut], dependencies=[Depends(require_auth)])
def list_steps(protocol_run_id: int, db: BaseDatabase = Depends(get_db), request: Request = None) -> list[schemas.StepRunOut]:
    if request:
        try:
            project_id = get_protocol_project(protocol_run_id, db)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        require_project_access(project_id, request, db)
    steps = db.list_step_runs(protocol_run_id)
    return [schemas.StepRunOut(**s.__dict__) for s in steps]


@app.post("/steps/{step_id}/actions/run", response_model=schemas.ActionResponse, dependencies=[Depends(require_auth)])
def run_step(
    step_id: int,
    db: BaseDatabase = Depends(get_db),
    queue: jobs.BaseQueue = Depends(get_queue),
    request: Request = None,
) -> schemas.ActionResponse:
    try:
        step = db.get_step_run(step_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if step.status not in (StepStatus.PENDING, StepStatus.BLOCKED, StepStatus.FAILED):
        raise HTTPException(status_code=409, detail="Step already running or completed")
    if request:
        project_id = get_protocol_project(step.protocol_run_id, db)
        require_project_access(project_id, request, db)
    try:
        step = db.update_step_status(step.id, StepStatus.RUNNING, expected_status=step.status)
    except ValueError:
        raise HTTPException(status_code=409, detail="Step state changed; retry")
    db.update_protocol_status(step.protocol_run_id, ProtocolStatus.RUNNING)
    job = queue.enqueue("execute_step_job", {"step_run_id": step.id}).asdict()
    record_event(
        db,
        step.protocol_run_id,
        "step_enqueued",
        "Step execution enqueued.",
        step_run_id=step.id,
        metadata={"job_id": job["job_id"]},
        request=request,
    )
    return schemas.ActionResponse(message="Step execution enqueued", job=job)


@app.post("/steps/{step_id}/actions/run_qa", response_model=schemas.ActionResponse, dependencies=[Depends(require_auth)])
def run_step_qa(
    step_id: int,
    db: BaseDatabase = Depends(get_db),
    queue: jobs.BaseQueue = Depends(get_queue),
    request: Request = None,
) -> schemas.ActionResponse:
    try:
        step = db.get_step_run(step_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if step.status in (StepStatus.COMPLETED, StepStatus.CANCELLED):
        raise HTTPException(status_code=409, detail="Step already completed or cancelled")
    if request:
        project_id = get_protocol_project(step.protocol_run_id, db)
        require_project_access(project_id, request, db)
    try:
        step = db.update_step_status(step.id, StepStatus.NEEDS_QA, expected_status=step.status)
    except ValueError:
        raise HTTPException(status_code=409, detail="Step state changed; retry")
    job = queue.enqueue("run_quality_job", {"step_run_id": step.id}).asdict()
    record_event(
        db,
        step.protocol_run_id,
        "qa_enqueued",
        "QA run enqueued.",
        step_run_id=step.id,
        metadata={"job_id": job["job_id"]},
        request=request,
    )
    return schemas.ActionResponse(message="QA enqueued", job=job)


@app.post("/protocols/{protocol_run_id}/actions/open_pr", response_model=schemas.ActionResponse, dependencies=[Depends(require_auth)])
def open_pr_now(
    protocol_run_id: int,
    db: BaseDatabase = Depends(get_db),
    queue: jobs.BaseQueue = Depends(get_queue),
    request: Request = None,
) -> schemas.ActionResponse:
    if request:
        project_id = get_protocol_project(protocol_run_id, db)
        require_project_access(project_id, request, db)
    job = queue.enqueue("open_pr_job", {"protocol_run_id": protocol_run_id}).asdict()
    record_event(
        db,
        protocol_run_id,
        "open_pr_enqueued",
        "Open PR/MR job enqueued.",
        metadata={"job_id": job["job_id"]},
        request=request,
    )
    return schemas.ActionResponse(message="Open PR/MR enqueued", job=job)


@app.post("/steps/{step_id}/actions/approve", response_model=schemas.StepRunOut, dependencies=[Depends(require_auth)])
def approve_step(step_id: int, db: BaseDatabase = Depends(get_db), request: Request = None) -> schemas.StepRunOut:
    if request:
        try:
            project_id = get_step_project(step_id, db)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        require_project_access(project_id, request, db)
    try:
        step = db.update_step_status(step_id, StepStatus.COMPLETED)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    record_event(
        db,
        protocol_run_id=step.protocol_run_id,
        event_type="manual_approval",
        message="Step marked as completed manually.",
        step_run_id=step.id,
        request=request,
    )
    maybe_complete_protocol(step.protocol_run_id, db)
    return schemas.StepRunOut(**step.__dict__)


@app.get("/protocols/{protocol_run_id}/events", response_model=list[schemas.EventOut], dependencies=[Depends(require_auth)])
def list_events(protocol_run_id: int, db: BaseDatabase = Depends(get_db), request: Request = None) -> list[schemas.EventOut]:
    if request:
        try:
            project_id = get_protocol_project(protocol_run_id, db)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        require_project_access(project_id, request, db)
    events = db.list_events(protocol_run_id)
    return [schemas.EventOut(**e.__dict__) for e in events]


@app.get("/events", response_model=list[schemas.EventOut], dependencies=[Depends(require_auth)])
def recent_events(
    limit: int = 50,
    project_id: Optional[int] = None,
    kind: Optional[str] = Query(default=None, description="Filter to onboarding events when kind=onboarding"),
    db: BaseDatabase = Depends(get_db),
    request: Request = None,
) -> list[schemas.EventOut]:
    if project_id and request:
        require_project_access(project_id, request, db)
    events = db.list_recent_events(limit=limit, project_id=project_id)
    filtered = []
    for ev in events:
        if kind == "onboarding":
            if ev.event_type.startswith("setup_") or (ev.protocol_name or "").startswith("setup-"):
                filtered.append(ev)
        else:
            filtered.append(ev)
    return [schemas.EventOut(**e.__dict__) for e in filtered]


@app.get("/projects/{project_id}/onboarding", response_model=schemas.OnboardingSummary, dependencies=[Depends(require_auth)])
def onboarding_summary(project_id: int, db: BaseDatabase = Depends(get_db), request: Request = None) -> schemas.OnboardingSummary:
    if request:
        require_project_access(project_id, request, db)
    try:
        project = db.get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _onboarding_summary(project, db)


@app.get("/queues", dependencies=[Depends(require_auth)])
def queue_stats(queue: jobs.BaseQueue = Depends(get_queue)) -> dict:
    return queue.stats()


@app.get("/queues/jobs", dependencies=[Depends(require_auth)])
def queue_jobs(status: Optional[str] = None, queue: jobs.BaseQueue = Depends(get_queue)) -> list[dict]:
    jobs_list = queue.list(status=status)
    return [job.asdict() for job in jobs_list]


@app.post(
    "/webhooks/github",
    response_model=schemas.ActionResponse,
    dependencies=[Depends(require_auth)],
)
async def github_webhook(
    request: Request,
    protocol_run_id: Optional[int] = None,
    db: BaseDatabase = Depends(get_db),
    queue: jobs.BaseQueue = Depends(get_queue),
) -> schemas.ActionResponse:
    body = await request.body()
    payload = json.loads(body.decode("utf-8") or "{}")
    event_type = request.headers.get("X-GitHub-Event", "github")
    config = request.app.state.config  # type: ignore[attr-defined]
    token = config.webhook_token
    if token:
        sig = request.headers.get("X-Hub-Signature-256", "")
        if not verify_signature(token, body, sig):
            metrics.inc_webhook_status("github", "unauthorized")
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
    metrics.inc_webhook("github")
    action = payload.get("action", "")
    branch = payload.get("ref") or payload.get("branch")
    conclusion = None
    status = None
    pr_number = None
    check_name = None
    sha = payload.get("after")

    if event_type == "workflow_run":
        workflow = payload.get("workflow_run") or {}
        conclusion = workflow.get("conclusion") or workflow.get("status")
        status = workflow.get("status")
        branch = workflow.get("head_branch") or branch
        if workflow.get("pull_requests"):
            pr_number = workflow["pull_requests"][0].get("number")
    elif event_type in ("check_suite", "check_run"):
        check_payload = payload.get("check_suite") or payload.get("check_run") or {}
        conclusion = check_payload.get("conclusion")
        status = check_payload.get("status")
        branch = check_payload.get("head_branch") or check_payload.get("check_suite", {}).get("head_branch") or branch
        prs = check_payload.get("pull_requests") or []
        if prs:
            pr_number = prs[0].get("number")
        check_name = check_payload.get("name")
    elif event_type == "pull_request":
        pr = payload.get("pull_request") or {}
        branch = pr.get("head", {}).get("ref") or branch
        pr_number = pr.get("number")
        status = pr.get("state")
        conclusion = "merged" if pr.get("merged") else pr.get("state")
        sha = pr.get("head", {}).get("sha")
    elif event_type == "status":
        branch = (payload.get("branches") or [{}])[0].get("name") or branch
        conclusion = payload.get("state")
        status = payload.get("state")
    if not protocol_run_id:
        run = db.find_protocol_run_by_branch(branch or "")
    else:
        run = db.get_protocol_run(protocol_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Protocol run not found for webhook")
    step = db.latest_step_run(run.id)
    message = f"GitHub webhook {event_type} action={action} branch={branch} conclusion={conclusion} status={status} pr={pr_number}"
    metadata = {
        "pr_number": pr_number,
        "conclusion": conclusion,
        "status": status,
        "action": action,
        "check_name": check_name,
        "branch": branch,
        "sha": sha,
        "protocol_run_id": run.id,
        "step_run_id": step.id if step else None,
    }
    record_event(
        db,
        protocol_run_id=run.id,
        step_run_id=step.id if step else None,
        event_type=event_type,
        message=message,
        metadata=metadata,
        request=request,
    )

    normalized = (conclusion or status or "").lower()
    success_states = {"success", "neutral", "passed", "ok", "merged"}
    running_states = {"in_progress", "queued", "requested", "pending"}
    failure_states = {"failure", "timed_out", "cancelled", "canceled", "action_required", "error"}

    auto_qa = getattr(config, "auto_qa_on_ci", False)
    if step and normalized in success_states:
        if auto_qa:
            db.update_step_status(step.id, StepStatus.NEEDS_QA, summary="CI passed; running QA")
            job = queue.enqueue("run_quality_job", {"step_run_id": step.id}).asdict()
            record_event(
                db,
                run.id,
                "qa_enqueued",
                "QA enqueued after CI success.",
                step_run_id=step.id,
                metadata={"job_id": job["job_id"], "source": "ci_webhook", "provider": "github"},
                request=request,
            )
            try:
                # Inline drain for fakeredis so auto-QA completes in dev/test without a separate worker.
                if isinstance(queue, jobs.RedisQueue) and queue.is_fakeredis:
                    drain_once(queue, db)
            except Exception:
                pass
        else:
            db.update_step_status(step.id, StepStatus.COMPLETED, summary="CI passed")
            maybe_complete_protocol(run.id, db)
    elif step and normalized in running_states:
        db.update_step_status(step.id, StepStatus.RUNNING, summary="CI running")
    elif step and normalized in failure_states:
        db.update_step_status(step.id, StepStatus.FAILED, summary="CI failed")
        db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
        record_event(
            db,
            run.id,
            event_type,
            "CI failed; protocol blocked",
            step_run_id=step.id,
            metadata={"conclusion": conclusion},
            request=request,
        )

    if event_type == "pull_request" and payload.get("pull_request", {}).get("merged"):
        db.update_protocol_status(run.id, ProtocolStatus.COMPLETED)
        record_event(
            db,
            run.id,
            "pr_merged",
            "PR merged; protocol completed",
            metadata={"pr_number": pr_number},
            request=request,
        )

    return schemas.ActionResponse(message="Webhook recorded")


@app.post(
    "/webhooks/gitlab",
    response_model=schemas.ActionResponse,
    dependencies=[Depends(require_auth)],
)
async def gitlab_webhook(
    request: Request,
    protocol_run_id: Optional[int] = None,
    db: BaseDatabase = Depends(get_db),
    queue: jobs.BaseQueue = Depends(get_queue),
) -> schemas.ActionResponse:
    body = await request.body()
    payload = json.loads(body.decode("utf-8") or "{}")
    event_type = request.headers.get("X-Gitlab-Event", "gitlab")
    config = request.app.state.config  # type: ignore[attr-defined]
    token = config.webhook_token
    if token:
        sig = request.headers.get("X-Gitlab-Token") or request.headers.get("X-TasksGodzilla-Webhook-Token")
        if sig != token:
            metrics.inc_webhook_status("gitlab", "unauthorized")
            raise HTTPException(status_code=401, detail="Invalid webhook token")
        # Optional HMAC header (custom) X-Gitlab-Signature-256
        hmac_sig = request.headers.get("X-Gitlab-Signature-256")
        if hmac_sig and not verify_signature(token, body, hmac_sig):
            metrics.inc_webhook_status("gitlab", "unauthorized")
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
    metrics.inc_webhook("gitlab")
    object_kind = payload.get("object_kind") or event_type
    attrs = payload.get("object_attributes", {})
    status = attrs.get("status") or attrs.get("state")
    ref = attrs.get("ref") or payload.get("ref")
    branch = attrs.get("source_branch") or ref
    pr_number = attrs.get("iid")
    if not protocol_run_id:
        run = db.find_protocol_run_by_branch(branch or "")  # type: ignore[arg-type]
    else:
        run = db.get_protocol_run(protocol_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Protocol run not found for webhook")
    step = db.latest_step_run(run.id)
    message = f"GitLab webhook {object_kind} status={status} ref={branch}"
    metadata = {
        "status": status,
        "ref": branch,
        "event": object_kind,
        "pr_number": pr_number,
        "protocol_run_id": run.id,
        "step_run_id": step.id if step else None,
    }
    record_event(
        db,
        protocol_run_id=run.id,
        step_run_id=step.id if step else None,
        event_type=object_kind,
        message=message,
        metadata=metadata,
        request=request,
    )

    normalized = (status or "").lower()
    success_states = {"success", "passed", "merge"}
    running_states = {"running", "pending"}
    failure_states = {"failed", "canceled", "cancelled"}

    if object_kind == "merge_request" and attrs.get("state") == "merged":
        db.update_protocol_status(run.id, ProtocolStatus.COMPLETED)
        record_event(
            db,
            run.id,
            "mr_merged",
            "Merge request merged; protocol completed",
            metadata=metadata,
            request=request,
        )
    auto_qa = getattr(config, "auto_qa_on_ci", False)
    if step and normalized in success_states:
        if auto_qa:
            db.update_step_status(step.id, StepStatus.NEEDS_QA, summary="CI passed; running QA")
            job = queue.enqueue("run_quality_job", {"step_run_id": step.id}).asdict()
            record_event(
                db,
                run.id,
                "qa_enqueued",
                "QA enqueued after CI success.",
                step_run_id=step.id,
                metadata={"job_id": job["job_id"], "source": "ci_webhook", "provider": "gitlab"},
                request=request,
            )
        else:
            db.update_step_status(step.id, StepStatus.COMPLETED, summary="CI passed")
            maybe_complete_protocol(run.id, db)
    elif step and normalized in running_states:
        db.update_step_status(step.id, StepStatus.RUNNING, summary="CI running")
    elif step and normalized in failure_states:
        db.update_step_status(step.id, StepStatus.FAILED, summary="CI failed")
        db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
        record_event(
            db,
            run.id,
            object_kind,
            "CI failed; protocol blocked",
            step_run_id=step.id,
            metadata={"status": status, "ref": branch},
            request=request,
        )
    return schemas.ActionResponse(message="Webhook recorded")
