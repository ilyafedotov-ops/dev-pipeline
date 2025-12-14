import html
import asyncio
import os
import time
import threading
import uuid
from dataclasses import asdict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
import json

from fastapi import Body, Depends, FastAPI, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse, JSONResponse

from tasksgodzilla import jobs
from tasksgodzilla.config import load_config
from tasksgodzilla.domain import ProtocolStatus, StepStatus
from tasksgodzilla.codemachine import ConfigError, config_to_template_payload, load_codemachine_config
from tasksgodzilla.codex import run_process
from tasksgodzilla.logging import log_context, log_extra, setup_logging, json_logging_from_env
from tasksgodzilla.metrics import metrics
from tasksgodzilla.storage import BaseDatabase, create_database
from tasksgodzilla.worker_runtime import RQWorkerThread, drain_once
from tasksgodzilla.health import check_db
from tasksgodzilla.spec import PROTOCOL_SPEC_KEY, SPEC_META_KEY, protocol_spec_hash
from tasksgodzilla.run_registry import RunRegistry
from tasksgodzilla.services import OrchestratorService, OnboardingService, CodeMachineService, ClarificationsService
from tasksgodzilla.services.policy import (
    PolicyService,
    validate_policy_override_definition,
    validate_policy_pack_definition,
)
from hmac import compare_digest
import hmac
import hashlib
from urllib.parse import quote

from . import schemas
from tasksgodzilla.git_utils import delete_remote_branch, list_remote_branches, resolve_project_repo_path
from tasksgodzilla.project_setup import local_repo_dir

logger = setup_logging(json_output=json_logging_from_env())
auth_scheme = HTTPBearer(auto_error=False)

try:  # Optional until OIDC is configured, but installed in requirements.
    from authlib.integrations.starlette_client import OAuth
except Exception:  # pragma: no cover - defensive for minimal deployments
    OAuth = None  # type: ignore[assignment]

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
    app.state.worker = None  # type: ignore[attr-defined]
    app.state.oauth = None  # type: ignore[attr-defined]
    if getattr(config, "oidc_enabled", False):
        if OAuth is None:
            logger.error("OIDC configured but authlib is unavailable", extra={"request_id": "-"})
        else:
            issuer = (config.oidc_issuer or "").rstrip("/")
            oauth = OAuth()
            oauth.register(
                name="oidc",
                client_id=config.oidc_client_id,
                client_secret=config.oidc_client_secret,
                server_metadata_url=f"{issuer}/.well-known/openid-configuration",
                client_kwargs={"scope": config.oidc_scopes},
            )
            app.state.oauth = oauth  # type: ignore[attr-defined]
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
    if config.inline_rq_worker and isinstance(queue, jobs.RedisQueue):
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

_SESSION_SECRET = os.environ.get("TASKSGODZILLA_SESSION_SECRET") or str(uuid.uuid4())
_SESSION_COOKIE_SECURE = os.environ.get("TASKSGODZILLA_SESSION_COOKIE_SECURE", "false").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
app.add_middleware(
    SessionMiddleware,
    secret_key=_SESSION_SECRET,
    session_cookie="tgz_session",
    same_site="lax",
    https_only=_SESSION_COOKIE_SECURE,
    max_age=60 * 60 * 24 * 7,
)

frontend_dir = Path(__file__).resolve().parent / "frontend"
if frontend_dir.exists():
    # Legacy (pre-Vite) console assets. Keep available, but do not occupy /console.
    app.mount("/console-legacy/static", StaticFiles(directory=frontend_dir), name="console-legacy-static")


def get_db(request: Request) -> BaseDatabase:
    return request.app.state.db  # type: ignore[attr-defined]


def get_queue(request: Request) -> jobs.BaseQueue:
    return request.app.state.queue  # type: ignore[attr-defined]


def get_worker(request: Request) -> Optional[RQWorkerThread]:
    return getattr(request.app.state, "worker", None)  # type: ignore[attr-defined]


def get_run_registry(db: BaseDatabase = Depends(get_db)) -> RunRegistry:
    return RunRegistry(db)


def get_protocol_project(protocol_run_id: int, db: BaseDatabase) -> int:
    run = db.get_protocol_run(protocol_run_id)
    return run.project_id


def get_step_project(step_run_id: int, db: BaseDatabase) -> int:
    step = db.get_step_run(step_run_id)
    return get_protocol_project(step.protocol_run_id, db)


def get_orchestrator(db: BaseDatabase = Depends(get_db)) -> OrchestratorService:
    """Dependency helper to construct an OrchestratorService for API routes."""
    return OrchestratorService(db=db)


def get_onboarding_service(db: BaseDatabase = Depends(get_db)) -> OnboardingService:
    """Dependency helper to construct an OnboardingService for API routes."""
    return OnboardingService(db=db)


def get_codemachine_service(db: BaseDatabase = Depends(get_db)) -> CodeMachineService:
    """Dependency helper to construct a CodeMachineService for API routes."""
    return CodeMachineService(db=db)


def get_policy_service(db: BaseDatabase = Depends(get_db)) -> PolicyService:
    return PolicyService(db=db)


def get_clarifications_service(db: BaseDatabase = Depends(get_db)) -> ClarificationsService:
    return ClarificationsService(db=db)


def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
) -> None:
    config = request.app.state.config  # type: ignore[attr-defined]
    # Prefer OIDC session auth for the web console when configured.
    if getattr(config, "oidc_enabled", False):
        try:
            user = getattr(request, "session", {}).get("user")
        except Exception:  # pragma: no cover - defensive
            user = None
        if user:
            return

    # Backward compatible admin/service token (still allowed when set).
    token = getattr(config, "api_token", None)
    if token:
        if credentials is None or credentials.scheme.lower() != "bearer" or credentials.credentials != token:
            raise HTTPException(status_code=401, detail="Unauthorized")
        return

    # No token configured: allow unauthenticated API access only when OIDC is not enabled.
    if getattr(config, "oidc_enabled", False):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return


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


def require_git_write_access(request: Request) -> None:
    """
    RBAC gate for destructive git operations (e.g., deleting remote branches).
    - When OIDC is enabled: requires a privileged role.
    - When using the admin bearer token: always allowed.
    """
    config = request.app.state.config  # type: ignore[attr-defined]
    admin_token = getattr(config, "api_token", None)
    if admin_token and request.headers.get("Authorization") == f"Bearer {admin_token}":
        return
    if not getattr(config, "oidc_enabled", False):
        # No RBAC model available; keep behavior backward compatible.
        return
    try:
        user = getattr(request, "session", {}).get("user") or {}
        roles = user.get("roles") or []
        if isinstance(roles, str):
            roles = [roles]
        roles_set = {str(r).lower() for r in roles}
    except Exception:
        roles_set = set()
    allowed = {"admin", "maintainer", "owner"}
    if roles_set & allowed:
        return
    raise HTTPException(status_code=403, detail="Forbidden")


def _repo_web_base_from_git_url(git_url: str) -> Optional[str]:
    """
    Best-effort normalize git remotes into a web base URL.
    Supports common GitHub/GitLab https + ssh formats.
    """
    url = (git_url or "").strip()
    if not url:
        return None
    # Local path
    if url.startswith("/") or url.startswith("."):
        return None
    host = None
    owner_repo = None
    if url.startswith("http"):
        if "github.com" in url:
            host = "github.com"
        elif "gitlab.com" in url:
            host = "gitlab.com"
        if host:
            owner_repo = url.split(f"{host}/", 1)[-1]
    elif url.startswith("git@"):
        # git@github.com:owner/repo.git
        if "github.com" in url:
            host = "github.com"
        elif "gitlab.com" in url:
            host = "gitlab.com"
        if host and ":" in url:
            owner_repo = url.split(":", 1)[-1]
    if not host or not owner_repo:
        return None
    owner_repo = owner_repo.rstrip("/").removesuffix(".git")
    if "/" not in owner_repo:
        return None
    return f"https://{host}/{owner_repo}"


def _pr_url(repo_web_base: Optional[str], provider: Optional[str], pr_number: Optional[int]) -> Optional[str]:
    if not repo_web_base or not provider or not pr_number:
        return None
    if provider == "github":
        return f"{repo_web_base}/pull/{pr_number}"
    if provider == "gitlab":
        return f"{repo_web_base}/-/merge_requests/{pr_number}"
    return None


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
    hint: Optional[str] = None
    if not run:
        hint = (
            "Onboarding has not started yet. Create the project again or run "
            "`python scripts/tasksgodzilla_cli.py projects onboarding-start <id>`."
        )
    else:
        event_types = [e.event_type for e in ev_out]
        has_enqueued = "setup_enqueued" in event_types
        has_progress = any(
            t
            in {
                "setup_started",
                "setup_cloned",
                "setup_discovery_started",
                "setup_discovery_completed",
                "setup_assets",
                "setup_completed",
            }
            for t in event_types
        )
        if has_enqueued and not has_progress:
            hint = (
                "Setup job is queued but not running. Start a worker with "
                "`.venv/bin/python scripts/rq_worker.py`, or restart the API with "
                "`TASKSGODZILLA_INLINE_RQ_WORKER=true` for inline processing."
            )
        else:
            discovery_stage = next((s for s in stages if s.key == "discovery"), None)
            if discovery_stage and discovery_stage.status == "skipped":
                if discovery_stage.message and "codex" in discovery_stage.message.lower():
                    hint = (
                        "Discovery was skipped because Codex is unavailable. Install the Codex CLI and "
                        "re-run onboarding to generate discovery artifacts."
                    )
    return schemas.OnboardingSummary(
        project_id=project.id,
        protocol_run_id=run.id if run else None,
        status=status,
        workspace_path=workspace_path,
        hint=hint,
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

    def _parse_int(value: Optional[str]) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except Exception:
            return None

    protocol_run_id = _parse_int(request.headers.get("X-Protocol-Run-ID"))
    step_run_id = _parse_int(request.headers.get("X-Step-Run-ID"))

    with log_context(request_id=request_id, protocol_run_id=protocol_run_id, step_run_id=step_run_id):
        response = await call_next(request)

    duration_s = (time.time() - start)
    metrics.observe_request(request.url.path, request.method, str(response.status_code), duration_s)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request",
        extra={
            **log_extra(request_id=request_id, protocol_run_id=protocol_run_id, step_run_id=step_run_id),
            "path": request.url.path,
            "method": request.method,
            "status_code": int(response.status_code),
            "duration_ms": duration_s * 1000.0,
            "client": request.client.host if request.client else None,
        },
    )
    return response


@app.get("/console-legacy", response_class=HTMLResponse)
def console_legacy() -> HTMLResponse:
    if not frontend_dir.exists():
        raise HTTPException(status_code=404, detail="Console assets not available")
    html = (frontend_dir / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)


def _get_console_dist_dir() -> Optional[Path]:
    # Prefer a checked-in build output (if present), otherwise use the dev build under web/console/dist.
    api_dir = Path(__file__).resolve().parent
    repo_root = Path(__file__).resolve().parents[2]
    candidates = [
        api_dir / "frontend_dist",
        repo_root / "web" / "console" / "dist",
    ]
    for d in candidates:
        if (d / "index.html").exists():
            return d
    return None


_console_dist_dir = _get_console_dist_dir()
if _console_dist_dir and (_console_dist_dir / "assets").exists():
    app.mount(
        "/console/assets",
        StaticFiles(directory=_console_dist_dir / "assets"),
        name="console-assets",
    )


def _oidc_required(request: Request) -> bool:
    config = request.app.state.config  # type: ignore[attr-defined]
    return bool(getattr(config, "oidc_enabled", False))


@app.get("/auth/login")
async def auth_login(request: Request, next: Optional[str] = None):
    config = request.app.state.config  # type: ignore[attr-defined]
    oauth = getattr(request.app.state, "oauth", None)  # type: ignore[attr-defined]
    if not getattr(config, "oidc_enabled", False):
        raise HTTPException(status_code=404, detail="OIDC not configured")
    if oauth is None:
        raise HTTPException(status_code=500, detail="OIDC client not initialized")
    if next:
        try:
            request.session["post_login_redirect"] = next
        except Exception:
            pass
    redirect_uri = str(request.url_for("auth_callback"))
    return await oauth.oidc.authorize_redirect(request, redirect_uri)  # type: ignore[union-attr]


@app.get("/auth/callback", name="auth_callback")
async def auth_callback(request: Request):
    config = request.app.state.config  # type: ignore[attr-defined]
    oauth = getattr(request.app.state, "oauth", None)  # type: ignore[attr-defined]
    if not getattr(config, "oidc_enabled", False):
        raise HTTPException(status_code=404, detail="OIDC not configured")
    if oauth is None:
        raise HTTPException(status_code=500, detail="OIDC client not initialized")
    token = await oauth.oidc.authorize_access_token(request)  # type: ignore[union-attr]
    userinfo = await oauth.oidc.parse_id_token(request, token)  # type: ignore[union-attr]
    user = {
        "sub": userinfo.get("sub"),
        "email": userinfo.get("email"),
        "name": userinfo.get("name") or userinfo.get("preferred_username"),
        "picture": userinfo.get("picture"),
        # Optional RBAC sources (provider-dependent).
        "roles": userinfo.get("roles") or userinfo.get("groups") or [],
    }
    try:
        request.session["user"] = user
    except Exception:
        pass
    try:
        next_url = request.session.pop("post_login_redirect", None)
    except Exception:
        next_url = None
    return RedirectResponse(url=next_url or "/console")


@app.get("/auth/me")
def auth_me(request: Request):
    config = request.app.state.config  # type: ignore[attr-defined]
    if not getattr(config, "oidc_enabled", False):
        return JSONResponse(content={"enabled": False, "user": None})
    try:
        user = getattr(request, "session", {}).get("user")
    except Exception:
        user = None
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return JSONResponse(content={"enabled": True, "user": user})


@app.post("/auth/logout")
def auth_logout(request: Request):
    try:
        request.session.clear()
    except Exception:
        pass
    return JSONResponse(content={"ok": True})


@app.get("/")
def root_redirect():
    return RedirectResponse(url="/console/", status_code=301)


@app.get("/console", response_class=HTMLResponse)
@app.get("/console/{path:path}", response_class=HTMLResponse)
def console(request: Request, path: str = ""):
    dist_dir = _get_console_dist_dir()
    if not dist_dir:
        raise HTTPException(status_code=404, detail="Console assets not available")
    if _oidc_required(request):
        try:
            user = getattr(request, "session", {}).get("user")
        except Exception:
            user = None
        if not user:
            next_url = "/console" + (f"/{path}" if path else "")
            return RedirectResponse(url=f"/auth/login?next={quote(next_url, safe='')}")
    html_text = (dist_dir / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html_text)


@app.get("/console/runs", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
def codex_runs_console(
    limit: int = Query(default=100, ge=1, le=500),
    db: BaseDatabase = Depends(get_db),
) -> HTMLResponse:
    runs = db.list_codex_runs(limit=limit)
    rows = []
    for run in runs:
        status = run.status.lower()
        run_id_safe = html.escape(run.run_id)
        kind_cell = html.escape(run.run_kind or run.job_type)
        project_cell = html.escape(str(run.project_id)) if run.project_id is not None else "-"
        protocol_cell = html.escape(str(run.protocol_run_id)) if run.protocol_run_id is not None else "-"
        step_cell = html.escape(str(run.step_run_id)) if run.step_run_id is not None else "-"
        attempt_cell = html.escape(str(run.attempt)) if run.attempt is not None else "-"
        worker_cell = html.escape(str(run.worker_id)) if run.worker_id else "-"
        log_cell = f'<a href="/codex/runs/{run_id_safe}/logs">logs</a>' if run.log_path else "-"
        rows.append(
            "<tr>"
            f"<td>{run_id_safe}</td>"
            f"<td>{html.escape(run.job_type)}</td>"
            f"<td>{kind_cell}</td>"
            f"<td>{project_cell}</td>"
            f"<td>{protocol_cell}</td>"
            f"<td>{step_cell}</td>"
            f"<td>{attempt_cell}</td>"
            f"<td>{worker_cell}</td>"
            f"<td><span class='pill status-{html.escape(status)}'>{html.escape(run.status)}</span></td>"
            f"<td>{html.escape(run.prompt_version or '-')}</td>"
            f"<td>{html.escape(run.created_at or '')}</td>"
            f"<td>{html.escape(run.started_at or '-')}</td>"
            f"<td>{html.escape(run.finished_at or '-')}</td>"
            f"<td>{log_cell}</td>"
            "</tr>"
        )
    rows_html = "\n".join(rows) if rows else "<tr><td colspan='14'>No runs yet</td></tr>"
    content = f"""
    <!doctype html>
    <html>
    <head>
        <title>Codex Runs</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 24px; background: #f8fafc; color: #0f172a; }}
            h2 {{ margin-bottom: 4px; }}
            p {{ margin-top: 0; color: #475569; }}
            table {{ border-collapse: collapse; width: 100%; background: #fff; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }}
            th, td {{ border: 1px solid #e2e8f0; padding: 8px; font-size: 14px; text-align: left; }}
            th {{ background: #f1f5f9; font-weight: 600; }}
            .pill {{ border-radius: 999px; padding: 2px 8px; font-size: 12px; text-transform: lowercase; }}
            .status-running {{ background: #dbeafe; color: #1d4ed8; }}
            .status-succeeded {{ background: #dcfce7; color: #166534; }}
            .status-failed {{ background: #fee2e2; color: #b91c1c; }}
            .status-cancelled {{ background: #fef9c3; color: #854d0e; }}
            .status-queued {{ background: #e2e8f0; color: #475569; }}
            a {{ color: #0ea5e9; }}
        </style>
    </head>
    <body>
        <h2>Codex Runs</h2>
        <p>Showing up to {len(runs)} run(s).</p>
        <table>
            <thead>
                <tr>
                    <th>Run ID</th>
                    <th>Job Type</th>
                    <th>Kind</th>
                    <th>Project</th>
                    <th>Protocol</th>
                    <th>Step</th>
                    <th>Attempt</th>
                    <th>Worker</th>
                    <th>Status</th>
                    <th>Prompt Version</th>
                    <th>Created</th>
                    <th>Started</th>
                    <th>Finished</th>
                    <th>Logs</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </body>
    </html>
    """
    return HTMLResponse(content=content)


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


@app.get("/codex/runs", response_model=list[schemas.CodexRunOut], dependencies=[Depends(require_auth)])
def list_codex_runs(
    job_type: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    project_id: Optional[int] = Query(default=None),
    protocol_run_id: Optional[int] = Query(default=None),
    step_run_id: Optional[int] = Query(default=None),
    run_kind: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: BaseDatabase = Depends(get_db),
):
    runs = db.list_codex_runs(
        job_type=job_type,
        status=status,
        project_id=project_id,
        protocol_run_id=protocol_run_id,
        step_run_id=step_run_id,
        run_kind=run_kind,
        limit=limit,
    )
    return [asdict(run) for run in runs]


@app.get(
    "/protocols/{protocol_run_id}/runs",
    response_model=list[schemas.CodexRunOut],
    dependencies=[Depends(require_auth)],
)
def list_codex_runs_for_protocol(
    protocol_run_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    run_kind: Optional[str] = Query(default=None),
    db: BaseDatabase = Depends(get_db),
    request: Request = None,
) -> list[dict]:
    if request:
        project_id = get_protocol_project(protocol_run_id, db)
        require_project_access(project_id, request, db)
    runs = db.list_codex_runs(protocol_run_id=protocol_run_id, run_kind=run_kind, limit=limit)
    return [asdict(run) for run in runs]


@app.get(
    "/steps/{step_run_id}/runs",
    response_model=list[schemas.CodexRunOut],
    dependencies=[Depends(require_auth)],
)
def list_codex_runs_for_step(
    step_run_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    run_kind: Optional[str] = Query(default=None),
    db: BaseDatabase = Depends(get_db),
    request: Request = None,
) -> list[dict]:
    if request:
        project_id = get_step_project(step_run_id, db)
        require_project_access(project_id, request, db)
    runs = db.list_codex_runs(step_run_id=step_run_id, run_kind=run_kind, limit=limit)
    return [asdict(run) for run in runs]


@app.post("/codex/runs/start", response_model=schemas.CodexRunOut, dependencies=[Depends(require_auth)])
def start_codex_run(
    payload: schemas.CodexRunCreate,
    registry: RunRegistry = Depends(get_run_registry),
) -> dict:
    log_path = Path(payload.log_path) if payload.log_path else None
    run = registry.start_run(
        job_type=payload.job_type,
        run_id=payload.run_id,
        params=payload.params,
        run_kind=payload.run_kind,
        project_id=payload.project_id,
        protocol_run_id=payload.protocol_run_id,
        step_run_id=payload.step_run_id,
        queue=payload.queue,
        attempt=payload.attempt,
        worker_id=payload.worker_id,
        prompt_version=payload.prompt_version,
        log_path=log_path,
        cost_tokens=payload.cost_tokens,
        cost_cents=payload.cost_cents,
    )
    return asdict(run)


@app.get("/codex/runs/{run_id}", response_model=schemas.CodexRunOut, dependencies=[Depends(require_auth)])
def get_codex_run(run_id: str, db: BaseDatabase = Depends(get_db)) -> dict:
    try:
        run = db.get_codex_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found")
    return asdict(run)


@app.get("/codex/runs/{run_id}/logs", response_class=PlainTextResponse, dependencies=[Depends(require_auth)])
def get_codex_run_logs(run_id: str, db: BaseDatabase = Depends(get_db)) -> PlainTextResponse:
    try:
        run = db.get_codex_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found")
    if not run.log_path:
        raise HTTPException(status_code=404, detail="Log path not recorded")
    log_path = Path(run.log_path)
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="Log file not found")
    try:
        content = log_path.read_text(encoding="utf-8")
    except Exception as exc:  # pragma: no cover - filesystem edge
        raise HTTPException(status_code=500, detail=f"Unable to read log file: {exc}") from exc
    return PlainTextResponse(content=content or "")


@app.get(
    "/codex/runs/{run_id}/logs/tail",
    response_model=schemas.LogTailResponse,
    dependencies=[Depends(require_auth)],
)
def tail_codex_run_logs(
    run_id: str,
    offset: int = Query(default=0, ge=0),
    max_bytes: int = Query(default=65536, ge=1024, le=1_000_000),
    db: BaseDatabase = Depends(get_db),
) -> schemas.LogTailResponse:
    """
    Incremental log reader for building a live console.
    Clients can poll with an offset and append the returned chunk.
    """
    try:
        run = db.get_codex_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found")
    if not run.log_path:
        raise HTTPException(status_code=404, detail="Log path not recorded")
    log_path = Path(run.log_path)
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="Log file not found")

    try:
        size = log_path.stat().st_size
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Unable to stat log file: {exc}") from exc

    safe_offset = min(offset, size)
    try:
        with log_path.open("rb") as f:
            f.seek(safe_offset)
            data = f.read(max_bytes)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Unable to read log file: {exc}") from exc

    next_offset = safe_offset + len(data)
    eof = next_offset >= size
    chunk = data.decode("utf-8", errors="replace")
    return schemas.LogTailResponse(
        run_id=run_id,
        offset=safe_offset,
        next_offset=next_offset,
        eof=eof,
        chunk=chunk,
    )


@app.get("/codex/runs/{run_id}/logs/stream", dependencies=[Depends(require_auth)])
async def stream_codex_run_logs(
    run_id: str,
    request: Request,
    offset: int = Query(default=0, ge=0),
    poll_interval_ms: int = Query(default=1000, ge=200, le=10000),
    db: BaseDatabase = Depends(get_db),
) -> StreamingResponse:
    """
    SSE log stream for operator-grade live tailing.
    Emits JSON payloads of the same shape as /logs/tail.
    """
    try:
        run = db.get_codex_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found")
    if not run.log_path:
        raise HTTPException(status_code=404, detail="Log path not recorded")
    log_path = Path(run.log_path)
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="Log file not found")

    async def _gen():
        current = offset
        while True:
            if await request.is_disconnected():
                break
            payload = await asyncio.to_thread(
                tail_codex_run_logs,
                run_id=run_id,
                offset=current,
                max_bytes=65536,
                db=db,
            )
            current = payload.next_offset
            if payload.chunk:
                data = json.dumps(payload.model_dump(), ensure_ascii=False)
                yield f"event: log\ndata: {data}\n\n"
            await asyncio.sleep(poll_interval_ms / 1000.0)

    return StreamingResponse(_gen(), media_type="text/event-stream")


@app.get(
    "/codex/runs/{run_id}/artifacts",
    response_model=list[schemas.RunArtifactOut],
    dependencies=[Depends(require_auth)],
)
def list_run_artifacts(
    run_id: str,
    kind: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: BaseDatabase = Depends(get_db),
) -> list[dict]:
    # Existence check for clearer errors.
    try:
        db.get_codex_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found")
    items = db.list_run_artifacts(run_id, kind=kind, limit=limit)
    return [asdict(item) for item in items]


@app.get(
    "/codex/runs/{run_id}/artifacts/{artifact_id}/content",
    response_class=PlainTextResponse,
    dependencies=[Depends(require_auth)],
)
def get_run_artifact_content(
    run_id: str,
    artifact_id: int,
    db: BaseDatabase = Depends(get_db),
) -> PlainTextResponse:
    try:
        artifact = db.get_run_artifact(artifact_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Artifact not found")
    if artifact.run_id != run_id:
        raise HTTPException(status_code=404, detail="Artifact not found for run")
    path = Path(artifact.path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact file not found")
    try:
        if path.stat().st_size > 1_000_000:
            raise HTTPException(status_code=413, detail="Artifact too large to display")
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Unable to stat artifact: {exc}") from exc
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Unable to read artifact: {exc}") from exc
    return PlainTextResponse(content=content or "")


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
        project_classification=payload.project_classification,
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


@app.get(
    "/projects/{project_id}/clarifications",
    response_model=list[schemas.ClarificationOut],
    dependencies=[Depends(require_auth)],
)
def list_project_clarifications(
    project_id: int,
    status: Optional[str] = None,
    limit: int = 200,
    db: BaseDatabase = Depends(get_db),
    request: Request = None,
) -> list[schemas.ClarificationOut]:
    if request:
        require_project_access(project_id, request, db)
    items = db.list_clarifications(project_id=project_id, status=status, limit=limit)
    return [schemas.ClarificationOut(**c.__dict__) for c in items]


@app.post(
    "/projects/{project_id}/clarifications/{key}",
    response_model=schemas.ClarificationOut,
    dependencies=[Depends(require_auth)],
)
def answer_project_clarification(
    project_id: int,
    key: str,
    payload: schemas.ClarificationAnswerRequest,
    clarifications: ClarificationsService = Depends(get_clarifications_service),
    db: BaseDatabase = Depends(get_db),
    request: Request = None,
) -> schemas.ClarificationOut:
    if request:
        require_project_access(project_id, request, db)
    try:
        answer_obj = (
            payload.answer
            if isinstance(payload.answer, dict)
            else ({"value": payload.answer} if payload.answer is not None else None)
        )
        updated = clarifications.set_clarification_answer(
            project_id=project_id,
            key=key,
            answer=answer_obj,
            answered_by=payload.answered_by,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return schemas.ClarificationOut(**updated.__dict__)


@app.get(
    "/protocols/{protocol_run_id}/clarifications",
    response_model=list[schemas.ClarificationOut],
    dependencies=[Depends(require_auth)],
)
def list_protocol_clarifications(
    protocol_run_id: int,
    status: Optional[str] = None,
    limit: int = 200,
    db: BaseDatabase = Depends(get_db),
    request: Request = None,
) -> list[schemas.ClarificationOut]:
    if request:
        project_id = get_protocol_project(protocol_run_id, db)
        require_project_access(project_id, request, db)
    items = db.list_clarifications(protocol_run_id=protocol_run_id, status=status, limit=limit)
    return [schemas.ClarificationOut(**c.__dict__) for c in items]


@app.post(
    "/protocols/{protocol_run_id}/clarifications/{key}",
    response_model=schemas.ClarificationOut,
    dependencies=[Depends(require_auth)],
)
def answer_protocol_clarification(
    protocol_run_id: int,
    key: str,
    payload: schemas.ClarificationAnswerRequest,
    clarifications: ClarificationsService = Depends(get_clarifications_service),
    db: BaseDatabase = Depends(get_db),
    request: Request = None,
) -> schemas.ClarificationOut:
    run = db.get_protocol_run(protocol_run_id)
    if request:
        require_project_access(run.project_id, request, db)
    try:
        answer_obj = (
            payload.answer
            if isinstance(payload.answer, dict)
            else ({"value": payload.answer} if payload.answer is not None else None)
        )
        updated = clarifications.set_clarification_answer(
            project_id=run.project_id,
            protocol_run_id=protocol_run_id,
            key=key,
            answer=answer_obj,
            answered_by=payload.answered_by,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return schemas.ClarificationOut(**updated.__dict__)


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
        require_git_write_access(request)
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
    orchestrator: OrchestratorService = Depends(get_orchestrator),
    policy_service: PolicyService = Depends(get_policy_service),
    request: Request = None,
) -> schemas.ProtocolRunOut:
    if request:
        require_project_access(project_id, request, db)
    try:
        db.get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    run = orchestrator.create_protocol_run(
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
    # Best-effort policy audit: record which policy was effective at creation time.
    try:
        effective = policy_service.resolve_effective_policy(project_id)
        policy_service.update_protocol_policy_audit(
            protocol_run_id=run.id,
            pack_key=effective.pack_key,
            pack_version=effective.pack_version,
            effective_hash=effective.effective_hash,
            policy=effective.policy if isinstance(effective.policy, dict) else None,
        )
        # Materialize protocol-level planning clarifications (if any).
        try:
            ClarificationsService(db).ensure_from_policy(
                project_id=project_id,
                policy=effective.policy if isinstance(effective.policy, dict) else {},
                applies_to="planning",
                protocol_run_id=run.id,
            )
        except Exception:
            pass
        run = db.get_protocol_run(run.id)
    except Exception:
        pass
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
    codemachine_service: CodeMachineService = Depends(get_codemachine_service),
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
        codemachine_service.import_workspace(project.id, run.id, payload.workspace_path)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    run = db.get_protocol_run(run.id)
    return schemas.CodeMachineImportResponse(
        protocol_run=_protocol_out(run, db=db),
        message="Imported CodeMachine workspace.",
        job=None,
    )



@app.get("/protocols", response_model=list[schemas.ProtocolRunOut], dependencies=[Depends(require_auth)])
def list_all_protocols(db: BaseDatabase = Depends(get_db)) -> list[schemas.ProtocolRunOut]:
    runs = db.list_all_protocol_runs()
    return [_protocol_out(r, db=db) for r in runs]


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


@app.get(
    "/protocols/{protocol_run_id}/ci/summary",
    response_model=schemas.CISummaryOut,
    dependencies=[Depends(require_auth)],
)
def protocol_ci_summary(
    protocol_run_id: int,
    db: BaseDatabase = Depends(get_db),
    request: Request = None,
) -> schemas.CISummaryOut:
    if request:
        project_id = get_protocol_project(protocol_run_id, db)
        require_project_access(project_id, request, db)
    run = db.get_protocol_run(protocol_run_id)
    project = db.get_project(run.project_id)
    repo_web_base = _repo_web_base_from_git_url(project.git_url)

    provider: Optional[str] = None
    pr_number: Optional[int] = None
    sha: Optional[str] = None
    status: Optional[str] = None
    conclusion: Optional[str] = None
    check_name: Optional[str] = None
    last_event_type: Optional[str] = None
    last_event_at: Optional[str] = None

    interesting = {
        "workflow_run",
        "check_suite",
        "check_run",
        "pull_request",
        "status",
        "merge_request",
        "pipeline",
    }
    for ev in reversed(db.list_events(protocol_run_id)):
        if ev.event_type not in interesting:
            continue
        meta = ev.metadata if isinstance(ev.metadata, dict) else {}
        # Prefer explicit provider if present.
        provider = meta.get("provider") or provider
        if not provider:
            provider = "gitlab" if ev.event_type in {"merge_request", "pipeline"} else "github"
        pr_number = meta.get("pr_number") if meta.get("pr_number") is not None else pr_number
        check_name = meta.get("check_name") if meta.get("check_name") is not None else check_name
        sha = meta.get("sha") if meta.get("sha") is not None else sha
        status = meta.get("status") if meta.get("status") is not None else status
        conclusion = meta.get("conclusion") if meta.get("conclusion") is not None else conclusion
        last_event_type = ev.event_type
        last_event_at = ev.created_at
        break

    pr_int: Optional[int] = None
    if isinstance(pr_number, int):
        pr_int = pr_number
    else:
        try:
            pr_int = int(str(pr_number)) if pr_number is not None else None
        except Exception:
            pr_int = None

    return schemas.CISummaryOut(
        protocol_run_id=protocol_run_id,
        provider=provider,
        pr_number=pr_int,
        pr_url=_pr_url(repo_web_base, provider, pr_int),
        sha=str(sha) if sha else None,
        status=str(status) if status else None,
        conclusion=str(conclusion) if conclusion else None,
        check_name=str(check_name) if check_name else None,
        last_event_type=last_event_type,
        last_event_at=last_event_at,
    )


@app.get(
    "/protocols/{protocol_run_id}/git/status",
    response_model=schemas.GitStatusOut,
    dependencies=[Depends(require_auth)],
)
def protocol_git_status(
    protocol_run_id: int,
    db: BaseDatabase = Depends(get_db),
    request: Request = None,
) -> schemas.GitStatusOut:
    if request:
        project_id = get_protocol_project(protocol_run_id, db)
        require_project_access(project_id, request, db)
    run = db.get_protocol_run(protocol_run_id)
    project = db.get_project(run.project_id)
    try:
        repo_root = resolve_project_repo_path(
            project.git_url,
            project.name,
            project.local_path,
            project_id=project.id,
            clone_if_missing=False,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    worktree_path = Path(run.worktree_path) if run.worktree_path else repo_root
    if not worktree_path.exists():
        raise HTTPException(status_code=409, detail="Worktree path not available")

    if not (worktree_path / ".git").exists():
        return schemas.GitStatusOut(
            protocol_run_id=protocol_run_id,
            repo_root=str(repo_root),
            worktree_path=str(worktree_path),
            branch=None,
            head_sha=None,
            dirty=False,
            changed_files=[],
        )

    try:
        branch_res = run_process(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=worktree_path, capture_output=True, text=True)
        head_res = run_process(["git", "rev-parse", "HEAD"], cwd=worktree_path, capture_output=True, text=True)
        status_res = run_process(["git", "status", "--porcelain"], cwd=worktree_path, capture_output=True, text=True)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Unable to query git status: {exc}") from exc

    branch = (branch_res.stdout or "").strip() if hasattr(branch_res, "stdout") else None
    head_sha = (head_res.stdout or "").strip() if hasattr(head_res, "stdout") else None
    raw_status = (status_res.stdout or "").strip() if hasattr(status_res, "stdout") else ""
    changed_files = []
    if raw_status:
        for line in raw_status.splitlines():
            # Format: XY path
            if len(line) >= 4:
                changed_files.append(line[3:])

    return schemas.GitStatusOut(
        protocol_run_id=protocol_run_id,
        repo_root=str(repo_root),
        worktree_path=str(worktree_path),
        branch=branch or None,
        head_sha=head_sha or None,
        dirty=bool(raw_status),
        changed_files=changed_files,
    )


@app.post("/protocols/{protocol_run_id}/actions/start", response_model=schemas.ActionResponse, dependencies=[Depends(require_auth)])
def start_protocol(
    protocol_run_id: int,
    db: BaseDatabase = Depends(get_db),
    queue: jobs.BaseQueue = Depends(get_queue),
    orchestrator: OrchestratorService = Depends(get_orchestrator),
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
        job_obj = orchestrator.start_protocol_run(protocol_run_id, queue)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    job = job_obj.asdict()
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
    orchestrator: OrchestratorService = Depends(get_orchestrator),
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
        run = orchestrator.pause_protocol(protocol_run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    record_event(db, protocol_run_id, "paused", "Protocol paused by user.", request=request)
    return _protocol_out(run, db=db)


@app.post("/protocols/{protocol_run_id}/actions/resume", response_model=schemas.ProtocolRunOut, dependencies=[Depends(require_auth)])
def resume_protocol(
    protocol_run_id: int,
    db: BaseDatabase = Depends(get_db),
    orchestrator: OrchestratorService = Depends(get_orchestrator),
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
        run = orchestrator.resume_protocol(protocol_run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    record_event(db, protocol_run_id, "resumed", "Protocol resumed by user.", request=request)
    return _protocol_out(run, db=db)


@app.post("/protocols/{protocol_run_id}/actions/cancel", response_model=schemas.ProtocolRunOut, dependencies=[Depends(require_auth)])
def cancel_protocol(
    protocol_run_id: int,
    db: BaseDatabase = Depends(get_db),
    orchestrator: OrchestratorService = Depends(get_orchestrator),
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
        run = orchestrator.cancel_protocol(protocol_run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    record_event(db, protocol_run_id, "cancelled", "Protocol cancelled by user.", request=request)
    return _protocol_out(run, db=db)


@app.post("/protocols/{protocol_run_id}/actions/run_next_step", response_model=schemas.ActionResponse, dependencies=[Depends(require_auth)])
def run_next_step(
    protocol_run_id: int,
    db: BaseDatabase = Depends(get_db),
    queue: jobs.BaseQueue = Depends(get_queue),
    orchestrator: OrchestratorService = Depends(get_orchestrator),
    request: Request = None,
) -> schemas.ActionResponse:
    if request:
        project_id = get_protocol_project(protocol_run_id, db)
        require_project_access(project_id, request, db)
    try:
        step, job_obj = orchestrator.enqueue_next_step(protocol_run_id, queue)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    job = job_obj.asdict()
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
    orchestrator: OrchestratorService = Depends(get_orchestrator),
    request: Request = None,
) -> schemas.ActionResponse:
    if request:
        project_id = get_protocol_project(protocol_run_id, db)
        require_project_access(project_id, request, db)
    try:
        step, job_obj = orchestrator.retry_latest_step(protocol_run_id, queue)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    job = job_obj.asdict()
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


@app.get("/steps", response_model=list[schemas.StepRunOut], dependencies=[Depends(require_auth)])
def list_all_steps(db: BaseDatabase = Depends(get_db)) -> list[schemas.StepRunOut]:
    steps = db.list_all_step_runs()
    return [schemas.StepRunOut(**s.__dict__) for s in steps]


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
    orchestrator: OrchestratorService = Depends(get_orchestrator),
    request: Request = None,
) -> schemas.ActionResponse:
    try:
        step = db.get_step_run(step_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if request:
        project_id = get_protocol_project(step.protocol_run_id, db)
        require_project_access(project_id, request, db)
    try:
        job_obj = orchestrator.run_step(step.id, queue)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    job = job_obj.asdict()
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
    orchestrator: OrchestratorService = Depends(get_orchestrator),
    request: Request = None,
) -> schemas.ActionResponse:
    try:
        step = db.get_step_run(step_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if request:
        project_id = get_protocol_project(step.protocol_run_id, db)
        require_project_access(project_id, request, db)
    try:
        job_obj = orchestrator.run_step_qa(step.id, queue)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    job = job_obj.asdict()
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
    orchestrator: OrchestratorService = Depends(get_orchestrator),
    request: Request = None,
) -> schemas.ActionResponse:
    if request:
        project_id = get_protocol_project(protocol_run_id, db)
        require_project_access(project_id, request, db)
    job = orchestrator.enqueue_open_protocol_pr(protocol_run_id, queue).asdict()
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
def approve_step(
    step_id: int,
    db: BaseDatabase = Depends(get_db),
    orchestrator: OrchestratorService = Depends(get_orchestrator),
    request: Request = None
) -> schemas.StepRunOut:
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
    orchestrator.check_and_complete_protocol(step.protocol_run_id)
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


@app.get("/policy_packs", response_model=list[schemas.PolicyPackOut], dependencies=[Depends(require_auth)])
def list_policy_packs(
    key: Optional[str] = None,
    status: Optional[str] = None,
    db: BaseDatabase = Depends(get_db),
) -> list[schemas.PolicyPackOut]:
    packs = db.list_policy_packs(key=key, status=status)
    return [schemas.PolicyPackOut(**p.__dict__) for p in packs]


@app.post("/policy_packs", response_model=schemas.PolicyPackOut, dependencies=[Depends(require_auth)])
def upsert_policy_pack(
    payload: schemas.PolicyPackCreate,
    db: BaseDatabase = Depends(get_db),
) -> schemas.PolicyPackOut:
    errors = validate_policy_pack_definition(pack_key=payload.key, pack_version=payload.version, pack=payload.pack)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})
    pack = db.upsert_policy_pack(
        key=payload.key,
        version=payload.version,
        name=payload.name,
        description=payload.description,
        status=payload.status,
        pack=payload.pack,
    )
    return schemas.PolicyPackOut(**pack.__dict__)


@app.get("/projects/{project_id}/policy", response_model=schemas.ProjectPolicyOut, dependencies=[Depends(require_auth)])
def get_project_policy(
    project_id: int,
    db: BaseDatabase = Depends(get_db),
    request: Request = None,
) -> schemas.ProjectPolicyOut:
    if request:
        require_project_access(project_id, request, db)
    proj = db.get_project(project_id)
    return schemas.ProjectPolicyOut(
        project_id=proj.id,
        policy_pack_key=proj.policy_pack_key,
        policy_pack_version=proj.policy_pack_version,
        policy_overrides=proj.policy_overrides,
        policy_repo_local_enabled=proj.policy_repo_local_enabled,
        policy_effective_hash=proj.policy_effective_hash,
        policy_enforcement_mode=proj.policy_enforcement_mode,
    )


@app.put("/projects/{project_id}/policy", response_model=schemas.ProjectPolicyOut, dependencies=[Depends(require_auth)])
def update_project_policy(
    project_id: int,
    payload: schemas.ProjectPolicyUpdate,
    db: BaseDatabase = Depends(get_db),
    policy_service: PolicyService = Depends(get_policy_service),
    request: Request = None,
) -> schemas.ProjectPolicyOut:
    if request:
        require_project_access(project_id, request, db)
    if payload.clear_policy_pack_version and payload.policy_pack_version is not None:
        raise HTTPException(
            status_code=400,
            detail={"errors": ["clear_policy_pack_version cannot be used with policy_pack_version"]},
        )
    if payload.policy_overrides is not None:
        errors = validate_policy_override_definition(payload.policy_overrides)
        if errors:
            raise HTTPException(status_code=400, detail={"errors": errors})
    proj = db.update_project_policy(
        project_id,
        policy_pack_key=payload.policy_pack_key,
        policy_pack_version=payload.policy_pack_version,
        clear_policy_pack_version=bool(payload.clear_policy_pack_version),
        policy_overrides=payload.policy_overrides,
        policy_repo_local_enabled=payload.policy_repo_local_enabled,
        policy_enforcement_mode=payload.policy_enforcement_mode,
    )
    # Compute and persist effective hash for quick visibility in UI.
    effective = policy_service.resolve_effective_policy(project_id)
    policy_service.update_project_policy_effective_hash(project_id, effective.effective_hash)
    proj = db.get_project(project_id)
    return schemas.ProjectPolicyOut(
        project_id=proj.id,
        policy_pack_key=proj.policy_pack_key,
        policy_pack_version=proj.policy_pack_version,
        policy_overrides=proj.policy_overrides,
        policy_repo_local_enabled=proj.policy_repo_local_enabled,
        policy_effective_hash=proj.policy_effective_hash,
        policy_enforcement_mode=proj.policy_enforcement_mode,
    )


@app.get(
    "/projects/{project_id}/policy/effective",
    response_model=schemas.EffectivePolicyOut,
    dependencies=[Depends(require_auth)],
)
def get_effective_policy(
    project_id: int,
    db: BaseDatabase = Depends(get_db),
    policy_service: PolicyService = Depends(get_policy_service),
    request: Request = None,
) -> schemas.EffectivePolicyOut:
    if request:
        require_project_access(project_id, request, db)
    effective = policy_service.resolve_effective_policy(project_id)
    policy_service.update_project_policy_effective_hash(project_id, effective.effective_hash)
    return schemas.EffectivePolicyOut(
        project_id=project_id,
        policy_pack_key=effective.pack_key,
        policy_pack_version=effective.pack_version,
        policy_effective_hash=effective.effective_hash,
        policy=effective.policy,
        sources=effective.sources,
    )


@app.get(
    "/projects/{project_id}/policy/findings",
    response_model=list[schemas.PolicyFindingOut],
    dependencies=[Depends(require_auth)],
)
def project_policy_findings(
    project_id: int,
    db: BaseDatabase = Depends(get_db),
    policy_service: PolicyService = Depends(get_policy_service),
    request: Request = None,
) -> list[schemas.PolicyFindingOut]:
    if request:
        require_project_access(project_id, request, db)
    findings = policy_service.evaluate_project(project_id)
    return [schemas.PolicyFindingOut(**f.asdict()) for f in findings]


@app.get(
    "/protocols/{protocol_run_id}/policy/findings",
    response_model=list[schemas.PolicyFindingOut],
    dependencies=[Depends(require_auth)],
)
def protocol_policy_findings(
    protocol_run_id: int,
    db: BaseDatabase = Depends(get_db),
    policy_service: PolicyService = Depends(get_policy_service),
    request: Request = None,
) -> list[schemas.PolicyFindingOut]:
    if request:
        project_id = get_protocol_project(protocol_run_id, db)
        require_project_access(project_id, request, db)
    findings = policy_service.evaluate_protocol(protocol_run_id)
    return [schemas.PolicyFindingOut(**f.asdict()) for f in findings]


@app.get(
    "/protocols/{protocol_run_id}/policy/snapshot",
    response_model=schemas.ProtocolPolicySnapshotOut,
    dependencies=[Depends(require_auth)],
)
def protocol_policy_snapshot(
    protocol_run_id: int,
    db: BaseDatabase = Depends(get_db),
    request: Request = None,
) -> schemas.ProtocolPolicySnapshotOut:
    if request:
        project_id = get_protocol_project(protocol_run_id, db)
        require_project_access(project_id, request, db)
    try:
        run = db.get_protocol_run(protocol_run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return schemas.ProtocolPolicySnapshotOut(
        protocol_run_id=run.id,
        policy_pack_key=run.policy_pack_key,
        policy_pack_version=run.policy_pack_version,
        policy_effective_hash=run.policy_effective_hash,
        policy_effective_json=getattr(run, "policy_effective_json", None),
    )


@app.get(
    "/steps/{step_run_id}/policy/findings",
    response_model=list[schemas.PolicyFindingOut],
    dependencies=[Depends(require_auth)],
)
def step_policy_findings(
    step_run_id: int,
    db: BaseDatabase = Depends(get_db),
    policy_service: PolicyService = Depends(get_policy_service),
    request: Request = None,
) -> list[schemas.PolicyFindingOut]:
    if request:
        project_id = get_step_project(step_run_id, db)
        require_project_access(project_id, request, db)
    findings = policy_service.evaluate_step(step_run_id)
    return [schemas.PolicyFindingOut(**f.asdict()) for f in findings]


@app.post(
    "/projects/{project_id}/onboarding/actions/start",
    response_model=schemas.ActionResponse,
    dependencies=[Depends(require_auth)],
)
def start_onboarding(
    project_id: int,
    payload: schemas.OnboardingStartRequest = Body(default=schemas.OnboardingStartRequest()),
    db: BaseDatabase = Depends(get_db),
    queue: jobs.BaseQueue = Depends(get_queue),
    onboarding: OnboardingService = Depends(get_onboarding_service),
    request: Request = None,
) -> schemas.ActionResponse:
    """
    Trigger (or re-trigger) onboarding for an existing project. This mirrors the
    behaviour used in `POST /projects` but can be called explicitly from the
    console.
    """
    if request:
        require_project_access(project_id, request, db)
    try:
        project = db.get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    protocol_name = f"setup-{project.id}"
    try:
        setup_run = db.find_protocol_run_by_name(protocol_name)
    except Exception:
        setup_run = None
    if not setup_run:
        setup_run = db.create_protocol_run(
            project_id=project.id,
            protocol_name=protocol_name,
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
        message="Project setup requested.",
        request=request,
    )
    if payload.inline:
        # Run setup in-process for convenience when no worker is available.
        onboarding.run_project_setup_job(project.id, protocol_run_id=setup_run.id)
        return schemas.ActionResponse(message="Project setup ran inline.", job=None)

    job = queue.enqueue(
        "project_setup_job",
        {"project_id": project.id, "protocol_run_id": setup_run.id},
    ).asdict()
    return schemas.ActionResponse(message="Project setup enqueued", job=job)


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
    orchestrator: OrchestratorService = Depends(get_orchestrator),
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
                if config.inline_rq_worker:
                    drain_once(queue, db)
            except Exception:
                pass
        else:
            db.update_step_status(step.id, StepStatus.COMPLETED, summary="CI passed")
            orchestrator.check_and_complete_protocol(run.id)
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
    orchestrator: OrchestratorService = Depends(get_orchestrator),
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
            orchestrator.check_and_complete_protocol(run.id)
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
