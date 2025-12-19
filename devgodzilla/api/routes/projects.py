from __future__ import annotations

import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from devgodzilla.api import schemas
from devgodzilla.api.dependencies import get_db, get_service_context
from devgodzilla.db.database import Database, _UNSET
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
    run_discovery_agent: bool = Field(default=False, description="Run headless agent discovery (writes tasksgodzilla/*)")
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
    db: Database = Depends(get_db)
):
    """Create a new project."""
    return db.create_project(
        name=project.name,
        git_url=project.git_url or "",
        base_branch=project.base_branch,
        local_path=project.local_path
    )

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

    # Compute stages
    stages = []
    
    # Stage 1: Repository Setup
    repo_status = "completed" if project.local_path else "pending"
    stages.append(schemas.OnboardingStage(
        name="Repository Setup",
        status=repo_status,
        completed_at=project.created_at if repo_status == "completed" else None
    ))

    # Stage 2: SpecKit Init
    spec_status = "completed" if project.constitution_hash else "pending"
    if repo_status == "pending":
        spec_status = "pending"
    
    stages.append(schemas.OnboardingStage(
        name="SpecKit Initialization",
        status=spec_status
    ))

    # Stage 3: Discovery
    stages.append(schemas.OnboardingStage(
        name="Discovery",
        status="skipped"
    ))

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

    if blocking_count > 0:
        overall_status = "blocked"
    else:
        overall_status = "completed" if (repo_status == "completed" and spec_status == "completed") else "pending"

    return schemas.OnboardingSummary(
        project_id=project_id,
        status=overall_status,
        stages=stages,
        events=[], 
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
            )
            discovery_success = bool(disc.success)
            discovery_log_path = str(disc.log_path)
            discovery_missing_outputs = [str(p) for p in disc.missing_outputs]
            discovery_error = disc.error
        except Exception as e:
            discovery_success = False
            discovery_error = str(e)
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
