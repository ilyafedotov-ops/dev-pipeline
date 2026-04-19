from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException

from devgodzilla.api import schemas
from devgodzilla.api.dependencies import get_db
from devgodzilla.db.database import Database
from devgodzilla.logging import get_logger, log_extra

router = APIRouter()
logger = get_logger(__name__)

@router.get("/clarifications", response_model=List[schemas.ClarificationOut])
def list_clarifications(
    project_id: Optional[int] = None,
    protocol_run_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 100,
    db: Database = Depends(get_db)
):
    """List clarifications."""
    clarifications = db.list_clarifications(
        project_id=project_id,
        protocol_run_id=protocol_run_id,
        status=status,
        limit=limit
    )
    logger.info(
        "clarifications_listed",
        extra=log_extra(
            project_id=project_id,
            protocol_run_id=protocol_run_id,
            status=status,
            limit=limit,
            result_count=len(clarifications),
        ),
    )
    return clarifications

@router.post("/clarifications/{clarification_id}/answer", response_model=schemas.ClarificationOut)
def answer_clarification(
    clarification_id: int,
    answer: schemas.ClarificationAnswer,
    db: Database = Depends(get_db)
):
    """Answer a clarification."""
    try:
        clarification = db.get_clarification_by_id(clarification_id)
    except KeyError:
        logger.warning("clarification_not_found", extra=log_extra(clarification_id=clarification_id))
        raise HTTPException(status_code=404, detail="Clarification not found")

    # Store answer as structured JSON (so UI can render rich answers later)
    payload = {"text": answer.answer}

    try:
        updated = db.answer_clarification(
            scope=clarification.scope,
            key=clarification.key,
            answer=payload,
            answered_by=answer.answered_by,
            status="answered",
        )
    except KeyError:
        logger.warning(
            "clarification_answer_not_found",
            extra=log_extra(clarification_id=clarification_id, scope=clarification.scope, key=clarification.key),
        )
        raise HTTPException(status_code=404, detail="Clarification not found")

    logger.info(
        "clarification_answered",
        extra=log_extra(
            project_id=getattr(updated, "project_id", None),
            protocol_run_id=getattr(updated, "protocol_run_id", None),
            clarification_id=clarification_id,
            scope=clarification.scope,
            key=clarification.key,
            answered_by=answer.answered_by,
        ),
    )
    return updated
