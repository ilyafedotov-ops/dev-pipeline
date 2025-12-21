"""
DevGodzilla Webhook Handlers

Handles incoming webhooks from Windmill and CI/CD systems.
"""

import json
import hashlib
import hmac
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel

from devgodzilla.api.dependencies import get_db
from devgodzilla.config import load_config
from devgodzilla.db.database import Database
from devgodzilla.logging import get_logger
from devgodzilla.models.domain import ProtocolStatus, StepStatus
from devgodzilla.services.base import ServiceContext
from devgodzilla.services.orchestrator import OrchestratorMode, OrchestratorResult, OrchestratorService
from devgodzilla.windmill.client import WindmillClient, WindmillConfig

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
logger = get_logger(__name__)


# ==================== Request Models ====================

class WindmillJobUpdate(BaseModel):
    """Windmill job status update."""
    job_id: str
    status: str  # running, success, failure, cancelled
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class GitHubWebhook(BaseModel):
    """GitHub webhook payload."""
    action: str
    repository: Dict[str, Any]
    sender: Dict[str, Any]
    # Workflow run specific
    workflow_run: Optional[Dict[str, Any]] = None
    # Check run specific
    check_run: Optional[Dict[str, Any]] = None
    # Pull request specific
    pull_request: Optional[Dict[str, Any]] = None


class GitLabWebhook(BaseModel):
    """GitLab webhook payload."""
    object_kind: str
    project: Dict[str, Any]
    user: Dict[str, Any]
    # Pipeline specific
    object_attributes: Optional[Dict[str, Any]] = None


def _normalize_repo_url(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = value.strip().lower()
    if text.endswith(".git"):
        text = text[:-4]
    if text.startswith("git@"):
        text = text.replace("git@", "", 1)
        text = text.replace(":", "/", 1)
    if text.startswith("https://"):
        text = text[len("https://") :]
    elif text.startswith("http://"):
        text = text[len("http://") :]
    return text.strip("/")


def _resolve_project_id(db: Database, candidates: list[str]) -> Optional[int]:
    normalized = {_normalize_repo_url(value) for value in candidates if value}
    normalized.discard(None)
    if not normalized:
        return None
    for project in db.list_projects():
        project_url = _normalize_repo_url(project.git_url)
        if project_url and project_url in normalized:
            return project.id
    return None


def _emit_ci_event(
    db: Database,
    *,
    event_type: str,
    message: str,
    project_id: Optional[int],
    protocol_run_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    if project_id is None and protocol_run_id is None:
        return
    try:
        db.append_event(
            protocol_run_id=protocol_run_id,
            project_id=project_id,
            event_type=event_type,
            message=message,
            metadata=metadata,
        )
    except Exception as exc:
        logger.error(
            "ci_event_persist_failed",
            extra={"event_type": event_type, "error": str(exc)},
        )


def _build_orchestrator(db: Database) -> OrchestratorService:
    config = load_config()
    ctx = ServiceContext(config=config)
    windmill_client = None
    mode = OrchestratorMode.LOCAL
    if getattr(config, "windmill_enabled", False):
        windmill_client = WindmillClient(
            WindmillConfig(
                base_url=config.windmill_url or "http://localhost:8000",
                token=config.windmill_token or "",
                workspace=getattr(config, "windmill_workspace", "devgodzilla"),
            )
        )
        mode = OrchestratorMode.WINDMILL
    return OrchestratorService(context=ctx, db=db, windmill_client=windmill_client, mode=mode)


def _extract_protocol_run_id(payload: dict) -> Optional[int]:
    candidates = [
        payload.get("protocol_run_id"),
        payload.get("protocolRunId"),
    ]
    for key in ("input", "flow_input", "args", "metadata", "context"):
        value = payload.get(key)
        if isinstance(value, dict):
            candidates.append(value.get("protocol_run_id"))
            candidates.append(value.get("protocolRunId"))
    for value in candidates:
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def _extract_flow_path(payload: dict) -> Optional[str]:
    direct = payload.get("flow_path") or payload.get("flow_id") or payload.get("path")
    if isinstance(direct, str):
        return direct
    flow = payload.get("flow")
    if isinstance(flow, dict):
        for key in ("path", "flow_path", "id"):
            if isinstance(flow.get(key), str):
                return flow.get(key)
    return None


def _extract_status(payload: dict) -> Optional[str]:
    for key in ("status", "state", "conclusion", "result"):
        value = payload.get(key)
        if isinstance(value, str):
            return value.lower()
        if isinstance(value, dict):
            inner = value.get("status") or value.get("state") or value.get("conclusion")
            if isinstance(inner, str):
                return inner.lower()
    return None


def _is_success_status(value: Optional[str]) -> bool:
    return value in ("success", "succeeded", "completed", "ok", "passed")


def _is_failure_status(value: Optional[str]) -> bool:
    return value in ("failure", "failed", "cancelled", "canceled", "error", "timed_out")


def _verify_github_signature(secret: str, body: bytes, signature_header: Optional[str]) -> bool:
    if not signature_header:
        return False
    algo, _, signature = signature_header.partition("=")
    algo = algo.strip().lower()
    signature = signature.strip()
    if not signature:
        return False
    if algo == "sha256":
        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    elif algo == "sha1":
        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha1).hexdigest()
    else:
        return False
    return hmac.compare_digest(digest, signature)


def _verify_gitlab_token(secret: str, token: Optional[str]) -> bool:
    if not token:
        return False
    return hmac.compare_digest(token, secret)


def _maybe_advance_protocol_on_ci(
    db: Database,
    *,
    protocol_run_id: Optional[int],
) -> Optional[OrchestratorResult]:
    if protocol_run_id is None:
        return None

    try:
        run = db.get_protocol_run(protocol_run_id)
    except KeyError:
        return None

    if run.status in (
        ProtocolStatus.PAUSED,
        ProtocolStatus.BLOCKED,
        ProtocolStatus.CANCELLED,
        ProtocolStatus.COMPLETED,
        ProtocolStatus.FAILED,
    ):
        return OrchestratorResult(
            success=False,
            error=f"Protocol in {run.status} state",
        )

    steps = db.list_step_runs(protocol_run_id)
    if any(s.status in (StepStatus.RUNNING, StepStatus.NEEDS_QA) for s in steps):
        return OrchestratorResult(success=False, error="Protocol has in-flight steps")

    orchestrator = _build_orchestrator(db)
    return orchestrator.enqueue_next_step(protocol_run_id)


# ==================== Windmill Webhooks ====================

@router.post("/windmill/job")
async def windmill_job_webhook(
    payload: WindmillJobUpdate,
    request: Request,
    db: Database = Depends(get_db),
):
    """
    Handle Windmill job status updates.
    
    Called by Windmill when a job completes, fails, or is cancelled.
    Updates the corresponding protocol/step run in the database.
    """
    logger.info(
        "windmill_webhook_received",
        extra={
            "job_id": payload.job_id,
            "status": payload.status,
        },
    )
    
    status_map = {
        "queued": "queued",
        "running": "running",
        "success": "succeeded",
        "completed": "succeeded",
        "failure": "failed",
        "failed": "failed",
        "cancelled": "cancelled",
        "canceled": "cancelled",
    }

    try:
        db.update_job_run_by_windmill_id(
            payload.job_id,
            status=status_map.get(payload.status.lower(), payload.status.lower()),
            result=payload.result,
            error=payload.error,
            started_at=payload.started_at.isoformat() if payload.started_at else None,
            finished_at=payload.finished_at.isoformat() if payload.finished_at else None,
        )
    except KeyError as exc:
        # Webhook can arrive before we persist the job run; don't fail the webhook.
        logger.warning(
            "windmill_job_not_found",
            extra={"job_id": payload.job_id, "error": str(exc)},
        )
    
    return {
        "status": "received",
        "job_id": payload.job_id,
    }


@router.post("/windmill/flow")
async def windmill_flow_webhook(
    request: Request,
    db: Database = Depends(get_db),
):
    """
    Handle Windmill flow completion webhook.
    
    Called when an entire flow completes.
    """
    payload = await request.json()

    logger.info(
        "windmill_flow_webhook_received",
        extra={"payload": payload},
    )

    status = _extract_status(payload)
    protocol_run_id = _extract_protocol_run_id(payload)
    flow_path = _extract_flow_path(payload)

    if protocol_run_id is None and flow_path:
        for run in db.list_all_protocol_runs(limit=200):
            if run.windmill_flow_id == flow_path:
                protocol_run_id = run.id
                break

    if protocol_run_id is not None:
        if _is_success_status(status):
            orchestrator = _build_orchestrator(db)
            orchestrator.check_and_complete_protocol(protocol_run_id)
        elif _is_failure_status(status):
            db.update_protocol_status(protocol_run_id, ProtocolStatus.BLOCKED)

    return {"status": "received"}


# ==================== GitHub Webhooks ====================

@router.post("/github")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(None),
    x_hub_signature_256: str = Header(None),
    x_hub_signature: str = Header(None),
    project_id: Optional[int] = Query(None, description="Override project ID for logging"),
    protocol_run_id: Optional[int] = Query(None, description="Override protocol run ID for logging"),
    db: Database = Depends(get_db),
):
    """
    Handle GitHub webhooks.
    
    Supported events:
    - workflow_run: When a CI workflow completes
    - check_run: When a check run completes
    - pull_request: When a PR is opened/merged
    """
    body = await request.body()
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    config = load_config()
    if config.webhook_token:
        signature = x_hub_signature_256 or x_hub_signature
        if not _verify_github_signature(config.webhook_token, body, signature):
            raise HTTPException(status_code=401, detail="Invalid GitHub signature")

    logger.info(
        "github_webhook_received",
        extra={
            "event": x_github_event,
            "action": payload.get("action"),
        },
    )
    
    repo = payload.get("repository", {})
    candidate_urls = [
        repo.get("clone_url"),
        repo.get("ssh_url"),
        repo.get("html_url"),
        repo.get("git_url"),
    ]
    if repo.get("full_name"):
        candidate_urls.append(f"github.com/{repo['full_name']}")
    resolved_project_id = project_id or _resolve_project_id(db, candidate_urls)

    event_type = f"ci_webhook_github_{x_github_event}" if x_github_event else "ci_webhook_github"
    _emit_ci_event(
        db,
        event_type=event_type,
        message=f"GitHub webhook {x_github_event or 'event'} received",
        project_id=resolved_project_id,
        protocol_run_id=protocol_run_id,
        metadata={
            "event": x_github_event,
            "action": payload.get("action"),
            "repository": repo.get("full_name") or repo.get("name"),
            "branch": payload.get("workflow_run", {}).get("head_branch")
            or payload.get("check_run", {}).get("check_suite", {}).get("head_branch")
            or payload.get("pull_request", {}).get("base", {}).get("ref"),
        },
    )

    if x_github_event == "workflow_run":
        return await _handle_workflow_run(
            payload,
            db=db,
            project_id=resolved_project_id,
            protocol_run_id=protocol_run_id,
        )
    elif x_github_event == "check_run":
        return await _handle_check_run(
            payload,
            db=db,
            project_id=resolved_project_id,
            protocol_run_id=protocol_run_id,
        )
    elif x_github_event == "pull_request":
        return await _handle_pull_request(
            payload,
            db=db,
            project_id=resolved_project_id,
            protocol_run_id=protocol_run_id,
        )
    
    return {"status": "ignored", "event": x_github_event}


async def _handle_workflow_run(
    payload: dict,
    *,
    db: Database,
    project_id: Optional[int],
    protocol_run_id: Optional[int],
):
    """Handle GitHub workflow_run event."""
    workflow_run = payload.get("workflow_run", {})
    conclusion = workflow_run.get("conclusion")
    
    if conclusion == "success":
        _emit_ci_event(
            db,
            event_type="ci_workflow_success",
            message="GitHub workflow succeeded",
            project_id=project_id,
            protocol_run_id=protocol_run_id,
            metadata={"workflow": workflow_run.get("name"), "id": workflow_run.get("id")},
        )
        if load_config().auto_qa_on_ci:
            _maybe_advance_protocol_on_ci(db, protocol_run_id=protocol_run_id)
    elif conclusion in ("failure", "cancelled"):
        _emit_ci_event(
            db,
            event_type="ci_workflow_failed",
            message="GitHub workflow failed",
            project_id=project_id,
            protocol_run_id=protocol_run_id,
            metadata={"workflow": workflow_run.get("name"), "id": workflow_run.get("id")},
        )
        if protocol_run_id is not None:
            db.update_protocol_status(protocol_run_id, ProtocolStatus.BLOCKED)
    
    return {
        "status": "processed",
        "workflow": workflow_run.get("name"),
        "conclusion": conclusion,
    }


async def _handle_check_run(
    payload: dict,
    *,
    db: Database,
    project_id: Optional[int],
    protocol_run_id: Optional[int],
):
    """Handle GitHub check_run event."""
    check_run = payload.get("check_run", {})
    conclusion = check_run.get("conclusion")
    if conclusion == "success":
        _emit_ci_event(
            db,
            event_type="ci_check_success",
            message="GitHub check run succeeded",
            project_id=project_id,
            protocol_run_id=protocol_run_id,
            metadata={"check": check_run.get("name"), "id": check_run.get("id")},
        )
    elif conclusion in ("failure", "cancelled"):
        _emit_ci_event(
            db,
            event_type="ci_check_failed",
            message="GitHub check run failed",
            project_id=project_id,
            protocol_run_id=protocol_run_id,
            metadata={"check": check_run.get("name"), "id": check_run.get("id")},
        )
    return {
        "status": "processed",
        "check": check_run.get("name"),
        "conclusion": conclusion,
    }


async def _handle_pull_request(
    payload: dict,
    *,
    db: Database,
    project_id: Optional[int],
    protocol_run_id: Optional[int],
):
    """Handle GitHub pull_request event."""
    action = payload.get("action")
    pr = payload.get("pull_request", {})

    _emit_ci_event(
        db,
        event_type="ci_pull_request",
        message=f"GitHub pull request {action}",
        project_id=project_id,
        protocol_run_id=protocol_run_id,
        metadata={"pr_number": pr.get("number"), "action": action},
    )
    
    return {
        "status": "processed",
        "action": action,
        "pr_number": pr.get("number"),
    }


# ==================== GitLab Webhooks ====================

@router.post("/gitlab")
async def gitlab_webhook(
    request: Request,
    x_gitlab_token: str = Header(None),
    project_id: Optional[int] = Query(None, description="Override project ID for logging"),
    protocol_run_id: Optional[int] = Query(None, description="Override protocol run ID for logging"),
    db: Database = Depends(get_db),
):
    """
    Handle GitLab webhooks.
    
    Supported events:
    - Pipeline: When a CI pipeline completes
    - Merge Request: When an MR is created/merged
    """
    body = await request.body()
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    config = load_config()
    if config.webhook_token:
        if not _verify_gitlab_token(config.webhook_token, x_gitlab_token):
            raise HTTPException(status_code=401, detail="Invalid GitLab token")
    
    from devgodzilla.logging import get_logger
    logger = get_logger(__name__)
    
    object_kind = payload.get("object_kind")
    
    logger.info(
        "gitlab_webhook_received",
        extra={"object_kind": object_kind},
    )
    
    project = payload.get("project", {})
    candidate_urls = [
        project.get("web_url"),
        project.get("git_ssh_url"),
        project.get("git_http_url"),
        project.get("http_url"),
        project.get("ssh_url"),
    ]
    resolved_project_id = project_id or _resolve_project_id(db, candidate_urls)

    event_type = f"ci_webhook_gitlab_{object_kind}" if object_kind else "ci_webhook_gitlab"
    attrs = payload.get("object_attributes", {}) or {}
    _emit_ci_event(
        db,
        event_type=event_type,
        message=f"GitLab webhook {object_kind or 'event'} received",
        project_id=resolved_project_id,
        protocol_run_id=protocol_run_id,
        metadata={
            "event": object_kind,
            "status": attrs.get("status"),
            "action": attrs.get("action"),
            "ref": attrs.get("ref"),
            "repository": project.get("path_with_namespace") or project.get("name"),
        },
    )

    if object_kind == "pipeline":
        return await _handle_gitlab_pipeline(
            payload,
            db=db,
            project_id=resolved_project_id,
            protocol_run_id=protocol_run_id,
        )
    elif object_kind == "merge_request":
        return await _handle_gitlab_mr(
            payload,
            db=db,
            project_id=resolved_project_id,
            protocol_run_id=protocol_run_id,
        )
    
    return {"status": "ignored", "object_kind": object_kind}


async def _handle_gitlab_pipeline(
    payload: dict,
    *,
    db: Database,
    project_id: Optional[int],
    protocol_run_id: Optional[int],
):
    """Handle GitLab pipeline event."""
    attrs = payload.get("object_attributes", {})
    status = attrs.get("status")
    if status == "success":
        _emit_ci_event(
            db,
            event_type="ci_pipeline_success",
            message="GitLab pipeline succeeded",
            project_id=project_id,
            protocol_run_id=protocol_run_id,
            metadata={"pipeline_id": attrs.get("id")},
        )
        if load_config().auto_qa_on_ci:
            _maybe_advance_protocol_on_ci(db, protocol_run_id=protocol_run_id)
    elif status in ("failed", "canceled", "cancelled"):
        _emit_ci_event(
            db,
            event_type="ci_pipeline_failed",
            message="GitLab pipeline failed",
            project_id=project_id,
            protocol_run_id=protocol_run_id,
            metadata={"pipeline_id": attrs.get("id")},
        )
        if protocol_run_id is not None:
            db.update_protocol_status(protocol_run_id, ProtocolStatus.BLOCKED)
    return {
        "status": "processed",
        "pipeline_status": attrs.get("status"),
    }


async def _handle_gitlab_mr(
    payload: dict,
    *,
    db: Database,
    project_id: Optional[int],
    protocol_run_id: Optional[int],
):
    """Handle GitLab merge request event."""
    attrs = payload.get("object_attributes", {})
    _emit_ci_event(
        db,
        event_type="ci_merge_request",
        message=f"GitLab merge request {attrs.get('action')}",
        project_id=project_id,
        protocol_run_id=protocol_run_id,
        metadata={"mr_iid": attrs.get("iid"), "action": attrs.get("action")},
    )
    return {
        "status": "processed",
        "action": attrs.get("action"),
        "mr_iid": attrs.get("iid"),
    }
