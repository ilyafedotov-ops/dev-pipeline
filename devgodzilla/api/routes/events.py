"""
DevGodzilla Events Endpoint

DB-backed Server-Sent Events (SSE) and WebSocket endpoints for real-time updates.
"""

import asyncio
import json
from typing import Any, AsyncGenerator, Dict, List, Optional, Set

from fastapi import APIRouter, Depends, Header, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from devgodzilla.api import schemas
from devgodzilla.api.dependencies import get_db
from devgodzilla.db.database import Database
from devgodzilla.events_catalog import normalize_event_type
from devgodzilla.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Events"])


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[WebSocket, Set[str]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[websocket] = set()

    def disconnect(self, websocket: WebSocket):
        self.active_connections.pop(websocket, None)

    def subscribe(self, websocket: WebSocket, channels: List[str]):
        if websocket in self.active_connections:
            self.active_connections[websocket].update(channels)

    def unsubscribe(self, websocket: WebSocket, channels: List[str]):
        if websocket in self.active_connections:
            self.active_connections[websocket].difference_update(channels)

    def get_subscriptions(self, websocket: WebSocket) -> Set[str]:
        return self.active_connections.get(websocket, set())

    async def broadcast(self, channel: str, message: dict):
        for ws, channels in list(self.active_connections.items()):
            if channel in channels or "events" in channels:
                try:
                    await ws.send_json(message)
                except Exception:
                    pass


ws_manager = ConnectionManager()


def _event_to_sse(event: schemas.EventOut) -> str:
    payload = event.model_dump()
    return (
        f"id: {event.id}\n"
        f"event: {event.event_type}\n"
        f"data: {json.dumps(payload, default=str)}\n\n"
    )

def _event_to_sse_message(event: schemas.EventOut) -> str:
    payload = event.model_dump()
    # Omit `event:` so browsers dispatch this as the default "message" event.
    return (
        f"id: {event.id}\n"
        f"data: {json.dumps(payload, default=str)}\n\n"
    )


# ==================== SSE Endpoint ====================

async def event_generator(
    db: Database,
    protocol_id: Optional[int] = None,
    project_id: Optional[int] = None,
    event_types: Optional[List[str]] = None,
    categories: Optional[List[str]] = None,
    *,
    since_id: int = 0,
    poll_interval_seconds: float = 0.5,
    named_events: bool = True,
) -> AsyncGenerator[str, None]:
    last_id = max(0, int(since_id))
    if named_events:
        yield "event: connected\ndata: {}\n\n"
    else:
        yield "data: {}\n\n"

    category_set = {normalize_event_type(c) for c in categories or [] if c}
    idle_ticks = 0
    while True:
        batch = db.list_events_since_id(
            since_id=last_id,
            limit=200,
            protocol_run_id=protocol_id,
            project_id=project_id,
            event_types=event_types,
        )
        if batch:
            idle_ticks = 0
            for e in batch:
                out = schemas.EventOut.model_validate(e)
                last_id = max(last_id, out.id)
                if category_set and (out.event_category or "other") not in category_set:
                    continue
                yield _event_to_sse(out) if named_events else _event_to_sse_message(out)
        else:
            idle_ticks += 1
            if idle_ticks >= int(30 / max(poll_interval_seconds, 0.1)):
                idle_ticks = 0
                yield ": heartbeat\n\n"

        await asyncio.sleep(poll_interval_seconds)


@router.get("/events")
async def events_stream(
    protocol_id: Optional[int] = Query(None, description="Filter by protocol ID"),
    project_id: Optional[int] = Query(None, description="Filter by project ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    kind: Optional[str] = Query(None, description="Deprecated: use event_type"),
    category: Optional[List[str]] = Query(None, description="Filter by event category"),
    since_id: int = Query(0, ge=0, description="Only stream events with id > since_id"),
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
    db: Database = Depends(get_db),
):
    """
    Server-Sent Events stream for real-time updates.
    
    Use query parameters to filter events:
    - protocol_id: Only receive events for this protocol
    - project_id: Only receive events for this project
    """
    effective_since = since_id
    if last_event_id and last_event_id.isdigit():
        effective_since = max(effective_since, int(last_event_id))

    effective_event_types = [event_type or kind] if (event_type or kind) else None
    return StreamingResponse(
        event_generator(
            db,
            protocol_id,
            project_id,
            event_types=effective_event_types,
            categories=category,
            since_id=effective_since,
            named_events=True,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )

@router.get("/events/stream")
async def events_stream_message(
    protocol_id: Optional[int] = Query(None, description="Filter by protocol ID"),
    project_id: Optional[int] = Query(None, description="Filter by project ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    kind: Optional[str] = Query(None, description="Deprecated: use event_type"),
    category: Optional[List[str]] = Query(None, description="Filter by event category"),
    since_id: int = Query(0, ge=0, description="Only stream events with id > since_id"),
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
    db: Database = Depends(get_db),
):
    """
    SSE stream using default browser "message" events.

    This is identical to `/events` but omits the `event:` field so clients can
    consume everything via `EventSource.onmessage` without registering each
    event type individually.
    """
    effective_since = since_id
    if last_event_id and last_event_id.isdigit():
        effective_since = max(effective_since, int(last_event_id))

    effective_event_types = [event_type or kind] if (event_type or kind) else None
    return StreamingResponse(
        event_generator(
            db,
            protocol_id,
            project_id,
            event_types=effective_event_types,
            categories=category,
            since_id=effective_since,
            named_events=False,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/events/recent")
async def recent_events(
    limit: int = Query(50, ge=1, le=200),
    protocol_id: Optional[int] = Query(None, description="Filter by protocol ID"),
    project_id: Optional[int] = Query(None, description="Filter by project ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    kind: Optional[str] = Query(None, description="Deprecated: use event_type"),
    category: Optional[List[str]] = Query(None, description="Filter by event category"),
    db: Database = Depends(get_db),
):
    """
    Get recent events (non-streaming).

    Returns the last N events from the DB-backed event store.
    """
    effective_event_types = [event_type or kind] if (event_type or kind) else None
    items = db.list_recent_events(
        limit=limit,
        protocol_run_id=protocol_id,
        project_id=project_id,
        event_types=effective_event_types,
        categories=category,
    )
    return {
        "events": [schemas.EventOut.model_validate(e).model_dump() for e in items],
    }


# ==================== WebSocket Endpoint ====================

async def _ws_event_pusher(
    websocket: WebSocket,
    db: Database,
    poll_interval: float = 0.5,
):
    """Background task to push events to WebSocket client based on subscriptions."""
    last_id = 0
    idle_ticks = 0

    while True:
        try:
            subscriptions = ws_manager.get_subscriptions(websocket)
            if not subscriptions:
                await asyncio.sleep(poll_interval)
                continue

            protocol_id = None
            project_id = None
            for sub in subscriptions:
                if sub.startswith("protocol:"):
                    try:
                        protocol_id = int(sub.split(":")[1])
                    except (ValueError, IndexError):
                        pass
                elif sub.startswith("project:"):
                    try:
                        project_id = int(sub.split(":")[1])
                    except (ValueError, IndexError):
                        pass

            batch = db.list_events_since_id(
                since_id=last_id,
                limit=200,
                protocol_run_id=protocol_id,
                project_id=project_id,
            )

            if batch:
                idle_ticks = 0
                for e in batch:
                    out = schemas.EventOut.model_validate(e)
                    last_id = max(last_id, out.id)

                    channel = "events"
                    if out.protocol_run_id:
                        channel = f"protocol:{out.protocol_run_id}"

                    message = {
                        "type": "event",
                        "channel": channel,
                        "payload": out.model_dump(),
                        "id": str(out.id),
                        "ts": out.created_at.isoformat() if out.created_at else None,
                    }
                    await websocket.send_json(message)
            else:
                idle_ticks += 1
                if idle_ticks >= int(30 / max(poll_interval, 0.1)):
                    idle_ticks = 0
                    await websocket.send_json({"type": "ping"})

            await asyncio.sleep(poll_interval)
        except WebSocketDisconnect:
            break
        except Exception as exc:
            logger.debug("ws_event_pusher_error", extra={"error": str(exc)})
            break


@router.websocket("/ws/events")
async def websocket_events(
    websocket: WebSocket,
    db: Database = Depends(get_db),
):
    """
    WebSocket endpoint for real-time event updates.

    Clients can subscribe to channels:
    - "events" - All events
    - "protocol:{id}" - Events for specific protocol
    - "project:{id}" - Events for specific project
    - "agents" - Agent status updates

    Message format:
    - Subscribe: {"type": "subscribe", "channels": ["events", "protocol:1"]}
    - Unsubscribe: {"type": "unsubscribe", "channels": ["protocol:1"]}
    - Ping: {"type": "ping"} -> responds with {"type": "pong"}
    """
    await ws_manager.connect(websocket)
    logger.info("websocket_connected", extra={"client": str(websocket.client)})

    pusher_task = asyncio.create_task(_ws_event_pusher(websocket, db))

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "subscribe":
                channels = data.get("channels", [])
                ws_manager.subscribe(websocket, channels)
                await websocket.send_json({
                    "type": "subscribed",
                    "channels": channels,
                })

            elif msg_type == "unsubscribe":
                channels = data.get("channels", [])
                ws_manager.unsubscribe(websocket, channels)
                await websocket.send_json({
                    "type": "unsubscribed",
                    "channels": channels,
                })

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info("websocket_disconnected", extra={"client": str(websocket.client)})
    except Exception as exc:
        logger.debug("websocket_error", extra={"error": str(exc)})
    finally:
        pusher_task.cancel()
        ws_manager.disconnect(websocket)
