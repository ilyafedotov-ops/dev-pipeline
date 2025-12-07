import copy
from pathlib import Path

from tasksgodzilla.domain import ProtocolStatus, StepStatus
from tasksgodzilla.engines import EngineMetadata, EngineRequest, EngineResult, registry
from tasksgodzilla.spec import PROTOCOL_SPEC_KEY
from tasksgodzilla.storage import Database
from tasksgodzilla.workers import codex_worker, codemachine_worker


class EchoEngine:
    metadata = EngineMetadata(id="runner-echo", display_name="Echo", kind="cli", default_model="echo-model")

    def execute(self, req: EngineRequest) -> EngineResult:
        text = (req.extra or {}).get("prompt_text", "")
        return EngineResult(success=True, stdout=text, stderr="", metadata={"engine": self.metadata.id})

    def qa(self, req: EngineRequest) -> EngineResult:
        return EngineResult(success=True, stdout="VERDICT: PASS", stderr="", metadata={"engine": self.metadata.id})

    def plan(self, req: EngineRequest) -> EngineResult:  # pragma: no cover - unused
        return EngineResult(success=True, stdout="", stderr="")


def _register_echo() -> None:
    try:
        registry.register(EchoEngine())
    except ValueError:
        pass


def _make_codex_workspace(root: Path, name: str) -> Path:
    workspace = root / "codex"
    protocol_root = workspace / ".protocols" / name
    protocol_root.mkdir(parents=True, exist_ok=True)
    (protocol_root / "plan.md").write_text("plan", encoding="utf-8")
    (protocol_root / "context.md").write_text("context", encoding="utf-8")
    (protocol_root / "log.md").write_text("", encoding="utf-8")
    (protocol_root / "00-work.md").write_text("do work", encoding="utf-8")
    prompts_dir = workspace / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "quality-validator.prompt.md").write_text("qa prompt", encoding="utf-8")
    return workspace


def _make_codemachine_workspace(root: Path) -> Path:
    workspace = root / "codemachine"
    config_dir = workspace / ".codemachine" / "config"
    (workspace / ".codemachine" / "outputs").mkdir(parents=True, exist_ok=True)
    (workspace / "outputs").mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)
    (workspace / ".codemachine" / "prompts").mkdir(parents=True, exist_ok=True)
    (workspace / ".codemachine" / "prompts" / "build.md").write_text("build prompt", encoding="utf-8")
    (config_dir / "main.agents.js").write_text(
        """
        export default [
          { "id": "build", "promptPath": "prompts/build.md", "engineId": "runner-echo", "model": "echo-model" }
        ];
        """,
        encoding="utf-8",
    )
    (workspace / ".codemachine" / "template.json").write_text('{"template":"mixed","version":"0.0.1"}', encoding="utf-8")
    return workspace


def test_mixed_engines_and_qa_policies(monkeypatch, tmp_path) -> None:
    _register_echo()
    # Avoid git side effects in codex worker.
    monkeypatch.setattr(codex_worker, "_load_project_with_context", lambda repo_root, *args, **kwargs: repo_root)
    monkeypatch.setattr(codex_worker, "git_push_and_open_pr", lambda *_, **__: False)
    monkeypatch.setattr(codex_worker, "trigger_ci_pipeline", lambda *_, **__: False)

    db = Database(tmp_path / "db.sqlite")
    db.init_schema()

    # Codex-style run with QA=full.
    codex_ws = _make_codex_workspace(tmp_path, "0001-mixed")
    codex_proj = db.create_project("codex", str(codex_ws), "main", None, None)
    codex_run = db.create_protocol_run(
        codex_proj.id,
        "0001-mixed",
        ProtocolStatus.PLANNED,
        "main",
        str(codex_ws),
        str(codex_ws / ".protocols" / "0001-mixed"),
        "codex run",
        template_config={
            PROTOCOL_SPEC_KEY: {
                "steps": [
                    {
                        "id": "00-work",
                        "name": "00-work.md",
                        "engine_id": "runner-echo",
                        "model": "echo-model",
                        "prompt_ref": "00-work.md",
                        "outputs": {"protocol": "00-work.md"},
                        "qa": {"policy": "full"},
                    }
                ]
            }
        },
    )
    codex_step = db.create_step_run(codex_run.id, 0, "00-work.md", "work", StepStatus.PENDING, model=None, engine_id="runner-echo")

    codex_worker.handle_execute_step(codex_step.id, db)
    codex_after_exec = db.get_step_run(codex_step.id)
    assert codex_after_exec.status == StepStatus.NEEDS_QA
    codex_worker.handle_quality(codex_step.id, db)
    codex_after_qa = db.get_step_run(codex_step.id)
    assert codex_after_qa.status == StepStatus.COMPLETED

    # CodeMachine-style run with QA skip policy.
    cm_ws = _make_codemachine_workspace(tmp_path)
    cm_proj = db.create_project("cm", str(cm_ws), "main", None, None)
    cm_run = db.create_protocol_run(
        cm_proj.id,
        "0002-mixed",
        ProtocolStatus.PLANNED,
        "main",
        str(cm_ws),
        str(cm_ws / ".codemachine"),
        "cm run",
    )
    codemachine_worker.import_codemachine_workspace(cm_proj.id, cm_run.id, str(cm_ws), db)

    cm_step = db.list_step_runs(cm_run.id)[0]
    cm_template = copy.deepcopy(db.get_protocol_run(cm_run.id).template_config or {})
    spec = cm_template.get(PROTOCOL_SPEC_KEY) or {}
    if spec.get("steps"):
        spec["steps"][0]["qa"] = {"policy": "skip"}
    cm_template[PROTOCOL_SPEC_KEY] = spec
    db.update_protocol_template(cm_run.id, cm_template, None)

    codex_worker.handle_execute_step(cm_step.id, db)
    codex_worker.handle_quality(cm_step.id, db)

    cm_after = db.get_step_run(cm_step.id)
    assert cm_after.status == StepStatus.COMPLETED
    events = [e.event_type for e in db.list_events(cm_run.id)]
    assert "qa_skipped_policy" in events
    assert "codemachine_step_completed" in events
