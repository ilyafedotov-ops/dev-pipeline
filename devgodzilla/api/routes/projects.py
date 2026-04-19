from __future__ import annotations

import json
import os
import re
import subprocess
import time
from typing import Any, List, Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from devgodzilla.api import schemas
from devgodzilla.api.dependencies import get_db, get_service_context
from devgodzilla.db.database import Database, _UNSET
from devgodzilla.events_catalog import normalize_event_type
from devgodzilla.logging import get_logger, log_extra
from devgodzilla.services.base import ServiceContext
from devgodzilla.services.policy import PolicyService
from devgodzilla.services.clarifier import ClarifierService
from devgodzilla.services.specification import SpecificationService
from pathlib import Path

router = APIRouter()
logger = get_logger(__name__)


def _looks_like_git_repository_url(value: Optional[str]) -> bool:
    url = (value or "").strip()
    if not url:
        return False
    if re.match(r"^git@[^:]+:.+", url):
        return True
    if not re.match(r"^(https?|ssh)://", url):
        return False
    parsed = urlparse(url)
    path = [segment for segment in parsed.path.split("/") if segment]
    if url.endswith(".git"):
        return True
    return (parsed.hostname or "").lower() in {
        "github.com",
        "gitlab.com",
        "bitbucket.org",
        "dev.azure.com",
    } and len(path) >= 2

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


def _append_project_event(
    db: Database,
    *,
    project_id: int,
    event_type: str,
    message: str,
    metadata: Optional[dict] = None,
) -> None:
    try:
        db.append_event(
            protocol_run_id=None,
            project_id=project_id,
            event_type=event_type,
            message=message,
            metadata=metadata,
        )
    except Exception:
        pass

def _normalize_policy_enforcement_mode(mode: Optional[str]) -> Optional[str]:
    if mode is None:
        return None
    value = str(mode).strip().lower()
    mapping = {
        "advisory": "warn",
        "mandatory": "block",
        "enforce": "block",
        "blocking": "block",
    }
    return mapping.get(value, value)


def _project_secrets_with_github_token(
    existing: Optional[dict],
    github_token: Optional[str],
) -> Optional[dict]:
    secrets = dict(existing or {})
    token = (github_token or "").strip()
    if token:
        secrets["github_token"] = token
    else:
        secrets.pop("github_token", None)
    return secrets or None


def _project_github_token(project: Any) -> Optional[str]:
    token = ((getattr(project, "secrets", None) or {}).get("github_token") or "").strip()
    return token or None


def _parse_github_owner_repo_from_url(git_url: Optional[str]) -> Optional[tuple[str, str]]:
    url = (git_url or "").strip()
    if not url or "github.com" not in url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        tail = url.split("github.com/", 1)[-1]
    elif url.startswith("git@"):
        tail = url.split(":", 1)[-1]
    elif url.startswith("ssh://git@"):
        tail = url.split("github.com/", 1)[-1]
    else:
        return None
    parts = tail.rstrip("/").removesuffix(".git").split("/")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        return None
    return parts[0], parts[1]


def _project_github_owner_repo(repo_path: Path, project: Any) -> Optional[tuple[str, str]]:
    from devgodzilla.services.git import run_process

    remote_url = (project.git_url or "").strip()
    result = run_process(
        ["git", "config", "--get", "remote.origin.url"],
        cwd=repo_path,
        check=False,
    )
    if result.returncode == 0 and (result.stdout or "").strip():
        remote_url = (result.stdout or "").strip()
    return _parse_github_owner_repo_from_url(remote_url)


def _github_headers(github_token: Optional[str]) -> Optional[dict[str, str]]:
    token = (github_token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    if not token:
        return None
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }


def _github_pr_check_status(item: dict[str, Any]) -> str:
    if item.get("draft"):
        return "draft"
    return "unknown"


def _list_github_pulls(owner: str, repo: str, *, github_token: Optional[str]) -> list[schemas.PullRequestOut]:
    headers = _github_headers(github_token)
    if headers is None:
        return []
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    try:
        response = httpx.get(
            url,
            headers=headers,
            params={"state": "open", "per_page": 100},
            timeout=30,
        )
    except Exception:
        return []
    if response.status_code != 200:
        return []
    pulls: list[schemas.PullRequestOut] = []
    for item in response.json():
        pulls.append(
            schemas.PullRequestOut(
                id=str(item.get("number", "")),
                title=item.get("title", ""),
                branch=((item.get("head") or {}).get("ref") or ""),
                status="draft" if item.get("draft") else (item.get("state", "open") or "open").lower(),
                checks=_github_pr_check_status(item),
                url=item.get("html_url", ""),
                author=((item.get("user") or {}).get("login") or ""),
                created_at=item.get("created_at", ""),
            )
        )
    return pulls


class ProjectOnboardRequest(BaseModel):
    branch: Optional[str] = Field(default=None, description="Branch to checkout after clone (defaults to project.base_branch)")
    clone_if_missing: bool = Field(default=True, description="Clone repo if local_path is missing")
    constitution_content: Optional[str] = Field(default=None, description="Optional custom constitution content")
    run_discovery_agent: bool = Field(
        default=True,
        description="Run headless agent discovery (writes specs/discovery/_runtime/* artifacts)",
    )
    discovery_pipeline: bool = Field(default=True, description="Use multi-stage discovery pipeline")
    discovery_engine_id: Optional[str] = Field(default=None, description="Engine ID for discovery (default: opencode)")
    discovery_model: Optional[str] = Field(default=None, description="Model for discovery (default: engine default)")


class ProjectOnboardResponse(BaseModel):
    success: bool
    project: schemas.ProjectOut
    local_path: str
    speckit_initialized: bool
    speckit_path: Optional[str] = None
    constitution_hash: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    discovery_success: bool = False
    discovery_log_path: Optional[str] = None
    discovery_missing_outputs: List[str] = Field(default_factory=list)
    discovery_error: Optional[str] = None
    error: Optional[str] = None


class OnboardingAcceptedResponse(BaseModel):
    """Returned when onboarding is deferred to background execution."""
    project_id: int
    status: str = "pending"
    message: str = "Onboarding started in background. Poll GET /projects/{project_id}/onboarding for progress."


class CreateBranchRequest(BaseModel):
    name: str = Field(..., description="New branch name (e.g. feature/foo)")
    base_ref: Optional[str] = Field(default=None, description="Base ref (branch/sha), defaults to project.base_branch")
    checkout: bool = Field(default=False, description="Checkout the new branch after creation")
    push: bool = Field(default=False, description="Push branch to origin and set upstream")


def _auto_onboard_project(ctx, db, created, project_req):
    """Handle auto-onboarding: Windmill queue or synchronous fallback."""
    import time as _t

    windmill_ok = getattr(ctx.config, "windmill_enabled", False)
    if windmill_ok:
        try:
            from devgodzilla.services.onboarding_queue import enqueue_project_onboarding

            _start = _t.perf_counter()
            result = enqueue_project_onboarding(
                ctx, db,
                project_id=created.id,
                branch=created.base_branch,
                run_discovery_agent=bool(project_req.auto_discovery),
            )
            _ms = int((_t.perf_counter() - _start) * 1000)
            logger.info(
                "onboarding_enqueue_success",
                extra=log_extra(
                    project_id=created.id,
                    windmill_job_id=result.windmill_job_id,
                    duration_ms=_ms,
                ),
            )
            return  # Windmill enqueued — done
        except Exception as exc:
            logger.warning(
                "onboarding_windmill_failed_fallback_sync",
                extra=log_extra(project_id=created.id, error=str(exc)),
            )
            _append_project_event(
                db, project_id=created.id,
                event_type="onboarding_enqueue_failed",
                message="Windmill unavailable, running onboarding synchronously",
                metadata={"error": str(exc)},
            )

    # No Windmill — run onboarding synchronously in-process
    if not (created.git_url or "").strip():
        _append_project_event(
            db, project_id=created.id,
            event_type="onboarding_failed",
            message="git_url is required for onboarding",
        )
        raise HTTPException(status_code=400, detail="git_url is required for onboarding")

    _append_project_event(
        db, project_id=created.id,
        event_type="onboarding_sync_start",
        message="Starting synchronous onboarding (no Windmill)",
    )
    try:
        from devgodzilla.api.routes.projects import _run_onboarding_work, ProjectOnboardRequest

        _req = ProjectOnboardRequest(
            branch=created.base_branch or "main",
            run_discovery_agent=bool(project_req.auto_discovery),
            clone_if_missing=True,
        )
        _append_project_event(
            db, project_id=created.id,
            event_type="onboarding_started",
            message="Onboarding started",
            metadata={
                "branch": created.base_branch or "main",
                "clone_if_missing": True,
            },
        )
        _run_onboarding_work(project_id=created.id, request=_req, ctx=ctx, db=db)

        _append_project_event(
            db, project_id=created.id,
            event_type="onboarding_sync_completed",
            message="Onboarding completed (synchronous, no Windmill)",
        )
        logger.info("onboarding_sync_completed", extra=log_extra(project_id=created.id))
    except Exception as exc:
        logger.exception("onboarding_sync_failed", extra=log_extra(project_id=created.id, error=str(exc)))
        _append_project_event(
            db, project_id=created.id,
            event_type="onboarding_sync_failed",
            message=f"Synchronous onboarding failed: {exc}",
            metadata={"error": str(exc)},
        )


@router.post("/projects", response_model=schemas.ProjectOut)
def create_project(
    project: schemas.ProjectCreate,
    db: Database = Depends(get_db),
    ctx: ServiceContext = Depends(get_service_context),
):
    """Create a new project."""
    logger.debug(
        "create_project_request",
        extra=log_extra(
            project_name=project.name,
            base_branch=project.base_branch,
            has_git_url=bool((project.git_url or "").strip()),
            auto_onboard=bool(project.auto_onboard),
            auto_discovery=bool(project.auto_discovery),
            local_path=project.local_path,
        ),
    )
    has_git_url = bool((project.git_url or "").strip())
    has_local_path = bool((project.local_path or "").strip())
    if project.auto_onboard and not (has_git_url or has_local_path):
        raise HTTPException(status_code=400, detail="git_url or local_path is required for auto onboarding")
    if project.auto_onboard and has_git_url and not _looks_like_git_repository_url(project.git_url):
        raise HTTPException(
            status_code=400,
            detail="git_url must be a cloneable Git repository URL for auto onboarding",
        )
    created = db.create_project(
        name=project.name,
        git_url=project.git_url or "",
        base_branch=project.base_branch,
        secrets=_project_secrets_with_github_token(None, project.github_token),
        local_path=project.local_path,
    )
    logger.info(
        "project_created",
        extra=log_extra(
            project_id=created.id,
            project_name=created.name,
            base_branch=created.base_branch,
            local_path=created.local_path,
            auto_onboard=bool(project.auto_onboard),
        ),
    )

    # Auto-onboard: try Windmill queue first, fallback to synchronous onboarding
    if project.auto_onboard:
        _auto_onboard_project(ctx, db, created, project)

    return created

@router.get("/projects", response_model=List[schemas.ProjectOut])
def list_projects(
    status: Optional[str] = None,
    db: Database = Depends(get_db)
):
    """List all projects, optionally filtered by status."""
    projects = db.list_projects()
    if status:
        projects = [p for p in projects if p.status == status]
    return projects

@router.get("/projects/{project_id}", response_model=schemas.ProjectOut)
def get_project(
    project_id: int,
    db: Database = Depends(get_db)
):
    """Get project by ID."""
    try:
        return db.get_project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")

@router.put("/projects/{project_id}", response_model=schemas.ProjectOut)
def update_project(
    project_id: int,
    project: schemas.ProjectUpdate,
    db: Database = Depends(get_db)
):
    """Update a project."""
    try:
        existing = db.get_project(project_id)
        secrets = _UNSET
        if "github_token" in project.model_fields_set:
            secrets = _project_secrets_with_github_token(existing.secrets, project.github_token)
        return db.update_project(
            project_id,
            name=project.name,
            description=project.description if project.description is not None else _UNSET,
            status=project.status.value if project.status else None,
            git_url=project.git_url,
            base_branch=project.base_branch,
            secrets=secrets,
            local_path=project.local_path,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")

@router.post("/projects/{project_id}/archive", response_model=schemas.ProjectOut)
def archive_project(
    project_id: int,
    db: Database = Depends(get_db)
):
    """Archive a project."""
    try:
        return db.update_project(project_id, status="archived")
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")

@router.post("/projects/{project_id}/unarchive", response_model=schemas.ProjectOut)
def unarchive_project(
    project_id: int,
    db: Database = Depends(get_db)
):
    """Unarchive a project."""
    try:
        return db.update_project(project_id, status="active")
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")

@router.delete("/projects/{project_id}")
def delete_project(
    project_id: int,
    db: Database = Depends(get_db)
):
    """Delete a project and all associated data."""
    try:
        db.get_project(project_id)  # Check exists first
        db.delete_project(project_id)
        return {"status": "deleted", "project_id": project_id}
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")


@router.get("/projects/{project_id}/onboarding", response_model=schemas.OnboardingSummary)
def get_project_onboarding(
    project_id: int,
    db: Database = Depends(get_db)
):
    """Get onboarding status summary."""
    try:
        project = db.get_project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")

    recent_events = db.list_recent_events(
        limit=50,
        project_id=project_id,
        categories=["onboarding", "discovery"],
    )
    event_set = {normalize_event_type(event.event_type) for event in recent_events}

    def _event_time(event_type: str) -> Optional[Any]:
        for event in recent_events:
            if normalize_event_type(event.event_type) == event_type:
                return event.created_at
        return None

    # Compute stages
    stages = []

    # Stage 1: Repository Setup
    repo_status = "completed" if project.local_path or "onboarding_repo_ready" in event_set else "pending"
    if repo_status == "pending" and ("onboarding_started" in event_set or "onboarding_enqueued" in event_set):
        repo_status = "running"

    repo_completed_at = _event_time("onboarding_repo_ready") if repo_status == "completed" else None
    if repo_completed_at is None and repo_status == "completed":
        repo_completed_at = project.updated_at or project.created_at

    stages.append(
        schemas.OnboardingStage(
            name="Repository Setup",
            status=repo_status,
            started_at=_event_time("onboarding_started") or _event_time("onboarding_enqueued"),
            completed_at=repo_completed_at,
        )
    )

    # Stage 2: SpecKit Init
    spec_status = "completed" if project.constitution_hash or "onboarding_speckit_initialized" in event_set else "pending"
    if "onboarding_failed" in event_set:
        spec_status = "failed"
    elif repo_status in ("running", "completed") and spec_status == "pending":
        spec_status = "running" if repo_status == "running" else "pending"

    spec_completed_at = _event_time("onboarding_speckit_initialized") if spec_status == "completed" else None
    if spec_completed_at is None and spec_status == "completed":
        spec_completed_at = project.updated_at or project.created_at

    stages.append(
        schemas.OnboardingStage(
            name="SpecKit Initialization",
            status=spec_status,
            started_at=_event_time("onboarding_repo_ready") or _event_time("onboarding_started"),
            completed_at=spec_completed_at,
        )
    )

    # Stage 3: Discovery
    if "discovery_completed" in event_set:
        discovery_status = "completed"
    elif "discovery_failed" in event_set:
        discovery_status = "failed"
    elif "discovery_started" in event_set:
        discovery_status = "running"
    elif "discovery_skipped" in event_set:
        discovery_status = "skipped"
    else:
        discovery_status = "pending"

    stages.append(
        schemas.OnboardingStage(
            name="Discovery",
            status=discovery_status,
            started_at=_event_time("discovery_started"),
            completed_at=_event_time("discovery_completed") if discovery_status == "completed" else None,
        )
    )

    # Calculate blocking clarifications
    try:
        clarifications = db.list_clarifications(project_id=project_id, status="open")
        blocking_count = sum(1 for c in clarifications if getattr(c, "blocking", False))
    except (KeyError, AttributeError):
        blocking_count = 0

    clarifications_status = "blocked" if blocking_count > 0 else "completed"
    if repo_status == "pending" or spec_status == "pending":
        clarifications_status = "pending"

    stages.append(schemas.OnboardingStage(
        name="Clarifications",
        status=clarifications_status,
    ))

    stage_statuses = {repo_status, spec_status, discovery_status, clarifications_status}
    if "failed" in stage_statuses:
        overall_status = "failed"
    elif blocking_count > 0:
        overall_status = "blocked"
    elif "running" in stage_statuses:
        overall_status = "running"
    elif stage_statuses.issubset({"completed", "skipped"}):
        overall_status = "completed"
    else:
        overall_status = "pending"

    events = [
        schemas.OnboardingEvent(
            id=event.id,
            event_type=event.event_type,
            message=event.message,
            metadata=event.metadata,
            created_at=event.created_at,
        )
        for event in reversed(recent_events)
    ]

    return schemas.OnboardingSummary(
        project_id=project_id,
        status=overall_status,
        stages=stages,
        events=events,
        blocking_clarifications=blocking_count
    )


def _run_onboarding_work(
    project_id: int,
    request: ProjectOnboardRequest,
    ctx: ServiceContext,
    db: Optional[Database] = None,
) -> ProjectOnboardResponse:
    """Execute the full onboarding pipeline (clone, speckit init, discovery).

    Designed to be called either synchronously or from a BackgroundTask.
    When *db* is ``None`` a fresh DB session is opened automatically (safe
    for background threads where the request-scoped DB is already closed).
    """
    from devgodzilla.services.git import GitService, run_process
    from devgodzilla.services.specification import SpecificationService

    if db is None:
        from devgodzilla.cli.main import get_db as _get_db
        db = _get_db()

    project = db.get_project(project_id)

    git = GitService(ctx)
    github_token = ((project.secrets or {}).get("github_token") or "").strip() or None
    repo_resolve_start = time.perf_counter()
    repo_path = git.resolve_repo_path(
        project.git_url,
        project.name,
        project.local_path,
        project_id=project.id,
        clone_if_missing=bool(request.clone_if_missing),
        github_token=github_token,
    )
    repo_resolve_duration_ms = int((time.perf_counter() - repo_resolve_start) * 1000)
    logger.info(
        "onboarding_repo_resolved",
        extra=log_extra(
            project_id=project_id,
            repo_path=str(repo_path),
            duration_ms=repo_resolve_duration_ms,
        ),
    )

    branch = (request.branch or project.base_branch or "main").strip()
    if branch:
        try:
            git_env = git.build_remote_git_env(project.git_url, github_token)
            run_process(["git", "fetch", "--prune", "origin", branch], cwd=repo_path, check=False, env=git_env)
            # Prefer tracking branch when available.
            res = run_process(["git", "checkout", branch], cwd=repo_path, check=False)
            if res.returncode != 0:
                run_process(
                    ["git", "checkout", "-B", branch, f"origin/{branch}"],
                    cwd=repo_path,
                    check=False,
                    env=git_env,
                )
        except Exception:
            # Best-effort: branch checkout isn't strictly required for SpecKit init.
            pass

    # Persist local_path (ensure DevGodzilla API can later find the repo).
    if not project.local_path or project.local_path != str(repo_path):
        try:
            db.update_project(project_id, local_path=str(repo_path))
        except Exception:
            pass

    _append_project_event(
        db,
        project_id=project_id,
        event_type="onboarding_repo_ready",
        message="Repository ready for onboarding",
        metadata={"repo_path": str(repo_path), "branch": branch},
    )

    constitution_content = request.constitution_content
    effective_policy = None
    if constitution_content is None:
        try:
            policy_service = PolicyService(ctx, db)
            effective_policy = policy_service.resolve_effective_policy(
                project_id,
                repo_root=repo_path,
                include_repo_local=True,
            )
            constitution_content = policy_service.render_constitution(effective_policy)
        except Exception:
            constitution_content = None
            effective_policy = None

    spec_service = SpecificationService(ctx, db)
    spec_init_start = time.perf_counter()
    init_result = spec_service.init_project(
        str(repo_path),
        constitution_content=constitution_content,
        project_id=project_id,
    )
    spec_init_duration_ms = int((time.perf_counter() - spec_init_start) * 1000)
    logger.info(
        "onboarding_speckit_initialized",
        extra=log_extra(
            project_id=project_id,
            success=bool(init_result.success),
            duration_ms=spec_init_duration_ms,
            spec_path=init_result.spec_path,
        ),
    )

    _append_project_event(
        db,
        project_id=project_id,
        event_type="onboarding_speckit_initialized" if init_result.success else "onboarding_failed",
        message="SpecKit initialized" if init_result.success else "SpecKit initialization failed",
        metadata={
            "warnings": init_result.warnings,
            "error": init_result.error,
            "spec_path": init_result.spec_path,
        },
    )

    if effective_policy is not None:
        try:
            clarifier = ClarifierService(ctx, db)
            clarifier.ensure_from_policy(
                project_id=project_id,
                policy=effective_policy.policy,
                applies_to="onboarding",
            )
        except Exception:
            pass

    discovery_success = False
    discovery_log_path: Optional[str] = None
    discovery_missing_outputs: List[str] = []
    discovery_error: Optional[str] = None
    if request.run_discovery_agent:
        discovery_start = time.perf_counter()
        _append_project_event(
            db,
            project_id=project_id,
            event_type="discovery_started",
            message="Discovery started",
            metadata={
                "engine_id": request.discovery_engine_id or "opencode",
                "model": request.discovery_model,
                "pipeline": bool(request.discovery_pipeline),
            },
        )
        try:
            from devgodzilla.services.discovery_agent import DiscoveryAgentService

            svc = DiscoveryAgentService(ctx)
            disc = svc.run_discovery(
                repo_root=repo_path,
                engine_id=request.discovery_engine_id or "opencode",
                model=request.discovery_model,
                pipeline=bool(request.discovery_pipeline),
                stages=None,
                timeout_seconds=int(os.environ.get("DEVGODZILLA_DISCOVERY_TIMEOUT_SECONDS", "900")),
                strict_outputs=True,
                project_id=project_id,
            )
            discovery_success = bool(disc.success)
            discovery_log_path = str(disc.log_path)
            discovery_missing_outputs = [str(p) for p in disc.missing_outputs]
            discovery_error = disc.error
            discovery_warning = disc.warning
            fallback_engine_id = disc.fallback_engine_id
        except Exception as e:
            discovery_success = False
            discovery_error = str(e)
            discovery_warning = None
            fallback_engine_id = None
        discovery_duration_ms = int((time.perf_counter() - discovery_start) * 1000)
        logger.info(
            "discovery_completed",
            extra=log_extra(
                project_id=project_id,
                success=discovery_success,
                duration_ms=discovery_duration_ms,
                log_path=discovery_log_path,
                missing_outputs=discovery_missing_outputs,
                error=discovery_error,
                warning=discovery_warning,
                fallback_engine_id=fallback_engine_id,
            ),
        )
        _append_project_event(
            db,
            project_id=project_id,
            event_type="discovery_completed" if discovery_success else "discovery_failed",
            message="Discovery completed" if discovery_success else ("Discovery failed" if not discovery_warning else f"Discovery completed with fallback: {discovery_warning}"),
            metadata={
                "success": discovery_success,
                "log_path": discovery_log_path,
                "missing_outputs": discovery_missing_outputs,
                "error": discovery_error,
                "warning": discovery_warning,
                "fallback_engine_id": fallback_engine_id,
            },
        )
    else:
        logger.debug(
            "discovery_skipped",
            extra=log_extra(project_id=project_id, reason="disabled"),
        )
        _append_project_event(
            db,
            project_id=project_id,
            event_type="discovery_skipped",
            message="Discovery skipped",
            metadata={"reason": "disabled"},
        )

    _append_project_event(
        db,
        project_id=project_id,
        event_type="onboarding_completed",
        message="Onboarding completed" if init_result.success else "Onboarding finished with errors",
    )

    updated_project = db.get_project(project_id)

    return ProjectOnboardResponse(
        success=init_result.success,
        project=schemas.ProjectOut.model_validate(updated_project),
        local_path=str(repo_path),
        speckit_initialized=init_result.success,
        speckit_path=init_result.spec_path,
        constitution_hash=init_result.constitution_hash,
        warnings=init_result.warnings,
        discovery_success=discovery_success,
        discovery_log_path=discovery_log_path,
        discovery_missing_outputs=discovery_missing_outputs,
        discovery_error=discovery_error,
        error=init_result.error,
    )


@router.post(
    "/projects/{project_id}/actions/onboard",
    response_model=ProjectOnboardResponse,
    responses={202: {"model": OnboardingAcceptedResponse}},
)
@router.post(
    "/projects/{project_id}/onboarding/actions/start",
    response_model=ProjectOnboardResponse,
    responses={202: {"model": OnboardingAcceptedResponse}},
)
def onboard_project(
    project_id: int,
    request: ProjectOnboardRequest = ProjectOnboardRequest(),  # Allow empty body
    background_tasks: BackgroundTasks = None,
    db: Database = Depends(get_db),
    ctx: ServiceContext = Depends(get_service_context),
):
    """
    Onboard a project repository for DevGodzilla workflows.

    Returns **200** with full results when onboarding completes quickly (e.g.
    mocked engines in tests).  Returns **202 Accepted** when the work is
    deferred to a background task — the caller should poll
    ``GET /projects/{project_id}/onboarding`` for progress.

    - Ensures the repo exists locally (clone if missing)
    - Checks out the requested branch (or project.base_branch)
    - Initializes `.specify/` via SpecificationService
    - Optionally runs the discovery agent
    """
    try:
        project = db.get_project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.git_url:
        raise HTTPException(status_code=400, detail="Project must have a git_url before onboarding")

    logger.debug(
        "onboarding_request_received",
        extra=log_extra(
            project_id=project_id,
            branch=request.branch or project.base_branch,
            clone_if_missing=bool(request.clone_if_missing),
            run_discovery_agent=bool(request.run_discovery_agent),
            discovery_pipeline=bool(request.discovery_pipeline),
            discovery_engine_id=request.discovery_engine_id,
            discovery_model=request.discovery_model,
        ),
    )

    # Record the initial onboarding event synchronously so status is visible
    # immediately via GET /onboarding even if we hand off to background.
    _append_project_event(
        db,
        project_id=project_id,
        event_type="onboarding_started",
        message="Onboarding started",
        metadata={
            "branch": request.branch or project.base_branch,
            "clone_if_missing": bool(request.clone_if_missing),
        },
    )

    # --- Try synchronous execution first (fast with mocked engines) --------
    try:
        result = _run_onboarding_work(project_id, request, ctx, db=db)
        return result
    except Exception as exc:
        # Synchronous path failed (likely slow engine / real AI call).
        # Delegate to background so the API responds immediately.
        logger.warning(
            "onboarding_sync_failed_switching_to_background",
            extra=log_extra(project_id=project_id, error=str(exc)),
        )
        _append_project_event(
            db,
            project_id=project_id,
            event_type="onboarding_deferred_background",
            message="Onboarding deferred to background (sync attempt failed)",
            metadata={"error": str(exc)},
        )

    # --- Background path ---------------------------------------------------
    if background_tasks is None:
        # No BackgroundTasks available (e.g. direct function call from
        # _auto_onboard_project).  Re-raise the original error so callers
        # that invoked us synchronously still see the failure.
        raise

    def _run_in_background() -> None:
        try:
            _run_onboarding_work(project_id, request, ctx)
        except Exception as bg_exc:
            from devgodzilla.cli.main import get_db as _get_db

            logger.exception(
                "onboarding_background_failed",
                extra=log_extra(project_id=project_id, error=str(bg_exc)),
            )
            try:
                _bg_db = _get_db()
                _append_project_event(
                    _bg_db,
                    project_id=project_id,
                    event_type="onboarding_failed",
                    message=f"Onboarding failed in background: {bg_exc}",
                    metadata={"error": str(bg_exc)},
                )
            except Exception:
                pass

    background_tasks.add_task(_run_in_background)

    return JSONResponse(
        status_code=202,
        content=OnboardingAcceptedResponse(project_id=project_id).model_dump(),
    )


@router.post("/projects/{project_id}/discovery/actions/retry", response_model=schemas.DiscoveryRetryResponse)
def retry_project_discovery(
    project_id: int,
    request: schemas.DiscoveryRetryRequest = schemas.DiscoveryRetryRequest(),
    db: Database = Depends(get_db),
    ctx: ServiceContext = Depends(get_service_context),
):
    """Retry repository discovery for a project."""
    try:
        project = db.get_project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.local_path:
        raise HTTPException(status_code=400, detail="Project has no local repository path")

    repo_root = Path(project.local_path).expanduser().resolve()
    if not repo_root.exists():
        raise HTTPException(status_code=404, detail="Project repository not found on disk")

    engine_id = request.discovery_engine_id or "opencode"
    pipeline = bool(request.discovery_pipeline)

    _append_project_event(
        db,
        project_id=project_id,
        event_type="discovery_started",
        message="Discovery started",
        metadata={
            "engine_id": engine_id,
            "model": request.discovery_model,
            "pipeline": pipeline,
            "retry": True,
        },
    )

    discovery_success = False
    discovery_log_path: Optional[str] = None
    discovery_missing_outputs: List[str] = []
    discovery_error: Optional[str] = None
    discovery_warning: Optional[str] = None
    fallback_engine_id: Optional[str] = None
    try:
        from devgodzilla.services.discovery_agent import DiscoveryAgentService

        svc = DiscoveryAgentService(ctx)
        disc = svc.run_discovery(
            repo_root=repo_root,
            engine_id=engine_id,
            model=request.discovery_model,
            pipeline=pipeline,
            stages=request.stages,
            timeout_seconds=int(os.environ.get("DEVGODZILLA_DISCOVERY_TIMEOUT_SECONDS", "900")),
            strict_outputs=bool(request.strict_outputs),
            project_id=project_id,
        )
        discovery_success = bool(disc.success)
        discovery_log_path = str(disc.log_path)
        discovery_missing_outputs = [str(p) for p in disc.missing_outputs]
        discovery_error = disc.error
        discovery_warning = disc.warning
        fallback_engine_id = disc.fallback_engine_id
    except Exception as e:
        discovery_success = False
        discovery_error = str(e)

    _append_project_event(
        db,
        project_id=project_id,
        event_type="discovery_completed" if discovery_success else "discovery_failed",
        message="Discovery completed" if discovery_success else ("Discovery failed" if not discovery_warning else f"Discovery completed with fallback: {discovery_warning}"),
        metadata={
            "success": discovery_success,
            "log_path": discovery_log_path,
            "missing_outputs": discovery_missing_outputs,
            "error": discovery_error,
            "warning": discovery_warning,
            "fallback_engine_id": fallback_engine_id,
            "engine_id": engine_id,
            "model": request.discovery_model,
            "pipeline": pipeline,
            "retry": True,
        },
    )

    return schemas.DiscoveryRetryResponse(
        success=discovery_success,
        discovery_log_path=discovery_log_path,
        discovery_missing_outputs=discovery_missing_outputs,
        discovery_error=discovery_error,
        discovery_warning=discovery_warning,
        fallback_engine_id=fallback_engine_id,
        engine_id=engine_id,
        model=request.discovery_model,
        pipeline=pipeline,
    )


@router.get("/projects/{project_id}/discovery/logs", response_model=schemas.ArtifactContentOut)
def get_project_discovery_logs(
    project_id: int,
    max_bytes: int = 200_000,
    db: Database = Depends(get_db),
):
    try:
        project = db.get_project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.local_path:
        raise HTTPException(status_code=400, detail="Project has no local repository path")

    repo_root = Path(project.local_path).expanduser().resolve()
    log_path = repo_root / "specs" / "discovery" / "_runtime" / "opencode-discovery.log"
    if not log_path.exists() or not log_path.is_file():
        return schemas.ArtifactContentOut(
            id="discovery-log",
            name=log_path.name,
            type="log",
            content="",
            truncated=False,
        )

    max_bytes = max(1, min(int(max_bytes), 2_000_000))
    raw = log_path.read_bytes()
    truncated = len(raw) > max_bytes
    if truncated:
        raw = raw[:max_bytes]
    try:
        content = raw.decode("utf-8")
    except Exception:
        content = raw.decode("utf-8", errors="replace")

    return schemas.ArtifactContentOut(
        id="discovery-log",
        name=log_path.name,
        type="log",
        content=content,
        truncated=truncated,
    )

@router.get("/projects/{project_id}/sprints", response_model=List[schemas.SprintOut])
def list_project_sprints(
    project_id: int,
    status: Optional[str] = None,
    db: Database = Depends(get_db)
):
    """List sprints for a specific project."""
    return db.list_sprints(project_id=project_id, status=status)

@router.get("/projects/{project_id}/tasks", response_model=List[schemas.AgileTaskOut])
def list_project_tasks(
    project_id: int,
    sprint_id: Optional[int] = None,
    board_status: Optional[str] = None,
    assignee: Optional[str] = None,
    limit: int = 100,
    db: Database = Depends(get_db)
):
    """List tasks for a specific project."""
    return db.list_tasks(
        project_id=project_id,
        sprint_id=sprint_id,
        board_status=board_status,
        assignee=assignee,
        limit=limit
    )

@router.get("/projects/{project_id}/policy", response_model=schemas.PolicyConfigOut)
def get_project_policy(
    project_id: int,
    db: Database = Depends(get_db)
):
    """Get policy configuration for a project."""
    try:
        project = db.get_project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return schemas.PolicyConfigOut(
        policy_pack_key=project.policy_pack_key,
        policy_pack_version=project.policy_pack_version,
        policy_overrides=project.policy_overrides,
        policy_repo_local_enabled=bool(project.policy_repo_local_enabled) if project.policy_repo_local_enabled is not None else False,
        policy_enforcement_mode=_normalize_policy_enforcement_mode(project.policy_enforcement_mode) or "warn",
    )

@router.put("/projects/{project_id}/policy", response_model=schemas.ProjectOut)
def update_project_policy(
    project_id: int,
    policy: schemas.PolicyConfigUpdate,
    db: Database = Depends(get_db),
    ctx: ServiceContext = Depends(get_service_context),
):
    """Update policy configuration for a project."""
    try:
        db.get_project(project_id)  # Check exists
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Build update kwargs
    kwargs = {}
    if policy.policy_pack_key is not None:
        kwargs["policy_pack_key"] = policy.policy_pack_key
    if policy.policy_pack_version is not None:
        kwargs["policy_pack_version"] = policy.policy_pack_version
    if policy.policy_overrides is not None:
        kwargs["policy_overrides"] = policy.policy_overrides
    if policy.policy_repo_local_enabled is not None:
        kwargs["policy_repo_local_enabled"] = policy.policy_repo_local_enabled
    if policy.policy_enforcement_mode is not None:
        kwargs["policy_enforcement_mode"] = _normalize_policy_enforcement_mode(policy.policy_enforcement_mode)

    updated = db.update_project_policy(project_id, **kwargs)
    try:
        if updated.local_path:
            constitution_path = Path(updated.local_path).expanduser() / ".specify" / "memory" / "constitution.md"
            if constitution_path.exists():
                policy_service = PolicyService(ctx, db)
                effective = policy_service.resolve_effective_policy(
                    project_id,
                    repo_root=Path(updated.local_path).expanduser(),
                    include_repo_local=True,
                )
                constitution_content = policy_service.render_constitution(effective)
                spec_service = SpecificationService(ctx, db)
                spec_service.save_constitution(updated.local_path, constitution_content, project_id=project_id)
    except Exception:
        pass

    return updated

@router.get("/projects/{project_id}/policy/effective", response_model=schemas.EffectivePolicyOut)
def get_effective_policy(
    project_id: int,
    db: Database = Depends(get_db),
    ctx: ServiceContext = Depends(get_service_context),
):
    """Get computed effective policy with hash."""
    try:
        project = db.get_project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    
    from devgodzilla.services.policy import PolicyService
    from pathlib import Path
    
    policy_service = PolicyService(ctx, db)
    
    # Determine repo root
    repo_root = None
    if project.local_path:
        try:
            repo_root = Path(project.local_path).expanduser()
        except Exception:
            pass
    
    effective = policy_service.resolve_effective_policy(
        project_id,
        repo_root=repo_root,
        include_repo_local=True,
    )
    
    return schemas.EffectivePolicyOut(
        hash=effective.effective_hash,
        policy=effective.policy,
        pack_key=effective.pack_key,
        pack_version=effective.pack_version,
    )

@router.get("/projects/{project_id}/policy/findings", response_model=List[schemas.PolicyFindingOut])
def get_policy_findings(
    project_id: int,
    db: Database = Depends(get_db),
    ctx: ServiceContext = Depends(get_service_context),
):
    """Get policy violation findings for a project."""
    try:
        db.get_project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    
    from devgodzilla.services.policy import PolicyService
    
    policy_service = PolicyService(ctx, db)
    findings = policy_service.evaluate_project(project_id)
    
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

@router.get("/projects/{project_id}/branches", response_model=List[schemas.BranchOut])
def list_project_branches(
    project_id: int,
    db: Database = Depends(get_db),
    ctx: ServiceContext = Depends(get_service_context),
):
    """List git branches for a project repository."""
    try:
        project = db.get_project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not project.local_path:
        raise HTTPException(status_code=400, detail="Project has no local repository path")
    
    from pathlib import Path
    from devgodzilla.services.git import GitService, run_process
    
    repo_path = Path(project.local_path).expanduser()
    if not repo_path.exists():
        raise HTTPException(status_code=400, detail="Project repository path does not exist")
    
    if not (repo_path / ".git").exists():
        raise HTTPException(status_code=400, detail="Project path is not a git repository")

    git_service = GitService(ctx)
    github_token = _project_github_token(project)
    branches = []
    
    # Get local branches with their SHAs
    try:
        result = run_process(
            ["git", "for-each-ref", "--format=%(refname:short) %(objectname)", "refs/heads/"],
            cwd=repo_path,
        )
        for line in result.stdout.strip().splitlines():
            if line:
                parts = line.split()
                if len(parts) >= 2:
                    branches.append(schemas.BranchOut(
                        name=parts[0],
                        sha=parts[1],
                        is_remote=False,
                    ))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to list local branches: {exc}")
    
    # Get remote branches with their SHAs
    try:
        result = run_process(
            ["git", "ls-remote", "--heads", "origin"],
            cwd=repo_path,
            check=False,
            env=git_service.build_repo_remote_git_env(repo_path, github_token),
        )
        if result.returncode != 0:
            stderr = (result.stderr or "").lower()
            # Repos used in local tests/dev can have no configured origin.
            if (
                "no such remote" in stderr
                or "could not read from remote repository" in stderr
                or "could not read username" in stderr
                or "authentication failed" in stderr
            ):
                return branches
            raise HTTPException(
                status_code=502,
                detail=f"Failed to list remote branches: {(result.stderr or result.stdout or '').strip()}",
            )
        for line in result.stdout.strip().splitlines():
            if line:
                parts = line.split()
                if len(parts) >= 2 and parts[1].startswith("refs/heads/"):
                    branch_name = parts[1].replace("refs/heads/", "")
                    # Only add if not already in local branches
                    if not any(b.name == branch_name and not b.is_remote for b in branches):
                        branches.append(schemas.BranchOut(
                            name=branch_name,
                            sha=parts[0],
                            is_remote=True,
                        ))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to list remote branches: {exc}")
    
    return branches


@router.post("/projects/{project_id}/branches")
def create_project_branch(
    project_id: int,
    request: CreateBranchRequest,
    db: Database = Depends(get_db),
):
    """Create a git branch in the project repository."""
    try:
        project = db.get_project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.local_path:
        raise HTTPException(status_code=400, detail="Project has no local repository path")

    from devgodzilla.services.git import run_process

    repo_path = Path(project.local_path).expanduser()
    if not repo_path.exists():
        raise HTTPException(status_code=400, detail="Project repository path does not exist")
    if not (repo_path / ".git").exists():
        raise HTTPException(status_code=400, detail="Project path is not a git repository")

    branch_name = (request.name or "").strip()
    if not branch_name:
        raise HTTPException(status_code=400, detail="Branch name is required")

    ref_check = run_process(["git", "check-ref-format", "--branch", branch_name], cwd=repo_path, check=False)
    if ref_check.returncode != 0:
        raise HTTPException(status_code=400, detail="Invalid branch name")

    base_ref = (request.base_ref or project.base_branch or "main").strip()
    base_commit = None
    for candidate in (base_ref, f"origin/{base_ref}"):
        res = run_process(["git", "rev-parse", "--verify", f"{candidate}^{{commit}}"], cwd=repo_path, check=False)
        if res.returncode == 0:
            base_commit = candidate
            break
    if not base_commit:
        raise HTTPException(status_code=400, detail=f"Base ref not found: {base_ref}")

    exists_res = run_process(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"], cwd=repo_path, check=False)
    if exists_res.returncode == 0:
        raise HTTPException(status_code=409, detail=f"Branch already exists: {branch_name}")

    run_process(["git", "branch", branch_name, base_commit], cwd=repo_path, check=True)
    if request.checkout:
        run_process(["git", "checkout", branch_name], cwd=repo_path, check=True)
    if request.push:
        run_process(["git", "push", "-u", "origin", branch_name], cwd=repo_path, check=True)

    _append_project_event(
        db,
        project_id=project_id,
        event_type="git_branch_created",
        message=f"Created branch {branch_name} from {base_commit}",
        metadata={"branch": branch_name, "base_ref": base_ref, "checkout": request.checkout, "push": request.push},
    )
    return {"message": f"Branch created: {branch_name}", "branch": branch_name}


@router.post("/projects/{project_id}/branches/{branch}/delete")
def delete_project_branch(
    project_id: int,
    branch: str,
    delete_remote: bool = False,
    db: Database = Depends(get_db),
):
    """Delete a local (and optionally remote) git branch for the project repository."""
    try:
        project = db.get_project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.local_path:
        raise HTTPException(status_code=400, detail="Project has no local repository path")

    from devgodzilla.services.git import run_process

    repo_path = Path(project.local_path).expanduser()
    if not repo_path.exists():
        raise HTTPException(status_code=400, detail="Project repository path does not exist")
    if not (repo_path / ".git").exists():
        raise HTTPException(status_code=400, detail="Project path is not a git repository")

    branch_name = (branch or "").strip()
    if not branch_name:
        raise HTTPException(status_code=400, detail="Branch name is required")

    current_branch = run_process(["git", "symbolic-ref", "--short", "HEAD"], cwd=repo_path, check=False).stdout.strip()
    if current_branch and current_branch == branch_name:
        raise HTTPException(status_code=400, detail="Cannot delete the currently checked out branch")

    exists_res = run_process(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"], cwd=repo_path, check=False)
    if exists_res.returncode != 0:
        raise HTTPException(status_code=404, detail=f"Local branch not found: {branch_name}")

    run_process(["git", "branch", "-D", branch_name], cwd=repo_path, check=True)

    deleted_remote_branch = False
    if delete_remote:
        remote_res = run_process(["git", "push", "origin", "--delete", branch_name], cwd=repo_path, check=False)
        deleted_remote_branch = remote_res.returncode == 0

    _append_project_event(
        db,
        project_id=project_id,
        event_type="git_branch_deleted",
        message=f"Deleted branch {branch_name}",
        metadata={"branch": branch_name, "deleted_remote": deleted_remote_branch},
    )
    return {"message": f"Branch deleted: {branch_name}"}

@router.get("/projects/{project_id}/clarifications", response_model=List[schemas.ClarificationOut])
def list_project_clarifications(
    project_id: int,
    status: Optional[str] = None,
    limit: int = 100,
    db: Database = Depends(get_db)
):
    """List clarifications scoped to a project."""
    try:
        db.get_project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return db.list_clarifications(
        project_id=project_id,
        status=status,
        limit=limit
    )

@router.post("/projects/{project_id}/clarifications/{key}", response_model=schemas.ClarificationOut)
def answer_project_clarification(
    project_id: int,
    key: str,
    answer: schemas.ClarificationAnswer,
    db: Database = Depends(get_db)
):
    """Answer a clarification scoped to a project."""
    try:
        db.get_project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Construct scope for project-level clarification
    scope = f"project:{project_id}"
    
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

@router.get("/projects/{project_id}/constitution")
def get_project_constitution_compat(
    project_id: int,
    db: Database = Depends(get_db),
):
    """Compatibility route — returns constitution content from disk."""
    from pathlib import Path as _Path
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    constitution_path = _Path(project.local_path).expanduser() / ".specify" / "memory" / "constitution.md"
    if constitution_path.exists():
        return {"content": constitution_path.read_text()}
    raise HTTPException(status_code=404, detail="Constitution not found")


@router.get("/projects/{project_id}/commits", response_model=List[schemas.CommitOut])
def list_project_commits(
    project_id: int,
    limit: int = 20,
    db: Database = Depends(get_db),
    ctx: ServiceContext = Depends(get_service_context),
):
    """List recent git commits for a project repository."""
    try:
        project = db.get_project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not project.local_path:
        raise HTTPException(status_code=400, detail="Project has no local repository path")
    
    from pathlib import Path
    from devgodzilla.services.git import run_process
    
    repo_path = Path(project.local_path).expanduser()
    if not repo_path.exists():
        raise HTTPException(status_code=400, detail="Project repository path does not exist")
    
    if not (repo_path / ".git").exists():
        raise HTTPException(status_code=400, detail="Project path is not a git repository")
    
    commits = []
    try:
        # Use git log to get recent commits with format: sha|subject|author name|ISO-8601 date
        result = run_process(
            ["git", "log", f"-{limit}", "--format=%H|%s|%an|%aI"],
            cwd=repo_path,
        )
        for line in result.stdout.strip().splitlines():
            if line:
                parts = line.split("|", 3)
                if len(parts) >= 4:
                    commits.append(schemas.CommitOut(
                        sha=parts[0],
                        message=parts[1],
                        author=parts[2],
                        date=parts[3],
                    ))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to list commits: {exc}")
    
    return commits

@router.get("/projects/{project_id}/pulls", response_model=List[schemas.PullRequestOut])
def list_project_pulls(
    project_id: int,
    db: Database = Depends(get_db),
    ctx: ServiceContext = Depends(get_service_context),
):
    """List open pull requests for a project repository (GitHub only)."""
    try:
        project = db.get_project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not project.local_path:
        return []  # No repo path, return empty list
    
    from devgodzilla.services.git import run_process

    repo_path = Path(project.local_path).expanduser()
    if not repo_path.exists() or not (repo_path / ".git").exists():
        return []

    github_token = _project_github_token(project)
    owner_repo = _project_github_owner_repo(repo_path, project)
    pulls: list[schemas.PullRequestOut] = []
    try:
        # Use GitHub CLI to list PRs (requires gh to be installed and authenticated)
        result = run_process(
            ["gh", "pr", "list", "--json", "number,title,headRefName,state,author,url,createdAt,statusCheckRollup"],
            cwd=repo_path,
            check=False,
            env={**os.environ, **({"GH_TOKEN": github_token, "GITHUB_TOKEN": github_token} if github_token else {})},
        )
        if result.returncode == 0 and result.stdout.strip():
            pr_data = json.loads(result.stdout)
            for pr in pr_data:
                # Determine check status
                checks = "unknown"
                if pr.get("statusCheckRollup"):
                    check_statuses = [c.get("conclusion") or c.get("state") for c in pr["statusCheckRollup"]]
                    if all(s in ("SUCCESS", "success", "COMPLETED") for s in check_statuses if s):
                        checks = "passing"
                    elif any(s in ("FAILURE", "failure", "FAILED") for s in check_statuses if s):
                        checks = "failing"
                    elif any(s in ("PENDING", "pending", "IN_PROGRESS", "QUEUED") for s in check_statuses if s):
                        checks = "pending"
                
                pulls.append(schemas.PullRequestOut(
                    id=str(pr.get("number", "")),
                    title=pr.get("title", ""),
                    branch=pr.get("headRefName", ""),
                    status=pr.get("state", "open").lower(),
                    checks=checks,
                    url=pr.get("url", ""),
                    author=pr.get("author", {}).get("login", "") if isinstance(pr.get("author"), dict) else "",
                    created_at=pr.get("createdAt", ""),
                ))
            return pulls
    except FileNotFoundError:
        pass
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to parse GitHub PR response: {exc}")
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise HTTPException(status_code=502, detail=f"Failed to list pull requests: {detail}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to list pull requests: {exc}")

    if owner_repo is None:
        return []
    owner, repo = owner_repo
    return _list_github_pulls(owner, repo, github_token=github_token)


@router.get("/projects/{project_id}/worktrees", response_model=List[schemas.WorktreeOut])
def list_project_worktrees(
    project_id: int,
    db: Database = Depends(get_db),
    ctx: ServiceContext = Depends(get_service_context),
):
    """List worktrees associated with protocols and spec runs for a project."""
    try:
        project = db.get_project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not project.local_path:
        return []
    
    from devgodzilla.services.git import run_process
    
    repo_path = Path(project.local_path).expanduser()
    if not repo_path.exists() or not (repo_path / ".git").exists():
        return []
    
    worktrees = []
    
    # Get all protocol runs for this project to find associated branches
    try:
        protocols = db.list_protocol_runs(project_id=project_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load protocol runs: {exc}")
    
    # Build a map of branch names to protocols
    branch_protocols = {}
    for p in protocols:
        # Protocol branch name is typically the protocol_name
        branch_name = p.protocol_name
        if branch_name:
            branch_protocols[branch_name] = p
    
    # Get git worktrees if any
    worktree_paths = {}
    try:
        result = run_process(
            ["git", "worktree", "list", "--porcelain"],
            cwd=repo_path,
            check=False,
        )
        if result.returncode == 0:
            current_worktree = None
            current_branch = None
            for line in result.stdout.strip().splitlines():
                if line.startswith("worktree "):
                    current_worktree = line.split(" ", 1)[1]
                elif line.startswith("branch refs/heads/"):
                    current_branch = line.replace("branch refs/heads/", "")
                    if current_worktree and current_branch:
                        worktree_paths[current_branch] = current_worktree
                    current_worktree = None
                    current_branch = None
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to list git worktrees: {exc}")
    
    github_token = _project_github_token(project)
    owner_repo = _project_github_owner_repo(repo_path, project)
    pulls_by_branch: dict[str, schemas.PullRequestOut] = {}
    if owner_repo is not None:
        owner, repo = owner_repo
        pulls_by_branch = {
            pull.branch: pull
            for pull in _list_github_pulls(owner, repo, github_token=github_token)
            if pull.branch
        }

    # Build worktree list from protocols
    for branch_name, protocol in branch_protocols.items():
        # Get last commit for this branch
        last_sha = None
        last_message = None
        last_date = None
        try:
            result = run_process(
                ["git", "log", "-1", "--format=%H|%s|%aI", branch_name],
                cwd=repo_path,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split("|", 2)
                if len(parts) >= 3:
                    last_sha = parts[0]
                    last_message = parts[1]
                    last_date = parts[2]
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Failed to read branch commit for {branch_name}: {exc}")
        
        # Check if there's a PR for this branch
        pr_url = None
        pull = pulls_by_branch.get(branch_name)
        if pull is not None:
            pr_url = pull.url

        worktrees.append(schemas.WorktreeOut(
            branch_name=branch_name,
            worktree_path=worktree_paths.get(branch_name) or protocol.worktree_path,
            protocol_run_id=protocol.id,
            protocol_name=protocol.protocol_name,
            protocol_status=protocol.status,
            spec_run_id=None,
            last_commit_sha=last_sha,
            last_commit_message=last_message,
            last_commit_date=last_date,
            pr_url=pr_url,
        ))
    
    # Also include worktrees from spec runs that aren't already listed
    try:
        spec_runs = db.list_spec_runs(project_id)
    except Exception:
        spec_runs = []
    
    existing_branches = {w.branch_name for w in worktrees}
    for sr in spec_runs:
        if not sr.branch_name or sr.branch_name in existing_branches:
            continue
        branch_name = sr.branch_name
        
        # Get last commit for this branch
        last_sha = None
        last_message = None
        last_date = None
        try:
            result = run_process(
                ["git", "log", "-1", "--format=%H|%s|%aI", branch_name],
                cwd=repo_path,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split("|", 2)
                if len(parts) >= 3:
                    last_sha = parts[0]
                    last_message = parts[1]
                    last_date = parts[2]
        except Exception:
            pass
        
        pr_url = None
        pull = pulls_by_branch.get(branch_name)
        if pull is not None:
            pr_url = pull.url
        
        worktrees.append(schemas.WorktreeOut(
            branch_name=branch_name,
            worktree_path=worktree_paths.get(branch_name) or sr.worktree_path,
            protocol_run_id=sr.protocol_run_id,
            protocol_name=sr.feature_name or sr.spec_name,
            protocol_status=sr.status,
            spec_run_id=sr.id,
            last_commit_sha=last_sha,
            last_commit_message=last_message,
            last_commit_date=last_date,
            pr_url=pr_url,
        ))
        existing_branches.add(branch_name)
    
    return worktrees
