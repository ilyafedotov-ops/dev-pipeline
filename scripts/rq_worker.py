#!/usr/bin/env python3
"""
Run an RQ worker to process TasksGodzilla jobs from Redis.

Environment:
  - TASKSGODZILLA_REDIS_URL (required)
  - TASKSGODZILLA_DB_PATH (for Database)
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rq import Queue, Worker  # type: ignore
import redis  # type: ignore

from tasksgodzilla.config import load_config  # noqa: E402
from tasksgodzilla.logging import setup_logging, json_logging_from_env, log_extra  # noqa: E402


def main() -> None:
    log_level = os.environ.get("TASKSGODZILLA_LOG_LEVEL") or "INFO"
    logger = setup_logging(log_level, json_output=json_logging_from_env())
    config = load_config()
    if not config.redis_url:
        logger.error("TASKSGODZILLA_REDIS_URL is required for RQ worker.")
        sys.exit(1)
    redis_conn = redis.from_url(config.redis_url)
    queues = [Queue("default", connection=redis_conn)]
    worker = Worker(queues, connection=redis_conn)
    logger.info("[rq-worker] Listening", extra={"redis": config.redis_url, "queues": [q.name for q in queues]})
    try:
        worker.work()
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("[rq-worker] fatal error", extra=log_extra(error=str(exc), error_type=exc.__class__.__name__))
        sys.exit(1)


if __name__ == "__main__":
    main()
