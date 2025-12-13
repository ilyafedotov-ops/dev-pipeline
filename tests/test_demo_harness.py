from pathlib import Path
import shutil

from tasksgodzilla.domain import ProtocolStatus, StepStatus
from tasksgodzilla.storage import Database
from tasksgodzilla.workers import codex_worker, onboarding_worker, spec_worker


def _seed_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "demo-repo"
    workspace.mkdir(parents=True, exist_ok=True)
    bootstrap = Path(__file__).resolve().parents[1] / "demo_bootstrap"
    if bootstrap.exists():
        for item in bootstrap.iterdir():
            dest = workspace / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                dest.write_text(item.read_text(encoding="utf-8"), encoding="utf-8")
    return workspace


def test_demo_harness_covers_discovery_to_validation(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TASKSGODZILLA_AUTO_CLONE", "false")
    # Treat Codex as unavailable so execution paths use the stubbed flow.
    monkeypatch.setattr(codex_worker.shutil, "which", lambda name: None if name == "codex" else shutil.which(name))

    db = Database(tmp_path / "db.sqlite")
    db.init_schema()

    workspace = _seed_workspace(tmp_path)
    project = db.create_project("demo", str(workspace), "main", None, None, None, str(workspace))
    db.update_project_policy(project.id, policy_pack_key="beginner-guided", policy_pack_version="1.0")

    # Discovery/onboarding should finish even when repo is local-only.
    onboarding_worker.handle_project_setup(project.id, db)
    setup_run = next(r for r in db.list_protocol_runs(project.id) if r.protocol_name.startswith("setup-"))
    setup_events = [e.event_type for e in db.list_events(setup_run.id)]
    assert "setup_assets" in setup_events

    run = db.create_protocol_run(
        project.id,
        "9000-demo",
        ProtocolStatus.PENDING,
        "main",
        None,
        None,
        "demo harness",
    )

    # Planning should succeed in stub mode when Codex is absent and generate specs/steps.
    codex_worker.handle_plan_protocol(run.id, db)
    run_after_plan = db.get_protocol_run(run.id)
    assert run_after_plan.status == ProtocolStatus.PLANNED
    events = [e.event_type for e in db.list_events(run.id)]
    assert "planned" in events
    assert "policy_autofix" in events

    proto_root = Path(db.get_protocol_run(run.id).protocol_root)
    step_file = proto_root / "01-demo.md"
    content = step_file.read_text(encoding="utf-8")
    assert "## Sub-tasks" in content
    assert "## Verification" in content
    assert "## Rollback" in content
    assert "## Definition of Done" in content

    audit_results = spec_worker.handle_spec_audit_job({"protocol_id": run.id, "backfill_missing": False}, db)
    assert audit_results and audit_results[0]["errors"] == []

    steps = {s.step_name: s for s in db.list_step_runs(run.id)}
    setup_step = next((s for s in steps.values() if s.step_type == "setup"), None)
    work_steps = [s for s in steps.values() if s.step_type != "setup"]
    assert setup_step is not None and work_steps

    db.update_step_status(setup_step.id, StepStatus.COMPLETED, summary="bootstrap ready")

    codex_worker.handle_execute_step(work_steps[0].id, db)
    step_after_exec = db.get_step_run(work_steps[0].id)
    assert step_after_exec.status == StepStatus.COMPLETED

    run_after_exec = db.get_protocol_run(run.id)
    assert run_after_exec.status == ProtocolStatus.COMPLETED

    events = [e.event_type for e in db.list_events(run.id)]
    assert {"planned", "spec_audit", "step_completed", "qa_skipped_policy", "protocol_completed"}.issubset(set(events))
