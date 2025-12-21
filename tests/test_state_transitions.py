import tempfile
from pathlib import Path

import pytest


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
    return db, project, repo


def _get_context():
    from devgodzilla.config import load_config
    from devgodzilla.services.base import ServiceContext

    return ServiceContext(config=load_config())


def test_protocol_completes_when_all_steps_terminal() -> None:
    from devgodzilla.services.orchestrator import OrchestratorMode, OrchestratorService

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db, project, repo = _setup_db(tmp)

        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="done",
            status="running",
            base_branch="main",
            worktree_path=str(repo),
            protocol_root=str(repo),
        )
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

        orchestrator = OrchestratorService(
            context=_get_context(),
            db=db,
            mode=OrchestratorMode.LOCAL,
        )
        assert orchestrator.check_and_complete_protocol(run.id) is True

        updated = db.get_protocol_run(run.id)
        assert updated.status == "completed"


def test_protocol_fails_when_any_step_failed() -> None:
    from devgodzilla.services.orchestrator import OrchestratorMode, OrchestratorService

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        db, project, repo = _setup_db(tmp)

        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="failed",
            status="running",
            base_branch="main",
            worktree_path=str(repo),
            protocol_root=str(repo),
        )
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
            status="failed",
        )

        orchestrator = OrchestratorService(
            context=_get_context(),
            db=db,
            mode=OrchestratorMode.LOCAL,
        )
        assert orchestrator.check_and_complete_protocol(run.id) is True

        updated = db.get_protocol_run(run.id)
        assert updated.status == "failed"
