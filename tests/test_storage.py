import tempfile
from pathlib import Path

from tasksgodzilla.domain import ProtocolStatus, StepStatus
from tasksgodzilla.storage import Database


def test_storage_round_trip_creates_records() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "orchestrator.sqlite"
        db = Database(db_path)
        db.init_schema()

        project = db.create_project(
            name="demo",
            git_url="git@example.com/demo.git",
            base_branch="main",
            ci_provider="github",
            default_models={"planning": "gpt-5.1-high"},
        )
        assert project.id > 0

        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="0001-demo",
            status=ProtocolStatus.PLANNING,
            base_branch="main",
            worktree_path="/tmp/worktree",
            protocol_root="/tmp/worktree/.protocols/0001-demo",
            description="demo run",
        )
        assert run.id > 0
        assert run.template_config is None
        assert run.template_source is None

        step = db.create_step_run(
            protocol_run_id=run.id,
            step_index=0,
            step_name="00-setup",
            step_type="setup",
            status=StepStatus.PENDING,
            model=None,
        )
        assert step.id > 0
        assert step.engine_id is None
        assert step.policy is None
        assert step.runtime_state is None

        db.append_event(
            protocol_run_id=run.id,
            step_run_id=step.id,
            event_type="note",
            message="created",
        )

        # Verify readbacks
        projects = db.list_projects()
        assert len(projects) == 1
        runs = db.list_protocol_runs(project.id)
        assert len(runs) == 1
        steps = db.list_step_runs(run.id)
        assert len(steps) == 1
        events = db.list_events(run.id)
        assert len(events) == 1
        recent = db.list_recent_events()
        assert len(recent) == 1
        assert recent[0].protocol_name == "0001-demo"
        assert recent[0].project_name == "demo"
