"""WebSocket endpoint for real-time event broadcasting.

Provides a simple in-memory WebSocket connection manager for development.
Broadcasts protocol status changes, run updates, task updates, and step updates
to all connected clients.

Endpoints:
    GET /ws/events — WebSocket endpoint that accepts connections and broadcasts events.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from devgodzilla.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


class ConnectionManager:
    """Simple in-memory WebSocket connection manager for development."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            "ws_client_connected",
            extra={"total_connections": len(self.active_connections)},
        )

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(
            "ws_client_disconnected",
            extra={"total_connections": len(self.active_connections)},
        )

    async def broadcast(self, message: dict[str, Any]) -> None:
        if not self.active_connections:
            return
        payload = json.dumps(message, default=str)
        disconnected: list[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)

    async def send_to(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        payload = json.dumps(message, default=str)
        try:
            await websocket.send_text(payload)
        except Exception:
            self.disconnect(websocket)


manager = ConnectionManager()


def build_event_message(
    event_type: str,
    channel: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a standard WebSocket event message envelope."""
    return {
        "type": event_type,
        "channel": channel,
        "payload": payload or {},
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


async def broadcast_event(
    event_type: str,
    channel: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Broadcast an event to all connected WebSocket clients."""
    message = build_event_message(event_type, channel, payload)
    await manager.broadcast(message)


# --- Subscription-aware connection handling ---


async def _handle_client_subscriptions(
    websocket: WebSocket,
    subscriptions: set[str],
) -> None:
    """Read messages from client and track subscriptions."""
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue

            msg_type = data.get("type")
            if msg_type == "subscribe":
                channels = data.get("channels", [])
                if isinstance(channels, list):
                    subscriptions.update(str(c) for c in channels)
            elif msg_type == "unsubscribe":
                channels = data.get("channels", [])
                if isinstance(channels, list):
                    for c in channels:
                        subscriptions.discard(str(c))
            elif msg_type == "ping":
                await manager.send_to(
                    websocket,
                    build_event_message("pong", "system"),
                )
    except WebSocketDisconnect:
        pass


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket) -> None:
    """WebSocket endpoint at /ws/events for real-time event streaming.

    Clients connect and can subscribe to channels:
    - protocol:{id} — Protocol run updates
    - step:{id} — Step run updates
    - events — System events
    - agents — Agent status updates

    Messages from server follow the envelope format:
        { "type": str, "channel": str, "payload": dict, "ts": str }

    Messages from client:
        { "type": "subscribe", "channels": ["protocol:1", "events"] }
        { "type": "unsubscribe", "channels": [...] }
        { "type": "ping" }
    """
    await manager.connect(websocket)
    subscriptions: set[str] = set()

    try:
        reader_task = asyncio.create_task(
            _handle_client_subscriptions(websocket, subscriptions)
        )
        await reader_task
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error("ws_error", extra={"error": str(exc)})
    finally:
        manager.disconnect(websocket)
