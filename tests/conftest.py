import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure repository root is on sys.path so in-tree packages and demo modules import cleanly.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Hypothesis configuration – cap example count to prevent timeouts
# ---------------------------------------------------------------------------
os.environ.setdefault("HYPOTHESIS_MAX_EXAMPLES", "10")

try:
    from hypothesis import HealthCheck, settings

    settings.register_profile(
        "ci",
        max_examples=10,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    # Use the CI profile by default so every run is fast and deterministic.
    settings.load_profile("ci")
except Exception:  # pragma: no cover – hypothesis not installed
    pass

# ---------------------------------------------------------------------------
# Auto-use environment fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _default_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set sensible defaults for all tests so no real infra is required."""
    # Prevent .env-provided Postgres URLs from leaking into SQLite-based tests.
    monkeypatch.setenv("DEVGODZILLA_DB_URL", "")
    # Default database path for tests that use file-based SQLite.
    monkeypatch.setenv("DEVGODZILLA_DATABASE_URL", "")
    # Redis – point at a non-existent instance so tests fail fast if they
    # accidentally try to connect instead of using the mock.
    monkeypatch.setenv("DEVGODZILLA_REDIS_URL", "redis://localhost:0/0")
    # Skip agent auth in tests.
    monkeypatch.setenv("DEVGODZILLA_ASSUME_AGENT_AUTH", "1")


# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def temp_db(tmp_path: Path):
    """Create a temporary SQLite database with the real DevGodzilla schema.

    Yields the ``SQLiteDatabase`` instance.  The underlying file lives in a
    temporary directory that is automatically cleaned up by pytest.
    """
    from devgodzilla.db.database import SQLiteDatabase

    db = SQLiteDatabase(tmp_path / "test_devgodzilla.db")
    db.init_schema()
    yield db


@pytest.fixture()
def db_session(temp_db):
    """Provide the ``Database``-protocol instance (temp SQLite) for direct use.

    This is the same object yielded by :pyfunc:`temp_db` but presented under a
    name that conveys "session-like" semantics – callers can create, query and
    mutate records through it, and the database is torn down when the test
    finishes.
    """
    return temp_db


@pytest.fixture()
def test_client(db_session, monkeypatch: pytest.MonkeyPatch):
    """Create a ``FastAPI`` ``TestClient`` with DB dependency overridden.

    The ``get_db`` dependency is patched to return the temporary SQLite
    database so API tests hit an isolated DB.  API token auth is disabled
    for the duration of the test.
    """
    from devgodzilla.api.app import app
    from devgodzilla.api.dependencies import get_db as api_get_db

    try:
        from fastapi.testclient import TestClient  # type: ignore
    except Exception:  # pragma: no cover – fastapi missing
        pytest.skip("fastapi not installed")

    monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

    app.dependency_overrides[api_get_db] = lambda: db_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(api_get_db, None)


@pytest.fixture()
def seeded_project(db_session):
    """Create and return a test project in the database."""
    return db_session.create_project(
        name="Test Project",
        git_url="https://github.com/example/test-repo.git",
        base_branch="main",
        ci_provider="github",
    )


@pytest.fixture()
def seeded_protocol(db_session, seeded_project):
    """Create a test protocol run linked to ``seeded_project``."""
    return db_session.create_protocol_run(
        project_id=seeded_project.id,
        protocol_name="test-protocol",
        status="pending",
        base_branch="main",
    )


@pytest.fixture()
def mock_windmill():
    """Return a ``MagicMock`` configured with typical Windmill response patterns."""
    from devgodzilla.windmill.client import JobStatus

    wm = MagicMock()

    # Default: get_job returns a completed job
    wm.get_job.return_value = MagicMock(
        id="wm-job-001",
        status=JobStatus.COMPLETED,
        created_at="2025-01-01T00:00:00Z",
        started_at="2025-01-01T00:00:01Z",
        completed_at="2025-01-01T00:00:10Z",
        result={"success": True, "output": "done"},
        error=None,
    )

    # Default: run_script returns a job id
    wm.run_script.return_value = "wm-job-001"

    # Default: list_flows returns an empty list
    wm.list_flows.return_value = []

    # Default: run_flow returns a job id
    wm.run_flow.return_value = "wm-flow-job-001"

    return wm


@pytest.fixture()
def sample_repo_url() -> str:
    """Return a test git repository URL."""
    return "https://github.com/example/test-repo.git"


@pytest.fixture()
def fake_agent_response() -> dict:
    """Return a realistic agent execution response dict."""
    return {
        "success": True,
        "output": (
            "Created file: src/feature.py\n"
            "Updated file: tests/test_feature.py\n"
            "All tests passed.\n"
            "Task completed successfully."
        ),
        "files_changed": [
            {"path": "src/feature.py", "action": "created"},
            {"path": "tests/test_feature.py", "action": "modified"},
        ],
        "metrics": {
            "tokens_used": 4200,
            "duration_seconds": 12.5,
            "model": "zai-coding-plan/glm-4.6",
        },
        "exit_code": 0,
    }


@pytest.fixture()
def mock_redis():
    """Return a ``MagicMock`` that behaves like a ``redis.Redis`` instance.

    Common operations (get, set, delete, exists, keys, lpush, rpush,
    lrange, publish, ping) are pre-configured with sensible defaults.
    """
    r = MagicMock()
    r.ping.return_value = True
    r.get.return_value = None
    r.set.return_value = True
    r.delete.return_value = 0
    r.exists.return_value = 0
    r.keys.return_value = []
    r.lpush.return_value = 1
    r.rpush.return_value = 1
    r.lrange.return_value = []
    r.publish.return_value = 0
    r.incr.return_value = 1
    r.expire.return_value = True
    return r


@pytest.fixture()
def mock_db():
    """Return a ``MagicMock`` standing in for the Database protocol.

    Useful for unit tests that don't need a real SQLite backend.
    """
    db = MagicMock()
    db.get_project.return_value = None
    db.list_projects.return_value = []
    db.create_project.return_value = MagicMock(id=1, name="mock-project")
    db.get_protocol_run.return_value = None
    db.list_protocol_runs.return_value = []
    db.create_protocol_run.return_value = MagicMock(id=1, protocol_name="mock-protocol")
    return db
