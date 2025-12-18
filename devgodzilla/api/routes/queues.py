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

router = APIRouter(tags=["Queues"])


@router.get("/queues", response_model=List[schemas.QueueStatsOut])
def get_queue_stats(db: Database = Depends(get_db)):
    """
    Return queue statistics for monitoring.
    
    Groups job runs by queue name and provides counts by status.
    """
    stats = db.get_queue_stats()
    return [schemas.QueueStatsOut.model_validate(s) for s in stats]


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
    return [schemas.QueueJobOut.model_validate(j) for j in jobs]
