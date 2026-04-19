"""Retry configuration loader."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from devgodzilla.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RetrySettings:
    """Retry settings for a specific error type or default."""
    
    max_attempts: int = 3
    initial_delay_seconds: float = 10.0
    max_delay_seconds: float = 300.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RetrySettings":
        """Create RetrySettings from a dictionary."""
        return cls(
            max_attempts=data.get('max_attempts', 3),
            initial_delay_seconds=data.get('initial_delay_seconds', 10.0),
            max_delay_seconds=data.get('max_delay_seconds', 300.0),
            backoff_multiplier=data.get('backoff_multiplier', 2.0),
            jitter=data.get('jitter', True),
        )


@dataclass
class CircuitBreakerSettings:
    """Circuit breaker configuration."""
    
    enabled: bool = True
    failure_threshold: int = 5
    recovery_timeout_seconds: float = 60.0
    half_open_max_calls: int = 3
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CircuitBreakerSettings":
        """Create CircuitBreakerSettings from a dictionary."""
        return cls(
            enabled=data.get('enabled', True),
            failure_threshold=data.get('failure_threshold', 5),
            recovery_timeout_seconds=data.get('recovery_timeout_seconds', 60.0),
            half_open_max_calls=data.get('half_open_max_calls', 3),
        )


@dataclass
class TimeoutSettings:
    """Timeout configuration for various operations."""
    
    default_step_seconds: float = 300.0
    max_step_seconds: float = 3600.0
    qa_check_seconds: float = 120.0
    planning_seconds: float = 600.0
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimeoutSettings":
        """Create TimeoutSettings from a dictionary."""
        return cls(
            default_step_seconds=data.get('default_step_seconds', 300.0),
            max_step_seconds=data.get('max_step_seconds', 3600.0),
            qa_check_seconds=data.get('qa_check_seconds', 120.0),
            planning_seconds=data.get('planning_seconds', 600.0),
        )


@dataclass
class ParallelismSettings:
    """Parallelism configuration."""
    
    max_concurrent_steps: int = 4
    max_concurrent_protocols: int = 10
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ParallelismSettings":
        """Create ParallelismSettings from a dictionary."""
        return cls(
            max_concurrent_steps=data.get('max_concurrent_steps', 4),
            max_concurrent_protocols=data.get('max_concurrent_protocols', 10),
        )


@dataclass
class FeedbackSettings:
    """Feedback loop configuration."""
    
    max_clarification_loops: int = 3
    max_replan_attempts: int = 2
    auto_retry_transient: bool = True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeedbackSettings":
        """Create FeedbackSettings from a dictionary."""
        return cls(
            max_clarification_loops=data.get('max_clarification_loops', 3),
            max_replan_attempts=data.get('max_replan_attempts', 2),
            auto_retry_transient=data.get('auto_retry_transient', True),
        )


@dataclass
class QueueSettings:
    """Queue configuration."""
    
    max_depth: int = 1000
    priority_levels: Dict[str, int] = field(default_factory=lambda: {
        'idle': 0,
        'low': 25,
        'normal': 50,
        'high': 75,
        'critical': 100,
    })
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QueueSettings":
        """Create QueueSettings from a dictionary."""
        return cls(
            max_depth=data.get('max_depth', 1000),
            priority_levels=data.get('priority_levels', {
                'idle': 0,
                'low': 25,
                'normal': 50,
                'high': 75,
                'critical': 100,
            }),
        )


@dataclass
class OrchestrationConfig:
    """Complete orchestration configuration."""
    
    retry: RetrySettings = field(default_factory=RetrySettings)
    retry_overrides: Dict[str, RetrySettings] = field(default_factory=dict)
    circuit_breaker: CircuitBreakerSettings = field(default_factory=CircuitBreakerSettings)
    timeouts: TimeoutSettings = field(default_factory=TimeoutSettings)
    parallelism: ParallelismSettings = field(default_factory=ParallelismSettings)
    feedback: FeedbackSettings = field(default_factory=FeedbackSettings)
    queue: QueueSettings = field(default_factory=QueueSettings)
    
    @classmethod
    def from_yaml(cls, path: str = "config/orchestration.yaml") -> "OrchestrationConfig":
        """Load configuration from YAML file.
        
        Args:
            path: Path to the YAML configuration file.
            
        Returns:
            OrchestrationConfig instance with loaded settings.
        """
        config_path = Path(path)
        
        if not config_path.exists():
            # Return defaults if file doesn't exist
            return cls()
        
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        
        return cls.from_dict(data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrchestrationConfig":
        """Create OrchestrationConfig from a dictionary.
        
        Args:
            data: Dictionary with configuration data.
            
        Returns:
            OrchestrationConfig instance with loaded settings.
        """
        retry_data = data.get('retry', {})
        retry_overrides = {}
        
        # Parse retry overrides
        overrides_data = retry_data.get('overrides', {})
        for error_type, override_data in overrides_data.items():
            retry_overrides[error_type] = RetrySettings.from_dict(override_data)
        
        return cls(
            retry=RetrySettings.from_dict(retry_data),
            retry_overrides=retry_overrides,
            circuit_breaker=CircuitBreakerSettings.from_dict(data.get('circuit_breaker', {})),
            timeouts=TimeoutSettings.from_dict(data.get('timeouts', {})),
            parallelism=ParallelismSettings.from_dict(data.get('parallelism', {})),
            feedback=FeedbackSettings.from_dict(data.get('feedback', {})),
            queue=QueueSettings.from_dict(data.get('queue', {})),
        )
    
    def get_retry_settings(self, error_type: str) -> RetrySettings:
        """Get retry settings for a specific error type.
        
        Args:
            error_type: Type of error (e.g., 'transient', 'timeout', 'agent_unavailable').
            
        Returns:
            RetrySettings for the error type, or default if no override exists.
        """
        return self.retry_overrides.get(error_type, self.retry)
    
    def calculate_delay(self, attempt: int, error_type: Optional[str] = None) -> float:
        """Calculate delay for a given retry attempt with exponential backoff.
        
        Args:
            attempt: Current attempt number (1-indexed).
            error_type: Optional error type to get specific settings.
            
        Returns:
            Delay in seconds before next retry.
        """
        import random
        
        settings = self.get_retry_settings(error_type) if error_type else self.retry
        
        # Calculate exponential backoff
        delay = settings.initial_delay_seconds * (settings.backoff_multiplier ** (attempt - 1))
        
        # Cap at max delay
        delay = min(delay, settings.max_delay_seconds)
        
        # Add jitter if enabled
        if settings.jitter:
            # Random jitter between 0% and 25% of delay
            jitter_amount = delay * random.random() * 0.25
            delay += jitter_amount
        
        return delay


# Singleton instance for convenience
_config_instance: Optional[OrchestrationConfig] = None


def get_orchestration_config(path: str = "config/orchestration.yaml") -> OrchestrationConfig:
    """Get the orchestration configuration (cached singleton).
    
    Args:
        path: Path to the YAML configuration file.
        
    Returns:
        OrchestrationConfig instance.
    """
    global _config_instance
    
    if _config_instance is None:
        _config_instance = OrchestrationConfig.from_yaml(path)
    
    return _config_instance


def reload_orchestration_config(path: str = "config/orchestration.yaml") -> OrchestrationConfig:
    """Force reload the orchestration configuration.
    
    Args:
        path: Path to the YAML configuration file.
        
    Returns:
        Fresh OrchestrationConfig instance.
    """
    global _config_instance
    _config_instance = OrchestrationConfig.from_yaml(path)
    return _config_instance
