import threading
import time
from typing import Optional

from deksdenflow.config import load_config
from deksdenflow.domain import ProtocolStatus, StepStatus
from deksdenflow.errors import DeksdenflowError
from deksdenflow.jobs import BaseQueue, Job, RedisQueue
from deksdenflow.storage import BaseDatabase, Database, create_database
from deksdenflow.workers import codex_worker, onboarding_worker, codemachine_worker, spec_worker
from deksdenflow.metrics import metrics
from deksdenflow.logging import get_logger, log_extra, setup_logging, json_logging_from_env


log = get_logger("deksdenflow.worker")


def process_job(job: Job, db: BaseDatabase) -> None:
    """
    Handle a single job. This is a placeholder that updates DB state and logs events.
    Replace with real integrations (Codex/Git/CI) as the orchestrator matures.
    """
    log.info(
        "job_start",
        extra={
            **log_extra(
                job_id=job.job_id,
                protocol_run_id=job.payload.get("protocol_run_id"),
                step_run_id=job.payload.get("step_run_id"),
            ),
            "job_type": job.job_type,
        },
    )
    if job.job_type == "plan_protocol_job":
        codex_worker.handle_plan_protocol(job.payload["protocol_run_id"], db)
    elif job.job_type == "execute_step_job":
        codex_worker.handle_execute_step(job.payload["step_run_id"], db)
    elif job.job_type == "run_quality_job":
        codex_worker.handle_quality(job.payload["step_run_id"], db)
    elif job.job_type == "project_setup_job":
        onboarding_worker.handle_project_setup(
            job.payload["project_id"],
            db,
            protocol_run_id=job.payload.get("protocol_run_id"),
        )
    elif job.job_type == "open_pr_job":
        codex_worker.handle_open_pr(job.payload["protocol_run_id"], db)
    elif job.job_type == "codemachine_import_job":
        codemachine_worker.handle_import_job(job.payload, db)
    elif job.job_type == "spec_audit_job":
        spec_worker.handle_spec_audit_job(job.payload, db)
    else:
        protocol_run_id = job.payload.get("protocol_run_id") or -1
        db.append_event(
            protocol_run_id=protocol_run_id,
            step_run_id=None,
            event_type="unknown_job",
            message=f"Unhandled job type {job.job_type}",
            metadata={"job_id": job.job_id, "protocol_run_id": protocol_run_id},
            job_id=job.job_id,
        )
    log.info(
        "job_end",
        extra={
            **log_extra(
                job_id=job.job_id,
                protocol_run_id=job.payload.get("protocol_run_id"),
                step_run_id=job.payload.get("step_run_id"),
            ),
            "job_type": job.job_type,
        },
    )


def _run_job_with_handling(
    job: Job,
    db: BaseDatabase,
    queue: Optional[BaseQueue] = None,
    requeue_on_retry: bool = False,
    rethrow: bool = False,
) -> Job:
    start = time.time()
    try:
        process_job(job, db)
        job.status = "finished"
        job.ended_at = time.time()
        metrics.inc_job(job.job_type, "completed")
        metrics.observe_job_duration(job.job_type, "completed", job.ended_at - start)
        return job
    except Exception as exc:  # pragma: no cover - best effort
        job.attempts += 1
        backoff = min(60, 2**job.attempts)
        retryable = True
        error_category = None
        if isinstance(exc, DeksdenflowError):
            retryable = exc.retryable
            error_category = exc.category
        context = log_extra(
            job_id=job.job_id,
            protocol_run_id=job.payload.get("protocol_run_id"),
            step_run_id=job.payload.get("step_run_id"),
            error=str(exc),
            error_type=exc.__class__.__name__,
            error_category=error_category,
        )
        if retryable and requeue_on_retry and queue and job.attempts < job.max_attempts:
            log.warning("Job failed; requeuing with backoff", extra={**context, "backoff": backoff})
            queue.requeue(job, delay_seconds=backoff)
            metrics.inc_job(job.job_type, "retried")
            metrics.observe_job_duration(job.job_type, "retried", time.time() - start)
        else:
            job.status = "failed"
            job.ended_at = time.time()
            job.error = str(exc)
            log.error("Job failed permanently", extra=context)
            proto_id = job.payload.get("protocol_run_id")
            step_id = job.payload.get("step_run_id")
            if proto_id:
                db.append_event(
                    proto_id,
                    "job_failed",
                    f"{job.job_type} failed: {exc}",
                    step_run_id=step_id,
                    metadata={
                        "error_type": exc.__class__.__name__,
                        "error_category": error_category,
                        "attempts": job.attempts,
                        "job_id": job.job_id,
                    },
                    job_id=job.job_id,
                )
                db.update_protocol_status(proto_id, ProtocolStatus.BLOCKED)
            if step_id:
                try:
                    db.update_step_status(step_id, StepStatus.FAILED, summary=f"{job.job_type} failed: {exc}")
                except Exception:  # pragma: no cover - best effort
                    pass
            metrics.inc_job(job.job_type, "failed")
            metrics.observe_job_duration(job.job_type, "failed", job.ended_at - start)
        if rethrow:
            raise
        return job


def drain_once(queue: BaseQueue, db: BaseDatabase) -> Optional[Job]:
    job = queue.claim()
    if not job:
        return None
    return _run_job_with_handling(job, db, queue=queue, requeue_on_retry=True, rethrow=False)


def rq_job_handler(job_type: str, payload: dict) -> None:
    """
    Entry point for RQ workers. Uses env-configured DB and processes a single job.
    """
    config = load_config()
    setup_logging(config.log_level, json_output=json_logging_from_env())
    db = create_database(db_path=config.db_path, db_url=config.db_url)
    db.init_schema()
    job = Job(job_id=str(payload.get("job_id", "")), job_type=job_type, payload=payload)
    _run_job_with_handling(job, db, queue=None, requeue_on_retry=False, rethrow=True)


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


class RQWorkerThread:
    """
    Lightweight RQ SimpleWorker loop for test/dev when using fakeredis.
    """

    def __init__(self, redis_queue: RedisQueue, poll_interval: float = 0.25) -> None:
        from rq import SimpleWorker  # type: ignore

        self.redis_queue = redis_queue
        self.poll_interval = poll_interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._worker_cls = SimpleWorker

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

    def _loop(self) -> None:
        q = self.redis_queue.get_rq_queue("default")
        # Re-create worker each burst to avoid stale state in fakeredis and sidestep signal handling.
        while not self._stop.is_set():
            worker = self._worker_cls([q], connection=self.redis_queue.redis_connection)
            try:
                # Disable signal handlers when running in background threads.
                worker._install_signal_handlers = lambda: None  # type: ignore[attr-defined]
                try:
                    from contextlib import nullcontext
                except ImportError:  # pragma: no cover - defensive
                    nullcontext = None  # type: ignore
                if nullcontext:
                    worker.death_penalty_class = lambda *args, **kwargs: nullcontext()  # type: ignore[assignment]
                worker.work(burst=True, with_scheduler=False)
            except Exception as exc:  # pragma: no cover - best effort
                log.warning("RQ worker loop error", extra={"error": str(exc)})
            time.sleep(self.poll_interval)
