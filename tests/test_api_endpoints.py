import os
import tempfile
from pathlib import Path

import pytest

try:
    from fastapi.testclient import TestClient  # type: ignore
    from deksdenflow.api.app import app
except ImportError:  # pragma: no cover - fastapi not installed in minimal envs
    TestClient = None  # type: ignore
    app = None  # type: ignore


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_api_projects_protocols_steps_end_to_end() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "api-test.sqlite"
        os.environ["DEKSDENFLOW_DB_PATH"] = str(db_path)
        os.environ.pop("DEKSDENFLOW_API_TOKEN", None)
        os.environ["DEKSDENFLOW_REDIS_URL"] = "fakeredis://"

        with TestClient(app) as client:  # type: ignore[arg-type]
            queue = client.app.state.queue  # type: ignore[attr-defined]
            db = client.app.state.db  # type: ignore[attr-defined]

            # Health
            resp = client.get("/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"

            # Create project
            proj = client.post(
                "/projects",
                json={
                    "name": "demo",
                    "git_url": "git@example.com/demo.git",
                    "base_branch": "main",
                    "ci_provider": "github",
                    "default_models": {"planning": "gpt-5.1-high"},
                },
            ).json()
            project_id = proj["id"]

            # Create protocol run
            run = client.post(
                f"/projects/{project_id}/protocols",
                json={
                    "protocol_name": "0001-demo",
                    "status": "planning",
                    "base_branch": "main",
                    "worktree_path": "/tmp/worktree",
                    "protocol_root": "/tmp/worktree/.protocols/0001-demo",
                    "description": "demo protocol",
                },
            ).json()
            protocol_run_id = run["id"]

            # Create step
            step = client.post(
                f"/protocols/{protocol_run_id}/steps",
                json={
                    "step_index": 0,
                    "step_name": "00-setup",
                    "step_type": "setup",
                    "status": "pending",
                },
            ).json()
            step_id = step["id"]

            # Trigger run action
            run_action = client.post(f"/steps/{step_id}/actions/run").json()
            assert run_action["job"]["job_type"] == "execute_step_job"

            # Background worker should mark it completed (stub). Allow a short window for queue drain.
            import time

            for _ in range(5):
                events = client.get(f"/protocols/{protocol_run_id}/events").json()
                if any(e["event_type"] == "step_completed" for e in events):
                    break
                time.sleep(0.2)
            else:
                assert False, "Expected step_completed event"

            # Approve step and list events
            client.post(f"/steps/{step_id}/actions/approve")
            events = client.get(f"/protocols/{protocol_run_id}/events").json()
            assert any(e["event_type"] == "manual_approval" for e in events)

            # Pause/resume/cancel protocol (skip if already terminal after approval)
            run_after = client.get(f"/protocols/{protocol_run_id}").json()
            terminal = run_after["status"] in ("completed", "cancelled", "failed")
            if not terminal:
                resp = client.post(f"/protocols/{protocol_run_id}/actions/pause")
                assert resp.status_code == 200
                assert resp.json()["status"] == "paused"
                resp = client.post(f"/protocols/{protocol_run_id}/actions/resume")
                assert resp.status_code == 200
                assert resp.json()["status"] == "running"
                resp = client.post(f"/protocols/{protocol_run_id}/actions/cancel")
                assert resp.status_code == 200
                assert resp.json()["status"] == "cancelled"

            ops = client.get("/events", params={"project_id": project_id}).json()
            assert any(o["protocol_run_id"] == protocol_run_id for o in ops)


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_protocol_spec_endpoint_exposes_hash_and_spec() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "api-test.sqlite"
        os.environ["DEKSDENFLOW_DB_PATH"] = str(db_path)
        os.environ.pop("DEKSDENFLOW_API_TOKEN", None)
        os.environ["DEKSDENFLOW_REDIS_URL"] = "fakeredis://"

        with TestClient(app) as client:  # type: ignore[arg-type]
            project = client.post(
                "/projects",
                json={"name": "demo", "git_url": "/tmp/demo.git", "base_branch": "main"},
            ).json()
            spec = {"steps": [{"id": "00-step", "name": "00-step.md", "engine_id": "codex", "prompt_ref": "00-step.md", "qa": {"policy": "skip"}}]}
            run = client.post(
                f"/projects/{project['id']}/protocols",
                json={
                    "protocol_name": "0001-spec",
                    "status": "planned",
                    "base_branch": "main",
                    "worktree_path": "/tmp/work",
                    "protocol_root": "/tmp/work/.protocols/0001-spec",
                    "description": "spec",
                    "template_config": {"protocol_spec": spec},
                },
            ).json()

            resp = client.get(f"/protocols/{run['id']}/spec")
            assert resp.status_code == 200
            body = resp.json()
            assert body["spec"] == spec
            assert body["spec_hash"]
            assert body["validation_status"] in (None, "valid")
