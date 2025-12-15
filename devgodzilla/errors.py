"""
DevGodzilla Error Hierarchy

Base error and specific error types for all DevGodzilla components.
Errors carry metadata for structured logging.
"""

from typing import Any, Dict, Optional


class DevGodzillaError(RuntimeError):
    """
    Base error for DevGodzilla components. Carries metadata for structured logging.
    
    Attributes:
        category: Error category for classification (e.g., "runtime", "validation")
        retryable: Whether the operation can be retried
        metadata: Additional context for logging and debugging
    """

    category: str = "runtime"
    retryable: bool = True

    def __init__(
        self,
        message: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        retryable: Optional[bool] = None,
    ) -> None:
        super().__init__(message)
        self.metadata = metadata or {}
        if retryable is not None:
            self.retryable = retryable


# Validation Errors
class ValidationError(DevGodzillaError):
    """Raised when input validation fails."""

    category = "validation"
    retryable = False


class BudgetExceededError(ValidationError, ValueError):
    """Raised when estimated tokens exceed configured budget."""

    category = "validation"
    retryable = False


# Configuration Errors
class ConfigError(DevGodzillaError):
    """Raised when configuration is invalid or missing."""

    category = "config"
    retryable = False


# Engine Errors
class EngineError(DevGodzillaError):
    """Base class for AI engine execution errors."""

    category = "engine"


class CodexCommandError(EngineError):
    """Raised when Codex execution fails."""

    category = "codex"


class OpenCodeCommandError(EngineError):
    """Raised when OpenCode execution (CLI/API) fails."""

    category = "opencode"


class ClaudeCodeError(EngineError):
    """Raised when Claude Code execution fails."""

    category = "claude_code"


class GeminiCliError(EngineError):
    """Raised when Gemini CLI execution fails."""

    category = "gemini_cli"


class EngineNotFoundError(EngineError):
    """Raised when a requested engine is not registered."""

    category = "engine"
    retryable = False


# Git Errors
class GitCommandError(DevGodzillaError):
    """Raised when git commands fail."""

    category = "git"


class GitLockError(GitCommandError):
    """Raised when git index.lock cannot be acquired after retries."""

    category = "git"
    retryable = False


# CI Errors
class CITriggerError(DevGodzillaError):
    """Raised when CI triggering via gh/glab fails."""

    category = "ci"
    retryable = False


# Orchestration Errors
class OrchestrationError(DevGodzillaError):
    """Base class for orchestration-related errors."""

    category = "orchestration"


class WindmillError(OrchestrationError):
    """Raised when Windmill API calls fail."""

    category = "windmill"


class DAGCycleError(OrchestrationError):
    """Raised when task dependencies contain cycles."""

    category = "orchestration"
    retryable = False


# Specification Errors
class SpecificationError(DevGodzillaError):
    """
    Raised when specification issues are detected.
    
    Used by the feedback loop to trigger clarification, re-planning, or re-specification.
    
    Attributes:
        action: The recommended action ("clarify", "re_plan", "re_specify")
        step_id: Optional step ID where the error occurred
    """

    category = "specification"
    retryable = True
    
    def __init__(
        self,
        message: str,
        *,
        action: str = "clarify",
        step_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        retryable: Optional[bool] = None,
    ) -> None:
        super().__init__(message, metadata=metadata, retryable=retryable)
        self.action = action
        self.step_id = step_id


# Quality Errors
class QualityError(DevGodzillaError):
    """Base class for QA-related errors."""

    category = "quality"


class QAGateFailed(QualityError):
    """Raised when a QA gate check fails."""

    category = "quality"
    retryable = True


# Storage Errors
class StorageError(DevGodzillaError):
    """Raised when database operations fail."""

    category = "storage"


class EntityNotFoundError(StorageError):
    """Raised when a requested entity is not found in storage."""

    category = "storage"
    retryable = False
