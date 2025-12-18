from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from devgodzilla.api import schemas
from devgodzilla.db.database import Database
from devgodzilla.api.dependencies import get_db

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.post("", response_model=schemas.AgileTaskOut)
def create_task(
    task: schemas.AgileTaskCreate,
    db: Database = Depends(get_db)
):
    return db.create_task(
        project_id=task.project_id,
        title=task.title,
        task_type=task.task_type,
        priority=task.priority,
        board_status=task.board_status,
        sprint_id=task.sprint_id,
        description=task.description,
        assignee=task.assignee,
        reporter=task.reporter,
        story_points=task.story_points,
        labels=task.labels,
        acceptance_criteria=task.acceptance_criteria,
        due_date=task.due_date.isoformat() if task.due_date else None,
        blocked_by=task.blocked_by,
        blocks=task.blocks,
    )

@router.get("/{task_id}", response_model=schemas.AgileTaskOut)
def get_task(task_id: int, db: Database = Depends(get_db)):
    try:
        return db.get_task(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Task not found")

@router.get("", response_model=List[schemas.AgileTaskOut])
def list_tasks(
    project_id: Optional[int] = None,
    sprint_id: Optional[int] = None,
    board_status: Optional[str] = None,
    assignee: Optional[str] = None,
    limit: int = 100,
    db: Database = Depends(get_db)
):
    return db.list_tasks(
        project_id=project_id,
        sprint_id=sprint_id,
        board_status=board_status,
        assignee=assignee,
        limit=limit
    )

@router.put("/{task_id}", response_model=schemas.AgileTaskOut)
def update_task(
    task_id: int,
    task: schemas.AgileTaskUpdate,
    db: Database = Depends(get_db)
):
    try:
        updates = task.model_dump(exclude_unset=True)
        if "due_date" in updates and updates["due_date"]:
            updates["due_date"] = updates["due_date"].isoformat()
        return db.update_task(task_id, **updates)
    except KeyError:
        raise HTTPException(status_code=404, detail="Task not found")

@router.patch("/{task_id}", response_model=schemas.AgileTaskOut)
def patch_task(
    task_id: int,
    task: schemas.AgileTaskUpdate,
    db: Database = Depends(get_db)
):
    return update_task(task_id, task, db)

@router.delete("/{task_id}")
def delete_task(task_id: int, db: Database = Depends(get_db)):
    try:
        db.delete_task(task_id)
        return {"status": "deleted"}
    except KeyError:
        raise HTTPException(status_code=404, detail="Task not found")
