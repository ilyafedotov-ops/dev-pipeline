"""
Queue Statistics API Routes

Provides endpoints for monitoring queue statistics and job status.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends

from devgodzilla.api import schemas
from devgodzilla.api.dependencies import get_db
from devgodzilla.db.database import Database
from devgodzilla.logging import get_logger, log_extra

router = APIRouter(tags=["Queues"])
logger = get_logger(__name__)


@router.get("/queues", response_model=List[schemas.QueueStatsOut])
def get_queue_stats(db: Database = Depends(get_db)):
    """
    Return queue statistics for monitoring.
    
    Groups job runs by queue name and provides counts by status.
    """
    stats = db.get_queue_stats()
    items = [schemas.QueueStatsOut.model_validate(s) for s in stats]
    logger.info("queue_stats_loaded", extra=log_extra(result_count=len(items)))
    return items

@router.get("/queues/stats", response_model=List[schemas.QueueStatsOut])
def get_queue_stats_alias(db: Database = Depends(get_db)):
    """Alias for `/queues` (kept for frontend/backwards compatibility)."""
    stats = db.get_queue_stats()
    items = [schemas.QueueStatsOut.model_validate(s) for s in stats]
    logger.info("queue_stats_loaded_alias", extra=log_extra(result_count=len(items)))
    return items


@router.get("/queues/jobs", response_model=List[schemas.QueueJobOut])
def list_queue_jobs(
    status: Optional[str] = None,
    limit: int = 100,
    db: Database = Depends(get_db)
):
    """
    List jobs in queues with optional status filter.
    
    Args:
        status: Filter by job status (queued, running, completed, failed)
        limit: Maximum number of jobs to return
    """
    jobs = db.list_queue_jobs(status=status, limit=limit)
    items = [schemas.QueueJobOut.model_validate(j) for j in jobs]
    logger.info("queue_jobs_listed", extra=log_extra(status=status, limit=limit, result_count=len(items)))
    return items
