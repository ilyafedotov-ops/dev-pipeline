import os
import subprocess
import tempfile
from pathlib import Path

import pytest

try:
    from fastapi.testclient import TestClient  # type: ignore
    from devgodzilla.api.app import app
except ImportError:  # pragma: no cover
    TestClient = None  # type: ignore
    app = None  # type: ignore


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True)
    (path / "README.md").write_text("demo", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=path,
        check=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "tester",
            "GIT_AUTHOR_EMAIL": "tester@example.com",
            "GIT_COMMITTER_NAME": "tester",
            "GIT_COMMITTER_EMAIL": "tester@example.com",
        },
    )


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_step_artifacts_list_and_content(monkeypatch: pytest.MonkeyPatch) -> None:
    from devgodzilla.db.database import SQLiteDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db_path = tmp / "devgodzilla.sqlite"
        repo = tmp / "repo"
        _init_repo(repo)

        monkeypatch.setenv("DEVGODZILLA_DB_PATH", str(db_path))

        db = SQLiteDatabase(db_path)
        db.init_schema()

        project = db.create_project(
            name="demo",
            git_url=str(repo),
            base_branch="main",
            local_path=str(repo),
        )

        protocol_root = repo / "specs" / "demo-proto"
        protocol_root.mkdir(parents=True, exist_ok=True)

        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="demo-proto",
            status="pending",
            base_branch="main",
            worktree_path=str(repo),
            protocol_root=str(protocol_root),
        )

        step = db.create_step_run(
            protocol_run_id=run.id,
            step_index=1,
            step_name="01-demo",
            step_type="exec",
            status="pending",
        )

        artifacts_dir = protocol_root / ".devgodzilla" / "steps" / str(step.id) / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        (artifacts_dir / "execution.log").write_text("hello from log\n", encoding="utf-8")
        (artifacts_dir / "changes.diff").write_text("diff --git a/README.md b/README.md\n", encoding="utf-8")

        with TestClient(app) as client:  # type: ignore[arg-type]
            listed = client.get(f"/steps/{step.id}/artifacts")
            assert listed.status_code == 200
            artifacts = listed.json()
            assert any(a["name"] == "execution.log" for a in artifacts)
            assert any(a["name"] == "changes.diff" for a in artifacts)

            content = client.get(f"/steps/{step.id}/artifacts/execution.log/content")
            assert content.status_code == 200
            data = content.json()
            assert "hello from log" in data["content"]
            assert data["truncated"] is False

            download = client.get(f"/steps/{step.id}/artifacts/execution.log/download")
            assert download.status_code == 200
            assert b"hello from log" in download.content
