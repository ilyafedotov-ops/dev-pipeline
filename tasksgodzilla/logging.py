import json
import logging
import os
from typing import Any, Dict, Optional

STANDARD_FIELDS = ("request_id", "job_id", "project_id", "protocol_run_id", "step_run_id")


class RequestIdFilter(logging.Filter):
    """
    Ensure that all standard context fields exist on every log record so formatters
    can rely on them. Defaults can be overridden per-handler if needed.
    """

    def __init__(self, defaults: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.defaults = {
            "request_id": "-",
            "job_id": "-",
            "project_id": "-",
            "protocol_run_id": "-",
            "step_run_id": "-",
        }
        if defaults:
            self.defaults.update({k: v for k, v in defaults.items() if v is not None})

    def filter(self, record: logging.LogRecord) -> bool:
        for key, default in self.defaults.items():
            if not hasattr(record, key):
                setattr(record, key, default)
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # pragma: no cover - formatting
        data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in STANDARD_FIELDS:
            data[field] = getattr(record, field, "-")
        for extra_key in (
            "path",
            "method",
            "status_code",
            "duration_ms",
            "client",
            "error",
            "error_type",
            "error_category",
        ):
            if hasattr(record, extra_key):
                data[extra_key] = getattr(record, extra_key)
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data)


def setup_logging(level: Optional[str] = None, json_output: bool = False) -> logging.Logger:
    resolved_level = level or os.environ.get("TASKSGODZILLA_LOG_LEVEL") or "INFO"
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
    return logging.getLogger("tasksgodzilla")


def get_logger(name: str = "tasksgodzilla") -> logging.Logger:
    return logging.getLogger(name)


def init_cli_logging(level: Optional[str] = None, json_output: bool = False) -> logging.Logger:
    """
    Initialize logging for CLI tools using the configured log level (default INFO).
    """
    return setup_logging(level or os.environ.get("TASKSGODZILLA_LOG_LEVEL") or "INFO", json_output=json_output)


def json_logging_from_env() -> bool:
    return os.environ.get("TASKSGODZILLA_LOG_JSON", "").lower() in ("1", "true", "yes")


def log_extra(
    *,
    request_id: Optional[str] = None,
    job_id: Optional[str] = None,
    project_id: Optional[int] = None,
    protocol_run_id: Optional[int] = None,
    step_run_id: Optional[int] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """
    Helper to build consistent extra dictionaries for structured logging. Only
    non-None values are included so defaults from RequestIdFilter still apply.
    """
    payload: Dict[str, Any] = {}
    if request_id is not None:
        payload["request_id"] = request_id
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
