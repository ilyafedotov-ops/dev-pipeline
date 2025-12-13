import os
import sys
from pathlib import Path

import pytest
import redis  # type: ignore

# Ensure repository root is on sys.path so in-tree packages and demo modules import cleanly.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def redis_url() -> str:
    url = os.environ.get("TASKSGODZILLA_REDIS_URL", "redis://localhost:6380/15")
    client = redis.Redis.from_url(url)
    try:
        client.ping()
    except Exception as exc:  # pragma: no cover - external service requirement
        pytest.fail(f"Redis not available at {url}: {exc}")
    client.flushdb()
    yield url
    try:
        client.flushdb()
    except Exception:
        pass


@pytest.fixture
def redis_env(monkeypatch: pytest.MonkeyPatch, redis_url: str) -> str:
    monkeypatch.setenv("TASKSGODZILLA_REDIS_URL", redis_url)
    client = redis.Redis.from_url(redis_url)
    client.flushdb()
    yield redis_url
    try:
        client.flushdb()
    except Exception:
        pass


@pytest.fixture
def redis_inline_worker_env(redis_env: str, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("TASKSGODZILLA_INLINE_RQ_WORKER", "true")
    return redis_env
