from typing import Any, Dict, Optional


class TasksGodzillaError(RuntimeError):
    """
    Base error for orchestrator components. Carries metadata for structured logging.
    """

    category: str = "runtime"
    retryable: bool = True

    def __init__(self, message: str, *, metadata: Optional[Dict[str, Any]] = None, retryable: Optional[bool] = None) -> None:
        super().__init__(message)
        self.metadata = metadata or {}
        if retryable is not None:
            self.retryable = retryable


class ValidationError(TasksGodzillaError):
    """Raised when input validation fails."""

    category = "validation"
    retryable = False


class BudgetExceededError(ValidationError, ValueError):
    """Raised when estimated tokens exceed configured budget."""

    category = "validation"
    retryable = False


class ConfigError(TasksGodzillaError):
    """Raised when configuration is invalid or missing."""

    category = "config"
    retryable = False


class CodexCommandError(TasksGodzillaError):
    """Raised when Codex execution fails."""

    category = "codex"


class OpenCodeCommandError(TasksGodzillaError):
    """Raised when OpenCode execution (CLI/API) fails."""

    category = "opencode"


class GitCommandError(TasksGodzillaError):
    """Raised when git commands fail."""

    category = "git"


class CITriggerError(TasksGodzillaError):
    """Raised when CI triggering via gh/glab fails."""

    category = "ci"
    retryable = False
