import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

try:
    from fastapi.testclient import TestClient  # type: ignore
    from devgodzilla.api.app import app
except ImportError:  # pragma: no cover
    TestClient = None  # type: ignore
    app = None  # type: ignore


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_metrics_summary_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        repo.mkdir(parents=True, exist_ok=True)

        db = SQLiteDatabase(db_path)
        db.init_schema()

        project = db.create_project(
            name="demo",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
        )
        archived = db.create_project(
            name="archived",
            git_url=str(repo / "archived"),
            base_branch="main",
            local_path=str(repo),
        )
        db.update_project(archived.id, status="archived")

        run_ok = db.create_protocol_run(
            project_id=project.id,
            protocol_name="ok",
            status="completed",
            base_branch="main",
            worktree_path=str(repo),
            protocol_root=str(repo),
        )
        run_fail = db.create_protocol_run(
            project_id=project.id,
            protocol_name="fail",
            status="failed",
            base_branch="main",
            worktree_path=str(repo),
            protocol_root=str(repo),
        )

        db.create_step_run(
            protocol_run_id=run_ok.id,
            step_index=0,
            step_name="Step 1",
            step_type="exec",
            status="completed",
        )
        db.create_step_run(
            protocol_run_id=run_ok.id,
            step_index=1,
            step_name="Step 2",
            step_type="exec",
            status="completed",
        )
        db.create_step_run(
            protocol_run_id=run_fail.id,
            step_index=0,
            step_name="Step A",
            step_type="exec",
            status="failed",
        )

        job1 = db.create_job_run(
            run_id="job-1",
            job_type="plan",
            status="succeeded",
            project_id=project.id,
            protocol_run_id=run_ok.id,
        )
        job2 = db.create_job_run(
            run_id="job-2",
            job_type="execute",
            status="failed",
            project_id=project.id,
            protocol_run_id=run_fail.id,
        )

        start = datetime.now(timezone.utc)
        end = start + timedelta(seconds=10)
        db.update_job_run(job1.run_id, started_at=start.isoformat(), finished_at=end.isoformat())
        db.update_job_run(job2.run_id, started_at=start.isoformat(), finished_at=end.isoformat())

        db.append_event(
            protocol_run_id=run_ok.id,
            event_type="protocol_started",
            message="started",
            project_id=project.id,
        )

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.delenv("DEVGODZILLA_API_TOKEN", raising=False)

        with TestClient(app) as client:  # type: ignore[arg-type]
            resp = client.get("/metrics/summary")
            assert resp.status_code == 200
            payload = resp.json()

        assert payload["active_projects"] == 1
        assert payload["total_protocol_runs"] == 2
        assert payload["total_step_runs"] == 3
        assert payload["total_job_runs"] == 2
        assert payload["success_rate"] == 50.0
        assert payload["recent_events_count"] == 1

        job_types = {m["job_type"]: m["count"] for m in payload["job_type_metrics"]}
        assert job_types["plan"] == 1
        assert job_types["execute"] == 1
