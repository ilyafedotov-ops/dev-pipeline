from pathlib import Path

from deksdenflow.domain import ProtocolStatus
from deksdenflow.spec import PROTOCOL_SPEC_KEY, protocol_spec_hash
from deksdenflow.spec_tools import audit_specs
from deksdenflow.storage import Database


def _make_workspace(tmp_path: Path, run_name: str) -> tuple[Path, Path]:
    workspace = tmp_path / "workspace"
    protocol_root = workspace / ".protocols" / run_name
    protocol_root.mkdir(parents=True, exist_ok=True)
    (protocol_root / "plan.md").write_text("plan", encoding="utf-8")
    (protocol_root / "context.md").write_text("context", encoding="utf-8")
    (protocol_root / "log.md").write_text("", encoding="utf-8")
    (protocol_root / "00-step.md").write_text("step content", encoding="utf-8")
    return workspace, protocol_root


def test_audit_specs_backfills_missing_spec(tmp_path) -> None:
    workspace, protocol_root = _make_workspace(tmp_path, "7001-demo")
    db = Database(tmp_path / "db.sqlite")
    db.init_schema()

    project = db.create_project("demo", str(workspace), "main", None, None)
    run = db.create_protocol_run(project.id, "7001-demo", ProtocolStatus.PLANNED, "main", str(workspace), str(protocol_root), "demo protocol")

    results = audit_specs(db, project_id=project.id, backfill_missing=True)
    assert results
    result = results[0]
    assert result["backfilled"] is True
    assert result["errors"] == []
    run_after = db.get_protocol_run(run.id)
    spec = run_after.template_config.get(PROTOCOL_SPEC_KEY)
    assert spec
    assert result["spec_hash"] == protocol_spec_hash(spec)


def test_audit_specs_reports_missing_without_backfill(tmp_path) -> None:
    workspace, protocol_root = _make_workspace(tmp_path, "7002-demo")
    db = Database(tmp_path / "db.sqlite")
    db.init_schema()

    project = db.create_project("demo", str(workspace), "main", None, None)
    db.create_protocol_run(project.id, "7002-demo", ProtocolStatus.PLANNED, "main", str(workspace), str(protocol_root), "demo protocol")

    results = audit_specs(db, project_id=project.id, backfill_missing=False)
    assert results
    result = results[0]
    assert result["backfilled"] is False
    assert any("missing" in err for err in result["errors"])
