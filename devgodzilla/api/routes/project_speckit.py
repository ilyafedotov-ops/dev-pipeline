from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from devgodzilla.api.dependencies import get_db, get_service_context
from devgodzilla.db.database import Database
from devgodzilla.services.base import ServiceContext
from devgodzilla.services.specification import SpecificationService
from devgodzilla.services.policy import PolicyService
from pathlib import Path

router = APIRouter(tags=["SpecKit"])


class SpecKitResponse(BaseModel):
    success: bool
    path: Optional[str] = None
    constitution_hash: Optional[str] = None
    error: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)


class ConstitutionRequest(BaseModel):
    content: str = Field(..., min_length=10)


class SpecifyRequest(BaseModel):
    description: str = Field(..., min_length=10)
    feature_name: Optional[str] = None
    base_branch: Optional[str] = None


class SpecifyResponse(BaseModel):
    success: bool
    spec_path: Optional[str] = None
    spec_number: Optional[int] = None
    feature_name: Optional[str] = None
    spec_run_id: Optional[int] = None
    worktree_path: Optional[str] = None
    branch_name: Optional[str] = None
    base_branch: Optional[str] = None
    spec_root: Optional[str] = None
    error: Optional[str] = None


class PlanRequest(BaseModel):
    spec_path: str
    spec_run_id: Optional[int] = None


class PlanResponse(BaseModel):
    success: bool
    plan_path: Optional[str] = None
    data_model_path: Optional[str] = None
    contracts_path: Optional[str] = None
    spec_run_id: Optional[int] = None
    worktree_path: Optional[str] = None
    error: Optional[str] = None


class TasksRequest(BaseModel):
    plan_path: str
    spec_run_id: Optional[int] = None


class TasksResponse(BaseModel):
    success: bool
    tasks_path: Optional[str] = None
    task_count: int = 0
    parallelizable_count: int = 0
    spec_run_id: Optional[int] = None
    worktree_path: Optional[str] = None
    error: Optional[str] = None


class ClarificationEntry(BaseModel):
    question: str
    answer: str


class ClarifyRequest(BaseModel):
    spec_path: str
    entries: List[ClarificationEntry] = Field(default_factory=list)
    notes: Optional[str] = None
    spec_run_id: Optional[int] = None


class ClarifyResponse(BaseModel):
    success: bool
    spec_path: Optional[str] = None
    clarifications_added: int = 0
    spec_run_id: Optional[int] = None
    worktree_path: Optional[str] = None
    error: Optional[str] = None


class ChecklistRequest(BaseModel):
    spec_path: str
    spec_run_id: Optional[int] = None


class ChecklistResponse(BaseModel):
    success: bool
    checklist_path: Optional[str] = None
    item_count: int = 0
    spec_run_id: Optional[int] = None
    worktree_path: Optional[str] = None
    error: Optional[str] = None


class AnalyzeRequest(BaseModel):
    spec_path: str
    plan_path: Optional[str] = None
    tasks_path: Optional[str] = None
    spec_run_id: Optional[int] = None


class AnalyzeResponse(BaseModel):
    success: bool
    report_path: Optional[str] = None
    spec_run_id: Optional[int] = None
    worktree_path: Optional[str] = None
    error: Optional[str] = None


class ImplementRequest(BaseModel):
    spec_path: str
    spec_run_id: Optional[int] = None


class ImplementResponse(BaseModel):
    success: bool
    run_path: Optional[str] = None
    metadata_path: Optional[str] = None
    spec_run_id: Optional[int] = None
    worktree_path: Optional[str] = None
    error: Optional[str] = None


def _service(
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
) -> SpecificationService:
    return SpecificationService(ctx, db)


@router.post("/projects/{project_id}/speckit/init", response_model=SpecKitResponse)
def init_project_speckit(
    project_id: int,
    request: Optional[ConstitutionRequest] = None,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(_service),
    ctx: ServiceContext = Depends(get_service_context),
):
    project = db.get_project(project_id)
    if not project.local_path:
        raise HTTPException(status_code=400, detail="Project has no local path")
    constitution_content = request.content if request else None
    if constitution_content is None:
        policy_service = PolicyService(ctx, db)
        effective = policy_service.resolve_effective_policy(
            project_id,
            repo_root=Path(project.local_path).expanduser(),
            include_repo_local=True,
        )
        constitution_content = policy_service.render_constitution(effective)
    result = service.init_project(
        project.local_path,
        constitution_content=constitution_content,
        project_id=project_id,
    )
    return SpecKitResponse(
        success=result.success,
        path=result.spec_path,
        constitution_hash=result.constitution_hash,
        error=result.error,
        warnings=result.warnings,
    )


@router.get("/projects/{project_id}/speckit/constitution")
def get_project_constitution(
    project_id: int,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(_service),
):
    project = db.get_project(project_id)
    if not project.local_path:
        raise HTTPException(status_code=400, detail="Project has no local path")
    content = service.get_constitution(project.local_path)
    if content is None:
        raise HTTPException(status_code=404, detail="Constitution not found")
    return {"content": content}


@router.put("/projects/{project_id}/speckit/constitution", response_model=SpecKitResponse)
def put_project_constitution(
    project_id: int,
    request: ConstitutionRequest,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(_service),
    ctx: ServiceContext = Depends(get_service_context),
):
    project = db.get_project(project_id)
    if not project.local_path:
        raise HTTPException(status_code=400, detail="Project has no local path")
    result = service.save_constitution(project.local_path, request.content, project_id=project_id)
    policy_service = PolicyService(ctx, db)
    override, meta = policy_service.policy_override_from_constitution(request.content)
    updates: dict[str, Any] = {}
    if isinstance(meta.get("key"), str):
        updates["policy_pack_key"] = meta["key"]
    if isinstance(meta.get("version"), str):
        updates["policy_pack_version"] = meta["version"]
    if override is not None:
        updates["policy_overrides"] = override
    if updates:
        db.update_project_policy(project_id, **updates)
    return SpecKitResponse(
        success=result.success,
        path=result.spec_path,
        constitution_hash=result.constitution_hash,
        error=result.error,
    )


@router.post("/projects/{project_id}/speckit/constitution/sync", response_model=SpecKitResponse)
def sync_project_constitution(
    project_id: int,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(_service),
    ctx: ServiceContext = Depends(get_service_context),
):
    project = db.get_project(project_id)
    if not project.local_path:
        raise HTTPException(status_code=400, detail="Project has no local path")
    policy_service = PolicyService(ctx, db)
    effective = policy_service.resolve_effective_policy(
        project_id,
        repo_root=Path(project.local_path).expanduser(),
        include_repo_local=True,
    )
    constitution_content = policy_service.render_constitution(effective)
    result = service.save_constitution(project.local_path, constitution_content, project_id=project_id)
    return SpecKitResponse(
        success=result.success,
        path=result.spec_path,
        constitution_hash=result.constitution_hash,
        error=result.error,
        warnings=result.warnings,
    )


@router.post("/projects/{project_id}/speckit/specify", response_model=SpecifyResponse)
def project_speckit_specify(
    project_id: int,
    request: SpecifyRequest,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(_service),
):
    project = db.get_project(project_id)
    if not project.local_path:
        raise HTTPException(status_code=400, detail="Project has no local path")
    
    # Emit start event
    try:
        db.append_event(
            protocol_run_id=None,
            project_id=project_id,
            event_type="speckit_specify_started",
            message=f"Starting spec generation: {request.description[:50]}...",
            metadata={
                "feature_name": request.feature_name,
                "description_preview": request.description[:100],
            },
        )
    except Exception:
        pass  # Don't fail the request if event emission fails
    
    result = service.run_specify(
        project.local_path,
        request.description,
        feature_name=request.feature_name,
        base_branch=request.base_branch,
        project_id=project_id,
    )
    
    # Emit result event
    try:
        if result.success:
            db.append_event(
                protocol_run_id=None,
                project_id=project_id,
                event_type="speckit_specify_completed",
                message=f"Spec generated: {result.feature_name}",
                metadata={
                    "spec_number": result.spec_number,
                    "feature_name": result.feature_name,
                    "spec_path": result.spec_path,
                    "spec_run_id": result.spec_run_id,
                },
            )
        else:
            db.append_event(
                protocol_run_id=None,
                project_id=project_id,
                event_type="speckit_specify_failed",
                message=f"Spec generation failed: {result.error or 'Unknown error'}",
                metadata={
                    "feature_name": request.feature_name,
                    "error": result.error,
                    "spec_run_id": result.spec_run_id,
                },
            )
    except Exception:
        pass  # Don't fail the request if event emission fails
    
    return SpecifyResponse(
        success=result.success,
        spec_path=result.spec_path,
        spec_number=result.spec_number,
        feature_name=result.feature_name,
        spec_run_id=result.spec_run_id,
        worktree_path=result.worktree_path,
        branch_name=result.branch_name,
        base_branch=result.base_branch,
        spec_root=result.spec_root,
        error=result.error,
    )


@router.post("/projects/{project_id}/speckit/plan", response_model=PlanResponse)
def project_speckit_plan(
    project_id: int,
    request: PlanRequest,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(_service),
):
    project = db.get_project(project_id)
    if not project.local_path:
        raise HTTPException(status_code=400, detail="Project has no local path")
    result = service.run_plan(
        project.local_path,
        request.spec_path,
        spec_run_id=request.spec_run_id,
        project_id=project_id,
    )
    return PlanResponse(
        success=result.success,
        plan_path=result.plan_path,
        data_model_path=result.data_model_path,
        contracts_path=result.contracts_path,
        spec_run_id=result.spec_run_id,
        worktree_path=result.worktree_path,
        error=result.error,
    )


@router.post("/projects/{project_id}/speckit/tasks", response_model=TasksResponse)
def project_speckit_tasks(
    project_id: int,
    request: TasksRequest,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(_service),
):
    project = db.get_project(project_id)
    if not project.local_path:
        raise HTTPException(status_code=400, detail="Project has no local path")
    result = service.run_tasks(
        project.local_path,
        request.plan_path,
        spec_run_id=request.spec_run_id,
        project_id=project_id,
    )
    return TasksResponse(
        success=result.success,
        tasks_path=result.tasks_path,
        task_count=result.task_count,
        parallelizable_count=result.parallelizable_count,
        spec_run_id=result.spec_run_id,
        worktree_path=result.worktree_path,
        error=result.error,
    )


@router.post("/projects/{project_id}/speckit/clarify", response_model=ClarifyResponse)
def project_speckit_clarify(
    project_id: int,
    request: ClarifyRequest,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(_service),
):
    project = db.get_project(project_id)
    if not project.local_path:
        raise HTTPException(status_code=400, detail="Project has no local path")
    result = service.run_clarify(
        project.local_path,
        request.spec_path,
        entries=[entry.dict() for entry in request.entries],
        notes=request.notes,
        spec_run_id=request.spec_run_id,
        project_id=project_id,
    )
    return ClarifyResponse(
        success=result.success,
        spec_path=result.spec_path,
        clarifications_added=result.clarifications_added,
        spec_run_id=result.spec_run_id,
        worktree_path=result.worktree_path,
        error=result.error,
    )


@router.post("/projects/{project_id}/speckit/checklist", response_model=ChecklistResponse)
def project_speckit_checklist(
    project_id: int,
    request: ChecklistRequest,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(_service),
):
    project = db.get_project(project_id)
    if not project.local_path:
        raise HTTPException(status_code=400, detail="Project has no local path")
    result = service.run_checklist(
        project.local_path,
        request.spec_path,
        spec_run_id=request.spec_run_id,
        project_id=project_id,
    )
    return ChecklistResponse(
        success=result.success,
        checklist_path=result.checklist_path,
        item_count=result.item_count,
        spec_run_id=result.spec_run_id,
        worktree_path=result.worktree_path,
        error=result.error,
    )


@router.post("/projects/{project_id}/speckit/analyze", response_model=AnalyzeResponse)
def project_speckit_analyze(
    project_id: int,
    request: AnalyzeRequest,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(_service),
):
    project = db.get_project(project_id)
    if not project.local_path:
        raise HTTPException(status_code=400, detail="Project has no local path")
    result = service.run_analyze(
        project.local_path,
        request.spec_path,
        plan_path=request.plan_path,
        tasks_path=request.tasks_path,
        spec_run_id=request.spec_run_id,
        project_id=project_id,
    )
    return AnalyzeResponse(
        success=result.success,
        report_path=result.report_path,
        spec_run_id=result.spec_run_id,
        worktree_path=result.worktree_path,
        error=result.error,
    )


@router.post("/projects/{project_id}/speckit/implement", response_model=ImplementResponse)
def project_speckit_implement(
    project_id: int,
    request: ImplementRequest,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(_service),
):
    project = db.get_project(project_id)
    if not project.local_path:
        raise HTTPException(status_code=400, detail="Project has no local path")
    result = service.run_implement(
        project.local_path,
        request.spec_path,
        spec_run_id=request.spec_run_id,
        project_id=project_id,
    )
    return ImplementResponse(
        success=result.success,
        run_path=result.run_path,
        metadata_path=result.metadata_path,
        spec_run_id=result.spec_run_id,
        worktree_path=result.worktree_path,
        error=result.error,
    )
