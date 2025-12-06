from pathlib import Path

from deksdenflow.domain import ProtocolStatus, StepStatus
from deksdenflow.engines import EngineMetadata, EngineRequest, EngineResult, registry
from deksdenflow.prompt_utils import fingerprint_file
from deksdenflow.spec import PROTOCOL_SPEC_KEY, protocol_spec_hash
from deksdenflow.storage import Database
from deksdenflow.workers import codex_worker


class FakeEngine:
    metadata = EngineMetadata(id="fake-engine-out", display_name="FakeOut", kind="cli", default_model="fake-model")

    def execute(self, req: EngineRequest) -> EngineResult:
        return EngineResult(success=True, stdout="hello world", stderr="", metadata={"engine": self.metadata.id})


def _register_fake_engine() -> None:
    try:
        registry.register(FakeEngine(), default=True)
    except ValueError:
        pass


def _make_protocol_workspace(tmp_path: Path, run_name: str) -> Path:
    workspace = tmp_path / "workspace"
    protocol_root = workspace / ".protocols" / run_name
    protocol_root.mkdir(parents=True, exist_ok=True)
    (protocol_root / "plan.md").write_text("plan", encoding="utf-8")
    (protocol_root / "context.md").write_text("context", encoding="utf-8")
    (protocol_root / "log.md").write_text("", encoding="utf-8")
    (protocol_root / "00-step.md").write_text("step content", encoding="utf-8")
    return workspace


def test_codex_spec_outputs_write_stdout(tmp_path, monkeypatch) -> None:
    _register_fake_engine()
    db = Database(tmp_path / "db.sqlite")
    db.init_schema()

    workspace = _make_protocol_workspace(tmp_path, "0001-demo")
    outputs_dir = workspace / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    project = db.create_project("demo", str(workspace), "main", None, None)
    run = db.create_protocol_run(project.id, "0001-demo", ProtocolStatus.PLANNED, "main", str(workspace), str(workspace / ".protocols" / "0001-demo"), "demo protocol")

    spec = {
        "steps": [
            {
                "id": "00-step",
                "name": "00-step.md",
                "engine_id": "fake-engine-out",
                "model": "fake-model",
                "prompt_ref": "00-step.md",
                "outputs": {
                    "protocol": "outputs/exec.md",
                    "aux": {"mirror": "outputs/mirror.md"},
                },
                "qa": {"policy": "skip"},
            }
        ]
    }
    db.update_protocol_template(run.id, {PROTOCOL_SPEC_KEY: spec}, None)
    step = db.create_step_run(run.id, 0, "00-step.md", "work", StepStatus.PENDING, model="fake-model", engine_id="fake-engine-out", policy=None)

    # Avoid git/codex CLI requirements
    monkeypatch.setattr(codex_worker.shutil, "which", lambda _: "codex")
    monkeypatch.setattr(codex_worker, "load_project", lambda repo_root, protocol_name, base_branch: Path(repo_root))

    codex_worker.handle_execute_step(step.id, db)

    exec_out = (workspace / "outputs" / "exec.md").read_text(encoding="utf-8")
    mirror_out = (workspace / "outputs" / "mirror.md").read_text(encoding="utf-8")
    assert "hello world" in exec_out
    assert "hello world" in mirror_out
    events = db.list_events(run.id)
    completed = next(e for e in events if e.event_type == "step_completed")
    outputs_meta = completed.metadata["outputs"]
    assert outputs_meta["protocol"].endswith("outputs/exec.md")
    assert outputs_meta["aux"]["mirror"].endswith("outputs/mirror.md")


def test_spec_validation_failure_blocks_execution(tmp_path, monkeypatch) -> None:
    _register_fake_engine()
    db = Database(tmp_path / "db.sqlite")
    db.init_schema()

    workspace = _make_protocol_workspace(tmp_path, "0002-demo")
    project = db.create_project("demo", str(workspace), "main", None, None)
    run = db.create_protocol_run(project.id, "0002-demo", ProtocolStatus.PLANNED, "main", str(workspace), str(workspace / ".protocols" / "0002-demo"), "demo protocol")

    bad_spec = {
        "steps": [
            {
                "id": "00-step",
                "name": "00-step.md",
                "engine_id": "fake-engine",
                "model": "fake-model",
                "prompt_ref": ".protocols/0002-demo/missing.md",
                "outputs": {
                    "protocol": "missing-dir/out.md",
                },
                "qa": {"policy": "skip"},
            }
        ]
    }
    db.update_protocol_template(run.id, {PROTOCOL_SPEC_KEY: bad_spec}, None)
    step = db.create_step_run(run.id, 0, "00-step.md", "work", StepStatus.PENDING, model="fake-model", engine_id="fake-engine", policy=None)

    monkeypatch.setattr(codex_worker.shutil, "which", lambda _: "codex")
    monkeypatch.setattr(codex_worker, "load_project", lambda repo_root, protocol_name, base_branch: Path(repo_root))

    codex_worker.handle_execute_step(step.id, db)

    step_after = db.get_step_run(step.id)
    assert step_after.status == StepStatus.FAILED
    events = [e.event_type for e in db.list_events(run.id)]
    assert "spec_validation_error" in events


def test_prompt_ref_outside_protocols_records_version(tmp_path, monkeypatch) -> None:
    _register_fake_engine()
    db = Database(tmp_path / "db.sqlite")
    db.init_schema()

    workspace = _make_protocol_workspace(tmp_path, "9001-demo")
    outputs_dir = workspace / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    external_prompt = workspace / "prompts" / "external.md"
    external_prompt.parent.mkdir(parents=True, exist_ok=True)
    external_prompt.write_text("external prompt", encoding="utf-8")

    project = db.create_project("demo", str(workspace), "main", None, None)
    run = db.create_protocol_run(project.id, "9001-demo", ProtocolStatus.PLANNED, "main", str(workspace), str(workspace / ".protocols" / "9001-demo"), "demo protocol")

    spec = {
        "steps": [
            {
                "id": "00-step",
                "name": "00-step.md",
                "engine_id": "fake-engine-out",
                "model": "fake-model",
                "prompt_ref": "prompts/external.md",
                "outputs": {"protocol": "outputs/out.md"},
                "qa": {"policy": "skip"},
            }
        ]
    }
    db.update_protocol_template(run.id, {PROTOCOL_SPEC_KEY: spec}, None)
    step = db.create_step_run(run.id, 0, "00-step.md", "work", StepStatus.PENDING, model="fake-model", engine_id="fake-engine-out", policy=None)

    monkeypatch.setattr(codex_worker.shutil, "which", lambda _: "codex")
    monkeypatch.setattr(codex_worker, "load_project", lambda repo_root, protocol_name, base_branch: Path(repo_root))

    codex_worker.handle_execute_step(step.id, db)

    step_after = db.get_step_run(step.id)
    assert step_after.status == StepStatus.NEEDS_QA
    events = db.list_events(run.id)
    completed = next(e for e in events if e.event_type == "step_completed")
    assert completed.metadata["prompt_versions"]["exec"] == fingerprint_file(external_prompt)
    assert completed.metadata["spec_hash"] == protocol_spec_hash(spec)


def test_custom_qa_prompt_version_is_recorded(tmp_path, monkeypatch) -> None:
    _register_fake_engine()
    db = Database(tmp_path / "db.sqlite")
    db.init_schema()

    workspace = _make_protocol_workspace(tmp_path, "9002-demo")
    outputs_dir = workspace / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    qa_prompt = workspace / "qa" / "custom.md"
    qa_prompt.parent.mkdir(parents=True, exist_ok=True)
    qa_prompt.write_text("QA prompt body", encoding="utf-8")

    project = db.create_project("demo", str(workspace), "main", None, None)
    run = db.create_protocol_run(project.id, "9002-demo", ProtocolStatus.PLANNED, "main", str(workspace), str(workspace / ".protocols" / "9002-demo"), "demo protocol")

    spec = {
        "steps": [
            {
                "id": "00-step",
                "name": "00-step.md",
                "engine_id": "fake-engine-out",
                "model": "fake-model",
                "prompt_ref": "00-step.md",
                "outputs": {"protocol": "outputs/out.md"},
                "qa": {"policy": "full", "prompt": "qa/custom.md", "model": "fake-model"},
            }
        ]
    }
    db.update_protocol_template(run.id, {PROTOCOL_SPEC_KEY: spec}, None)
    step = db.create_step_run(run.id, 0, "00-step.md", "work", StepStatus.PENDING, model="fake-model", engine_id="fake-engine-out", policy=None)

    monkeypatch.setattr(codex_worker.shutil, "which", lambda _: "codex")
    monkeypatch.setattr(codex_worker, "load_project", lambda repo_root, protocol_name, base_branch: Path(repo_root))

    codex_worker.handle_execute_step(step.id, db)

    # Force stub QA path for portability but keep prompt version resolution
    monkeypatch.setattr(codex_worker.shutil, "which", lambda _: None)
    codex_worker.handle_quality(step.id, db)

    qa_event = next(e for e in db.list_events(run.id) if e.event_type == "qa_passed")
    assert qa_event.metadata["prompt_versions"]["qa"] == fingerprint_file(qa_prompt)
    assert qa_event.metadata["spec_hash"] == protocol_spec_hash(spec)


def test_quality_uses_spec_prompt_and_engine(monkeypatch, tmp_path) -> None:
    from types import SimpleNamespace

    from deksdenflow.qa import QualityResult, codex as qa_codex

    _register_fake_engine()
    db = Database(tmp_path / "db.sqlite")
    db.init_schema()

    workspace = _make_protocol_workspace(tmp_path, "9100-demo")
    qa_prompt = workspace / "custom_prompts" / "qa.md"
    qa_prompt.parent.mkdir(parents=True, exist_ok=True)
    qa_prompt.write_text("Custom QA prompt", encoding="utf-8")

    project = db.create_project("demo", str(workspace), "main", None, None)
    run = db.create_protocol_run(project.id, "9100-demo", ProtocolStatus.PLANNED, "main", str(workspace), str(workspace / ".protocols" / "9100-demo"), "demo protocol")

    spec = {
        "steps": [
            {
                "id": "00-step",
                "name": "00-step.md",
                "engine_id": "fake-engine-out",
                "model": "fake-model",
                "prompt_ref": "00-step.md",
                "outputs": {"protocol": "outputs/out.md"},
                "qa": {"policy": "full", "prompt": "custom_prompts/qa.md", "engine_id": "qa-engine", "model": "qa-model"},
            }
        ]
    }
    db.update_protocol_template(run.id, {PROTOCOL_SPEC_KEY: spec}, None)
    step = db.create_step_run(run.id, 0, "00-step.md", "work", StepStatus.NEEDS_QA, model="fake-model", engine_id="fake-engine-out", policy=None)

    # Force real QA path without Codex CLI but with resolved worktree/prompt
    monkeypatch.setattr(codex_worker.shutil, "which", lambda _: "codex")
    monkeypatch.setattr(codex_worker, "load_project", lambda repo_root, protocol_name, base_branch: Path(repo_root))
    monkeypatch.setattr(qa_codex, "run_process", lambda *args, **kwargs: SimpleNamespace(stdout=""))

    captured: dict[str, object] = {}

    def fake_run_quality_check(**kwargs):
        captured.update(kwargs)
        protocol_root = kwargs["protocol_root"]
        return QualityResult(report_path=protocol_root / "quality-report.md", verdict="PASS", output="ok")

    monkeypatch.setattr(codex_worker, "run_quality_check", fake_run_quality_check)

    codex_worker.handle_quality(step.id, db)

    step_after = db.get_step_run(step.id)
    assert step_after.status == StepStatus.COMPLETED
    assert captured.get("prompt_file") == qa_prompt.resolve()
    assert captured.get("engine_id") == "qa-engine"
    qa_event = next(e for e in db.list_events(run.id) if e.event_type == "qa_passed")
    assert qa_event.metadata["prompt_versions"]["qa"] == fingerprint_file(qa_prompt)
    assert qa_event.metadata["spec_hash"] == protocol_spec_hash(spec)
