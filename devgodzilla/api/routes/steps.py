from typing import List
from fastapi import APIRouter, Depends, HTTPException

from devgodzilla.api import schemas
from devgodzilla.api.dependencies import get_db
from devgodzilla.db.database import Database

router = APIRouter()

@router.get("/steps", response_model=List[schemas.StepOut])
def list_steps(
    protocol_run_id: int,
    db: Database = Depends(get_db)
):
    """List steps for a protocol run."""
    return db.list_step_runs(protocol_run_id)

@router.get("/steps/{step_id}", response_model=schemas.StepOut)
def get_step(
    step_id: int,
    db: Database = Depends(get_db)
):
    """Get a step by ID."""
    try:
        return db.get_step_run(step_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Step not found")
