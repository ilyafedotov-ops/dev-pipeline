#!/usr/bin/env python3
"""
Run the TasksGodzilla orchestrator API (FastAPI + SQLite).

Install dependencies first:
  pip install fastapi uvicorn
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn  # noqa: E402
from tasksgodzilla.logging import setup_logging, json_logging_from_env, log_extra  # noqa: E402


def main() -> None:
    log_level = os.environ.get("TASKSGODZILLA_LOG_LEVEL") or "INFO"
    logger = setup_logging(log_level, json_output=json_logging_from_env())
    host = os.environ.get("TASKSGODZILLA_API_HOST") or "0.0.0.0"
    port = int(os.environ.get("TASKSGODZILLA_API_PORT") or "8010")
    try:
        # Allow our central logging config to drive output (structured/JSON) instead of uvicorn defaults.
        uvicorn.run("tasksgodzilla.api.app:app", host=host, port=port, reload=False, log_config=None)
    except Exception as exc:  # pragma: no cover - best effort
        logger.error("API server failed", extra=log_extra(error=str(exc), error_type=exc.__class__.__name__))
        sys.exit(1)


if __name__ == "__main__":
    main()
