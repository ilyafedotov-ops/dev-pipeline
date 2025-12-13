import tempfile
from pathlib import Path

import pytest

try:
    from fastapi.testclient import TestClient  # type: ignore
    from tasksgodzilla.api.app import app
except ImportError:  # pragma: no cover
    TestClient = None  # type: ignore
    app = None  # type: ignore


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_log_tail_endpoint_reads_incrementally(redis_env: str, monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "logs-tail.sqlite"
        log_path = Path(tmpdir) / "run.log"
        log_path.write_text("hello\n", encoding="utf-8")

        monkeypatch.setenv("TASKSGODZILLA_DB_PATH", str(db_path))

        with TestClient(app) as client:  # type: ignore[arg-type]
            # Create run record pointing at the temp log file.
            resp = client.post(
                "/codex/runs/start",
                json={
                    "job_type": "execute_step_job",
                    "run_id": "run-1",
                    "status": "running",
                    "log_path": str(log_path),
                },
            )
            assert resp.status_code == 200, resp.text

            resp = client.get("/codex/runs/run-1/logs/tail?offset=0&max_bytes=1024")
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["chunk"].startswith("hello\n")
            next_offset = data["next_offset"]
            assert next_offset >= len("hello\n")

            # Append and read again from previous offset.
            log_path.write_text("hello\nworld\n", encoding="utf-8")
            resp = client.get(f"/codex/runs/run-1/logs/tail?offset={next_offset}&max_bytes=1024")
            assert resp.status_code == 200, resp.text
            data2 = resp.json()
            assert "world\n" in data2["chunk"]

