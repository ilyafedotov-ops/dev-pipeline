"""
CLI Executions API Routes

Endpoints for tracking and monitoring in-progress CLI executions.
"""

import asyncio
import json
import os
import signal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from devgodzilla.logging import get_logger
from devgodzilla.services.cli_execution_tracker import (
    get_execution_tracker,
    ExecutionStatus,
)

router = APIRouter(tags=["cli-executions"])
logger = get_logger(__name__)


# =============================================================================
# Schemas
# =============================================================================

class LogEntryOut(BaseModel):
    timestamp: str
    level: str
    message: str
    source: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CLIExecutionOut(BaseModel):
    execution_id: str
    execution_type: str
    engine_id: str
    project_id: Optional[int] = None
    status: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    command: Optional[str] = None
    working_dir: Optional[str] = None
    pid: Optional[int] = None
    exit_code: Optional[int] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    log_count: int = 0
    logs: Optional[List[LogEntryOut]] = None


class CLIExecutionListOut(BaseModel):
    executions: List[CLIExecutionOut]
    total: int
    active_count: int


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/cli-executions", response_model=CLIExecutionListOut)
def list_cli_executions(
    execution_type: Optional[str] = Query(None, description="Filter by execution type"),
    project_id: Optional[int] = Query(None, description="Filter by project ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, description="Maximum number of executions to return"),
):
    """
    List CLI executions with optional filters.
    
    Returns both active and recent completed executions.
    """
    tracker = get_execution_tracker()
    
    status_enum = None
    if status:
        try:
            status_enum = ExecutionStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    executions = tracker.list_executions(
        execution_type=execution_type,
        project_id=project_id,
        status=status_enum,
        limit=limit,
    )
    
    active_count = len(tracker.list_active())
    
    return CLIExecutionListOut(
        executions=[
            CLIExecutionOut(**e.to_dict(include_logs=False))
            for e in executions
        ],
        total=len(executions),
        active_count=active_count,
    )


@router.get("/cli-executions/active", response_model=CLIExecutionListOut)
def list_active_executions(
    limit: int = Query(50, description="Maximum number of executions to return"),
):
    """
    List currently running CLI executions.
    """
    tracker = get_execution_tracker()
    active = tracker.list_active(limit=limit)
    
    return CLIExecutionListOut(
        executions=[
            CLIExecutionOut(**e.to_dict(include_logs=False))
            for e in active
        ],
        total=len(active),
        active_count=len(active),
    )


@router.get("/cli-executions/{execution_id}", response_model=CLIExecutionOut)
def get_cli_execution(
    execution_id: str,
    include_logs: bool = Query(True, description="Include log entries"),
    log_limit: int = Query(500, description="Maximum number of log entries to return"),
):
    """
    Get details of a specific CLI execution, optionally including logs.
    """
    tracker = get_execution_tracker()
    execution = tracker.get_execution(execution_id)
    
    if not execution:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")
    
    return CLIExecutionOut(**execution.to_dict(include_logs=include_logs, log_limit=log_limit))


@router.get("/cli-executions/{execution_id}/logs")
def get_execution_logs(
    execution_id: str,
    limit: int = Query(1000, description="Maximum number of log entries"),
    level: Optional[str] = Query(None, description="Filter by log level"),
):
    """
    Get logs for a specific execution.
    """
    tracker = get_execution_tracker()
    execution = tracker.get_execution(execution_id)
    
    if not execution:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")
    
    logs = list(execution.logs)[-limit:]
    
    if level:
        logs = [log for log in logs if log.level == level]
    
    return {
        "execution_id": execution_id,
        "status": execution.status.value,
        "log_count": len(logs),
        "logs": [
            {
                "timestamp": log.timestamp.isoformat(),
                "level": log.level,
                "message": log.message,
                "source": log.source,
                "metadata": log.metadata,
            }
            for log in logs
        ],
    }


@router.get("/cli-executions/{execution_id}/logs/stream")
async def stream_execution_logs(
    execution_id: str,
):
    """
    Stream logs for an execution in real-time using Server-Sent Events (SSE).
    
    The stream will:
    - Send existing logs first
    - Then stream new logs as they arrive
    - Close when the execution completes
    """
    tracker = get_execution_tracker()
    execution = tracker.get_execution(execution_id)
    
    if not execution:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")
    
    async def event_generator():
        # Create an async queue for new logs
        log_queue: asyncio.Queue = asyncio.Queue()
        
        def on_log(entry):
            try:
                log_queue.put_nowait(entry)
            except asyncio.QueueFull:
                pass
        
        # Subscribe to updates
        tracker.subscribe(execution_id, on_log)
        
        try:
            # First, send existing logs
            for log in list(execution.logs):
                data = json.dumps({
                    "timestamp": log.timestamp.isoformat(),
                    "level": log.level,
                    "message": log.message,
                    "source": log.source,
                    "metadata": log.metadata,
                })
                yield f"data: {data}\n\n"
            
            # Send current status
            yield f"event: status\ndata: {json.dumps({'status': execution.status.value})}\n\n"
            
            # Stream new logs until execution completes
            while True:
                current_execution = tracker.get_execution(execution_id)
                if not current_execution:
                    yield f"event: status\ndata: {json.dumps({'status': 'not_found'})}\n\n"
                    break
                    
                if current_execution.status in (
                    ExecutionStatus.SUCCEEDED,
                    ExecutionStatus.FAILED,
                    ExecutionStatus.CANCELLED,
                ):
                    # Send final status and any remaining logs
                    try:
                        while True:
                            entry = log_queue.get_nowait()
                            data = json.dumps({
                                "timestamp": entry.timestamp.isoformat(),
                                "level": entry.level,
                                "message": entry.message,
                                "source": entry.source,
                                "metadata": entry.metadata,
                            })
                            yield f"data: {data}\n\n"
                    except asyncio.QueueEmpty:
                        pass
                    
                    yield f"event: complete\ndata: {json.dumps({'status': current_execution.status.value, 'exit_code': current_execution.exit_code, 'error': current_execution.error})}\n\n"
                    break
                
                # Wait for new logs (with timeout)
                try:
                    entry = await asyncio.wait_for(log_queue.get(), timeout=1.0)
                    data = json.dumps({
                        "timestamp": entry.timestamp.isoformat(),
                        "level": entry.level,
                        "message": entry.message,
                        "source": entry.source,
                        "metadata": entry.metadata,
                    })
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    # Send heartbeat
                    yield ": heartbeat\n\n"
        finally:
            tracker.unsubscribe(execution_id, on_log)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/cli-executions/{execution_id}/cancel")
def cancel_execution(execution_id: str):
    """
    Cancel a running execution.
    
    Best effort:
    - Sends SIGTERM to the tracked PID (if available)
    - Marks the execution as cancelled in the tracker
    """
    tracker = get_execution_tracker()
    execution = tracker.get_execution(execution_id)
    
    if not execution:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")
    
    if execution.status != ExecutionStatus.RUNNING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel execution with status {execution.status.value}"
        )
    
    pid = execution.pid
    termination_attempted = False
    termination_result = "no_pid"
    termination_error = None

    if pid:
        termination_attempted = True
        try:
            os.kill(pid, signal.SIGTERM)
            termination_result = "signal_sent"
        except ProcessLookupError:
            termination_result = "process_not_found"
        except Exception as exc:  # noqa: BLE001
            termination_result = "signal_failed"
            termination_error = str(exc) or exc.__class__.__name__

    tracker.cancel(execution_id)

    payload = {
        "execution_id": execution_id,
        "status": "cancelled",
        "message": "Execution marked as cancelled",
        "pid": pid,
        "termination_attempted": termination_attempted,
        "termination_result": termination_result,
    }
    if termination_error:
        payload["termination_error"] = termination_error
    return payload
