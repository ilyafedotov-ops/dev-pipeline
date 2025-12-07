import pytest

from tasksgodzilla.jobs import RedisQueue, create_queue


def test_job_queue_enqueue_and_list_with_fakeredis() -> None:
    queue = RedisQueue("fakeredis://")
    job = queue.enqueue("demo_job", {"value": 1})
    assert job.job_type == "demo_job"
    stats = queue.stats()
    assert stats["default"]["queued"] >= 1


def test_create_queue_without_redis_errors() -> None:
    with pytest.raises(RuntimeError):
        create_queue(None)


def test_claim_returns_enqueued_job_with_fakeredis() -> None:
    queue = RedisQueue("fakeredis://")
    queue.redis_connection.flushdb()
    job = queue.enqueue("demo_job", {"value": 2})
    claimed = queue.claim()
    assert claimed is not None
    assert claimed.job_type == "demo_job"
    assert claimed.payload["value"] == 2
