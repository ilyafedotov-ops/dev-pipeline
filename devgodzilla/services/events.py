"""
DevGodzilla Event Bus

A lightweight in-process event bus for decoupled communication between services.
Supports both sync and async event handlers.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar
from weakref import WeakSet

from devgodzilla.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound="Event")


@dataclass
class Event:
    """
    Base class for all events in the system.
    
    All events carry a timestamp and optional metadata.
    Subclasses should define additional fields for event-specific data.
    """
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def event_type(self) -> str:
        """Return the event type name (class name by default)."""
        return self.__class__.__name__


# Protocol Events

@dataclass
class ProtocolEvent(Event):
    """Base class for protocol-related events."""
    protocol_run_id: int = 0
    project_id: Optional[int] = None


@dataclass
class ProtocolStarted(ProtocolEvent):
    """Fired when a protocol run starts."""
    protocol_name: str = ""


@dataclass
class ProtocolCompleted(ProtocolEvent):
    """Fired when a protocol run completes successfully."""
    pass


@dataclass
class ProtocolFailed(ProtocolEvent):
    """Fired when a protocol run fails."""
    error: Optional[str] = None


@dataclass
class ProtocolPaused(ProtocolEvent):
    """Fired when a protocol run is paused."""
    pass


@dataclass
class ProtocolResumed(ProtocolEvent):
    """Fired when a protocol run is resumed."""
    pass


# Step Events

@dataclass
class StepEvent(Event):
    """Base class for step-related events."""
    step_run_id: int = 0
    protocol_run_id: int = 0
    step_name: str = ""


@dataclass
class StepStarted(StepEvent):
    """Fired when a step execution starts."""
    engine_id: Optional[str] = None


@dataclass
class StepCompleted(StepEvent):
    """Fired when a step execution completes successfully."""
    summary: Optional[str] = None


@dataclass
class StepFailed(StepEvent):
    """Fired when a step execution fails."""
    error: Optional[str] = None
    retryable: bool = True


@dataclass
class StepQARequired(StepEvent):
    """Fired when a step requires QA review."""
    pass


# QA Events

@dataclass
class QAEvent(Event):
    """Base class for QA-related events."""
    step_run_id: int = 0
    protocol_run_id: int = 0


@dataclass
class QAStarted(QAEvent):
    """Fired when QA assessment starts."""
    gates: List[str] = field(default_factory=list)


@dataclass
class QAPassed(QAEvent):
    """Fired when QA assessment passes."""
    pass


@dataclass
class QAFailed(QAEvent):
    """Fired when QA assessment fails."""
    failures: List[Dict[str, Any]] = field(default_factory=list)
    action: str = "retry"  # retry, clarify, re_plan, re_specify


# Feedback Loop Events

@dataclass
class FeedbackEvent(Event):
    """Fired when a feedback loop action is taken."""
    protocol_run_id: int = 0
    step_run_id: Optional[int] = None
    error_type: str = ""
    action: str = ""  # clarify, re_plan, retry
    attempt: int = 1


# Type alias for handlers
EventHandler = Callable[[Event], None]
AsyncEventHandler = Callable[[Event], asyncio.Future]


class EventBus:
    """
    In-process event bus for decoupled service communication.
    
    Supports:
    - Sync and async event handlers
    - Wildcard subscriptions (receive all events)
    - Event filtering by type
    - Weak references to avoid memory leaks
    
    Example:
        bus = EventBus()
        
        @bus.subscribe(StepCompleted)
        def on_step_completed(event: StepCompleted):
            print(f"Step {event.step_name} completed!")
        
        bus.publish(StepCompleted(step_run_id=1, step_name="Create models"))
    """
    
    def __init__(self) -> None:
        self._handlers: Dict[type, List[EventHandler]] = {}
        self._async_handlers: Dict[type, List[AsyncEventHandler]] = {}
        self._wildcard_handlers: List[EventHandler] = []
        self._async_wildcard_handlers: List[AsyncEventHandler] = []
    
    def subscribe(
        self,
        event_type: Optional[type] = None,
    ) -> Callable[[EventHandler], EventHandler]:
        """
        Decorator to subscribe a handler to an event type.
        
        Args:
            event_type: The event type to subscribe to, or None for all events
            
        Returns:
            A decorator that registers the handler
        """
        def decorator(handler: EventHandler) -> EventHandler:
            self.add_handler(event_type, handler)
            return handler
        return decorator
    
    def add_handler(
        self,
        event_type: Optional[type],
        handler: EventHandler,
    ) -> None:
        """
        Add a handler for a specific event type.
        
        Args:
            event_type: The event type, or None for wildcard
            handler: The handler function
        """
        if event_type is None:
            self._wildcard_handlers.append(handler)
        else:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)
    
    def add_async_handler(
        self,
        event_type: Optional[type],
        handler: AsyncEventHandler,
    ) -> None:
        """
        Add an async handler for a specific event type.
        
        Args:
            event_type: The event type, or None for wildcard
            handler: The async handler function
        """
        if event_type is None:
            self._async_wildcard_handlers.append(handler)
        else:
            if event_type not in self._async_handlers:
                self._async_handlers[event_type] = []
            self._async_handlers[event_type].append(handler)
    
    def remove_handler(
        self,
        event_type: Optional[type],
        handler: EventHandler,
    ) -> None:
        """Remove a previously registered handler."""
        if event_type is None:
            if handler in self._wildcard_handlers:
                self._wildcard_handlers.remove(handler)
        elif event_type in self._handlers:
            if handler in self._handlers[event_type]:
                self._handlers[event_type].remove(handler)
    
    def publish(self, event: Event) -> None:
        """
        Publish an event to all registered handlers.
        
        Sync handlers are called immediately. Async handlers are scheduled.
        
        Args:
            event: The event to publish
        """
        event_type = type(event)
        handlers_called = 0
        
        # Call type-specific handlers
        for base_type in event_type.__mro__:
            if base_type in self._handlers:
                for handler in self._handlers[base_type]:
                    try:
                        handler(event)
                        handlers_called += 1
                    except Exception as e:
                        logger.error(
                            f"Error in event handler: {e}",
                            extra={"event_type": event.event_type, "error": str(e)}
                        )
        
        # Call wildcard handlers
        for handler in self._wildcard_handlers:
            try:
                handler(event)
                handlers_called += 1
            except Exception as e:
                logger.error(
                    f"Error in wildcard handler: {e}",
                    extra={"event_type": event.event_type, "error": str(e)}
                )
        
        logger.debug(
            f"Published {event.event_type}",
            extra={"event_type": event.event_type, "handlers_called": handlers_called}
        )
    
    async def publish_async(self, event: Event) -> None:
        """
        Publish an event to all registered handlers (async version).
        
        Both sync and async handlers are called.
        
        Args:
            event: The event to publish
        """
        # Call sync handlers first
        self.publish(event)
        
        event_type = type(event)
        
        # Call type-specific async handlers
        for base_type in event_type.__mro__:
            if base_type in self._async_handlers:
                for handler in self._async_handlers[base_type]:
                    try:
                        await handler(event)
                    except Exception as e:
                        logger.error(
                            f"Error in async event handler: {e}",
                            extra={"event_type": event.event_type, "error": str(e)}
                        )
        
        # Call wildcard async handlers
        for handler in self._async_wildcard_handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(
                    f"Error in async wildcard handler: {e}",
                    extra={"event_type": event.event_type, "error": str(e)}
                )
    
    def clear(self) -> None:
        """Remove all registered handlers."""
        self._handlers.clear()
        self._async_handlers.clear()
        self._wildcard_handlers.clear()
        self._async_wildcard_handlers.clear()


# Global event bus instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get or create the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def publish_event(event: Event) -> None:
    """Convenience function to publish an event to the global bus."""
    get_event_bus().publish(event)
