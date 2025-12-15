from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException

from devgodzilla.api import schemas
from devgodzilla.api.dependencies import get_db
from devgodzilla.db.database import Database

router = APIRouter()

@router.get("/clarifications", response_model=List[schemas.ClarificationOut])
def list_clarifications(
    project_id: Optional[int] = None,
    protocol_run_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 100,
    db: Database = Depends(get_db)
):
    """List clarifications."""
    return db.list_clarifications(
        project_id=project_id,
        protocol_run_id=protocol_run_id,
        status=status,
        limit=limit
    )

@router.post("/clarifications/{clarification_id}/answer", response_model=schemas.ClarificationOut)
def answer_clarification(
    clarification_id: int,
    answer: schemas.ClarificationAnswer,
    db: Database = Depends(get_db)
):
    """Answer a clarification."""
    # We need to find the clarification first to get scope/key
    # The DB interface uses scope/key for updates, or we need to find by ID
    
    # Currently DB interface only has upsert/answer by scope/key
    # We need to add get_clarification_by_id or list and filter
    
    # Hack: List all and find by ID (inefficient but works for now)
    # Or rely on client passing scope/key? Rest API usually uses ID.
    
    # Let's assume we can fetch by ID or add that method to DatabaseProtocol later.
    # For now, let's look up logic
    
    # Since we can't easily modify DB interface right now without touching huge file,
    # let's try to pass ID. Accessing internal rows is possible via list.
    
    # For MVP: Return 501 if not easy, or implement lookup
    raise HTTPException(status_code=501, detail="Answer by ID not yet supported in DB layer")
