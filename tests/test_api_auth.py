import os
import tempfile
from pathlib import Path

import pytest

try:
    from fastapi.testclient import TestClient  # type: ignore
    from tasksgodzilla.api.app import app
except ImportError:  # pragma: no cover - fastapi not installed in minimal envs
    TestClient = None  # type: ignore
    app = None  # type: ignore


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_auth_rejects_missing_token_when_enabled() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "api-auth.sqlite"
        os.environ["TASKSGODZILLA_DB_PATH"] = str(db_path)
        os.environ["TASKSGODZILLA_API_TOKEN"] = "secret-token"
        os.environ["TASKSGODZILLA_REDIS_URL"] = "fakeredis://"

        with TestClient(app) as client:  # type: ignore[arg-type]
            resp = client.get("/projects")
            assert resp.status_code == 401

            resp = client.get("/projects", headers={"Authorization": "Bearer secret-token"})
            assert resp.status_code in (200, 204, 404)  # list may be empty, but auth should pass
