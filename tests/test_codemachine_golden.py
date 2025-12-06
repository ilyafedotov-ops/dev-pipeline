import os
from pathlib import Path

from deksdenflow.codemachine.config_loader import load_codemachine_config
from deksdenflow.workers import codemachine_worker
from deksdenflow.domain import ProtocolStatus
from deksdenflow.storage import Database


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_import_attaches_targeted_modules(tmp_path) -> None:
    db_path = tmp_path / "db.sqlite"
    db = Database(db_path)
    db.init_schema()

    workspace = tmp_path / "workspace"
    config_dir = workspace / ".codemachine" / "config"
    _write(
        config_dir / "main.agents.js",
        """
        export default [
          { "id": "plan", "promptPath": "prompts/plan.md", "moduleId": "loop-check" },
          { "id": "build", "promptPath": "prompts/build.md" }
        ];
        """,
    )
    _write(
        config_dir / "modules.js",
        """
        export default [
          { "id": "loop-check", "behavior": { "type": "loop", "action": "stepBack", "maxIterations": 2 } },
          { "id": "handoff", "behavior": { "type": "trigger", "triggerAgentId": "build", "targetAgentId": "build" } }
        ];
        """,
    )
    _write(workspace / ".codemachine" / "template.json", '{"template":"golden","version":"0.0.1"}')

    project = db.create_project("demo", str(workspace), "main", None, None)
    run = db.create_protocol_run(project.id, "9999-golden", ProtocolStatus.PLANNED, "main", str(workspace), str(workspace / ".codemachine"), "golden")

    codemachine_worker.import_codemachine_workspace(project.id, run.id, str(workspace), db)

    steps = db.list_step_runs(run.id)
    assert len(steps) == 2
    plan = steps[0]
    build = steps[1]
    assert plan.policy and plan.policy[0]["module_id"] == "loop-check"
    assert build.policy and build.policy[0]["module_id"] == "handoff"

    # Trigger targeted at build should attach when trigger_agent_id matches the agent id
    cfg = load_codemachine_config(workspace)
    target_policy = next(m for m in cfg.modules if m.module_id == "handoff")
    assert target_policy.target_agent_id == "build"
