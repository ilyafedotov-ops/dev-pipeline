"""
DevGodzilla SpecKit API Routes

REST endpoints for SpecKit integration: initialization, spec generation,
planning, and task management.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from devgodzilla.api.dependencies import get_db, get_service_context
from devgodzilla.db.database import Database
from devgodzilla.services.base import ServiceContext
from devgodzilla.services.specification import SpecificationService

router = APIRouter(prefix="/speckit", tags=["SpecKit"])


class InitRequest(BaseModel):
    project_id: int
    constitution_content: Optional[str] = None


class SpecKitResponse(BaseModel):
    success: bool
    path: Optional[str] = None
    constitution_hash: Optional[str] = None
    error: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)


class SpecifyRequest(BaseModel):
    project_id: int
    description: str = Field(..., min_length=10, description="Feature description")
    feature_name: Optional[str] = Field(None, description="Optional feature name")


class SpecifyResponse(BaseModel):
    success: bool
    spec_path: Optional[str] = None
    spec_number: Optional[int] = None
    feature_name: Optional[str] = None
    error: Optional[str] = None


class PlanRequest(BaseModel):
    project_id: int
    spec_path: str = Field(..., description="Path to spec.md file")


class PlanResponse(BaseModel):
    success: bool
    plan_path: Optional[str] = None
    data_model_path: Optional[str] = None
    contracts_path: Optional[str] = None
    error: Optional[str] = None


class TasksRequest(BaseModel):
    project_id: int
    plan_path: str = Field(..., description="Path to plan.md file")


class TasksResponse(BaseModel):
    success: bool
    tasks_path: Optional[str] = None
    task_count: int = 0
    parallelizable_count: int = 0
    error: Optional[str] = None


class ConstitutionRequest(BaseModel):
    content: str = Field(..., min_length=10)


class SpecListItem(BaseModel):
    name: str
    path: str
    has_spec: bool
    has_plan: bool
    has_tasks: bool


def get_specification_service(
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
) -> SpecificationService:
    return SpecificationService(ctx, db)


@router.post("/init", response_model=SpecKitResponse)
def init_speckit(
    request: InitRequest,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(get_specification_service),
):
    """Initialize SpecKit for a project."""
    project = db.get_project(request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.local_path:
        raise HTTPException(status_code=400, detail="Project has no local path")

    result = service.init_project(
        project.local_path,
        constitution_content=request.constitution_content,
        project_id=request.project_id,
    )

    return SpecKitResponse(
        success=result.success,
        path=result.spec_path,
        constitution_hash=result.constitution_hash,
        error=result.error,
        warnings=result.warnings,
    )


@router.get("/constitution/{project_id}")
def get_constitution(
    project_id: int,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(get_specification_service),
):
    """Get project constitution."""
    project = db.get_project(project_id)
    if not project or not project.local_path:
        raise HTTPException(status_code=404, detail="Project not found")

    content = service.get_constitution(project.local_path)
    if content is None:
        raise HTTPException(status_code=404, detail="Constitution not found. Run init first.")

    return {"content": content}


@router.put("/constitution/{project_id}", response_model=SpecKitResponse)
def save_constitution(
    project_id: int,
    request: ConstitutionRequest,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(get_specification_service),
):
    """Save project constitution."""
    project = db.get_project(project_id)
    if not project or not project.local_path:
        raise HTTPException(status_code=404, detail="Project not found")

    result = service.save_constitution(
        project.local_path,
        request.content,
        project_id=project_id,
    )

    return SpecKitResponse(
        success=result.success,
        path=result.spec_path,
        constitution_hash=result.constitution_hash,
        error=result.error,
    )


@router.post("/specify", response_model=SpecifyResponse)
def run_specify(
    request: SpecifyRequest,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(get_specification_service),
):
    """Generate a feature specification."""
    project = db.get_project(request.project_id)
    if not project or not project.local_path:
        raise HTTPException(status_code=404, detail="Project not found")

    result = service.run_specify(
        project.local_path,
        request.description,
        feature_name=request.feature_name,
        project_id=request.project_id,
    )

    return SpecifyResponse(
        success=result.success,
        spec_path=result.spec_path,
        spec_number=result.spec_number,
        feature_name=result.feature_name,
        error=result.error,
    )


@router.post("/plan", response_model=PlanResponse)
def run_plan(
    request: PlanRequest,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(get_specification_service),
):
    """Generate an implementation plan from a spec."""
    project = db.get_project(request.project_id)
    if not project or not project.local_path:
        raise HTTPException(status_code=404, detail="Project not found")

    result = service.run_plan(
        project.local_path,
        request.spec_path,
        project_id=request.project_id,
    )

    return PlanResponse(
        success=result.success,
        plan_path=result.plan_path,
        data_model_path=result.data_model_path,
        contracts_path=result.contracts_path,
        error=result.error,
    )


@router.post("/tasks", response_model=TasksResponse)
def run_tasks(
    request: TasksRequest,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(get_specification_service),
):
    """Generate a task list from a plan."""
    project = db.get_project(request.project_id)
    if not project or not project.local_path:
        raise HTTPException(status_code=404, detail="Project not found")

    result = service.run_tasks(
        project.local_path,
        request.plan_path,
        project_id=request.project_id,
    )

    return TasksResponse(
        success=result.success,
        tasks_path=result.tasks_path,
        task_count=result.task_count,
        parallelizable_count=result.parallelizable_count,
        error=result.error,
    )


@router.get("/specs/{project_id}", response_model=List[SpecListItem])
def list_specs(
    project_id: int,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(get_specification_service),
):
    """List all specs in a project."""
    project = db.get_project(project_id)
    if not project or not project.local_path:
        raise HTTPException(status_code=404, detail="Project not found")

    specs = service.list_specs(project.local_path)
    return [SpecListItem(**spec) for spec in specs]


@router.get("/status/{project_id}")
def get_speckit_status(
    project_id: int,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(get_specification_service),
):
    """Get SpecKit status for a project."""
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.local_path:
        return {
            "initialized": False,
            "constitution_hash": None,
            "constitution_version": None,
            "spec_count": 0,
        }

    from pathlib import Path
    specify_path = Path(project.local_path) / ".specify"
    initialized = specify_path.exists()

    specs = service.list_specs(project.local_path) if initialized else []

    return {
        "initialized": initialized,
        "constitution_hash": project.constitution_hash,
        "constitution_version": project.constitution_version,
        "spec_count": len(specs),
        "specs": specs,
    }
