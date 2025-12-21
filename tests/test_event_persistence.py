import tempfile
from pathlib import Path

import pytest


def test_event_persistence_sink_writes_db() -> None:
    from devgodzilla.db.database import SQLiteDatabase
    from devgodzilla.services.event_persistence import install_db_event_sink
    from devgodzilla.services.events import ProtocolStarted, get_event_bus

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
        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name="demo-proto",
            status="pending",
            base_branch="main",
            worktree_path=str(repo),
            protocol_root=str(repo),
        )

        install_db_event_sink(db_provider=lambda: db)
        get_event_bus().publish(
            ProtocolStarted(protocol_run_id=run.id, protocol_name=run.protocol_name, project_id=project.id)
        )

        events = db.list_recent_events(limit=10)
        assert events
        assert any(e.event_type == "protocol_started" for e in events)
        assert any(e.protocol_run_id == run.id for e in events)
