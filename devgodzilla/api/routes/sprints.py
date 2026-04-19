from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from devgodzilla.api import schemas
from devgodzilla.db.database import Database
from devgodzilla.api.dependencies import get_db
from devgodzilla.logging import get_logger, log_extra
from devgodzilla.services.sprint_integration import SprintIntegrationService
from devgodzilla.models.domain import Sprint, AgileTask

router = APIRouter(prefix="/sprints", tags=["sprints"])
logger = get_logger(__name__)


def get_sprint_integration(db: Database = Depends(get_db)) -> SprintIntegrationService:
    return SprintIntegrationService(db)

@router.post("", response_model=schemas.SprintOut)
def create_sprint(
    sprint: schemas.SprintCreate,
    db: Database = Depends(get_db)
):
    created = db.create_sprint(
        project_id=sprint.project_id,
        name=sprint.name,
        goal=sprint.goal,
        status=sprint.status,
        start_date=sprint.start_date.isoformat() if sprint.start_date else None,
        end_date=sprint.end_date.isoformat() if sprint.end_date else None,
        velocity_planned=sprint.velocity_planned
    )
    logger.info(
        "sprint_created",
        extra=log_extra(
            project_id=created.project_id,
            sprint_id=created.id,
            status=created.status,
            velocity_planned=created.velocity_planned,
        ),
    )
    return created

@router.get("/{sprint_id}", response_model=schemas.SprintOut)
def get_sprint(sprint_id: int, db: Database = Depends(get_db)):
    try:
        sprint = db.get_sprint(sprint_id)
    except KeyError:
        logger.warning("sprint_not_found", extra=log_extra(sprint_id=sprint_id))
        raise HTTPException(status_code=404, detail="Sprint not found")
    logger.info(
        "sprint_loaded",
        extra=log_extra(
            project_id=sprint.project_id,
            sprint_id=sprint.id,
            status=sprint.status,
        ),
    )
    return sprint

@router.get("", response_model=List[schemas.SprintOut])
def list_sprints(
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Database = Depends(get_db)
):
    sprints = db.list_sprints(project_id=project_id, status=status)
    logger.info(
        "sprints_listed",
        extra=log_extra(project_id=project_id, status=status, result_count=len(sprints)),
    )
    return sprints

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
        updated = db.update_sprint(sprint_id, **updates)
    except KeyError:
        logger.warning("sprint_update_not_found", extra=log_extra(sprint_id=sprint_id))
        raise HTTPException(status_code=404, detail="Sprint not found")
    logger.info(
        "sprint_updated",
        extra=log_extra(
            project_id=updated.project_id,
            sprint_id=updated.id,
            status=updated.status,
            updated_fields=sorted(updates.keys()),
        ),
    )
    return updated

@router.get("/{sprint_id}/tasks", response_model=List[schemas.AgileTaskOut])
def list_sprint_tasks(
    sprint_id: int,
    db: Database = Depends(get_db)
):
    tasks = db.list_tasks(sprint_id=sprint_id)
    logger.info("sprint_tasks_listed", extra=log_extra(sprint_id=sprint_id, result_count=len(tasks)))
    return tasks

@router.get("/{sprint_id}/metrics", response_model=schemas.SprintMetricsOut)
def get_sprint_metrics(
    sprint_id: int,
    db: Database = Depends(get_db)
):
    try:
        sprint = db.get_sprint(sprint_id)
    except KeyError:
        logger.warning("sprint_metrics_not_found", extra=log_extra(sprint_id=sprint_id))
        raise HTTPException(status_code=404, detail="Sprint not found")

    tasks = db.list_tasks(sprint_id=sprint_id)
    total_tasks = len(tasks)
    completed_tasks = sum(1 for t in tasks if t.board_status == "done")
    total_points = sum(t.story_points or 0 for t in tasks)
    completed_points = sum(t.story_points or 0 for t in tasks if t.board_status == "done")

    # Generate burndown data points
    burndown = _calculate_burndown_data(sprint, tasks)
    
    # Calculate velocity trend (simplified - using historical sprints from same project)
    velocity_trend = _calculate_velocity_trend(db, sprint.project_id, sprint_id)

    logger.info(
        "sprint_metrics_computed",
        extra=log_extra(
            project_id=sprint.project_id,
            sprint_id=sprint_id,
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            total_points=total_points,
            completed_points=completed_points,
        ),
    )
    return schemas.SprintMetricsOut(
        sprint_id=sprint_id,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        total_points=total_points,
        completed_points=completed_points,
        burndown=burndown,
        velocity_trend=velocity_trend
    )

@router.delete("/{sprint_id}")
def delete_sprint(sprint_id: int, db: Database = Depends(get_db)):
    try:
        db.delete_sprint(sprint_id)
    except KeyError:
        logger.warning("sprint_delete_not_found", extra=log_extra(sprint_id=sprint_id))
        raise HTTPException(status_code=404, detail="Sprint not found")
    logger.info("sprint_deleted", extra=log_extra(sprint_id=sprint_id))
    return {"status": "deleted"}


# =============================================================================
# Sprint-Protocol Integration Endpoints
# =============================================================================

@router.post("/{sprint_id}/actions/link-protocol", response_model=schemas.SyncResult)
async def link_protocol_to_sprint(
    sprint_id: int,
    request: schemas.LinkProtocolRequest,
    service: SprintIntegrationService = Depends(get_sprint_integration),
):
    """Link a protocol run to a sprint and optionally sync tasks."""
    try:
        await service.link_protocol_to_sprint(request.protocol_run_id, sprint_id)
        tasks = []
        if request.auto_sync:
            tasks = await service.sync_protocol_to_sprint(
                request.protocol_run_id, sprint_id, create_missing_tasks=True
            )
        logger.info(
            "protocol_linked_to_sprint",
            extra=log_extra(
                sprint_id=sprint_id,
                protocol_run_id=request.protocol_run_id,
                auto_sync=bool(request.auto_sync),
                tasks_synced=len(tasks),
            ),
        )
        return schemas.SyncResult(
            sprint_id=sprint_id,
            protocol_run_id=request.protocol_run_id,
            tasks_synced=len(tasks),
            task_ids=[t.id for t in tasks],
        )
    except KeyError as e:
        logger.warning(
            "protocol_link_to_sprint_not_found",
            extra=log_extra(sprint_id=sprint_id, protocol_run_id=request.protocol_run_id, error=str(e)),
        )
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        logger.warning(
            "protocol_link_to_sprint_invalid",
            extra=log_extra(sprint_id=sprint_id, protocol_run_id=request.protocol_run_id, error=str(e)),
        )
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{sprint_id}/actions/sync-from-protocol", response_model=schemas.SyncResult)
async def sync_sprint_from_protocol(
    sprint_id: int,
    request: schemas.LinkProtocolRequest,
    service: SprintIntegrationService = Depends(get_sprint_integration),
):
    """Sync tasks from a protocol run to this sprint."""
    try:
        tasks = await service.sync_protocol_to_sprint(
            request.protocol_run_id, sprint_id, create_missing_tasks=True
        )
        logger.info(
            "sprint_synced_from_protocol",
            extra=log_extra(
                sprint_id=sprint_id,
                protocol_run_id=request.protocol_run_id,
                tasks_synced=len(tasks),
            ),
        )
        return schemas.SyncResult(
            sprint_id=sprint_id,
            protocol_run_id=request.protocol_run_id,
            tasks_synced=len(tasks),
            task_ids=[t.id for t in tasks],
        )
    except KeyError as e:
        logger.warning(
            "sprint_sync_from_protocol_not_found",
            extra=log_extra(sprint_id=sprint_id, protocol_run_id=request.protocol_run_id, error=str(e)),
        )
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        logger.warning(
            "sprint_sync_from_protocol_invalid",
            extra=log_extra(sprint_id=sprint_id, protocol_run_id=request.protocol_run_id, error=str(e)),
        )
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{sprint_id}/velocity", response_model=schemas.SprintVelocityOut)
async def get_sprint_velocity(
    sprint_id: int,
    db: Database = Depends(get_db),
    service: SprintIntegrationService = Depends(get_sprint_integration),
):
    """Get sprint velocity metrics."""
    try:
        sprint = db.get_sprint(sprint_id)
    except KeyError:
        logger.warning("sprint_velocity_not_found", extra=log_extra(sprint_id=sprint_id))
        raise HTTPException(status_code=404, detail="Sprint not found")

    velocity = await service.calculate_sprint_velocity(sprint_id)
    tasks = db.list_tasks(sprint_id=sprint_id)
    total_points = sum(t.story_points or 0 for t in tasks)
    completed_points = sum(t.story_points or 0 for t in tasks if t.board_status == "done")

    logger.info(
        "sprint_velocity_computed",
        extra=log_extra(
            project_id=sprint.project_id,
            sprint_id=sprint_id,
            velocity_actual=velocity,
            total_points=total_points,
            completed_points=completed_points,
        ),
    )
    return schemas.SprintVelocityOut(
        sprint_id=sprint_id,
        velocity_actual=velocity,
        total_points=total_points,
        completed_points=completed_points,
        completion_rate=completed_points / total_points if total_points > 0 else 0.0,
    )


@router.post("/{sprint_id}/actions/complete", response_model=schemas.SprintOut)
async def complete_sprint(
    sprint_id: int,
    service: SprintIntegrationService = Depends(get_sprint_integration),
):
    """Mark sprint as completed and finalize metrics."""
    try:
        sprint = await service.complete_sprint(sprint_id)
    except KeyError:
        logger.warning("sprint_complete_not_found", extra=log_extra(sprint_id=sprint_id))
        raise HTTPException(status_code=404, detail="Sprint not found")
    logger.info(
        "sprint_completed",
        extra=log_extra(project_id=sprint.project_id, sprint_id=sprint.id, status=sprint.status),
    )
    return sprint


from devgodzilla.services.task_sync import TaskSyncService

def get_task_sync(db: Database = Depends(get_db)) -> TaskSyncService:
    return TaskSyncService(db)

@router.post("/{sprint_id}/actions/import-tasks", response_model=schemas.SyncResult)
async def import_tasks_to_sprint(
    sprint_id: int,
    request: schemas.ImportTasksRequest,
    db: Database = Depends(get_db),
    task_sync: TaskSyncService = Depends(get_task_sync),
):
    """Import tasks from SpecKit tasks.md file into sprint."""
    try:
        sprint = db.get_sprint(sprint_id)
    except KeyError:
        logger.warning("sprint_import_tasks_not_found", extra=log_extra(sprint_id=sprint_id))
        raise HTTPException(status_code=404, detail="Sprint not found")
    
    try:
        tasks = await task_sync.import_speckit_tasks(
            project_id=sprint.project_id,
            spec_path=request.spec_path,
            sprint_id=sprint_id,
            overwrite_existing=request.overwrite_existing,
        )
    except FileNotFoundError as e:
        logger.warning(
            "sprint_import_tasks_missing_file",
            extra=log_extra(
                project_id=sprint.project_id,
                sprint_id=sprint_id,
                spec_path=request.spec_path,
                error=str(e),
            ),
        )
        raise HTTPException(status_code=404, detail=str(e))
    logger.info(
        "sprint_tasks_imported",
        extra=log_extra(
            project_id=sprint.project_id,
            sprint_id=sprint_id,
            spec_path=request.spec_path,
            overwrite_existing=bool(request.overwrite_existing),
            tasks_synced=len(tasks),
        ),
    )
    
    return schemas.SyncResult(
        sprint_id=sprint_id,
        protocol_run_id=0,  # Not protocol-linked
        tasks_synced=len(tasks),
        task_ids=[t.id for t in tasks],
    )


def _calculate_burndown_data(sprint: Sprint, tasks: List[AgileTask]) -> List[schemas.BurndownPointOut]:
    """Calculate burndown chart data points for a sprint."""
    burndown_points = []
    
    # If no start/end dates, return empty burndown
    if not sprint.start_date or not sprint.end_date:
        return burndown_points
    
    try:
        start_date = datetime.fromisoformat(sprint.start_date.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(sprint.end_date.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        # If date parsing fails, return empty burndown
        return burndown_points
    
    total_points = sum(t.story_points or 0 for t in tasks)
    if total_points == 0:
        return burndown_points
    
    # Calculate ideal burndown (linear)
    sprint_days = (end_date - start_date).days
    if sprint_days <= 0:
        return burndown_points
    
    current_date = start_date
    daily_ideal_burn = total_points / sprint_days
    
    for day in range(sprint_days + 1):
        date_str = current_date.strftime("%Y-%m-%d")
        ideal_remaining = max(0, total_points - (day * daily_ideal_burn))
        
        # For actual, we'd need task completion timestamps
        # For now, use a simplified calculation based on current completion
        completed_points = sum(t.story_points or 0 for t in tasks if t.board_status == "done")
        actual_remaining = total_points - completed_points
        
        burndown_points.append(schemas.BurndownPointOut(
            date=date_str,
            ideal=ideal_remaining,
            actual=actual_remaining
        ))
        
        current_date += timedelta(days=1)
    
    return burndown_points


def _calculate_velocity_trend(db: Database, project_id: int, current_sprint_id: int) -> List[int]:
    """Calculate velocity trend from historical sprints in the same project."""
    # Get completed sprints from the same project (excluding current sprint)
    all_sprints = db.list_sprints(project_id=project_id)
    completed_sprints = [
        s for s in all_sprints
        if s.id != current_sprint_id and s.status == "completed"
    ]

    # Sort oldest to newest with deterministic tie-breaking.
    completed_sprints.sort(key=lambda s: (s.created_at or "", s.id))

    # Calculate velocity for up to the first 5 completed sprints.
    velocity_trend = []
    for sprint in completed_sprints[:5]:
        tasks = db.list_tasks(sprint_id=sprint.id)
        completed_points = sum(t.story_points or 0 for t in tasks if t.board_status == "done")
        velocity_trend.append(completed_points)

    # If we have fewer than 5 sprints, pad with zeros on the left.
    while len(velocity_trend) < 5:
        velocity_trend.insert(0, 0)

    return velocity_trend
