#!/usr/bin/env python3
"""
Run the DeksdenFlow orchestrator API (FastAPI + SQLite).

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
from deksdenflow.logging import setup_logging, json_logging_from_env, log_extra  # noqa: E402


def main() -> None:
    logger = setup_logging(os.environ.get("DEKSDENFLOW_LOG_LEVEL", "INFO"), json_output=json_logging_from_env())
    host = os.environ.get("DEKSDENFLOW_API_HOST", "0.0.0.0")
    port = int(os.environ.get("DEKSDENFLOW_API_PORT", "8010"))
    try:
        uvicorn.run("deksdenflow.api.app:app", host=host, port=port, reload=False)
    except Exception as exc:  # pragma: no cover - best effort
        logger.error("API server failed", extra=log_extra(error=str(exc), error_type=exc.__class__.__name__))
        sys.exit(1)


if __name__ == "__main__":
    main()
