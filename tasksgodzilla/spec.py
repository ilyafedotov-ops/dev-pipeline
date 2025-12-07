"""
Shared protocol/step specification helpers to unify Codex and CodeMachine paths.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from jsonschema import Draft7Validator

from tasksgodzilla.codemachine.config_loader import AgentSpec, CodeMachineConfig
from tasksgodzilla.domain import StepStatus
from tasksgodzilla.storage import BaseDatabase

# Key used inside protocol_run.template_config to persist the normalized spec.
PROTOCOL_SPEC_KEY = "protocol_spec"
SPEC_META_KEY = "spec_meta"


def load_protocol_spec_schema(schema_path: Optional[Path] = None) -> dict:
    """
    Load the ProtocolSpec JSON Schema from disk. Allows overriding the path for tests.
    """
    path = schema_path or Path(__file__).resolve().parents[1] / "schemas" / "protocol-spec.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def protocol_spec_hash(spec: Dict[str, Any]) -> str:
    """
    Stable short hash for a ProtocolSpec to attach to events/metrics.
    """
    data = json.dumps(spec or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:12]


def update_spec_meta(
    db: BaseDatabase,
    protocol_run_id: int,
    template_config: dict,
    template_source: Optional[dict],
    *,
    status: str,
    errors: Optional[List[str]] = None,
) -> dict:
    """
    Store spec validation metadata on the protocol template_config to avoid
    repeated event scans. Returns the updated template_config.
    """
    meta = dict(template_config.get(SPEC_META_KEY) or {})
    meta["status"] = status
    meta["errors"] = errors or []
    from datetime import datetime, timezone

    meta["validated_at"] = datetime.now(timezone.utc).isoformat()
    template_config[SPEC_META_KEY] = meta
    db.update_protocol_template(protocol_run_id, template_config, template_source)
    return template_config


def _resolve_path_candidates(path_value: str, base: Path, workspace: Path) -> tuple[Path, List[Path]]:
    """
    Resolve a spec path value relative to the protocol base and workspace,
    returning the first existing candidate (or the first candidate if none exist)
    plus the full candidate list for diagnostics.
    """
    path = Path(path_value)
    if path.is_absolute():
        return path, [path]
    candidates: List[Path] = [(base / path).resolve()]
    if workspace != base:
        candidates.append((workspace / path).resolve())
    resolved = next((p for p in candidates if p.exists()), candidates[0])
    return resolved, candidates


def _resolve_output_path(path_value: str, base: Path, workspace: Path, *, prefer_workspace: bool = False) -> Path:
    """
    Resolve an output path, preferring a candidate whose parent exists even if the
    file itself has not been created yet.
    """
    path = Path(path_value)
    if path.is_absolute():
        return path
    candidates: List[Path] = []
    if prefer_workspace and workspace != base:
        candidates.append((workspace / path).resolve())
    candidates.append((base / path).resolve())
    if not prefer_workspace and workspace != base:
        candidates.append((workspace / path).resolve())
    for cand in candidates:
        if cand.parent.exists():
            return cand
    return candidates[0]


def resolve_spec_path(path_value: str, base: Path, workspace: Optional[Path] = None) -> Path:
    """
    Resolve a path from a ProtocolSpec value (prompt_ref or outputs) against the
    protocol base and workspace root. Prefers existing candidates, otherwise the
    first candidate is returned for validation error reporting.
    """
    workspace_root = workspace or base
    resolved, _ = _resolve_path_candidates(path_value, base, workspace_root)
    return resolved


def infer_step_type_from_name(name: str) -> str:
    lower = name.lower()
    if lower.startswith("00-") or "setup" in lower:
        return "setup"
    if "qa" in lower:
        return "qa"
    return "work"


def build_spec_from_protocol_files(
    protocol_root: Path,
    default_engine_id: str = "codex",
    default_qa_policy: str = "full",
    default_qa_prompt: str = "prompts/quality-validator.prompt.md",
) -> Dict[str, Any]:
    """
    Create a ProtocolSpec from Codex-generated step files.
    """
    steps: List[Dict[str, Any]] = []
    step_files = sorted([p for p in protocol_root.glob("*.md") if p.name[0:2].isdigit()])
    for idx, path in enumerate(step_files):
        steps.append(
            {
                "id": path.stem,
                "name": path.name,
                "engine_id": default_engine_id,
                "model": None,
                "prompt_ref": str(path),
                "outputs": {"protocol": str(path)},
                "step_type": infer_step_type_from_name(path.name),
                "policies": [],
                "qa": {"policy": default_qa_policy, "prompt": default_qa_prompt},
                "order": idx,
            }
        )
    return {"steps": steps}


def _policies_for_agent(agent: AgentSpec, modules: List[Any]) -> List[dict]:
    """
    Attach module policies to a CodeMachine agent when explicitly referenced.
    Mirrors the previous worker logic but centralized for spec generation.
    """
    from tasksgodzilla.codemachine.config_loader import policy_to_dict  # local import to avoid cycles

    policies: List[dict] = []
    agent_modules = agent.raw.get("moduleId") or agent.raw.get("module_id") or agent.raw.get("module")
    agent_module_ids = set()
    if isinstance(agent_modules, str):
        agent_module_ids.add(agent_modules)
    elif isinstance(agent_modules, list):
        agent_module_ids.update(str(m) for m in agent_modules)

    for mod in modules:
        target_agent = (mod.target_agent_id or mod.raw.get("targetAgentId") or mod.raw.get("target_agent_id") or "").strip()
        should_attach = False
        if mod.module_id in agent_module_ids:
            should_attach = True
        if target_agent and target_agent == agent.id:
            should_attach = True
        if getattr(mod, "behavior", None) == "trigger" and mod.trigger_agent_id == agent.id:
            should_attach = True
        if should_attach:
            policies.append(policy_to_dict(mod))
    return policies


def build_spec_from_codemachine_config(
    cfg: CodeMachineConfig,
    qa_policy: str = "skip",
    qa_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a ProtocolSpec from a CodeMachine config (main agents only).
    Defaults to skipping QA to mirror current behavior until QA is normalized.
    """
    steps: List[Dict[str, Any]] = []
    for idx, agent in enumerate(cfg.main_agents):
        step_name = f"{idx:02d}-{agent.id}"
        steps.append(
            {
                "id": agent.id,
                "name": step_name,
                "engine_id": agent.engine_id,
                "model": agent.model,
                "prompt_ref": agent.prompt_path,
                "outputs": {"aux": {"codemachine": f"outputs/{agent.id}.md"}},
                "step_type": infer_step_type_from_name(step_name),
                "policies": _policies_for_agent(agent, cfg.modules),
                "qa": {"policy": qa_policy, "prompt": qa_prompt},
                "order": idx,
                "description": agent.description,
            }
        )
    return {"steps": steps, "placeholders": cfg.placeholders, "template": cfg.template}


def create_steps_from_spec(
    protocol_run_id: int,
    spec: Dict[str, Any],
    db: BaseDatabase,
    existing_names: Optional[set] = None,
) -> int:
    """
    Materialize StepRun rows from a ProtocolSpec; skips already-present steps.
    """
    created = 0
    existing = existing_names or set()
    steps = spec.get("steps") or []
    for idx, step in enumerate(steps):
        step_name = str(step.get("name") or step.get("id") or f"{idx:02d}-step")
        if step_name in existing:
            continue
        db.create_step_run(
            protocol_run_id=protocol_run_id,
            step_index=idx,
            step_name=step_name,
            step_type=str(step.get("step_type") or infer_step_type_from_name(step_name)),
            status=StepStatus.PENDING,
            model=step.get("model"),
            engine_id=step.get("engine_id"),
            policy=step.get("policies"),
            summary=step.get("description"),
        )
        created += 1
    return created


def get_step_spec(template_config: Optional[dict], step_name: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve the spec entry for a given step name from a protocol template_config.
    """
    if not template_config:
        return None
    spec = template_config.get(PROTOCOL_SPEC_KEY) if isinstance(template_config, dict) else None
    if not spec:
        return None
    steps = spec.get("steps") or []
    for step in steps:
        name = str(step.get("name") or step.get("id") or "")
        if name == step_name:
            return step
    return None


def validate_step_spec_paths(base: Path, step_spec: Dict[str, Any], workspace: Optional[Path] = None) -> List[str]:
    """
    Validate prompt_ref and output paths exist. When relative, paths are resolved
    against the protocol base and the workspace root to support prompts/outputs
    outside `.protocols/`.
    Returns a list of errors; empty list if valid.
    """
    errors: List[str] = []
    workspace_root = workspace or base
    prompt_ref = step_spec.get("prompt_ref")
    step_name = step_spec.get("name") or step_spec.get("id") or "(unknown)"
    if prompt_ref:
        pr_path, _ = _resolve_path_candidates(prompt_ref, base, workspace_root)
        if not pr_path.exists():
            errors.append(f"prompt_ref missing: {pr_path}")
    else:
        default_prompt = (base / step_name).resolve()
        if not default_prompt.exists():
            errors.append(f"prompt_ref missing: {default_prompt}")

    outputs_cfg = step_spec.get("outputs") if isinstance(step_spec, dict) else None
    if isinstance(outputs_cfg, dict):
        protocol_output = outputs_cfg.get("protocol")
        if protocol_output:
            proto_path = _resolve_output_path(protocol_output, base, workspace_root)
            if not proto_path.parent.exists():
                errors.append(f"output parent missing: {proto_path.parent}")
        aux_outputs = outputs_cfg.get("aux") if isinstance(outputs_cfg.get("aux"), dict) else {}
        if isinstance(aux_outputs, dict):
            for key, path_val in aux_outputs.items():
                aux_path = _resolve_output_path(str(path_val), base, workspace_root)
                if not aux_path.parent.exists():
                    errors.append(f"output parent missing ({key}): {aux_path.parent}")
    return errors


def validate_protocol_spec(base: Path, spec: Dict[str, Any], workspace: Optional[Path] = None, schema: Optional[dict] = None) -> List[str]:
    """
    Validate all steps in a protocol spec relative to a base path.
    """
    if not spec or not isinstance(spec, dict):
        return ["protocol spec missing or malformed"]
    errors: List[str] = []
    schema_data = schema
    if schema_data is None:
        try:
            schema_data = load_protocol_spec_schema()
        except Exception as exc:  # pragma: no cover - best effort if schema file missing
            errors.append(f"schema: {exc}")
            schema_data = None
    if schema_data is not None:
        try:
            validator = Draft7Validator(schema_data)
            for err in validator.iter_errors(spec):
                location = "/".join(str(p) for p in err.path) or "(root)"
                errors.append(f"schema:{location}: {err.message}")
        except Exception as exc:  # pragma: no cover - defensive guard
            errors.append(f"schema: {exc}")
    steps = spec.get("steps")
    if not isinstance(steps, list):
        errors.append("protocol spec steps must be a list")
        return errors
    for step in steps:
        step_name = str(step.get("name") or step.get("id") or "(unknown)")
        errs = validate_step_spec_paths(base, step, workspace=workspace)
        errors.extend([f"{step_name}: {e}" for e in errs])
    return errors


def resolve_outputs_map(
    outputs_cfg: Optional[dict],
    *,
    base: Path,
    workspace: Path,
    default_protocol: Path,
    default_aux: Optional[Dict[str, Path]] = None,
    prefer_workspace: bool = False,
) -> tuple[Path, Dict[str, Path]]:
    """
    Resolve protocol/aux output paths for a step. Falls back to provided
    defaults when spec values are absent. All returned paths are absolute.
    """
    protocol_path = default_protocol
    aux_paths: Dict[str, Path] = dict(default_aux or {})
    if outputs_cfg and isinstance(outputs_cfg, dict):
        protocol_output = outputs_cfg.get("protocol")
        if protocol_output:
            protocol_path = _resolve_output_path(str(protocol_output), base, workspace, prefer_workspace=prefer_workspace)
        aux_cfg = outputs_cfg.get("aux") if isinstance(outputs_cfg.get("aux"), dict) else {}
        if isinstance(aux_cfg, dict):
            for key, path_val in aux_cfg.items():
                aux_paths[key] = _resolve_output_path(str(path_val), base, workspace, prefer_workspace=prefer_workspace)
    return protocol_path, aux_paths
