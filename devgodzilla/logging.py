"""
DevGodzilla Structured Logging

Provides structured logging with context propagation, JSON formatting,
and sensitive data redaction.
"""

import json
import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from urllib.parse import urlsplit, urlunsplit
from typing import Any, Dict, Generator, Optional


STANDARD_FIELDS = ("request_id", "run_id", "job_id", "project_id", "protocol_run_id", "step_run_id")

_RESERVED_LOG_RECORD_ATTRS = set(
    logging.LogRecord(
        name="",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="",
        args=(),
        exc_info=None,
    ).__dict__.keys()
)
_RESERVED_LOG_RECORD_ATTRS.update({"asctime", "message"})


def _json_fallback(value: Any) -> str:  # pragma: no cover - defensive
    """Best-effort conversion for non-JSON-serializable values (Path, Exception, etc.)."""
    try:
        return str(value)
    except Exception:
        return repr(value)


_REDACTED = "[REDACTED]"
_SECRET_KEY_MARKERS = (
    "token", "secret", "password", "passwd", "api_key", "apikey",
    "access_key", "private_key", "bearer", "credential"
)


def _looks_sensitive_key(key: str) -> bool:
    """Check if a key name suggests sensitive data."""
    lower = (key or "").lower()
    return any(marker in lower for marker in _SECRET_KEY_MARKERS)


def _strip_url_credentials(value: str) -> str:
    """Remove user:pass@ from URLs (redis/postgres/http/etc)."""
    try:
        parts = urlsplit(value)
    except Exception:
        return value
    if not parts.scheme or not parts.netloc:
        return value
    if "@" not in parts.netloc:
        return value
    hostpart = parts.netloc.rsplit("@", 1)[-1]
    return urlunsplit((parts.scheme, hostpart, parts.path, parts.query, parts.fragment))


def _sanitize_for_logging(key: str, value: Any) -> Any:
    """Sanitize a value for safe logging (redact secrets, strip credentials)."""
    if _looks_sensitive_key(key):
        return _REDACTED
    if isinstance(value, str):
        return _strip_url_credentials(value)
    if isinstance(value, dict):
        return {k: _sanitize_for_logging(str(k), v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_for_logging(key, v) for v in value]
    return value


# Context variable for log context propagation
_LOG_CONTEXT: ContextVar[Dict[str, Any]] = ContextVar("DEVGODZILLA_LOG_CONTEXT", default={})


def get_log_context() -> Dict[str, Any]:
    """Return a copy of the current log context to avoid accidental mutation."""
    return dict(_LOG_CONTEXT.get() or {})


def set_log_context(**fields: Any) -> None:
    """Update the current log context with new fields."""
    current = get_log_context()
    current.update({k: v for k, v in fields.items() if v is not None})
    _LOG_CONTEXT.set(current)


def clear_log_context() -> None:
    """Clear all fields from the current log context."""
    _LOG_CONTEXT.set({})


@contextmanager
def log_context(**fields: Any) -> Generator[None, None, None]:
    """Context manager for temporarily adding fields to the log context."""
    token = _LOG_CONTEXT.set({**get_log_context(), **{k: v for k, v in fields.items() if v is not None}})
    try:
        yield
    finally:
        _LOG_CONTEXT.reset(token)


class RequestIdFilter(logging.Filter):
    """
    Logging filter that ensures all standard context fields exist on every log record.
    
    Propagates contextvars-based fields onto log records and provides defaults
    for missing fields so formatters can rely on them.
    """

    def __init__(self, defaults: Optional[Dict[str, Any]] = None) -> None:
        super().__init__()
        self.defaults = {
            "request_id": "-",
            "run_id": "-",
            "job_id": "-",
            "project_id": "-",
            "protocol_run_id": "-",
            "step_run_id": "-",
        }
        if defaults:
            self.defaults.update({k: v for k, v in defaults.items() if v is not None})

    def filter(self, record: logging.LogRecord) -> bool:
        # Propagate contextvars-based fields onto the record
        ctx = get_log_context()
        for key, value in ctx.items():
            if value is None:
                continue
            if key in _RESERVED_LOG_RECORD_ATTRS:
                continue
            if not hasattr(record, key):
                setattr(record, key, value)
        
        # Apply defaults for missing standard fields
        for key, default in self.defaults.items():
            if not hasattr(record, key):
                ctx_value = ctx.get(key)
                if ctx_value is not None:
                    setattr(record, key, ctx_value)
                else:
                    setattr(record, key, default)
        return True


class JsonFormatter(logging.Formatter):
    """JSON log formatter that includes all context fields and sanitizes sensitive data."""
    
    def format(self, record: logging.LogRecord) -> str:  # pragma: no cover - formatting
        data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Include standard fields
        for field in STANDARD_FIELDS:
            data[field] = getattr(record, field, "-")
        
        # Include all custom LogRecord attributes (everything passed via `extra=`)
        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_RECORD_ATTRS:
                continue
            if key in data:
                continue
            data[key] = value
        
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        
        # Sanitize sensitive data
        sanitized = {k: _sanitize_for_logging(k, v) for k, v in data.items()}
        return json.dumps(sanitized, default=_json_fallback)


def setup_logging(level: Optional[str] = None, json_output: bool = False) -> logging.Logger:
    """
    Configure the root logger with structured logging support.
    
    Args:
        level: Log level (default: from DEVGODZILLA_LOG_LEVEL or INFO)
        json_output: If True, use JSON formatting; otherwise use text format
        
    Returns:
        The devgodzilla logger instance
    """
    resolved_level = level or os.environ.get("DEVGODZILLA_LOG_LEVEL") or "INFO"
    
    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s "
                "req=%(request_id)s job=%(job_id)s project=%(project_id)s "
                "protocol=%(protocol_run_id)s step=%(step_run_id)s"
            )
        )
    
    root = logging.getLogger()
    root.handlers = []
    root.setLevel(getattr(logging, str(resolved_level).upper(), logging.INFO))
    root.addHandler(handler)
    
    return logging.getLogger("devgodzilla")


def get_logger(name: str = "devgodzilla") -> logging.Logger:
    """Get a logger instance with the specified name."""
    return logging.getLogger(name)


def init_cli_logging(level: Optional[str] = None, json_output: bool = False) -> logging.Logger:
    """
    Initialize logging for CLI tools using the configured log level.
    
    Args:
        level: Log level (default: from DEVGODZILLA_LOG_LEVEL or INFO)
        json_output: If True, use JSON formatting
        
    Returns:
        The devgodzilla logger instance
    """
    return setup_logging(
        level or os.environ.get("DEVGODZILLA_LOG_LEVEL") or "INFO",
        json_output=json_output
    )


def json_logging_from_env() -> bool:
    """Check if JSON logging is enabled via environment variable."""
    return os.environ.get("DEVGODZILLA_LOG_JSON", "").lower() in ("1", "true", "yes")


def log_extra(
    *,
    request_id: Optional[str] = None,
    run_id: Optional[str] = None,
    job_id: Optional[str] = None,
    project_id: Optional[int] = None,
    protocol_run_id: Optional[int] = None,
    step_run_id: Optional[int] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """
    Build a consistent extra dict for structured logging.
    
    Only non-None values are included so defaults from RequestIdFilter still apply.
    
    Example:
        logger.info("Processing step", extra=log_extra(step_run_id=123, status="running"))
    """
    payload: Dict[str, Any] = {}
    if request_id is not None:
        payload["request_id"] = request_id
    if run_id is not None:
        payload["run_id"] = run_id
    if job_id is not None:
        payload["job_id"] = job_id
    if project_id is not None:
        payload["project_id"] = project_id
    if protocol_run_id is not None:
        payload["protocol_run_id"] = protocol_run_id
    if step_run_id is not None:
        payload["step_run_id"] = step_run_id
    payload.update({k: v for k, v in extra.items() if v is not None})
    return payload


# Standard exit codes for CLIs
EXIT_OK = 0
EXIT_CONFIG_ERROR = 2
EXIT_DEP_MISSING = 3
EXIT_RUNTIME_ERROR = 1
