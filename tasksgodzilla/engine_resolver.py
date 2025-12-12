"""
Skeleton resolver to unify prompt/output resolution across Codex and CodeMachine.

The goal is to replace the split `_resolve_codex_context` / `_resolve_codemachine_context`
paths with a single resolver that:
- Reads a `StepSpec` (engine/model/prompt_ref/outputs/qa/policies).
- Resolves prompt + output paths relative to the protocol and workspace roots.
- Carries along prompt versions, spec hash, and agent metadata for event logging.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from tasksgodzilla.prompt_utils import prompt_version
from tasksgodzilla.spec import protocol_spec_hash, resolve_spec_path


@dataclass
class ResolvedOutputs:
    protocol: Optional[Path]
    aux: Dict[str, Path]
    raw: Dict[str, Any]


@dataclass
class StepResolution:
    engine_id: str
    model: Optional[str]
    prompt_path: Path
    prompt_text: str
    prompt_version: str
    workdir: Path
    protocol_root: Path
    workspace_root: Path
    outputs: ResolvedOutputs
    qa: Dict[str, Any]
    policies: List[Dict[str, Any]]
    spec_hash: Optional[str] = None
    agent_id: Optional[str] = None
    step_name: Optional[str] = None


def _read_prompt_text(prompt_path: Path) -> str:
    try:
        return prompt_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _resolve_outputs(
    raw_outputs: Dict[str, Any],
    protocol_root: Path,
    workspace_root: Path,
    *,
    outputs_root: Optional[Path] = None,
    prefer_workspace_outputs: bool = False,
) -> ResolvedOutputs:
    aux_cfg = (raw_outputs or {}).get("aux") or {}
    aux: Dict[str, Path] = {}

    def _pick_path(value: str, *, prefer_workspace: bool = True) -> Path:
        path_val = Path(value)
        if path_val.is_absolute():
            return path_val
        primary_root = outputs_root or protocol_root
        candidates: List[Path] = []
        if prefer_workspace:
            candidates.extend([(workspace_root / path_val).resolve(), (primary_root / path_val).resolve()])
        else:
            candidates.extend([(primary_root / path_val).resolve(), (workspace_root / path_val).resolve()])
        if primary_root != protocol_root:
            candidates.append((protocol_root / path_val).resolve())
        for cand in candidates:
            if cand.parent.exists():
                return cand
        return candidates[0]

    for key, value in aux_cfg.items():
        try:
            aux[str(key)] = _pick_path(str(value), prefer_workspace=prefer_workspace_outputs)
        except Exception:
            continue
    protocol_path = None
    if isinstance(raw_outputs, dict) and raw_outputs.get("protocol"):
        try:
            protocol_path = _pick_path(str(raw_outputs["protocol"]), prefer_workspace=prefer_workspace_outputs)
        except Exception:
            protocol_path = None
    return ResolvedOutputs(protocol=protocol_path, aux=aux, raw=raw_outputs or {})


def resolve_prompt_and_outputs(
    step_spec: Dict[str, Any],
    protocol_root: Path,
    workspace_root: Path,
    *,
    protocol_spec: Optional[Dict[str, Any]] = None,
    outputs_root: Optional[Path] = None,
    default_engine_id: str = "codex",
    default_model: Optional[str] = None,
) -> StepResolution:
    """
    Unified resolver for both Codex and CodeMachine step specs.

    This is intentionally side-effect free: it only resolves paths and returns
    structured data for the caller to act on. Future work should replace the
    worker-specific `_resolve_*_context` helpers with this resolver.
    """
    engine_id = step_spec.get("engine_id") or default_engine_id
    model = step_spec.get("model") or default_model
    prompt_ref = step_spec.get("prompt_ref") or step_spec.get("prompt") or step_spec.get("file")
    if not prompt_ref:
        raise ValueError("StepSpec is missing prompt_ref/prompt/file")
    prompt_path = resolve_spec_path(str(prompt_ref), protocol_root, workspace=workspace_root)
    prompt_text = _read_prompt_text(prompt_path)

    outputs_cfg = step_spec.get("outputs") or {}
    prefer_workspace_outputs = protocol_root.name == ".codemachine" and outputs_root is None
    resolved_outputs = _resolve_outputs(
        outputs_cfg,
        protocol_root,
        workspace_root,
        outputs_root=outputs_root,
        prefer_workspace_outputs=prefer_workspace_outputs,
    )
    qa_cfg = step_spec.get("qa") or {}
    policies = list(step_spec.get("policies") or [])
    spec_hash_val = protocol_spec_hash(protocol_spec) if protocol_spec else None

    return StepResolution(
        engine_id=engine_id,
        model=model,
        prompt_path=prompt_path,
        prompt_text=prompt_text,
        prompt_version=prompt_version(prompt_path),
        workdir=workspace_root,
        protocol_root=protocol_root,
        workspace_root=workspace_root,
        outputs=resolved_outputs,
        qa=qa_cfg,
        policies=policies,
        spec_hash=spec_hash_val,
        agent_id=step_spec.get("agent_id") or step_spec.get("agent"),
        step_name=step_spec.get("name") or step_spec.get("id"),
    )
