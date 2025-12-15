"""
DevGodzilla Webhook Handlers

Handles incoming webhooks from Windmill and CI/CD systems.
"""

import hashlib
import hmac
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


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


# ==================== Windmill Webhooks ====================

@router.post("/windmill/job")
async def windmill_job_webhook(
    payload: WindmillJobUpdate,
    request: Request,
):
    """
    Handle Windmill job status updates.
    
    Called by Windmill when a job completes, fails, or is cancelled.
    Updates the corresponding protocol/step run in the database.
    """
    from devgodzilla.logging import get_logger
    logger = get_logger(__name__)
    
    logger.info(
        "windmill_webhook_received",
        extra={
            "job_id": payload.job_id,
            "status": payload.status,
        },
    )
    
    # TODO: Look up job_run by windmill_job_id and update status
    # db.update_job_run_by_windmill_id(payload.job_id, status=payload.status)
    
    return {
        "status": "received",
        "job_id": payload.job_id,
    }


@router.post("/windmill/flow")
async def windmill_flow_webhook(
    request: Request,
):
    """
    Handle Windmill flow completion webhook.
    
    Called when an entire flow completes.
    """
    payload = await request.json()
    
    from devgodzilla.logging import get_logger
    logger = get_logger(__name__)
    
    logger.info(
        "windmill_flow_webhook_received",
        extra={"payload": payload},
    )
    
    # TODO: Update protocol_run by windmill_flow_id
    
    return {"status": "received"}


# ==================== GitHub Webhooks ====================

@router.post("/github")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(None),
    x_hub_signature_256: str = Header(None),
):
    """
    Handle GitHub webhooks.
    
    Supported events:
    - workflow_run: When a CI workflow completes
    - check_run: When a check run completes
    - pull_request: When a PR is opened/merged
    """
    payload = await request.json()
    
    from devgodzilla.logging import get_logger
    logger = get_logger(__name__)
    
    logger.info(
        "github_webhook_received",
        extra={
            "event": x_github_event,
            "action": payload.get("action"),
        },
    )
    
    if x_github_event == "workflow_run":
        return await _handle_workflow_run(payload)
    elif x_github_event == "check_run":
        return await _handle_check_run(payload)
    elif x_github_event == "pull_request":
        return await _handle_pull_request(payload)
    
    return {"status": "ignored", "event": x_github_event}


async def _handle_workflow_run(payload: dict):
    """Handle GitHub workflow_run event."""
    workflow_run = payload.get("workflow_run", {})
    conclusion = workflow_run.get("conclusion")
    
    if conclusion == "success":
        # CI passed - could auto-advance protocol
        pass
    elif conclusion in ("failure", "cancelled"):
        # CI failed - trigger feedback loop
        pass
    
    return {
        "status": "processed",
        "workflow": workflow_run.get("name"),
        "conclusion": conclusion,
    }


async def _handle_check_run(payload: dict):
    """Handle GitHub check_run event."""
    check_run = payload.get("check_run", {})
    return {
        "status": "processed",
        "check": check_run.get("name"),
        "conclusion": check_run.get("conclusion"),
    }


async def _handle_pull_request(payload: dict):
    """Handle GitHub pull_request event."""
    action = payload.get("action")
    pr = payload.get("pull_request", {})
    
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
):
    """
    Handle GitLab webhooks.
    
    Supported events:
    - Pipeline: When a CI pipeline completes
    - Merge Request: When an MR is created/merged
    """
    payload = await request.json()
    
    from devgodzilla.logging import get_logger
    logger = get_logger(__name__)
    
    object_kind = payload.get("object_kind")
    
    logger.info(
        "gitlab_webhook_received",
        extra={"object_kind": object_kind},
    )
    
    if object_kind == "pipeline":
        return await _handle_gitlab_pipeline(payload)
    elif object_kind == "merge_request":
        return await _handle_gitlab_mr(payload)
    
    return {"status": "ignored", "object_kind": object_kind}


async def _handle_gitlab_pipeline(payload: dict):
    """Handle GitLab pipeline event."""
    attrs = payload.get("object_attributes", {})
    return {
        "status": "processed",
        "pipeline_status": attrs.get("status"),
    }


async def _handle_gitlab_mr(payload: dict):
    """Handle GitLab merge request event."""
    attrs = payload.get("object_attributes", {})
    return {
        "status": "processed",
        "action": attrs.get("action"),
        "mr_iid": attrs.get("iid"),
    }
