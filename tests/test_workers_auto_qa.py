import os
from pathlib import Path

from tasksgodzilla.domain import ProtocolStatus, StepStatus
from tasksgodzilla.prompt_utils import prompt_version
from tasksgodzilla.storage import Database
from tasksgodzilla.workers import codex_worker


def test_execute_step_auto_qa_runs_quality(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TASKSGODZILLA_AUTO_QA_AFTER_EXEC", "true")
    db_path = tmp_path / "db.sqlite"
    db = Database(db_path)
    db.init_schema()

    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)

    project = db.create_project("demo", str(repo_root), "main", None, None)
    run = db.create_protocol_run(
        project.id,
        "0001-demo",
        ProtocolStatus.RUNNING,
        "main",
        None,
        None,
        "demo protocol",
    )
    step = db.create_step_run(run.id, 0, "00-setup.md", "setup", StepStatus.PENDING, model=None)

    # Ensure stub path (no codex)
    monkeypatch.setattr(codex_worker.shutil, "which", lambda _: None)

    codex_worker.handle_execute_step(step.id, db)

    step_after = db.get_step_run(step.id)
    assert step_after.status == StepStatus.COMPLETED
    run_after = db.get_protocol_run(run.id)
    assert run_after.status in (ProtocolStatus.RUNNING, ProtocolStatus.COMPLETED)


def test_handle_quality_records_prompt_version(monkeypatch, tmp_path) -> None:
    db = Database(tmp_path / "db.sqlite")
    db.init_schema()
    repo_root = tmp_path / "repo"
    prompt_dir = repo_root / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    qa_prompt = prompt_dir / "quality-validator.prompt.md"
    qa_prompt.write_text("qa prompt v1", encoding="utf-8")

    project = db.create_project("demo", str(repo_root), "main", None, None)
    run = db.create_protocol_run(project.id, "0002-demo", ProtocolStatus.RUNNING, "main", None, None, "demo protocol")
    step = db.create_step_run(run.id, 0, "00-setup.md", "setup", StepStatus.NEEDS_QA, model=None)

    # Force stub branch
    monkeypatch.setattr(codex_worker.shutil, "which", lambda _: None)

    codex_worker.handle_quality(step.id, db)

    events = db.list_events(run.id)
    qa_events = [e for e in events if e.event_type == "qa_passed"]
    assert qa_events, "expected qa_passed event"
    metadata = qa_events[0].metadata or {}
    assert metadata.get("prompt_versions", {}).get("qa") == prompt_version(qa_prompt)
