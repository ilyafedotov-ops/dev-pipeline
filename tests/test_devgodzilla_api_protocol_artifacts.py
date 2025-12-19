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
def test_protocol_artifacts_aggregate(monkeypatch: pytest.MonkeyPatch) -> None:
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

        step1 = db.create_step_run(
            protocol_run_id=run.id,
            step_index=1,
            step_name="01-demo",
            step_type="exec",
            status="pending",
        )
        step2 = db.create_step_run(
            protocol_run_id=run.id,
            step_index=2,
            step_name="02-demo",
            step_type="exec",
            status="pending",
        )

        a1 = protocol_root / ".devgodzilla" / "steps" / str(step1.id) / "artifacts"
        a2 = protocol_root / ".devgodzilla" / "steps" / str(step2.id) / "artifacts"
        a1.mkdir(parents=True, exist_ok=True)
        a2.mkdir(parents=True, exist_ok=True)
        (a1 / "execution.log").write_text("s1\n", encoding="utf-8")
        (a2 / "quality-report.md").write_text("# report\n", encoding="utf-8")

        with TestClient(app) as client:  # type: ignore[arg-type]
            resp = client.get(f"/protocols/{run.id}/artifacts")
            assert resp.status_code == 200
            items = resp.json()
            assert any(i["step_run_id"] == step1.id and i["name"] == "execution.log" for i in items)
            assert any(i["step_run_id"] == step2.id and i["name"] == "quality-report.md" for i in items)
