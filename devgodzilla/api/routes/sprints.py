from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from devgodzilla.api import schemas
from devgodzilla.db.database import Database
from devgodzilla.api.dependencies import get_db

router = APIRouter(prefix="/sprints", tags=["sprints"])

@router.post("", response_model=schemas.SprintOut)
def create_sprint(
    sprint: schemas.SprintCreate,
    db: Database = Depends(get_db)
):
    return db.create_sprint(
        project_id=sprint.project_id,
        name=sprint.name,
        goal=sprint.goal,
        status=sprint.status,
        start_date=sprint.start_date.isoformat() if sprint.start_date else None,
        end_date=sprint.end_date.isoformat() if sprint.end_date else None,
        velocity_planned=sprint.velocity_planned
    )

@router.get("/{sprint_id}", response_model=schemas.SprintOut)
def get_sprint(sprint_id: int, db: Database = Depends(get_db)):
    try:
        return db.get_sprint(sprint_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sprint not found")

@router.get("", response_model=List[schemas.SprintOut])
def list_sprints(
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Database = Depends(get_db)
):
    return db.list_sprints(project_id=project_id, status=status)

@router.put("/{sprint_id}", response_model=schemas.SprintOut)
def update_sprint(
    sprint_id: int,
    sprint: schemas.SprintUpdate,
    db: Database = Depends(get_db)
):
    try:
        updates = sprint.model_dump(exclude_unset=True)
        if "start_date" in updates and updates["start_date"]:
            updates["start_date"] = updates["start_date"].isoformat()
        if "end_date" in updates and updates["end_date"]:
            updates["end_date"] = updates["end_date"].isoformat()
        return db.update_sprint(sprint_id, **updates)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sprint not found")

@router.get("/{sprint_id}/tasks", response_model=List[schemas.AgileTaskOut])
def list_sprint_tasks(
    sprint_id: int,
    db: Database = Depends(get_db)
):
    return db.list_tasks(sprint_id=sprint_id)

@router.get("/{sprint_id}/metrics", response_model=schemas.SprintMetrics)
def get_sprint_metrics(
    sprint_id: int,
    db: Database = Depends(get_db)
):
    try:
        db.get_sprint(sprint_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Sprint not found")

    tasks = db.list_tasks(sprint_id=sprint_id)
    total_tasks = len(tasks)
    completed_tasks = sum(1 for t in tasks if t.board_status == "done")
    total_points = sum(t.story_points or 0 for t in tasks)
    completed_points = sum(t.story_points or 0 for t in tasks if t.board_status == "done")

    return schemas.SprintMetrics(
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        total_points=total_points,
        completed_points=completed_points,
        burndown=[],
        velocity=completed_points
    )

@router.delete("/{sprint_id}")
def delete_sprint(sprint_id: int, db: Database = Depends(get_db)):
    try:
        db.delete_sprint(sprint_id)
        return {"status": "deleted"}
    except KeyError:
        raise HTTPException(status_code=404, detail="Sprint not found")
