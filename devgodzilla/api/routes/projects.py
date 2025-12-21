from __future__ import annotations

import os
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from devgodzilla.api import schemas
from devgodzilla.api.dependencies import get_db, get_service_context
from devgodzilla.db.database import Database, _UNSET
from devgodzilla.events_catalog import normalize_event_type
from devgodzilla.services.base import ServiceContext
from devgodzilla.services.policy import PolicyService
from devgodzilla.services.clarifier import ClarifierService
from devgodzilla.services.specification import SpecificationService
from pathlib import Path

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


class ProjectOnboardRequest(BaseModel):
    branch: Optional[str] = Field(default=None, description="Branch to checkout after clone (defaults to project.base_branch)")
    clone_if_missing: bool = Field(default=True, description="Clone repo if local_path is missing")
    constitution_content: Optional[str] = Field(default=None, description="Optional custom constitution content")
    run_discovery_agent: bool = Field(default=True, description="Run headless agent discovery (writes tasksgodzilla/*)")
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


@router.post("/projects", response_model=schemas.ProjectOut)
def create_project(
    project: schemas.ProjectCreate,
    db: Database = Depends(get_db),
    ctx: ServiceContext = Depends(get_service_context),
):
    """Create a new project."""
    if project.auto_onboard and not (project.git_url or "").strip():
        raise HTTPException(status_code=400, detail="git_url is required for auto onboarding")
    if project.auto_onboard and not getattr(ctx.config, "windmill_enabled", False):
        raise HTTPException(status_code=503, detail="Windmill integration not configured")

    created = db.create_project(
        name=project.name,
        git_url=project.git_url or "",
        base_branch=project.base_branch,
        local_path=project.local_path,
    )

    if project.auto_onboard:
        try:
            from devgodzilla.services.onboarding_queue import enqueue_project_onboarding

            enqueue_project_onboarding(
                ctx,
                db,
                project_id=created.id,
                branch=created.base_branch,
                run_discovery_agent=bool(project.auto_discovery),
            )
        except Exception as exc:
            _append_project_event(
                db,
                project_id=created.id,
                event_type="onboarding_enqueue_failed",
                message="Failed to enqueue onboarding",
                metadata={"error": str(exc)},
            )
            raise HTTPException(status_code=502, detail=f"Failed to enqueue onboarding: {exc}")

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
        return db.update_project(
            project_id,
            name=project.name,
            description=project.description if project.description is not None else _UNSET,
            status=project.status.value if project.status else None,
            git_url=project.git_url,
            base_branch=project.base_branch,
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


@router.post("/projects/{project_id}/actions/onboard", response_model=ProjectOnboardResponse)
@router.post("/projects/{project_id}/onboarding/actions/start", response_model=ProjectOnboardResponse)
def onboard_project(
    project_id: int,
    request: ProjectOnboardRequest = ProjectOnboardRequest(), # Allow empty body
    db: Database = Depends(get_db),
    ctx: ServiceContext = Depends(get_service_context),
):
    """
    Onboard a project repository for DevGodzilla workflows.

    - Ensures the repo exists locally (clone if missing)
    - Checks out the requested branch (or project.base_branch)
    - Initializes `.specify/` via SpecificationService
    """
    try:
        project = db.get_project(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.git_url:
        raise HTTPException(status_code=400, detail="Project has no git_url")

    from devgodzilla.services.git import GitService, run_process
    from devgodzilla.services.specification import SpecificationService

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

    git = GitService(ctx)
    try:
        repo_path = git.resolve_repo_path(
            project.git_url,
            project.name,
            project.local_path,
            project_id=project.id,
            clone_if_missing=bool(request.clone_if_missing),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Clone failed: {exc}")

    branch = (request.branch or project.base_branch or "main").strip()
    if branch:
        try:
            run_process(["git", "fetch", "--prune", "origin", branch], cwd=repo_path, check=False)
            # Prefer tracking branch when available.
            res = run_process(["git", "checkout", branch], cwd=repo_path, check=False)
            if res.returncode != 0:
                run_process(["git", "checkout", "-B", branch, f"origin/{branch}"], cwd=repo_path, check=False)
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
    init_result = spec_service.init_project(
        str(repo_path),
        constitution_content=constitution_content,
        project_id=project_id,
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
        except Exception as e:
            discovery_success = False
            discovery_error = str(e)
        _append_project_event(
            db,
            project_id=project_id,
            event_type="discovery_completed" if discovery_success else "discovery_failed",
            message="Discovery completed" if discovery_success else "Discovery failed",
            metadata={
                "success": discovery_success,
                "log_path": discovery_log_path,
                "missing_outputs": discovery_missing_outputs,
                "error": discovery_error,
            },
        )
    else:
        _append_project_event(
            db,
            project_id=project_id,
            event_type="discovery_skipped",
            message="Discovery skipped",
            metadata={"reason": "disabled"},
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
    except Exception as e:
        discovery_success = False
        discovery_error = str(e)

    _append_project_event(
        db,
        project_id=project_id,
        event_type="discovery_completed" if discovery_success else "discovery_failed",
        message="Discovery completed" if discovery_success else "Discovery failed",
        metadata={
            "success": discovery_success,
            "log_path": discovery_log_path,
            "missing_outputs": discovery_missing_outputs,
            "error": discovery_error,
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
    log_path = repo_root / "opencode-discovery.log"
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
    except Exception:
        pass
    
    # Get remote branches with their SHAs
    try:
        result = run_process(
            ["git", "ls-remote", "--heads", "origin"],
            cwd=repo_path,
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
    except Exception:
        pass
    
    return branches

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
        # Use git log to get recent commits with format: sha|subject|author name|relative date
        result = run_process(
            ["git", "log", f"-{limit}", "--format=%H|%s|%an|%ar"],
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
    except Exception:
        pass
    
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
    
    from pathlib import Path
    from devgodzilla.services.git import run_process
    import json
    
    repo_path = Path(project.local_path).expanduser()
    if not repo_path.exists() or not (repo_path / ".git").exists():
        return []
    
    pulls = []
    try:
        # Use GitHub CLI to list PRs (requires gh to be installed and authenticated)
        result = run_process(
            ["gh", "pr", "list", "--json", "number,title,headRefName,state,author,url,createdAt,statusCheckRollup"],
            cwd=repo_path,
            check=False,
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
    except Exception:
        pass  # gh CLI not available or not authenticated
    
    return pulls


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
    except Exception:
        protocols = []
    
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
    except Exception:
        pass
    
    # Build worktree list from protocols
    for branch_name, protocol in branch_protocols.items():
        # Get last commit for this branch
        last_sha = None
        last_message = None
        last_date = None
        try:
            result = run_process(
                ["git", "log", "-1", "--format=%H|%s|%ar", branch_name],
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
        
        # Check if there's a PR for this branch
        pr_url = None
        try:
            result = run_process(
                ["gh", "pr", "view", branch_name, "--json", "url"],
                cwd=repo_path,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                import json
                pr_data = json.loads(result.stdout)
                pr_url = pr_data.get("url")
        except Exception:
            pass
        
        worktrees.append(schemas.WorktreeOut(
            branch_name=branch_name,
            worktree_path=worktree_paths.get(branch_name) or protocol.worktree_path,
            protocol_run_id=protocol.id,
            protocol_name=protocol.protocol_name,
            protocol_status=protocol.status,
            spec_run_id=None,  # Could be populated if we track spec runs per protocol
            last_commit_sha=last_sha,
            last_commit_message=last_message,
            last_commit_date=last_date,
            pr_url=pr_url,
        ))
    
    return worktrees
