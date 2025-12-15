"""
DevGodzilla Service Base

Defines the base Service class and ServiceContext that all services inherit from.
This provides a consistent interface for dependency injection and context propagation.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from devgodzilla.config import Config
from devgodzilla.logging import get_logger


@dataclass
class ServiceContext:
    """
    Context object providing shared dependencies and runtime state to services.
    
    Attributes:
        config: Application configuration
        request_id: Optional request correlation ID for tracing
        metadata: Additional contextual metadata
    """
    config: Config
    request_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def with_request_id(self, request_id: str) -> "ServiceContext":
        """Return a new context with the specified request_id."""
        return ServiceContext(
            config=self.config,
            request_id=request_id,
            metadata=self.metadata.copy(),
        )

    def with_metadata(self, **kwargs: Any) -> "ServiceContext":
        """Return a new context with additional metadata."""
        new_metadata = {**self.metadata, **kwargs}
        return ServiceContext(
            config=self.config,
            request_id=self.request_id,
            metadata=new_metadata,
        )


class Service:
    """
    Base class for all DevGodzilla services.
    
    Services are the primary abstraction for business logic in DevGodzilla.
    Each service receives a ServiceContext providing access to configuration,
    logging, and other shared dependencies.
    
    Example:
        class MyService(Service):
            def do_something(self) -> str:
                self.logger.info("Doing something", extra=self.log_extra())
                return "done"
    """

    def __init__(self, context: ServiceContext) -> None:
        """
        Initialize the service with a context.
        
        Args:
            context: ServiceContext providing configuration and dependencies
        """
        self.context = context
        self.config = context.config
        self.logger = get_logger(self.__class__.__name__)

    def log_extra(
        self,
        *,
        request_id: Optional[str] = None,
        project_id: Optional[int] = None,
        protocol_run_id: Optional[int] = None,
        step_run_id: Optional[int] = None,
        **extra: Any,
    ) -> Dict[str, Any]:
        """
        Build a consistent extra dict for structured logging.
        
        Uses context request_id by default, but can be overridden.
        Only non-None values are included.
        """
        payload: Dict[str, Any] = {}
        
        # Use context request_id as fallback
        effective_request_id = request_id or self.context.request_id
        if effective_request_id is not None:
            payload["request_id"] = effective_request_id
            
        if project_id is not None:
            payload["project_id"] = project_id
        if protocol_run_id is not None:
            payload["protocol_run_id"] = protocol_run_id
        if step_run_id is not None:
            payload["step_run_id"] = step_run_id
            
        payload.update({k: v for k, v in extra.items() if v is not None})
        return payload
