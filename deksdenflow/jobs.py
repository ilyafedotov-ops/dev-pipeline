import json
import threading
import time
import uuid
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class Job:
    job_id: str
    job_type: str
    payload: Dict[str, Any]
    status: str = "queued"
    queue: str = "default"
    created_at: float = time.time()
    attempts: int = 0
    max_attempts: int = 3
    next_run_at: float = 0.0

    def asdict(self) -> Dict[str, Any]:
        return asdict(self)


class BaseQueue(Protocol):
    def enqueue(self, job_type: str, payload: Dict[str, Any], queue: Optional[str] = None) -> Job:
        ...

    def claim(self, queue: Optional[str] = None) -> Optional[Job]:
        ...

    def list(self, status: Optional[str] = None) -> List[Job]:
        ...

    def requeue(self, job: Job, delay_seconds: float) -> None:
        ...

    def stats(self) -> Dict[str, Any]:
        ...


class InMemoryQueue:
    """
    Minimal in-memory job queue placeholder.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: List[Job] = []

    def enqueue(self, job_type: str, payload: Dict[str, Any], queue: Optional[str] = None) -> Job:
        job = Job(
            job_id=str(uuid.uuid4()),
            job_type=job_type,
            payload=payload,
            queue=queue or "default",
        )
        with self._lock:
            self._jobs.append(job)
        return job

    def claim(self, queue: Optional[str] = None) -> Optional[Job]:
        """
        Pop the next queued job. Intended for a worker loop; non-blocking.
        """
        with self._lock:
            for idx, job in enumerate(self._jobs):
                if job.status == "queued" and job.next_run_at <= time.time() and (queue is None or job.queue == queue):
                    job.status = "in_progress"
                    return self._jobs.pop(idx)
        return None

    def list(self, status: Optional[str] = None) -> List[Job]:
        with self._lock:
            if status:
                return [job for job in self._jobs if job.status == status]
            return list(self._jobs)

    def requeue(self, job: Job, delay_seconds: float) -> None:
        job.status = "queued"
        job.next_run_at = time.time() + delay_seconds
        with self._lock:
            self._jobs.append(job)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._jobs)
            queued = len([j for j in self._jobs if j.status == "queued"])
            in_progress = len([j for j in self._jobs if j.status == "in_progress"])
        return {"backend": "in-memory", "total": total, "queued": queued, "in_progress": in_progress}


class RedisQueue:
    """
    Redis-backed queue using RQ.
    """

    def __init__(self, redis_url: str) -> None:
        try:
            import redis  # type: ignore
            from rq import Queue  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("Redis/RQ not installed; install redis rq or omit DEKSDENFLOW_REDIS_URL") from exc
        self._redis = redis.Redis.from_url(redis_url)
        self._queue_cls = Queue
        self._queues: Dict[str, Queue] = {}

    def _get_queue(self, name: str):
        if name not in self._queues:
            self._queues[name] = self._queue_cls(name, connection=self._redis)
        return self._queues[name]

    def enqueue(self, job_type: str, payload: Dict[str, Any], queue: Optional[str] = None) -> Job:
        job = Job(
            job_id=str(uuid.uuid4()),
            job_type=job_type,
            payload=payload,
            queue=queue or "default",
        )
        q = self._get_queue(job.queue)
        # Jobs will be processed by scripts/rq_worker.py
        job.payload["job_id"] = job.job_id
        q.enqueue("deksdenflow.worker_runtime.rq_job_handler", job.job_type, job.payload)
        return job

    def claim(self, queue: Optional[str] = None) -> Optional[Job]:
        return None

    def list(self, status: Optional[str] = None) -> List[Job]:
        # Listing RQ jobs requires fetching from Redis; return empty for now.
        return []

    def requeue(self, job: Job, delay_seconds: float) -> None:
        q = self._get_queue(job.queue)
        q.enqueue_in(time.timedelta(seconds=delay_seconds), "deksdenflow.worker_runtime.rq_job_handler", job.job_type, job.payload)

    def stats(self) -> Dict[str, Any]:
        q = self._get_queue("default")
        return {
            "backend": "redis-rq",
            "queued": q.count,
        }


def create_queue(redis_url: Optional[str]) -> BaseQueue:
    if redis_url:
        try:
            return RedisQueue(redis_url)
        except RuntimeError:
            # Fall back to in-memory if redis dependency is missing
            return InMemoryQueue()
    return InMemoryQueue()
