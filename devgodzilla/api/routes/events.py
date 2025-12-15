"""
DevGodzilla Events Endpoint

Server-Sent Events (SSE) endpoint for real-time updates.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

router = APIRouter(tags=["Events"])

# In-memory event queue (would use Redis in production)
_event_queues: Dict[str, asyncio.Queue] = {}


# ==================== Event Types ====================

class Event:
    """Base event class."""
    
    def __init__(
        self,
        event_type: str,
        data: Dict[str, Any],
        *,
        protocol_id: Optional[int] = None,
        project_id: Optional[int] = None,
    ):
        self.event_type = event_type
        self.data = data
        self.protocol_id = protocol_id
        self.project_id = project_id
        self.timestamp = datetime.now().isoformat()
    
    def to_sse(self) -> str:
        """Convert to SSE format."""
        payload = {
            "type": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp,
        }
        if self.protocol_id:
            payload["protocol_id"] = self.protocol_id
        if self.project_id:
            payload["project_id"] = self.project_id
        
        return f"event: {self.event_type}\ndata: {json.dumps(payload)}\n\n"


# ==================== Event Publishing ====================

async def publish_event(event: Event):
    """Publish an event to all connected clients."""
    for queue in _event_queues.values():
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass  # Drop event if queue is full


def emit_protocol_started(protocol_id: int, protocol_name: str, project_id: int):
    """Emit protocol started event."""
    asyncio.create_task(publish_event(Event(
        "protocol.started",
        {"name": protocol_name},
        protocol_id=protocol_id,
        project_id=project_id,
    )))


def emit_protocol_completed(protocol_id: int, status: str, project_id: int):
    """Emit protocol completed event."""
    asyncio.create_task(publish_event(Event(
        "protocol.completed",
        {"status": status},
        protocol_id=protocol_id,
        project_id=project_id,
    )))


def emit_step_started(protocol_id: int, step_id: int, step_name: str):
    """Emit step started event."""
    asyncio.create_task(publish_event(Event(
        "step.started",
        {"step_id": step_id, "step_name": step_name},
        protocol_id=protocol_id,
    )))


def emit_step_completed(protocol_id: int, step_id: int, status: str):
    """Emit step completed event."""
    asyncio.create_task(publish_event(Event(
        "step.completed",
        {"step_id": step_id, "status": status},
        protocol_id=protocol_id,
    )))


def emit_qa_result(protocol_id: int, step_id: int, verdict: str, findings_count: int):
    """Emit QA result event."""
    asyncio.create_task(publish_event(Event(
        "qa.result",
        {"step_id": step_id, "verdict": verdict, "findings_count": findings_count},
        protocol_id=protocol_id,
    )))


def emit_clarification_needed(protocol_id: int, clarification_id: int, question: str):
    """Emit clarification needed event."""
    asyncio.create_task(publish_event(Event(
        "clarification.needed",
        {"clarification_id": clarification_id, "question": question},
        protocol_id=protocol_id,
    )))


# ==================== SSE Endpoint ====================

async def event_generator(
    client_id: str,
    protocol_id: Optional[int] = None,
    project_id: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    """Generate SSE events for a client."""
    queue = asyncio.Queue(maxsize=100)
    _event_queues[client_id] = queue
    
    try:
        # Send initial connection event
        yield Event("connected", {"client_id": client_id}).to_sse()
        
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30)
                
                # Filter by protocol/project if specified
                if protocol_id and event.protocol_id != protocol_id:
                    continue
                if project_id and event.project_id != project_id:
                    continue
                
                yield event.to_sse()
            except asyncio.TimeoutError:
                # Send heartbeat
                yield ": heartbeat\n\n"
    finally:
        del _event_queues[client_id]


@router.get("/events")
async def events_stream(
    protocol_id: Optional[int] = Query(None, description="Filter by protocol ID"),
    project_id: Optional[int] = Query(None, description="Filter by project ID"),
):
    """
    Server-Sent Events stream for real-time updates.
    
    Connect to this endpoint to receive live updates about:
    - Protocol status changes
    - Step execution progress
    - QA results
    - Clarification requests
    
    Use query parameters to filter events:
    - protocol_id: Only receive events for this protocol
    - project_id: Only receive events for this project
    """
    import uuid
    client_id = str(uuid.uuid4())
    
    return StreamingResponse(
        event_generator(client_id, protocol_id, project_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/events/recent")
async def recent_events(
    limit: int = Query(50, ge=1, le=200),
):
    """
    Get recent events (non-streaming).
    
    Returns the last N events from the event store.
    """
    # In production, this would query an event store
    return {
        "events": [],
        "message": "Event store not yet implemented",
    }
