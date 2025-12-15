from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks

from devgodzilla.api import schemas
from devgodzilla.api.dependencies import get_db, get_service_context
from devgodzilla.services.base import ServiceContext
from devgodzilla.db.database import Database
from devgodzilla.services.planning import PlanningService

router = APIRouter()

@router.post("/protocols", response_model=schemas.ProtocolOut)
def create_protocol(
    protocol: schemas.ProtocolCreate,
    background_tasks: BackgroundTasks,
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db)
):
    """Create a new protocol run."""
    # Create the run record
    run = db.create_protocol_run(
        project_id=protocol.project_id,
        protocol_name=protocol.name,
        status="pending",
        base_branch=protocol.branch_name or "main",
        description=protocol.description,
    )
    
    # If using planning service, we should trigger plan_protocol in background
    # But for now, we just return the pending run. The CLI triggers planning explicitly.
    # We could add an option 'plan: bool = False' to trigger it.
    
    return run

@router.get("/protocols", response_model=List[schemas.ProtocolOut])
def list_protocols(
    project_id: Optional[int] = None,
    limit: int = 20,
    db: Database = Depends(get_db)
):
    """List protocol runs."""
    if project_id is None:
        # We need to support listing all, but our DB interface requires project_id
        # We might need to extend the DB interface or fetch for all projects (inefficient).
        # For now, require project_id
        raise HTTPException(status_code=400, detail="project_id is required")
        
    runs = db.list_protocol_runs(project_id=project_id)
    return runs[:limit]

@router.get("/protocols/{protocol_id}", response_model=schemas.ProtocolOut)
def get_protocol(
    protocol_id: int,
    db: Database = Depends(get_db)
):
    """Get a protocol run by ID."""
    try:
        return db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Protocol {protocol_id} not found")

@router.post("/protocols/{protocol_id}/actions/start", response_model=schemas.ProtocolOut)
def start_protocol(
    protocol_id: int,
    background_tasks: BackgroundTasks,
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db)
):
    """Start planning/execution for a protocol."""
    try:
        run = db.get_protocol_run(protocol_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Protocol not found")
        
    if run.status not in ["pending", "planned"]:
        raise HTTPException(status_code=400, detail=f"Cannot start protocol in {run.status} state")
        
    # Update status to planning
    db.update_protocol_status(protocol_id, "planning")
    
    # Trigger planning service in background
    def run_planning():
        service = PlanningService(ctx, db)
        service.plan_protocol(protocol_id)
        
    background_tasks.add_task(run_planning)
    
    return db.get_protocol_run(protocol_id)
