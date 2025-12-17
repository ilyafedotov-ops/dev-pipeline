import tempfile
from pathlib import Path

import pytest

try:
    from fastapi.testclient import TestClient  # type: ignore
    from tasksgodzilla.api.app import app
    import importlib
except ImportError:  # pragma: no cover
    TestClient = None  # type: ignore
    app = None  # type: ignore
    importlib = None  # type: ignore


class FakeWindmillClient:
    def __init__(self, logs: str, result: dict | None = None, error: object | None = None) -> None:
        self._logs = logs
        self._result = result or {}
        self._error = error

    def get_job_logs(self, job_id: str) -> str:
        return self._logs

    def get_job(self, job_id: str) -> dict:
        return {"result": self._result, "error": self._error}

class DummyQueue:
    def stats(self) -> dict:
        return {}

    def list(self, status: str | None = None) -> list:
        return []


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_codex_logs_tail_supports_windmill_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "windmill-logs.sqlite"
        monkeypatch.setenv("TASKSGODZILLA_DB_PATH", str(db_path))
        api_app_module = importlib.import_module("tasksgodzilla.api.app")  # type: ignore[union-attr]
        monkeypatch.setattr(api_app_module.jobs, "create_queue", lambda redis_url: DummyQueue())

        with TestClient(app) as client:  # type: ignore[arg-type]
            client.app.state.windmill = FakeWindmillClient("hello\nworld\n")  # type: ignore[attr-defined]

            resp = client.post(
                "/codex/runs/start",
                json={
                    "job_type": "windmill",
                    "run_id": "wm-1",
                    "log_path": "windmill://job/job-123/logs",
                },
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["log_path"].startswith("windmill://job/job-123")

            resp = client.get("/codex/runs/wm-1/logs/tail?offset=0&max_bytes=1024")
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["chunk"] == "hello\nworld\n"
            assert data["eof"] is True


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_run_artifact_content_supports_windmill_result_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "windmill-artifacts.sqlite"
        monkeypatch.setenv("TASKSGODZILLA_DB_PATH", str(db_path))
        api_app_module = importlib.import_module("tasksgodzilla.api.app")  # type: ignore[union-attr]
        monkeypatch.setattr(api_app_module.jobs, "create_queue", lambda redis_url: DummyQueue())

        with TestClient(app) as client:  # type: ignore[arg-type]
            client.app.state.windmill = FakeWindmillClient("", result={"ok": True})  # type: ignore[attr-defined]

            resp = client.post(
                "/codex/runs/start",
                json={
                    "job_type": "windmill",
                    "run_id": "wm-2",
                    "log_path": "windmill://job/job-456/logs",
                },
            )
            assert resp.status_code == 200, resp.text

            # Insert a Windmill-backed artifact reference directly.
            db = client.app.state.db  # type: ignore[attr-defined]
            artifact = db.upsert_run_artifact(
                "wm-2",
                "result.json",
                kind="result",
                path="windmill://job/job-456/result",
                sha256=None,
                bytes=None,
            )

            resp = client.get(f"/codex/runs/wm-2/artifacts/{artifact.id}/content")
            assert resp.status_code == 200, resp.text
            assert '"ok": true' in resp.text
