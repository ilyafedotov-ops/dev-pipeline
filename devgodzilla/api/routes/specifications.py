"""
Specifications API Routes

Endpoints for listing and managing feature specifications across projects.
"""
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException

from devgodzilla.api.dependencies import get_db, get_service_context, Database
from devgodzilla.services.base import ServiceContext
from devgodzilla.services.specification import SpecificationService

router = APIRouter(tags=["specifications"])


class SpecificationOut(BaseModel):
    id: int
    path: str
    title: str
    project_id: int
    project_name: str
    status: str
    created_at: Optional[str] = None
    tasks_generated: bool = False
    protocol_id: Optional[int] = None
    sprint_id: Optional[int] = None
    sprint_name: Optional[str] = None
    linked_tasks: int = 0
    completed_tasks: int = 0
    story_points: int = 0


def get_specification_service(
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
) -> SpecificationService:
    return SpecificationService(ctx, db)


@router.get("/specifications", response_model=List[SpecificationOut])
def list_specifications(
    project_id: Optional[int] = None,
    limit: int = 100,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(get_specification_service),
):
    """
    List all feature specifications across projects.
    
    Optionally filter by project_id.
    """
    limit = max(1, min(limit, 500))
    
    # Get projects to iterate
    if project_id:
        try:
            projects = [db.get_project(project_id)]
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    else:
        projects = db.list_projects()[:100]
    
    specifications = []
    spec_id = 0
    
    for project in projects:
        if not project.local_path:
            continue
            
        try:
            specs = service.list_specs(project.id)
            for spec in specs:
                spec_id += 1
                # Determine status based on what exists
                if spec.has_tasks:
                    status = "completed"
                elif spec.has_plan:
                    status = "in-progress"
                elif spec.has_spec:
                    status = "draft"
                else:
                    continue  # Skip if no spec file
                
                # Try to extract title from spec name
                title = spec.name.replace("-", " ").replace("_", " ").title()
                if title.startswith("Feature "):
                    title = title[8:]
                
                specifications.append(SpecificationOut(
                    id=spec_id,
                    path=spec.path,
                    title=title,
                    project_id=project.id,
                    project_name=project.name,
                    status=status,
                    tasks_generated=spec.has_tasks,
                ))
        except Exception:
            # Skip projects with errors
            continue
    
    return specifications[:limit]


@router.get("/specifications/{spec_id}", response_model=SpecificationOut)
def get_specification(
    spec_id: int,
    db: Database = Depends(get_db),
    service: SpecificationService = Depends(get_specification_service),
):
    """Get a single specification by ID."""
    # For now, list all and find by ID
    specs = list_specifications(db=db, service=service)
    for spec in specs:
        if spec.id == spec_id:
            return spec
    raise HTTPException(status_code=404, detail=f"Specification {spec_id} not found")
