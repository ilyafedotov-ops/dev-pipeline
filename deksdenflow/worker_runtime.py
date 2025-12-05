import threading
import time
from typing import Optional

import logging

from deksdenflow.config import load_config
from deksdenflow.domain import ProtocolStatus, StepStatus
from deksdenflow.jobs import BaseQueue, Job
from deksdenflow.storage import BaseDatabase, Database, create_database
from deksdenflow.workers import codex_worker
from deksdenflow.metrics import metrics
from deksdenflow.logging import setup_logging


log = logging.getLogger("deksdenflow.worker")


def process_job(job: Job, db: BaseDatabase) -> None:
    """
    Handle a single job. This is a placeholder that updates DB state and logs events.
    Replace with real integrations (Codex/Git/CI) as the orchestrator matures.
    """
    if job.job_type == "plan_protocol_job":
        codex_worker.handle_plan_protocol(job.payload["protocol_run_id"], db)
    elif job.job_type == "execute_step_job":
        codex_worker.handle_execute_step(job.payload["step_run_id"], db)
    elif job.job_type == "run_quality_job":
        codex_worker.handle_quality(job.payload["step_run_id"], db)
    else:
        protocol_run_id = job.payload.get("protocol_run_id") or -1
        db.append_event(
            protocol_run_id=protocol_run_id,
            step_run_id=None,
            event_type="unknown_job",
            message=f"Unhandled job type {job.job_type}",
        )


def drain_once(queue: BaseQueue, db: BaseDatabase) -> Optional[Job]:
    job = queue.claim()
    if not job:
        return None

    try:
        process_job(job, db)
        metrics.inc_job(job.job_type, "completed")
    except Exception as exc:  # pragma: no cover - best effort
        job.attempts += 1
        backoff = min(60, 2 ** job.attempts)
        if job.attempts < job.max_attempts:
            log.warning("Job failed; requeuing with backoff", extra={"job_id": job.job_id, "error": str(exc)})
            queue.requeue(job, delay_seconds=backoff)
        else:
            log.error("Job failed permanently", extra={"job_id": job.job_id, "error": str(exc)})
            proto_id = job.payload.get("protocol_run_id")
            step_id = job.payload.get("step_run_id")
            if proto_id:
                db.append_event(proto_id, "job_failed", f"{job.job_type} failed: {exc}", step_run_id=step_id)
                db.update_protocol_status(proto_id, ProtocolStatus.BLOCKED)
            metrics.inc_job(job.job_type, "failed")
    return job


def rq_job_handler(job_type: str, payload: dict) -> None:
    """
    Entry point for RQ workers. Uses env-configured DB and processes a single job.
    """
    config = load_config()
    setup_logging(config.log_level)
    db = create_database(db_path=config.db_path, db_url=config.db_url)
    db.init_schema()
    job = Job(job_id=str(payload.get("job_id", "")), job_type=job_type, payload=payload)
    process_job(job, db)
    metrics.inc_job(job_type, "completed")


class BackgroundWorker:
    def __init__(self, queue: BaseQueue, db: BaseDatabase, poll_interval: float = 0.5) -> None:
        self.queue = queue
        self.db = db
        self.poll_interval = poll_interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

    def _loop(self) -> None:
        while not self._stop.is_set():
            job = drain_once(self.queue, self.db)
            if job is None:
                time.sleep(self.poll_interval)
