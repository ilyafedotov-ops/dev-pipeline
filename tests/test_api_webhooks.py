import os
import tempfile
from pathlib import Path

import pytest

try:
    from fastapi.testclient import TestClient  # type: ignore
    from deksdenflow.api.app import app
except ImportError:  # pragma: no cover
    TestClient = None  # type: ignore
    app = None  # type: ignore


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_github_webhook_updates_step_and_protocol() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["DEKSDENFLOW_DB_PATH"] = str(Path(tmpdir) / "db.sqlite")
        os.environ.pop("DEKSDENFLOW_API_TOKEN", None)

        with TestClient(app) as client:  # type: ignore[arg-type]
            proj = client.post(
                "/projects",
                json={"name": "demo", "git_url": "git@example.com/demo.git", "base_branch": "main"},
            ).json()
            run = client.post(
                f"/projects/{proj['id']}/protocols",
                json={"protocol_name": "0001-demo", "status": "running", "base_branch": "main"},
            ).json()
            step = client.post(
                f"/protocols/{run['id']}/steps",
                json={"step_index": 0, "step_name": "00-setup", "step_type": "setup"},
            ).json()

            payload = {"workflow_run": {"conclusion": "failure", "head_branch": "0001-demo"}, "action": "completed"}
            resp = client.post(
                "/webhooks/github",
                json=payload,
                headers={"X-GitHub-Event": "workflow_run"},
            )
            assert resp.status_code == 200

            step_after = client.get(f"/protocols/{run['id']}/steps").json()[0]
            assert step_after["status"] == "failed"

            events = client.get(f"/protocols/{run['id']}/events").json()
            assert any("GitHub webhook" in e["message"] for e in events)


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_gitlab_webhook_updates_step() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["DEKSDENFLOW_DB_PATH"] = str(Path(tmpdir) / "db.sqlite")
        os.environ.pop("DEKSDENFLOW_API_TOKEN", None)

        with TestClient(app) as client:  # type: ignore[arg-type]
            proj = client.post(
                "/projects",
                json={"name": "demo", "git_url": "git@example.com/demo.git", "base_branch": "main"},
            ).json()
            run = client.post(
                f"/projects/{proj['id']}/protocols",
                json={"protocol_name": "0002-demo", "status": "running", "base_branch": "main"},
            ).json()
            client.post(
                f"/protocols/{run['id']}/steps",
                json={"step_index": 1, "step_name": "01-work", "step_type": "work"},
            )

            payload = {"object_attributes": {"status": "success"}, "ref": "0002-demo"}
            resp = client.post(
                "/webhooks/gitlab",
                json=payload,
                headers={"X-Gitlab-Event": "Pipeline Hook"},
            )
            assert resp.status_code == 200
            step_after = client.get(f"/protocols/{run['id']}/steps").json()[0]
            assert step_after["status"] == "completed"


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_github_pr_merge_completes_protocol() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["DEKSDENFLOW_DB_PATH"] = str(Path(tmpdir) / "db.sqlite")
        os.environ.pop("DEKSDENFLOW_API_TOKEN", None)

        with TestClient(app) as client:  # type: ignore[arg-type]
            proj = client.post(
                "/projects",
                json={"name": "demo", "git_url": "git@example.com/demo.git", "base_branch": "main"},
            ).json()
            run = client.post(
                f"/projects/{proj['id']}/protocols",
                json={"protocol_name": "0003-demo", "status": "running", "base_branch": "main"},
            ).json()
            payload = {
                "action": "closed",
                "pull_request": {
                    "head": {"ref": "0003-demo", "sha": "abc123"},
                    "number": 7,
                    "state": "closed",
                    "merged": True,
                },
            }
            resp = client.post(
                "/webhooks/github",
                json=payload,
                headers={"X-GitHub-Event": "pull_request"},
            )
            assert resp.status_code == 200
            run_after = client.get(f"/protocols/{run['id']}").json()
            assert run_after["status"] == "completed"
            events = client.get(f"/protocols/{run['id']}/events").json()
            assert any(e["event_type"] == "pr_merged" for e in events)


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_gitlab_merge_request_updates_protocol() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["DEKSDENFLOW_DB_PATH"] = str(Path(tmpdir) / "db.sqlite")
        os.environ.pop("DEKSDENFLOW_API_TOKEN", None)

        with TestClient(app) as client:  # type: ignore[arg-type]
            proj = client.post(
                "/projects",
                json={"name": "demo", "git_url": "git@example.com/demo.git", "base_branch": "main"},
            ).json()
            run = client.post(
                f"/projects/{proj['id']}/protocols",
                json={"protocol_name": "0004-demo", "status": "running", "base_branch": "main"},
            ).json()
            payload = {
                "object_kind": "merge_request",
                "object_attributes": {
                    "state": "merged",
                    "source_branch": "0004-demo",
                    "iid": 11,
                },
            }
            resp = client.post(
                "/webhooks/gitlab",
                json=payload,
                headers={"X-Gitlab-Event": "Merge Request Hook"},
            )
            assert resp.status_code == 200
            run_after = client.get(f"/protocols/{run['id']}").json()
            assert run_after["status"] == "completed"
            events = client.get(f"/protocols/{run['id']}/events").json()
            assert any(e["event_type"] in ("merge_request", "mr_merged") for e in events)
