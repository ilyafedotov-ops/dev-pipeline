from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException

from devgodzilla.api import schemas
from devgodzilla.api.dependencies import get_db
from devgodzilla.db.database import Database

router = APIRouter()

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
    db: Database = Depends(get_db)
):
    """List all projects."""
    return db.list_projects()

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
