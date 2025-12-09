from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from tasksgodzilla.jobs import BaseQueue, Job, RedisQueue


@dataclass
class QueueService:
    """Service for job queue management and task enqueueing.
    
    This service provides a high-level interface for enqueueing background jobs
    to the task queue (Redis/RQ).
    
    Responsibilities:
    - Enqueue protocol planning jobs
    - Enqueue step execution jobs
    - Enqueue QA jobs
    - Enqueue project setup jobs
    - Enqueue PR/MR creation jobs
    - Provide factory methods for queue construction
    
    Job Types:
    - plan_protocol_job: Plan a protocol run
    - execute_step_job: Execute a protocol step
    - run_quality_job: Run QA for a step
    - project_setup_job: Set up a new project
    - open_pr_job: Open PR/MR for a protocol
    
    Queue Backend:
    - Uses Redis/RQ for distributed job processing
    - Supports inline execution when Redis unavailable (dev mode)
    
    Usage:
        # Create from Redis URL
        queue_service = QueueService.from_redis_url(
            "redis://localhost:6379/0"
        )
        
        # Enqueue jobs
        job = queue_service.enqueue_plan_protocol(protocol_run_id=123)
        job = queue_service.enqueue_execute_step(step_run_id=456)
        job = queue_service.enqueue_run_quality(step_run_id=456)
    """

    queue: BaseQueue

    @classmethod
    def from_redis_url(cls, redis_url: str) -> "QueueService":
        """Construct a QueueService backed by a Redis/RQ queue."""
        return cls(queue=RedisQueue(redis_url))

    def enqueue_plan_protocol(self, protocol_run_id: int) -> Job:
        return self.queue.enqueue("plan_protocol_job", {"protocol_run_id": protocol_run_id})

    def enqueue_execute_step(self, step_run_id: int) -> Job:
        return self.queue.enqueue("execute_step_job", {"step_run_id": step_run_id})

    def enqueue_run_quality(self, step_run_id: int) -> Job:
        return self.queue.enqueue("run_quality_job", {"step_run_id": step_run_id})

    def enqueue_project_setup(self, project_id: int, protocol_run_id: Optional[int] = None) -> Job:
        payload = {"project_id": project_id}
        if protocol_run_id is not None:
            payload["protocol_run_id"] = protocol_run_id
        return self.queue.enqueue("project_setup_job", payload)

    def enqueue_open_pr(self, protocol_run_id: int) -> Job:
        return self.queue.enqueue("open_pr_job", {"protocol_run_id": protocol_run_id})

