import importlib
import tempfile
from pathlib import Path

import pytest

try:
    from fastapi.testclient import TestClient  # type: ignore
    from tasksgodzilla.api.app import app
except ImportError:  # pragma: no cover
    TestClient = None  # type: ignore
    app = None  # type: ignore


class DummyQueue:
    def stats(self) -> dict:
        return {}

    def list(self, status: str | None = None) -> list:
        return []


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_run_artifact_upsert_endpoint_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    api_app_module = importlib.import_module("tasksgodzilla.api.app")
    monkeypatch.setattr(api_app_module.jobs, "create_queue", lambda redis_url: DummyQueue())

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "artifacts-upsert.sqlite"
        log_path = Path(tmpdir) / "run.log"
        log_path.write_text("hello\n", encoding="utf-8")
        monkeypatch.setenv("TASKSGODZILLA_DB_PATH", str(db_path))

        with TestClient(app) as client:  # type: ignore[arg-type]
            resp = client.post(
                "/codex/runs/start",
                json={
                    "job_type": "windmill",
                    "run_id": "run-xyz",
                    "log_path": str(log_path),
                },
            )
            assert resp.status_code == 200, resp.text

            resp = client.post(
                "/codex/runs/run-xyz/artifacts/upsert",
                json={
                    "name": "windmill.result",
                    "kind": "result",
                    "path": "windmill://job/job-123/result",
                },
            )
            assert resp.status_code == 200, resp.text
            artifact = resp.json()
            assert artifact["run_id"] == "run-xyz"
            assert artifact["path"].startswith("windmill://job/")

            listed = client.get("/codex/runs/run-xyz/artifacts")
            assert listed.status_code == 200, listed.text
            items = listed.json()
            assert any(i["id"] == artifact["id"] for i in items)

