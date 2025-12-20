"""
DevGodzilla Event Persistence

Binds the in-process EventBus (`devgodzilla.services.events`) to the database
events table (`db.append_event`).
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Protocol, cast

from devgodzilla.events_catalog import normalize_event_type
from devgodzilla.logging import get_logger
from devgodzilla.services.events import Event as BusEvent
from devgodzilla.services.events import get_event_bus

logger = get_logger(__name__)


class _EventDB(Protocol):
    def append_event(
        self,
        protocol_run_id: Optional[int],
        event_type: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        step_run_id: Optional[int] = None,
        project_id: Optional[int] = None,
    ) -> Any: ...


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if dataclasses.is_dataclass(value):
        return {k: _json_safe(v) for k, v in dataclasses.asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _default_message(event: BusEvent) -> str:
    pieces: list[str] = [normalize_event_type(event.event_type)]
    step_name = getattr(event, "step_name", None)
    protocol_name = getattr(event, "protocol_name", None)
    if step_name:
        pieces.append(str(step_name))
    if protocol_name:
        pieces.append(str(protocol_name))
    return " - ".join(pieces)


def install_db_event_sink(
    *,
    db_provider: Callable[[], _EventDB],
) -> None:
    """
    Install a global EventBus handler that persists events into the DB.

    Idempotent: calling multiple times installs the sink only once per process.
    """
    bus = get_event_bus()

    if getattr(bus, "_db_sink_installed", False):
        return

    def _persist(event: BusEvent) -> None:
        protocol_run_id = cast(Optional[int], getattr(event, "protocol_run_id", None))
        project_id = cast(Optional[int], getattr(event, "project_id", None))
        
        # Require at least one of protocol_run_id or project_id
        if not protocol_run_id and not project_id:
            return
            
        step_run_id = cast(Optional[int], getattr(event, "step_run_id", None))

        try:
            db = db_provider()
            payload = _json_safe(event)
            normalized_type = normalize_event_type(event.event_type)
            db.append_event(
                protocol_run_id=protocol_run_id,
                step_run_id=step_run_id,
                project_id=project_id,
                event_type=normalized_type,
                message=_default_message(event),
                metadata=cast(Dict[str, Any], payload) if isinstance(payload, dict) else {"event": payload},
            )
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "event_persist_failed",
                extra={"event_type": getattr(event, "event_type", None), "error": str(exc)},
            )

    bus.add_handler(None, _persist)
    setattr(bus, "_db_sink_installed", True)
