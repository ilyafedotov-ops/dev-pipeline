from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from devgodzilla.api import schemas
from devgodzilla.config import load_config
from devgodzilla.db.database import Database
from devgodzilla.api.dependencies import get_db
from devgodzilla.logging import get_logger, log_extra
from devgodzilla.services.base import ServiceContext
from devgodzilla.services.orchestrator import OrchestratorMode, OrchestratorService
from devgodzilla.windmill.client import WindmillClient, WindmillConfig

router = APIRouter(prefix="/tasks", tags=["tasks"])
logger = get_logger(__name__)

@router.post("", response_model=schemas.AgileTaskOut)
def create_task(
    task: schemas.AgileTaskCreate,
    db: Database = Depends(get_db)
):
    created = db.create_task(
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
    logger.info(
        "task_created",
        extra=log_extra(
            project_id=created.project_id,
            task_id=created.id,
            sprint_id=created.sprint_id,
            task_type=created.task_type,
            board_status=created.board_status,
            priority=created.priority,
        ),
    )
    return created

@router.get("/{task_id}", response_model=schemas.AgileTaskOut)
def get_task(task_id: int, db: Database = Depends(get_db)):
    try:
        task = db.get_task(task_id)
    except KeyError:
        logger.warning("task_not_found", extra=log_extra(task_id=task_id))
        raise HTTPException(status_code=404, detail="Task not found")
    logger.info(
        "task_loaded",
        extra=log_extra(
            project_id=task.project_id,
            task_id=task.id,
            sprint_id=task.sprint_id,
            board_status=task.board_status,
        ),
    )
    return task

@router.get("", response_model=List[schemas.AgileTaskOut])
def list_tasks(
    project_id: Optional[int] = None,
    sprint_id: Optional[int] = None,
    board_status: Optional[str] = None,
    assignee: Optional[str] = None,
    limit: int = 100,
    db: Database = Depends(get_db)
):
    tasks = db.list_tasks(
        project_id=project_id,
        sprint_id=sprint_id,
        board_status=board_status,
        assignee=assignee,
        limit=limit
    )
    logger.info(
        "tasks_listed",
        extra=log_extra(
            project_id=project_id,
            sprint_id=sprint_id,
            board_status=board_status,
            assignee=assignee,
            limit=limit,
            result_count=len(tasks),
        ),
    )
    return tasks

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
        updated = db.update_task(task_id, **updates)
    except KeyError:
        logger.warning("task_update_not_found", extra=log_extra(task_id=task_id))
        raise HTTPException(status_code=404, detail="Task not found")
    logger.info(
        "task_updated",
        extra=log_extra(
            project_id=updated.project_id,
            task_id=updated.id,
            sprint_id=updated.sprint_id,
            updated_fields=sorted(updates.keys()),
            board_status=updated.board_status,
        ),
    )
    return updated

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
    except KeyError:
        logger.warning("task_delete_not_found", extra=log_extra(task_id=task_id))
        raise HTTPException(status_code=404, detail="Task not found")
    logger.info("task_deleted", extra=log_extra(task_id=task_id))
    return {"status": "deleted"}


def _build_orchestrator(db: Database) -> OrchestratorService:
    config = load_config()
    ctx = ServiceContext(config=config)
    windmill_client = None
    mode = OrchestratorMode.LOCAL
    if getattr(config, "windmill_enabled", False):
        windmill_client = WindmillClient(
            WindmillConfig(
                base_url=config.windmill_url or "http://localhost:8000",
                token=config.windmill_token or "",
                workspace=getattr(config, "windmill_workspace", "devgodzilla"),
            )
        )
        mode = OrchestratorMode.WINDMILL
    return OrchestratorService(context=ctx, db=db, windmill_client=windmill_client, mode=mode)


@router.post("/{task_id}/execute", response_model=dict)
def execute_task(task_id: int, db: Database = Depends(get_db)):
    """Start implementation execution for a task."""
    # 1. Get the task
    try:
        task = db.get_task(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Task not found")

    # 2. Check task has step_run_id linked
    if not task.step_run_id:
        # If no step_run linked, just update board_status to in_progress
        db.update_task(task_id, board_status="in_progress")
        logger.info("task_moved_to_in_progress", extra=log_extra(task_id=task_id, note="no_step_run_linked"))
        return {"status": "moved", "message": "Task moved to in_progress (no step run linked)", "task_id": task_id}

    # 3. Update task board_status
    db.update_task(task_id, board_status="in_progress")

    # 4. Execute the step via orchestrator
    try:
        orchestrator = _build_orchestrator(db)
        result = orchestrator.run_step(task.step_run_id)
        logger.info("task_execution_started", extra=log_extra(
            task_id=task_id, step_run_id=task.step_run_id,
            protocol_run_id=task.protocol_run_id, job_id=result.job_id
        ))
        return {
            "status": "executing",
            "message": "Task execution started",
            "task_id": task_id,
            "step_run_id": task.step_run_id,
            "job_id": result.job_id,
        }
    except Exception as e:
        logger.error("task_execution_failed", extra=log_extra(task_id=task_id, error=str(e)))
        raise HTTPException(status_code=500, detail=f"Execution failed: {e}")
