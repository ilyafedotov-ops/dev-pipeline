import ast
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


class ConfigError(ValueError):
    """Raised when CodeMachine config files are missing or malformed."""


@dataclass
class AgentSpec:
    id: str
    name: Optional[str]
    description: Optional[str]
    prompt_path: str
    mirror_path: Optional[str]
    engine_id: Optional[str]
    model: Optional[str]
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModulePolicy:
    module_id: str
    behavior: str
    action: Optional[str]
    max_iterations: Optional[int] = None
    step_back: Optional[int] = None
    skip_steps: List[int] = field(default_factory=list)
    trigger_agent_id: Optional[str] = None
    target_agent_id: Optional[str] = None
    condition: Optional[object] = None
    conditions: List[object] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CodeMachineConfig:
    main_agents: List[AgentSpec]
    sub_agents: List[AgentSpec]
    modules: List[ModulePolicy]
    placeholders: Dict[str, Any]
    template: Dict[str, Any]


def agent_to_dict(agent: AgentSpec) -> Dict[str, Any]:
    data = asdict(agent)
    data.pop("raw", None)
    return data


def policy_to_dict(policy: ModulePolicy) -> Dict[str, Any]:
    data = asdict(policy)
    data.pop("raw", None)
    return data


def config_to_template_payload(cfg: CodeMachineConfig) -> Dict[str, Any]:
    """
    Convert a loaded config into a JSON-serializable payload suitable for persistence.
    """
    return {
        "main_agents": [agent_to_dict(a) for a in cfg.main_agents],
        "sub_agents": [agent_to_dict(a) for a in cfg.sub_agents],
        "modules": [policy_to_dict(m) for m in cfg.modules],
        "placeholders": cfg.placeholders,
        "template": cfg.template,
    }


def _strip_js_wrappers(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("export default"):
        stripped = stripped[len("export default") :].strip()
    if stripped.startswith("module.exports"):
        parts = stripped.split("=", 1)
        stripped = parts[1].strip() if len(parts) > 1 else ""
    stripped = re.sub(r"^const\s+\w+\s*=\s*", "", stripped)
    if stripped.endswith(";"):
        stripped = stripped[:-1].strip()
    return stripped


def _parse_js_like(text: str) -> Any:
    candidate = _strip_js_wrappers(text)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        normalized = re.sub(r"\btrue\b", "True", candidate)
        normalized = re.sub(r"\bfalse\b", "False", normalized)
        normalized = re.sub(r"\bnull\b", "None", normalized)
        try:
            return ast.literal_eval(normalized)
        except Exception as exc:
            raise ConfigError(f"Unable to parse config content: {exc}") from exc


def _load_config_value(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return _parse_js_like(path.read_text(encoding="utf-8"))
    except ConfigError:
        raise
    except Exception as exc:
        raise ConfigError(f"Failed to read config file {path}: {exc}") from exc


def _normalize_agents(raw: Any, kind: str) -> List[AgentSpec]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ConfigError(f"{kind} agents config must be a list")
    normalized: List[AgentSpec] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ConfigError(f"{kind} agent entry must be an object")
        agent_id = str(entry.get("id") or entry.get("agentId") or "").strip()
        prompt_path = entry.get("promptPath") or entry.get("prompt") or entry.get("path")
        if not agent_id:
            raise ConfigError(f"{kind} agent is missing an id")
        if not prompt_path:
            raise ConfigError(f"{kind} agent {agent_id} is missing promptPath")
        normalized.append(
            AgentSpec(
                id=agent_id,
                name=entry.get("name"),
                description=entry.get("description"),
                prompt_path=str(prompt_path),
                mirror_path=entry.get("mirrorPath"),
                engine_id=entry.get("engineId"),
                model=entry.get("model"),
                raw=entry,
            )
        )
    return normalized


def normalize_module_policy(raw: Dict[str, Any]) -> ModulePolicy:
    if not isinstance(raw, dict):
        raise ConfigError("Module entry must be an object")
    module_id = str(raw.get("id") or raw.get("module_id") or raw.get("name") or "").strip()
    behavior_block = raw.get("behavior") or {}
    behavior = str(behavior_block.get("type") or raw.get("behavior") or "unknown").lower()
    action = behavior_block.get("action") or raw.get("action")
    step_back = behavior_block.get("stepBack") or behavior_block.get("step_back")
    max_iterations = behavior_block.get("maxIterations") or behavior_block.get("max_iterations")
    skip = behavior_block.get("skip") or behavior_block.get("skipSteps") or []
    trigger_agent_id = behavior_block.get("triggerAgentId") or behavior_block.get("trigger_agent_id")
    target_agent_id = behavior_block.get("targetAgentId") or raw.get("targetAgentId") or raw.get("target_agent_id")
    condition = behavior_block.get("condition") or raw.get("condition")
    conditions = behavior_block.get("conditions") or raw.get("conditions") or []

    skip_steps = []
    if isinstance(skip, list):
        skip_steps = [int(s) for s in skip if isinstance(s, (int, float))]

    return ModulePolicy(
        module_id=module_id or "(unknown)",
        behavior=behavior,
        action=str(action) if action else None,
        max_iterations=int(max_iterations) if isinstance(max_iterations, (int, float)) else None,
        step_back=int(step_back) if isinstance(step_back, (int, float)) else None,
        skip_steps=skip_steps,
        trigger_agent_id=str(trigger_agent_id) if trigger_agent_id else None,
        target_agent_id=str(target_agent_id) if target_agent_id else None,
        condition=condition,
        conditions=conditions if isinstance(conditions, list) else [],
        raw=raw,
    )


def load_codemachine_config(root: Path) -> CodeMachineConfig:
    """
    Load CodeMachine workspace configuration from `.codemachine/`.
    Returns normalized agents/modules/placeholders plus the raw template JSON.
    """
    workspace = Path(root)
    codemachine_root = workspace / ".codemachine"
    if codemachine_root.exists():
        workspace = codemachine_root
    config_dir = workspace / "config"

    main_agents_raw = _load_config_value(config_dir / "main.agents.js") or []
    sub_agents_raw = _load_config_value(config_dir / "sub.agents.js") or []
    modules_raw = _load_config_value(config_dir / "modules.js") or []
    placeholders_raw = _load_config_value(config_dir / "placeholders.js") or {}
    template_raw = _load_config_value(workspace / "template.json") or {}

    main_agents = _normalize_agents(main_agents_raw, "main")
    sub_agents = _normalize_agents(sub_agents_raw, "sub")

    modules: List[ModulePolicy] = []
    if modules_raw:
        if not isinstance(modules_raw, list):
            raise ConfigError("modules config must be a list")
        modules = [normalize_module_policy(m) for m in modules_raw]

    placeholders = placeholders_raw if isinstance(placeholders_raw, dict) else {}
    template = template_raw if isinstance(template_raw, dict) else {}

    return CodeMachineConfig(
        main_agents=main_agents,
        sub_agents=sub_agents,
        modules=modules,
        placeholders=placeholders,
        template=template,
    )
