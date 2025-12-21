import hashlib
import hmac
import json
import tempfile
from pathlib import Path

import pytest

try:
    from fastapi.testclient import TestClient  # type: ignore
    from devgodzilla.api.app import app
except ImportError:  # pragma: no cover
    TestClient = None  # type: ignore
    app = None  # type: ignore


def _sign_github(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _setup_db(tmp: Path):
    from devgodzilla.db.database import SQLiteDatabase

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
    run = db.create_protocol_run(
        project_id=project.id,
        protocol_name="demo-proto",
        status="running",
        base_branch="main",
        worktree_path=str(repo),
        protocol_root=str(repo),
    )
    return db, project, run, db_path


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_windmill_flow_webhook_completes_protocol(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db, project, run, db_path = _setup_db(tmp)

        db.create_step_run(
            protocol_run_id=run.id,
            step_index=0,
            step_name="Step 1",
            step_type="exec",
            status="completed",
        )
        db.create_step_run(
            protocol_run_id=run.id,
            step_index=1,
            step_name="Step 2",
            step_type="exec",
            status="completed",
        )
        flow_id = f"f/devgodzilla/protocol-{run.id}"
        db.update_protocol_windmill(run.id, windmill_flow_id=flow_id)

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.setenv("DEVGODZILLA_WEBHOOK_TOKEN", "secret")
        monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)

        payload = {
            "status": "success",
            "flow_path": flow_id,
            "input": {"protocol_run_id": run.id},
        }

        with TestClient(app) as client:  # type: ignore[arg-type]
            resp = client.post(
                "/webhooks/windmill/flow",
                json=payload,
                headers={"X-DevGodzilla-Webhook-Token": "secret"},
            )
            assert resp.status_code == 200

        updated = db.get_protocol_run(run.id)
        assert updated.status == "completed"


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_github_workflow_failure_blocks_protocol(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db, project, run, db_path = _setup_db(tmp)

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.setenv("DEVGODZILLA_WEBHOOK_TOKEN", "secret")
        monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)

        payload = {
            "action": "completed",
            "workflow_run": {
                "conclusion": "failure",
                "name": "CI",
                "id": 123,
            },
            "repository": {"full_name": "demo/repo"},
        }
        body = json.dumps(payload).encode("utf-8")
        signature = _sign_github("secret", body)

        with TestClient(app) as client:  # type: ignore[arg-type]
            resp = client.post(
                f"/webhooks/github?project_id={project.id}&protocol_run_id={run.id}",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Github-Event": "workflow_run",
                    "X-Hub-Signature-256": signature,
                },
            )
            assert resp.status_code == 200

        updated = db.get_protocol_run(run.id)
        assert updated.status == "blocked"
