from pathlib import Path
import copy

from deksdenflow.domain import ProtocolStatus, StepStatus
from deksdenflow.engines import EngineMetadata, EngineRequest, EngineResult, registry
from deksdenflow.prompt_utils import fingerprint_file
from deksdenflow.spec import PROTOCOL_SPEC_KEY
from deksdenflow.storage import Database
from deksdenflow.workers import codemachine_worker, codex_worker


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class FakeEngine:
    metadata = EngineMetadata(id="fake-engine", display_name="Fake", kind="cli", default_model="fake-model")

    def plan(self, req: EngineRequest) -> EngineResult:  # pragma: no cover - not used here
        return EngineResult(success=True, stdout="plan", stderr="")

    def execute(self, req: EngineRequest) -> EngineResult:
        return EngineResult(success=True, stdout=f"output for {req.step_run_id}", stderr="", metadata={"engine": self.metadata.id})

    def qa(self, req: EngineRequest) -> EngineResult:  # pragma: no cover - not used here
        return EngineResult(success=True, stdout="qa", stderr="")


def _register_fake_engine() -> None:
    try:
        registry.register(FakeEngine())
    except ValueError:
        # Already registered in another test run
        pass


class CaptureEngine:
    metadata = EngineMetadata(id="fake-engine-capture", display_name="FakeCapture", kind="cli", default_model="fake-model")

    def execute(self, req: EngineRequest) -> EngineResult:
        prompt_text = (req.extra or {}).get("prompt_text", "")
        return EngineResult(success=True, stdout=prompt_text, stderr="", metadata={"engine": self.metadata.id})

    def plan(self, req: EngineRequest) -> EngineResult:  # pragma: no cover - unused
        return EngineResult(success=True, stdout="", stderr="")

    def qa(self, req: EngineRequest) -> EngineResult:  # pragma: no cover - unused
        return EngineResult(success=True, stdout="", stderr="")


def _make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    config_dir = workspace / ".codemachine" / "config"
    (workspace / ".codemachine" / "outputs").mkdir(parents=True, exist_ok=True)
    (workspace / "outputs").mkdir(parents=True, exist_ok=True)
    _write(
        config_dir / "main.agents.js",
        """
        export default [
          { "id": "build", "promptPath": "prompts/build.md", "engineId": "fake-engine", "model": "fake-model" }
        ];
        """,
    )
    _write(workspace / ".codemachine" / "prompts" / "build.md", "Build prompt")
    _write(workspace / ".codemachine" / "inputs" / "specifications.md", "Spec text")
    _write(workspace / ".codemachine" / "template.json", '{"template":"demo","version":"0.0.1"}')
    return workspace


def test_codemachine_execute_writes_outputs_and_events(tmp_path) -> None:
    _register_fake_engine()
    db = Database(tmp_path / "db.sqlite")
    db.init_schema()

    workspace = _make_workspace(tmp_path)
    project = db.create_project("demo", str(workspace), "main", None, None)
    run = db.create_protocol_run(project.id, "1234-demo", ProtocolStatus.PLANNED, "main", str(workspace), str(workspace / ".codemachine"), "demo protocol")
    codemachine_worker.import_codemachine_workspace(project.id, run.id, str(workspace), db)
    step = db.list_step_runs(run.id)[0]

    codex_worker.handle_execute_step(step.id, db)

    step_after = db.get_step_run(step.id)
    assert step_after.status == StepStatus.NEEDS_QA

    protocol_output = workspace / ".protocols" / run.protocol_name / f"{step.step_name}.md"
    codemachine_output = workspace / "outputs" / "build.md"
    assert protocol_output.exists()
    assert codemachine_output.exists()
    assert "output for" in protocol_output.read_text(encoding="utf-8")
    assert "output for" in codemachine_output.read_text(encoding="utf-8")

    events = db.list_events(run.id)
    types = [e.event_type for e in events]
    assert "codemachine_step_completed" in types
    assert "step_completed" in types
    completed = next(e for e in events if e.event_type == "step_completed")
    outputs_meta = completed.metadata.get("outputs")
    assert outputs_meta["protocol"].endswith(f"{step.step_name}.md")
    assert outputs_meta["aux"]["codemachine"].endswith("build.md")


def test_codemachine_quality_is_skipped(tmp_path) -> None:
    _register_fake_engine()
    db = Database(tmp_path / "db.sqlite")
    db.init_schema()

    workspace = _make_workspace(tmp_path)
    project = db.create_project("demo", str(workspace), "main", None, None)
    run = db.create_protocol_run(project.id, "5678-demo", ProtocolStatus.PLANNED, "main", str(workspace), str(workspace / ".codemachine"), "demo protocol")
    codemachine_worker.import_codemachine_workspace(project.id, run.id, str(workspace), db)
    step = db.list_step_runs(run.id)[0]

    codex_worker.handle_execute_step(step.id, db)
    codex_worker.handle_quality(step.id, db)

    step_after = db.get_step_run(step.id)
    assert step_after.status == StepStatus.COMPLETED
    events = [e.event_type for e in db.list_events(run.id)]
    assert "qa_skipped_codemachine" in events


def test_codemachine_quality_runs_when_policy_full(tmp_path) -> None:
    _register_fake_engine()
    db = Database(tmp_path / "db.sqlite")
    db.init_schema()

    workspace = _make_workspace(tmp_path)
    project = db.create_project("demo", str(workspace), "main", None, None)
    run = db.create_protocol_run(project.id, "8888-demo", ProtocolStatus.PLANNED, "main", str(workspace), str(workspace / ".codemachine"), "demo protocol")
    codemachine_worker.import_codemachine_workspace(project.id, run.id, str(workspace), db)

    # Flip QA policy to full for the first step via the stored protocol spec.
    run = db.get_protocol_run(run.id)
    template_cfg = copy.deepcopy(run.template_config or {})
    spec = template_cfg.get(PROTOCOL_SPEC_KEY) or {}
    steps = spec.get("steps") or []
    if steps:
        steps[0]["qa"] = {"policy": "full", "model": "fake-model"}
    template_cfg[PROTOCOL_SPEC_KEY] = spec
    db.update_protocol_template(run.id, template_cfg, run.template_source)

    step = db.list_step_runs(run.id)[0]
    codex_worker.handle_execute_step(step.id, db)
    codex_worker.handle_quality(step.id, db)

    step_after = db.get_step_run(step.id)
    assert step_after.status == StepStatus.COMPLETED
    events = [e.event_type for e in db.list_events(run.id)]
    assert "qa_passed" in events


def test_codemachine_exec_uses_spec_prompt_outside_codemachine(tmp_path) -> None:
    try:
        registry.register(CaptureEngine())
    except ValueError:
        pass
    db = Database(tmp_path / "db.sqlite")
    db.init_schema()

    workspace = _make_workspace(tmp_path)
    external_prompt = workspace / "prompts" / "external.md"
    external_prompt.parent.mkdir(parents=True, exist_ok=True)
    external_prompt.write_text("External prompt", encoding="utf-8")

    project = db.create_project("demo", str(workspace), "main", None, None)
    run = db.create_protocol_run(project.id, "7777-demo", ProtocolStatus.PLANNED, "main", str(workspace), str(workspace / ".codemachine"), "demo protocol")
    codemachine_worker.import_codemachine_workspace(project.id, run.id, str(workspace), db)

    # Update spec to point at the external prompt and capture engine.
    run = db.get_protocol_run(run.id)
    template_cfg = copy.deepcopy(run.template_config or {})
    spec = template_cfg.get(PROTOCOL_SPEC_KEY) or {}
    steps = spec.get("steps") or []
    if steps:
        steps[0]["prompt_ref"] = "prompts/external.md"
        steps[0]["engine_id"] = "fake-engine-capture"
    template_cfg[PROTOCOL_SPEC_KEY] = spec
    db.update_protocol_template(run.id, template_cfg, run.template_source)

    step = db.list_step_runs(run.id)[0]
    db.update_step_status(step.id, step.status, engine_id="fake-engine-capture")

    codex_worker.handle_execute_step(step.id, db)

    protocol_output = workspace / ".protocols" / run.protocol_name / f"{step.step_name}.md"
    codemachine_output = workspace / "outputs" / "build.md"
    assert "External prompt" in protocol_output.read_text(encoding="utf-8")
    assert "External prompt" in codemachine_output.read_text(encoding="utf-8")

    events = db.list_events(run.id)
    completed = next(e for e in events if e.event_type == "codemachine_step_completed")
    assert completed.metadata["prompt_versions"]["exec"] == fingerprint_file(external_prompt)


def test_codemachine_outputs_follow_spec_map(tmp_path) -> None:
    _register_fake_engine()
    db = Database(tmp_path / "db.sqlite")
    db.init_schema()

    workspace = _make_workspace(tmp_path)
    project = db.create_project("demo", str(workspace), "main", None, None)
    run = db.create_protocol_run(project.id, "9999-demo", ProtocolStatus.PLANNED, "main", str(workspace), str(workspace / ".codemachine"), "demo protocol")
    codemachine_worker.import_codemachine_workspace(project.id, run.id, str(workspace), db)

    run = db.get_protocol_run(run.id)
    template_cfg = copy.deepcopy(run.template_config or {})
    spec = template_cfg.get(PROTOCOL_SPEC_KEY) or {}
    steps = spec.get("steps") or []
    if steps:
        steps[0]["outputs"] = {"protocol": "outputs/spec-protocol.md", "aux": {"codemachine": "outputs/spec-cm.md"}}
    template_cfg[PROTOCOL_SPEC_KEY] = spec
    db.update_protocol_template(run.id, template_cfg, run.template_source)

    step = db.list_step_runs(run.id)[0]
    codex_worker.handle_execute_step(step.id, db)

    proto_out = workspace / "outputs" / "spec-protocol.md"
    cm_out = workspace / "outputs" / "spec-cm.md"
    assert proto_out.exists()
    assert cm_out.exists()
    assert proto_out.read_text(encoding="utf-8")
    assert cm_out.read_text(encoding="utf-8")

    event = next(e for e in db.list_events(run.id) if e.event_type == "codemachine_step_completed")
    outputs_meta = event.metadata["outputs"]
    assert outputs_meta["protocol"].endswith("spec-protocol.md")
    assert outputs_meta["aux"]["codemachine"].endswith("spec-cm.md")
