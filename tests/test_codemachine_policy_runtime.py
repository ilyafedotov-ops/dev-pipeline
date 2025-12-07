from pathlib import Path

import pytest

from tasksgodzilla.codemachine.policy_runtime import apply_loop_policies, apply_trigger_policies
from tasksgodzilla.domain import ProtocolStatus, StepStatus
from tasksgodzilla.storage import Database
from tasksgodzilla.workers import codex_worker


def _make_db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "db.sqlite")
    db.init_schema()
    return db


def test_apply_loop_policy_resets_steps_and_tracks_state(tmp_path) -> None:
    db = _make_db(tmp_path)
    project = db.create_project("demo", str(tmp_path / "repo"), "main", None, None)
    run = db.create_protocol_run(project.id, "0001-demo", ProtocolStatus.RUNNING, "main", None, None, "demo protocol")
    policy = {
        "module_id": "iteration-checker",
        "behavior": "loop",
        "action": "stepBack",
        "max_iterations": 2,
        "step_back": 1,
        "skip_steps": [],
    }

    step0 = db.create_step_run(run.id, 0, "00-plan", "work", StepStatus.COMPLETED, model=None)
    step1 = db.create_step_run(run.id, 1, "01-build", "work", StepStatus.FAILED, model=None, policy=[policy])
    step2 = db.create_step_run(run.id, 2, "02-qa", "work", StepStatus.COMPLETED, model=None)

    decision = apply_loop_policies(db.get_step_run(step1.id), db, reason="qa_failed")
    assert decision and decision["applied"]

    step0_after = db.get_step_run(step0.id)
    step1_after = db.get_step_run(step1.id)
    step2_after = db.get_step_run(step2.id)
    assert step0_after.status == StepStatus.PENDING
    assert step1_after.status == StepStatus.PENDING
    assert step2_after.status == StepStatus.PENDING
    loops = (step1_after.runtime_state or {}).get("loop_counts", {})
    assert loops.get("iteration-checker") == 1

    events = [e for e in db.list_events(run.id) if e.event_type == "loop_decision"]
    assert events, "expected loop_decision event"
    assert events[-1].metadata["target_step_index"] == 0
    assert 1 in events[-1].metadata.get("steps_reset", [])


def test_apply_loop_policy_honors_max_iterations(tmp_path) -> None:
    db = _make_db(tmp_path)
    project = db.create_project("demo", str(tmp_path / "repo"), "main", None, None)
    run = db.create_protocol_run(project.id, "0002-demo", ProtocolStatus.RUNNING, "main", None, None, "demo protocol")
    policy = {
        "module_id": "iteration-checker",
        "behavior": "loop",
        "action": "stepBack",
        "max_iterations": 1,
        "step_back": 1,
        "skip_steps": [],
    }
    step = db.create_step_run(run.id, 0, "00-setup", "setup", StepStatus.FAILED, model=None, policy=[policy])
    db.update_step_status(step.id, StepStatus.FAILED, runtime_state={"loop_counts": {"iteration-checker": 1}})

    decision = apply_loop_policies(db.get_step_run(step.id), db, reason="qa_failed")
    assert decision is None

    step_after = db.get_step_run(step.id)
    assert step_after.status == StepStatus.FAILED

    events = [e for e in db.list_events(run.id) if e.event_type == "loop_limit_reached"]
    assert events, "expected loop_limit_reached event"
    meta = events[-1].metadata or {}
    assert meta.get("iterations") == 1
    assert meta.get("max_iterations") == 1


def test_loop_policy_respects_condition_reason(tmp_path) -> None:
    db = _make_db(tmp_path)
    project = db.create_project("demo", str(tmp_path / "repo"), "main", None, None)
    run = db.create_protocol_run(project.id, "0002b-demo", ProtocolStatus.RUNNING, "main", None, None, "demo protocol")
    policy = {
        "module_id": "iteration-checker",
        "behavior": "loop",
        "action": "stepBack",
        "max_iterations": 2,
        "step_back": 0,
        "skip_steps": [],
        "condition": "qa_failed",
    }
    step = db.create_step_run(run.id, 0, "00-setup", "setup", StepStatus.FAILED, model=None, policy=[policy])

    no_op = apply_loop_policies(db.get_step_run(step.id), db, reason="exec_failed")
    assert no_op is None
    assert db.get_step_run(step.id).status == StepStatus.FAILED
    events = [e for e in db.list_events(run.id) if e.event_type == "loop_condition_skipped"]
    assert events and events[-1].metadata.get("reason") == "exec_failed"

    decision = apply_loop_policies(db.get_step_run(step.id), db, reason="qa_failed")
    assert decision and decision["applied"]
    assert db.get_step_run(step.id).status == StepStatus.PENDING


def test_apply_trigger_policy_sets_target_pending(tmp_path) -> None:
    db = _make_db(tmp_path)
    project = db.create_project("demo", str(tmp_path / "repo"), "main", None, None)
    run = db.create_protocol_run(project.id, "0004-demo", ProtocolStatus.RUNNING, "main", None, None, "demo protocol")
    trigger_policy = {
        "module_id": "handoff",
        "behavior": "trigger",
        "action": "mainAgentCall",
        "trigger_agent_id": "qa",
    }

    step0 = db.create_step_run(run.id, 0, "00-plan", "work", StepStatus.COMPLETED, model=None, policy=[trigger_policy])
    step1 = db.create_step_run(run.id, 1, "01-qa", "work", StepStatus.FAILED, model=None)

    decision = apply_trigger_policies(db.get_step_run(step0.id), db, reason="qa_passed")
    assert decision and decision["applied"]
    step1_after = db.get_step_run(step1.id)
    assert step1_after.status == StepStatus.PENDING
    assert step1_after.runtime_state.get("last_triggered_by") == step0.step_name

    events = [e for e in db.list_events(run.id) if e.event_type == "trigger_decision"]
    assert events, "expected trigger_decision event"
    assert events[-1].metadata.get("target_step_index") == 1


def test_apply_trigger_policy_skips_missing_target(tmp_path) -> None:
    db = _make_db(tmp_path)
    project = db.create_project("demo", str(tmp_path / "repo"), "main", None, None)
    run = db.create_protocol_run(project.id, "0005-demo", ProtocolStatus.RUNNING, "main", None, None, "demo protocol")
    trigger_policy = {"module_id": "handoff", "behavior": "trigger", "trigger_agent_id": "nonexistent"}
    step0 = db.create_step_run(run.id, 0, "00-plan", "work", StepStatus.COMPLETED, model=None, policy=[trigger_policy])

    decision = apply_trigger_policies(db.get_step_run(step0.id), db, reason="qa_passed")
    assert decision is None

    events = [e for e in db.list_events(run.id) if e.event_type == "trigger_missing_target"]
    assert events, "expected trigger_missing_target event"


def test_trigger_policy_respects_conditions(tmp_path) -> None:
    db = _make_db(tmp_path)
    project = db.create_project("demo", str(tmp_path / "repo"), "main", None, None)
    run = db.create_protocol_run(project.id, "0005b-demo", ProtocolStatus.RUNNING, "main", None, None, "demo protocol")
    trigger_policy = {
        "module_id": "handoff",
        "behavior": "trigger",
        "trigger_agent_id": "qa",
        "conditions": ["qa_passed"],
    }

    step0 = db.create_step_run(run.id, 0, "00-plan", "work", StepStatus.COMPLETED, model=None, policy=[trigger_policy])
    step1 = db.create_step_run(run.id, 1, "01-qa", "work", StepStatus.FAILED, model=None)

    no_op = apply_trigger_policies(db.get_step_run(step0.id), db, reason="exec_completed")
    assert no_op is None
    step1_after = db.get_step_run(step1.id)
    assert step1_after.status == StepStatus.FAILED
    skipped_events = [e for e in db.list_events(run.id) if e.event_type == "trigger_condition_skipped"]
    assert skipped_events and skipped_events[-1].metadata.get("reason") == "exec_completed"

    decision = apply_trigger_policies(db.get_step_run(step0.id), db, reason="qa_passed")
    assert decision and decision["applied"]
    step1_after = db.get_step_run(step1.id)
    assert step1_after.status == StepStatus.PENDING
    assert step1_after.runtime_state.get("last_triggered_by") == step0.step_name


def test_handle_quality_applies_loop_policy(monkeypatch, tmp_path) -> None:
    db = _make_db(tmp_path)
    repo_root = tmp_path / "repo"
    prompt_dir = repo_root / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    qa_prompt = prompt_dir / "quality-validator.prompt.md"
    qa_prompt.write_text("qa prompt", encoding="utf-8")

    protocol_root = repo_root / ".protocols" / "0003-demo"
    protocol_root.mkdir(parents=True, exist_ok=True)
    (protocol_root / "plan.md").write_text("plan", encoding="utf-8")
    (protocol_root / "context.md").write_text("context", encoding="utf-8")
    (protocol_root / "log.md").write_text("", encoding="utf-8")
    (protocol_root / "00-setup.md").write_text("step", encoding="utf-8")

    project = db.create_project("demo", str(repo_root), "main", None, None)
    run = db.create_protocol_run(
        project.id,
        "0003-demo",
        ProtocolStatus.RUNNING,
        "main",
        str(repo_root),
        str(protocol_root),
        "demo protocol",
    )
    policy = {
        "module_id": "iteration-checker",
        "behavior": "loop",
        "action": "stepBack",
        "max_iterations": 2,
        "step_back": 0,  # stays on the same step
        "skip_steps": [],
    }
    step = db.create_step_run(run.id, 0, "00-setup.md", "setup", StepStatus.NEEDS_QA, model="codex-5.1", policy=[policy])

    class FakeResult:
        def __init__(self) -> None:
            self.verdict = "FAIL"
            self.stdout = "VERDICT: FAIL"

    class DummyProc:
        def __init__(self, stdout: str = "") -> None:
            self.stdout = stdout

    monkeypatch.setattr(codex_worker.shutil, "which", lambda _: "codex")
    monkeypatch.setattr(codex_worker, "load_project", lambda repo_root, protocol_name, base_branch: repo_root)
    monkeypatch.setattr(codex_worker, "run_quality_check", lambda **_: FakeResult())
    monkeypatch.setattr(codex_worker, "run_process", lambda *args, **kwargs: DummyProc(""))
    monkeypatch.setattr("tasksgodzilla.qa.codex.run_process", lambda *args, **kwargs: DummyProc(""))

    codex_worker.handle_quality(step.id, db)

    step_after = db.get_step_run(step.id)
    assert step_after.status == StepStatus.PENDING
    loops = (step_after.runtime_state or {}).get("loop_counts", {})
    assert loops.get("iteration-checker") == 1

    run_after = db.get_protocol_run(run.id)
    assert run_after.status == ProtocolStatus.RUNNING

    events = [e.event_type for e in db.list_events(run.id)]
    assert "qa_failed" in events
    assert "loop_decision" in events


def test_handle_quality_triggers_followup(monkeypatch, tmp_path) -> None:
    db = _make_db(tmp_path)
    repo_root = tmp_path / "repo"
    prompt_dir = repo_root / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    qa_prompt = prompt_dir / "quality-validator.prompt.md"
    qa_prompt.write_text("qa prompt", encoding="utf-8")

    protocol_root = repo_root / ".protocols" / "0006-demo"
    protocol_root.mkdir(parents=True, exist_ok=True)
    (protocol_root / "plan.md").write_text("plan", encoding="utf-8")
    (protocol_root / "context.md").write_text("context", encoding="utf-8")
    (protocol_root / "log.md").write_text("", encoding="utf-8")
    (protocol_root / "00-plan.md").write_text("step", encoding="utf-8")
    (protocol_root / "01-qa.md").write_text("qa step", encoding="utf-8")

    project = db.create_project("demo", str(repo_root), "main", None, None)
    run = db.create_protocol_run(
        project.id,
        "0006-demo",
        ProtocolStatus.RUNNING,
        "main",
        str(repo_root),
        str(protocol_root),
        "demo protocol",
    )
    trigger_policy = {"module_id": "handoff", "behavior": "trigger", "trigger_agent_id": "qa"}
    step0 = db.create_step_run(run.id, 0, "00-plan.md", "setup", StepStatus.NEEDS_QA, model="codex-5.1", policy=[trigger_policy])
    step1 = db.create_step_run(run.id, 1, "01-qa.md", "work", StepStatus.FAILED, model=None)

    class FakeResult:
        def __init__(self) -> None:
            self.verdict = "PASS"
            self.stdout = "VERDICT: PASS"

    class DummyProc:
        def __init__(self, stdout: str = "") -> None:
            self.stdout = stdout

    monkeypatch.setattr(codex_worker.shutil, "which", lambda _: None)
    monkeypatch.setattr(codex_worker, "load_project", lambda repo_root, protocol_name, base_branch: repo_root)
    monkeypatch.setattr(codex_worker, "run_quality_check", lambda **_: FakeResult())
    monkeypatch.setattr("tasksgodzilla.qa.build_prompt", lambda *_args, **_kwargs: "prompt")
    monkeypatch.setattr("tasksgodzilla.qa.codex.run_process", lambda *args, **kwargs: DummyProc(""))

    codex_worker.handle_quality(step0.id, db)

    step0_after = db.get_step_run(step0.id)
    step1_after = db.get_step_run(step1.id)
    assert step0_after.status == StepStatus.COMPLETED
    assert step1_after.status in (StepStatus.PENDING, StepStatus.NEEDS_QA)
    assert step1_after.runtime_state.get("last_triggered_by") == step0.step_name
    assert step1_after.runtime_state.get("inline_trigger_depth") >= 1

    events = [e.event_type for e in db.list_events(run.id)]
    assert "qa_passed" in events
    assert "trigger_decision" in events
    assert "trigger_executed_inline" in events


def test_handle_execute_step_triggers_inline(monkeypatch, tmp_path) -> None:
    db = _make_db(tmp_path)
    repo_root = tmp_path / "repo"
    (repo_root / "prompts").mkdir(parents=True, exist_ok=True)
    protocol_root = repo_root / ".protocols" / "0007-demo"
    protocol_root.mkdir(parents=True, exist_ok=True)
    (protocol_root / "plan.md").write_text("plan", encoding="utf-8")
    (protocol_root / "context.md").write_text("context", encoding="utf-8")
    (protocol_root / "log.md").write_text("", encoding="utf-8")
    (protocol_root / "00-main.md").write_text("step", encoding="utf-8")
    (protocol_root / "01-qa.md").write_text("qa step", encoding="utf-8")

    project = db.create_project("demo", str(repo_root), "main", None, None)
    run = db.create_protocol_run(
        project.id,
        "0007-demo",
        ProtocolStatus.RUNNING,
        "main",
        str(repo_root),
        str(protocol_root),
        "demo protocol",
    )
    trigger_policy = {"module_id": "handoff", "behavior": "trigger", "trigger_agent_id": "qa"}
    step0 = db.create_step_run(run.id, 0, "00-main.md", "setup", StepStatus.PENDING, model="codex-5.1", policy=[trigger_policy])
    step1 = db.create_step_run(run.id, 1, "01-qa.md", "work", StepStatus.FAILED, model=None)

    monkeypatch.setattr(codex_worker.shutil, "which", lambda _: None)
    monkeypatch.delenv("TASKSGODZILLA_REDIS_URL", raising=False)

    codex_worker.handle_execute_step(step0.id, db)

    step0_after = db.get_step_run(step0.id)
    step1_after = db.get_step_run(step1.id)
    assert step0_after.status == StepStatus.NEEDS_QA
    assert step1_after.status == StepStatus.NEEDS_QA
    assert step1_after.runtime_state.get("inline_trigger_depth") >= 1

    events = [e.event_type for e in db.list_events(run.id)]
    assert "trigger_decision" in events
    assert "trigger_executed_inline" in events


def test_inline_trigger_depth_guard(monkeypatch, tmp_path) -> None:
    db = _make_db(tmp_path)
    repo_root = tmp_path / "repo"
    (repo_root / "prompts").mkdir(parents=True, exist_ok=True)
    protocol_root = repo_root / ".protocols" / "0008-demo"
    protocol_root.mkdir(parents=True, exist_ok=True)
    (protocol_root / "plan.md").write_text("plan", encoding="utf-8")
    (protocol_root / "context.md").write_text("context", encoding="utf-8")
    (protocol_root / "log.md").write_text("", encoding="utf-8")
    (protocol_root / "00-main.md").write_text("step", encoding="utf-8")

    project = db.create_project("demo", str(repo_root), "main", None, None)
    run = db.create_protocol_run(
        project.id,
        "0008-demo",
        ProtocolStatus.RUNNING,
        "main",
        str(repo_root),
        str(protocol_root),
        "demo protocol",
    )
    trigger_policy = {"module_id": "handoff", "behavior": "trigger", "trigger_agent_id": "main"}
    step0 = db.create_step_run(run.id, 0, "00-main.md", "setup", StepStatus.PENDING, model="codex-5.1", policy=[trigger_policy])

    monkeypatch.setattr(codex_worker.shutil, "which", lambda _: None)
    monkeypatch.setattr(codex_worker, "MAX_INLINE_TRIGGER_DEPTH", 1)

    codex_worker.handle_execute_step(step0.id, db)

    events = [e.event_type for e in db.list_events(run.id)]
    assert "trigger_inline_depth_exceeded" in events or "trigger_executed_inline" in events
