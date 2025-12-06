from pathlib import Path

from deksdenflow.domain import ProtocolStatus
from deksdenflow.spec import PROTOCOL_SPEC_KEY
from deksdenflow.storage import Database
from deksdenflow.workers import spec_worker


def _make_workspace(tmp_path: Path, run_name: str) -> tuple[Path, Path]:
    workspace = tmp_path / "workspace"
    protocol_root = workspace / ".protocols" / run_name
    protocol_root.mkdir(parents=True, exist_ok=True)
    (protocol_root / "plan.md").write_text("plan", encoding="utf-8")
    (protocol_root / "context.md").write_text("context", encoding="utf-8")
    (protocol_root / "log.md").write_text("", encoding="utf-8")
    (protocol_root / "00-step.md").write_text("step content", encoding="utf-8")
    return workspace, protocol_root


def test_spec_audit_job_backfills_and_emits_event(tmp_path) -> None:
    workspace, protocol_root = _make_workspace(tmp_path, "8001-demo")
    db = Database(tmp_path / "db.sqlite")
    db.init_schema()

    project = db.create_project("demo", str(workspace), "main", None, None)
    run = db.create_protocol_run(project.id, "8001-demo", ProtocolStatus.PLANNED, "main", str(workspace), str(protocol_root), "demo protocol")

    results = spec_worker.handle_spec_audit_job({"project_id": project.id, "backfill_missing": True}, db)
    assert results
    run_after = db.get_protocol_run(run.id)
    spec = (run_after.template_config or {}).get(PROTOCOL_SPEC_KEY)
    assert spec
    events = db.list_events(run.id)
    audit_events = [e for e in events if e.event_type == "spec_audit"]
    assert audit_events
    meta = audit_events[0].metadata or {}
    assert meta.get("backfilled") is True
    assert meta.get("errors") == []
