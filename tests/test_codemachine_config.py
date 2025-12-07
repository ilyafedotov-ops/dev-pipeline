import json
from pathlib import Path

import pytest

from tasksgodzilla.codemachine.config_loader import ConfigError, load_codemachine_config


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_load_codemachine_config_with_export_default(tmp_path) -> None:
    workspace = tmp_path / ".codemachine"
    config_dir = workspace / "config"
    _write(
        config_dir / "main.agents.js",
        """
        export default [
          { "id": "plan", "name": "Planner", "promptPath": "prompts/plan.md", "engineId": "codex", "model": "gpt-5.1-high" },
          { "id": "build", "name": "Builder", "promptPath": "prompts/build.md", "mirrorPath": "prompts/build.mirror.md" }
        ];
        """,
    )
    _write(
        config_dir / "sub.agents.js",
        "module.exports = [{ 'id': 'qa', 'name': 'QA', 'promptPath': 'prompts/qa.md' }];",
    )
    _write(
        config_dir / "modules.js",
        """
        export default [
          { "id": "iteration-checker", "behavior": { "type": "loop", "action": "stepBack", "stepBack": 2, "maxIterations": 3, "skip": [0] } },
          { "id": "handoff", "behavior": { "type": "trigger", "action": "mainAgentCall", "triggerAgentId": "qa" } }
        ];
        """,
    )
    _write(config_dir / "placeholders.js", "export default { 'PROMPTS_ROOT': 'prompts' };")
    _write(
        workspace / "template.json",
        json.dumps({"template": "spec-to-code", "version": "1.2.3", "engineDefaults": {"execute": "codex"}}),
    )

    cfg = load_codemachine_config(tmp_path)

    assert len(cfg.main_agents) == 2
    assert cfg.main_agents[0].id == "plan"
    assert cfg.main_agents[0].engine_id == "codex"
    assert cfg.main_agents[0].model == "gpt-5.1-high"
    assert cfg.main_agents[1].mirror_path == "prompts/build.mirror.md"

    assert len(cfg.sub_agents) == 1
    assert cfg.sub_agents[0].id == "qa"

    assert len(cfg.modules) == 2
    loop_module = cfg.modules[0]
    assert loop_module.behavior == "loop"
    assert loop_module.action == "stepBack"
    assert loop_module.step_back == 2
    assert loop_module.max_iterations == 3
    assert loop_module.skip_steps == [0]

    trigger_module = cfg.modules[1]
    assert trigger_module.behavior == "trigger"
    assert trigger_module.trigger_agent_id == "qa"

    assert cfg.placeholders["PROMPTS_ROOT"] == "prompts"
    assert cfg.template["template"] == "spec-to-code"


def test_load_config_requires_prompt_path(tmp_path) -> None:
    workspace = tmp_path / ".codemachine"
    config_dir = workspace / "config"
    _write(config_dir / "main.agents.js", 'export default [{ "id": "broken" }];')

    with pytest.raises(ConfigError):
        load_codemachine_config(tmp_path)


def test_module_conditions_and_target_agent(tmp_path) -> None:
    workspace = tmp_path / ".codemachine"
    config_dir = workspace / "config"
    _write(
        config_dir / "main.agents.js",
        """
        export default [
          { "id": "plan", "promptPath": "prompts/plan.md" },
          { "id": "build", "promptPath": "prompts/build.md" }
        ];
        """,
    )
    _write(
        config_dir / "modules.js",
        """
        export default [
          { "id": "loop-check", "behavior": { "type": "loop", "action": "stepBack", "stepBack": 1, "condition": "needs_more" } },
          { "id": "handoff", "behavior": { "type": "trigger", "triggerAgentId": "qa", "conditions": ["ready"], "targetAgentId": "build" } }
        ];
        """,
    )
    cfg = load_codemachine_config(tmp_path)
    assert cfg.modules[0].condition == "needs_more"
    assert cfg.modules[1].target_agent_id == "build"
    assert cfg.modules[1].conditions == ["ready"]
