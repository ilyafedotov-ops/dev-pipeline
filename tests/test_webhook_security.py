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


def _setup_db(tmp: Path) -> Path:
    from devgodzilla.db.database import SQLiteDatabase

    db_path = tmp / "devgodzilla.sqlite"
    repo = tmp / "repo"
    repo.mkdir(parents=True, exist_ok=True)

    db = SQLiteDatabase(db_path)
    db.init_schema()
    db.create_project(
        name="demo",
        git_url=str(repo),
        base_branch="main",
        local_path=str(repo),
    )
    return db_path


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_github_webhook_requires_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = _setup_db(tmp)

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.setenv("DEVGODZILLA_WEBHOOK_TOKEN", "secret")
        monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)

        payload = {"action": "completed", "workflow_run": {"conclusion": "success"}}

        with TestClient(app) as client:  # type: ignore[arg-type]
            resp = client.post(
                "/webhooks/github",
                json=payload,
                headers={"X-Github-Event": "workflow_run"},
            )
            assert resp.status_code == 401


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_github_webhook_rejects_invalid_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = _setup_db(tmp)

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.setenv("DEVGODZILLA_WEBHOOK_TOKEN", "secret")
        monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)

        payload = {"action": "completed", "workflow_run": {"conclusion": "success"}}
        body = json.dumps(payload).encode("utf-8")

        with TestClient(app) as client:  # type: ignore[arg-type]
            resp = client.post(
                "/webhooks/github",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Github-Event": "workflow_run",
                    "X-Hub-Signature-256": "sha256=deadbeef",
                },
            )
            assert resp.status_code == 401


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_gitlab_webhook_token_required(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = _setup_db(tmp)

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.setenv("DEVGODZILLA_WEBHOOK_TOKEN", "secret")
        monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)

        payload = {"object_kind": "pipeline", "object_attributes": {"status": "success", "id": 1}}

        with TestClient(app) as client:  # type: ignore[arg-type]
            resp = client.post(
                "/webhooks/gitlab",
                json=payload,
                headers={"X-Gitlab-Token": "wrong"},
            )
            assert resp.status_code == 401


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_gitlab_webhook_accepts_valid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = _setup_db(tmp)

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))
        monkeypatch.setenv("DEVGODZILLA_WEBHOOK_TOKEN", "secret")
        monkeypatch.delenv("DEVGODZILLA_DB_URL", raising=False)

        payload = {
            "object_kind": "pipeline",
            "object_attributes": {"status": "success", "id": 1},
            "project": {"path_with_namespace": "demo/repo"},
        }

        with TestClient(app) as client:  # type: ignore[arg-type]
            resp = client.post(
                "/webhooks/gitlab",
                json=payload,
                headers={"X-Gitlab-Token": "secret"},
            )
            assert resp.status_code == 200
