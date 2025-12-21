"""
DevGodzilla Application Logs Endpoint

SSE streaming and REST endpoints for real-time application logs.
"""

import asyncio
import json
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Header, Query
from fastapi.responses import StreamingResponse

from devgodzilla.logging import get_log_buffer

router = APIRouter(tags=["Logs"])


def _log_to_sse(log: Dict[str, Any]) -> str:
    return (
        f"id: {log['id']}\n"
        f"event: log\n"
        f"data: {json.dumps(log, default=str)}\n\n"
    )


async def log_stream_generator(
    since_id: int = 0,
    level: Optional[str] = None,
    source: Optional[str] = None,
    poll_interval_seconds: float = 0.5,
) -> AsyncGenerator[str, None]:
    buffer = get_log_buffer()
    last_id = max(0, since_id)
    yield "event: connected\ndata: {}\n\n"

    idle_ticks = 0
    while True:
        logs = buffer.get_logs_since(last_id, level=level, source=source)
        if logs:
            idle_ticks = 0
            for log in logs:
                last_id = max(last_id, log["id"])
                yield _log_to_sse(log)
        else:
            idle_ticks += 1
            if idle_ticks >= int(30 / max(poll_interval_seconds, 0.1)):
                idle_ticks = 0
                yield ": heartbeat\n\n"

        await asyncio.sleep(poll_interval_seconds)


@router.get("/logs/stream")
async def logs_stream(
    since_id: int = Query(0, ge=0, description="Only stream logs with id > since_id"),
    level: Optional[str] = Query(None, description="Filter by log level (debug, info, warn, error)"),
    source: Optional[str] = Query(None, description="Filter by logger name (partial match)"),
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
):
    """
    Server-Sent Events stream for real-time application logs.

    Streams structured log entries from the DevGodzilla API.
    Use query parameters to filter logs by level or source.
    """
    effective_since = since_id
    if last_event_id and last_event_id.isdigit():
        effective_since = max(effective_since, int(last_event_id))

    return StreamingResponse(
        log_stream_generator(
            since_id=effective_since,
            level=level,
            source=source,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/logs/recent")
def get_recent_logs(
    limit: int = Query(100, ge=1, le=1000, description="Number of logs to return"),
    level: Optional[str] = Query(None, description="Filter by log level (debug, info, warn, error)"),
    source: Optional[str] = Query(None, description="Filter by logger name (partial match)"),
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get recent application logs (non-streaming).

    Returns the last N logs from the in-memory ring buffer.
    """
    buffer = get_log_buffer()
    logs = buffer.get_recent(limit=limit, level=level, source=source)
    return {"logs": logs}
