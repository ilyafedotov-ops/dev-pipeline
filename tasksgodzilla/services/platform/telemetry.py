from __future__ import annotations

from dataclasses import dataclass

from tasksgodzilla.logging import get_logger
from tasksgodzilla.metrics import metrics

log = get_logger(__name__)


@dataclass
class TelemetryService:
    """Service for metrics and observability.
    
    This service provides a centralized interface for recording metrics and
    telemetry data across the system.
    
    Responsibilities:
    - Record token usage metrics
    - Track execution phases and models
    - Provide observability for budget tracking
    
    Metrics Collected:
    - Token usage by phase (planning, exec, qa, decompose)
    - Token usage by model
    - Cumulative token consumption
    
    Usage:
        telemetry_service = TelemetryService()
        
        # Record token usage
        telemetry_service.observe_tokens(
            phase="exec",
            model="zai-coding-plan/glm-4.6",
            tokens=5000
        )
    """

    def observe_tokens(self, phase: str, model: str, tokens: int) -> None:
        """Record estimated token usage for a given phase/model."""
        metrics.observe_tokens(phase, model, tokens)

