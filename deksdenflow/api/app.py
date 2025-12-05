import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional
import json

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from deksdenflow import jobs
from deksdenflow.config import load_config
from deksdenflow.domain import ProtocolStatus, StepStatus
from deksdenflow.logging import RequestIdFilter, get_logger, setup_logging
from deksdenflow.metrics import metrics
from deksdenflow.storage import Database
from deksdenflow.worker_runtime import BackgroundWorker
from hmac import compare_digest
import hmac
import hashlib

from . import schemas

logger = setup_logging()
auth_scheme = HTTPBearer(auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config()
    logger.info("Starting API", extra={"request_id": "-", "env": config.environment})
    db = Database(config.db_path)
    db.init_schema()
    queue = jobs.create_queue(config.redis_url)
    app.state.config = config  # type: ignore[attr-defined]
    app.state.db = db  # type: ignore[attr-defined]
    app.state.queue = queue  # type: ignore[attr-defined]
    app.state.metrics = metrics  # type: ignore[attr-defined]
    worker = None
    if isinstance(queue, jobs.InMemoryQueue):
        worker = BackgroundWorker(queue=queue, db=db)
        app.state.worker = worker  # type: ignore[attr-defined]
        worker.start()
    try:
        yield
    finally:
        if worker:
            worker.stop()
        logger.info("Shutting down API", extra={"request_id": "-"})


app = FastAPI(title="DeksdenFlow Orchestrator API", version="0.1.0", lifespan=lifespan)


def get_db(request: Request) -> Database:
    return request.app.state.db  # type: ignore[attr-defined]


def get_queue(request: Request) -> jobs.BaseQueue:
    return request.app.state.queue  # type: ignore[attr-defined]


def get_worker(request: Request) -> BackgroundWorker:
    return request.app.state.worker  # type: ignore[attr-defined]


def get_protocol_project(protocol_run_id: int, db: Database) -> int:
    run = db.get_protocol_run(protocol_run_id)
    return run.project_id


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


def require_project_access(project_id: int, request: Request, db: Database) -> None:
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
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
            "duration_ms": f"{duration_s * 1000:.2f}",
        },
    )
    return response


@app.get("/health", response_model=schemas.Health)
def health() -> schemas.Health:
    return schemas.Health()


@app.get("/metrics")
def metrics_endpoint():
    data = metrics.to_prometheus()
    from fastapi import Response

    return Response(content=data, media_type="text/plain; version=0.0.4")


@app.post("/projects", response_model=schemas.ProjectOut, dependencies=[Depends(require_auth)])
def create_project(payload: schemas.ProjectCreate, db: Database = Depends(get_db)) -> schemas.ProjectOut:
    project = db.create_project(
        name=payload.name,
        git_url=payload.git_url,
        base_branch=payload.base_branch,
        ci_provider=payload.ci_provider,
        default_models=payload.default_models,
        secrets=payload.secrets,
    )
    return schemas.ProjectOut(**project.__dict__)


@app.get("/projects", response_model=list[schemas.ProjectOut], dependencies=[Depends(require_auth)])
def list_projects(db: Database = Depends(get_db)) -> list[schemas.ProjectOut]:
    projects = db.list_projects()
    return [schemas.ProjectOut(**p.__dict__) for p in projects]


@app.get("/projects/{project_id}", response_model=schemas.ProjectOut, dependencies=[Depends(require_auth)])
def get_project(project_id: int, db: Database = Depends(get_db), request: Request = None) -> schemas.ProjectOut:
    if request:
        require_project_access(project_id, request, db)
    try:
        project = db.get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return schemas.ProjectOut(**project.__dict__)


@app.post("/projects/{project_id}/protocols", response_model=schemas.ProtocolRunOut, dependencies=[Depends(require_auth)])
def create_protocol_run(
    project_id: int,
    payload: schemas.ProtocolRunCreate,
    db: Database = Depends(get_db),
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
    )
    return schemas.ProtocolRunOut(**run.__dict__)


@app.get("/projects/{project_id}/protocols", response_model=list[schemas.ProtocolRunOut], dependencies=[Depends(require_auth)])
def list_protocol_runs(project_id: int, db: Database = Depends(get_db), request: Request = None) -> list[schemas.ProtocolRunOut]:
    if request:
        require_project_access(project_id, request, db)
    runs = db.list_protocol_runs(project_id)
    return [schemas.ProtocolRunOut(**r.__dict__) for r in runs]


@app.get("/protocols/{protocol_run_id}", response_model=schemas.ProtocolRunOut, dependencies=[Depends(require_auth)])
def get_protocol(protocol_run_id: int, db: Database = Depends(get_db), request: Request = None) -> schemas.ProtocolRunOut:
    if request:
        project_id = get_protocol_project(protocol_run_id, db)
        require_project_access(project_id, request, db)
    try:
        run = db.get_protocol_run(protocol_run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return schemas.ProtocolRunOut(**run.__dict__)


@app.post("/protocols/{protocol_run_id}/actions/start", response_model=schemas.ActionResponse, dependencies=[Depends(require_auth)])
def start_protocol(
    protocol_run_id: int,
    db: Database = Depends(get_db),
    queue: jobs.BaseQueue = Depends(get_queue),
    request: Request = None,
) -> schemas.ActionResponse:
    if request:
        project_id = get_protocol_project(protocol_run_id, db)
        require_project_access(project_id, request, db)
    try:
        db.update_protocol_status(protocol_run_id, ProtocolStatus.RUNNING)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    job = queue.enqueue("plan_protocol_job", {"protocol_run_id": protocol_run_id}).asdict()
    return schemas.ActionResponse(message="Protocol planning enqueued", job=job)


@app.post("/protocols/{protocol_run_id}/steps", response_model=schemas.StepRunOut, dependencies=[Depends(require_auth)])
def create_step(
    protocol_run_id: int,
    payload: schemas.StepRunCreate,
    db: Database = Depends(get_db),
) -> schemas.StepRunOut:
    try:
        db.get_protocol_run(protocol_run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    step = db.create_step_run(
        protocol_run_id=protocol_run_id,
        step_index=payload.step_index,
        step_name=payload.step_name,
        step_type=payload.step_type,
        status=payload.status,
        model=payload.model,
        summary=payload.summary,
    )
    return schemas.StepRunOut(**step.__dict__)


@app.get("/protocols/{protocol_run_id}/steps", response_model=list[schemas.StepRunOut], dependencies=[Depends(require_auth)])
def list_steps(protocol_run_id: int, db: Database = Depends(get_db)) -> list[schemas.StepRunOut]:
    steps = db.list_step_runs(protocol_run_id)
    return [schemas.StepRunOut(**s.__dict__) for s in steps]


@app.post("/steps/{step_id}/actions/run", response_model=schemas.ActionResponse, dependencies=[Depends(require_auth)])
def run_step(
    step_id: int,
    db: Database = Depends(get_db),
    queue: jobs.BaseQueue = Depends(get_queue),
    request: Request = None,
) -> schemas.ActionResponse:
    try:
        step = db.update_step_status(step_id, StepStatus.RUNNING)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if request:
        project_id = get_protocol_project(step.protocol_run_id, db)
        require_project_access(project_id, request, db)
    job = queue.enqueue("execute_step_job", {"step_run_id": step.id}).asdict()
    return schemas.ActionResponse(message="Step execution enqueued", job=job)


@app.post("/steps/{step_id}/actions/run_qa", response_model=schemas.ActionResponse, dependencies=[Depends(require_auth)])
def run_step_qa(
    step_id: int,
    db: Database = Depends(get_db),
    queue: jobs.BaseQueue = Depends(get_queue),
    request: Request = None,
) -> schemas.ActionResponse:
    try:
        step = db.update_step_status(step_id, StepStatus.NEEDS_QA)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if request:
        project_id = get_protocol_project(step.protocol_run_id, db)
        require_project_access(project_id, request, db)
    job = queue.enqueue("run_quality_job", {"step_run_id": step.id}).asdict()
    return schemas.ActionResponse(message="QA enqueued", job=job)


@app.post("/steps/{step_id}/actions/approve", response_model=schemas.StepRunOut, dependencies=[Depends(require_auth)])
def approve_step(step_id: int, db: Database = Depends(get_db)) -> schemas.StepRunOut:
    try:
        step = db.update_step_status(step_id, StepStatus.COMPLETED)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.append_event(
        protocol_run_id=step.protocol_run_id,
        step_run_id=step.id,
        event_type="manual_approval",
        message="Step marked as completed manually.",
    )
    return schemas.StepRunOut(**step.__dict__)


@app.get("/protocols/{protocol_run_id}/events", response_model=list[schemas.EventOut], dependencies=[Depends(require_auth)])
def list_events(protocol_run_id: int, db: Database = Depends(get_db)) -> list[schemas.EventOut]:
    events = db.list_events(protocol_run_id)
    return [schemas.EventOut(**e.__dict__) for e in events]


@app.get("/queues", dependencies=[Depends(require_auth)])
def queue_stats(queue: jobs.BaseQueue = Depends(get_queue)) -> dict:
    return queue.stats()


@app.get("/queues/jobs", dependencies=[Depends(require_auth)])
def queue_jobs(queue: jobs.BaseQueue = Depends(get_queue)) -> list[dict]:
    all_jobs = []
    for status in (None, "queued", "started", "failed"):
        all_jobs.extend(
            [
                {**job.asdict(), "status": status or job.status}
                for job in queue.list(status=status)
            ]
        )
    return all_jobs


@app.post(
    "/webhooks/github",
    response_model=schemas.ActionResponse,
    dependencies=[Depends(require_auth)],
)
async def github_webhook(
    request: Request,
    protocol_run_id: Optional[int] = None,
    db: Database = Depends(get_db),
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
    conclusion = payload.get("workflow_run", {}).get("conclusion")
    if not protocol_run_id:
        branch = payload.get("workflow_run", {}).get("head_branch") or payload.get("ref", "")
        run = db.find_protocol_run_by_branch(branch or "")
    else:
        run = db.get_protocol_run(protocol_run_id)
    branch = payload.get("workflow_run", {}).get("head_branch") or payload.get("ref", "")
    if not run:
        raise HTTPException(status_code=404, detail="Protocol run not found for webhook")
    step = db.latest_step_run(run.id)
    message = f"GitHub webhook {event_type} action={action} branch={branch} conclusion={conclusion}"
    db.append_event(
        protocol_run_id=run.id,
        step_run_id=step.id if step else None,
        event_type=event_type,
        message=message,
    )

    if conclusion in ("success", "neutral"):
        if step:
            db.update_step_status(step.id, StepStatus.COMPLETED, summary="CI passed")
    elif conclusion in ("failure", "timed_out", "cancelled"):
        if step:
            db.update_step_status(step.id, StepStatus.FAILED, summary="CI failed")
            db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)

    return schemas.ActionResponse(message="Webhook recorded")


@app.post(
    "/webhooks/gitlab",
    response_model=schemas.ActionResponse,
    dependencies=[Depends(require_auth)],
)
async def gitlab_webhook(
    request: Request,
    protocol_run_id: Optional[int] = None,
    db: Database = Depends(get_db),
) -> schemas.ActionResponse:
    body = await request.body()
    payload = json.loads(body.decode("utf-8") or "{}")
    event_type = request.headers.get("X-Gitlab-Event", "gitlab")
    config = request.app.state.config  # type: ignore[attr-defined]
    token = config.webhook_token
    if token:
        sig = request.headers.get("X-Gitlab-Token") or request.headers.get("X-Deksdenflow-Webhook-Token")
        if sig != token:
            metrics.inc_webhook_status("gitlab", "unauthorized")
            raise HTTPException(status_code=401, detail="Invalid webhook token")
    metrics.inc_webhook("gitlab")
    status = payload.get("object_attributes", {}).get("status")
    ref = payload.get("ref")
    ref = payload.get("ref")
    run = db.get_protocol_run(protocol_run_id) if protocol_run_id else db.find_protocol_run_by_branch(ref or "")  # type: ignore[arg-type]
    if not run:
        raise HTTPException(status_code=404, detail="Protocol run not found for webhook")
    step = db.latest_step_run(run.id)
    message = f"GitLab webhook {event_type} status={status} ref={ref}"
    db.append_event(
        protocol_run_id=run.id,
        step_run_id=step.id if step else None,
        event_type=event_type,
        message=message,
    )
    if status in ("success", "passed"):
        if step:
            db.update_step_status(step.id, StepStatus.COMPLETED, summary="CI passed")
    elif status in ("failed", "canceled"):
        if step:
            db.update_step_status(step.id, StepStatus.FAILED, summary="CI failed")
            db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
    return schemas.ActionResponse(message="Webhook recorded")
