"""
Helpers for executing CodeMachine-style steps inside the orchestrator.

This module resolves agents/prompts from `ProtocolRun.template_config`, applies
placeholders, and builds prompt text so workers can call the configured engine
without depending on the CodeMachine CLI runtime.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple

from tasksgodzilla.domain import ProtocolRun, StepRun
from tasksgodzilla.logging import get_logger
from tasksgodzilla.spec import resolve_spec_path

log = get_logger(__name__)


def is_codemachine_run(run: ProtocolRun) -> bool:
    """
    Heuristic to detect CodeMachine-derived runs: template_config with main agents
    or a protocol_root that points at a `.codemachine` workspace.
    """
    cfg = run.template_config or {}
    if cfg.get("main_agents"):
        return True
    if run.protocol_root:
        root = Path(run.protocol_root)
        if ".codemachine" in root.parts or root.name == ".codemachine":
            return True
    return False


def _agent_id_from_step(step_name: str) -> str:
    # Mirror policy_runtime logic: strip numeric prefix and extension.
    tail = step_name
    if "-" in tail:
        tail = tail.split("-", 1)[1]
    if "." in tail:
        tail = tail.rsplit(".", 1)[0]
    return tail


def find_agent_for_step(step: StepRun, template_config: Dict[str, object]) -> Optional[Dict[str, object]]:
    agent_id = _agent_id_from_step(step.step_name)
    for agent in template_config.get("main_agents") or []:
        if not isinstance(agent, dict):
            continue
        if str(agent.get("id") or agent.get("agent_id")) == agent_id:
            return agent
    return None


def _apply_placeholders(path_str: str, placeholders: Dict[str, object]) -> str:
    resolved = path_str
    parts = resolved.split("/")
    if parts and parts[0] in placeholders:
        parts[0] = str(placeholders[parts[0]])
        resolved = "/".join(parts)
    for key, value in placeholders.items():
        val = str(value)
        tokens = [f"{{{{{key}}}}}", f"<{key}>", f"${{{key}}}", f"${key}"]
        for token in tokens:
            resolved = resolved.replace(token, val)
    return resolved


def resolve_prompt_path(agent: Dict[str, object], codemachine_root: Path, placeholders: Dict[str, object]) -> Path:
    raw_path = agent.get("prompt_path") or agent.get("promptPath") or agent.get("prompt")
    if not raw_path:
        raise ValueError(f"Agent {agent.get('id')} is missing prompt_path")
    resolved_str = _apply_placeholders(str(raw_path), placeholders)
    path = Path(resolved_str)
    if not path.is_absolute():
        path = (codemachine_root / resolved_str).resolve()
        if not path.exists():
            alt = (codemachine_root.parent / resolved_str).resolve()
            if alt.exists():
                path = alt
    return path


def build_prompt_text(
    agent: Dict[str, object],
    codemachine_root: Path,
    placeholders: Dict[str, object],
    *,
    step_spec: Optional[dict] = None,
    workspace: Optional[Path] = None,
) -> Tuple[str, Path]:
    """
    Return prompt text and the resolved prompt path for the given agent.

    If a step spec provides prompt_ref, resolve it relative to the protocol
    root/workspace (supporting prompts outside `.codemachine`). Falls back to
    the agent prompt path. Specification text is appended when present.
    """
    prompt_path: Optional[Path] = None
    workspace_root = workspace or codemachine_root.parent
    if step_spec:
        prompt_ref = step_spec.get("prompt_ref")
        if prompt_ref:
            prompt_ref_str = _apply_placeholders(str(prompt_ref), placeholders)
            try:
                prompt_path = resolve_spec_path(prompt_ref_str, codemachine_root, workspace=workspace_root)
            except Exception:  # pragma: no cover - defensive
                prompt_path = (codemachine_root / prompt_ref_str).resolve()
            if prompt_path and not prompt_path.exists():
                prompt_path = None
    if prompt_path is None:
        prompt_path = resolve_prompt_path(agent, codemachine_root, placeholders)
    prompt_text = prompt_path.read_text(encoding="utf-8")

    spec_path = codemachine_root / "inputs" / "specifications.md"
    if spec_path.exists():
        prompt_text = f"{prompt_text}\n\n---\n# Specification\n{spec_path.read_text(encoding='utf-8')}"

    return prompt_text, prompt_path


def output_paths(
    workspace_root: Path,
    codemachine_root: Path,
    run: ProtocolRun,
    step: StepRun,
    agent_id: str,
) -> Tuple[Path, Path]:
    """
    Compute protocol (.protocols) and aux (codemachine) destinations for a step.
    """
    protocol_root = workspace_root / ".protocols" / run.protocol_name
    protocol_root.mkdir(parents=True, exist_ok=True)

    codemachine_aux_root = protocol_root / "aux" / "codemachine"
    codemachine_aux_root.mkdir(parents=True, exist_ok=True)

    filename = step.step_name if step.step_name.endswith(".md") else f"{step.step_name}.md"
    protocol_path = protocol_root / filename
    codemachine_path = codemachine_aux_root / f"{agent_id}.md"
    return protocol_path, codemachine_path
