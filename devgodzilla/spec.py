"""
DevGodzilla Spec Module

Protocol/step specification helpers for unified execution paths.
Handles spec parsing, validation, and step materialization.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from devgodzilla.logging import get_logger
from devgodzilla.models.domain import StepStatus

logger = get_logger(__name__)

# Key used inside protocol_run.template_config to persist the normalized spec
PROTOCOL_SPEC_KEY = "protocol_spec"
SPEC_META_KEY = "spec_meta"


def protocol_spec_hash(spec: Dict[str, Any]) -> str:
    """
    Stable short hash for a ProtocolSpec to attach to events/metrics.
    
    Args:
        spec: Protocol specification dict
        
    Returns:
        12-character hash
    """
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:12]


def infer_step_type_from_name(name: str) -> str:
    """
    Infer step type from step name.
    
    Uses naming conventions to determine step type:
    - Names containing 'test', 'verify', 'check' -> 'verify'
    - Names containing 'plan', 'design' -> 'plan'
    - Names containing 'review', 'qa', 'quality' -> 'review'
    - Default -> 'execute'
    """
    name_lower = name.lower()
    if any(kw in name_lower for kw in ["test", "verify", "check", "validate"]):
        return "verify"
    if any(kw in name_lower for kw in ["plan", "design", "architect"]):
        return "plan"
    if any(kw in name_lower for kw in ["review", "qa", "quality", "audit"]):
        return "review"
    return "execute"


def resolve_spec_path(
    path_value: str,
    base: Path,
    workspace: Optional[Path] = None,
) -> Path:
    """
    Resolve a path from a ProtocolSpec value.
    
    Prefers existing candidates, otherwise returns the first candidate.
    Paths are resolved against the protocol base and workspace root.
    
    Args:
        path_value: Path string (may be relative)
        base: Protocol base directory
        workspace: Optional workspace root
        
    Returns:
        Resolved absolute Path
    """
    if Path(path_value).is_absolute():
        return Path(path_value)
    
    candidates = [base / path_value]
    if workspace and workspace != base:
        candidates.append(workspace / path_value)
    
    # Return first existing candidate
    for candidate in candidates:
        if candidate.exists():
            return candidate
    
    # Return first candidate if none exist
    return candidates[0]


def build_spec_from_protocol_files(
    protocol_root: Path,
    *,
    default_engine_id: Optional[str] = None,
    default_qa_policy: str = "full",
    default_qa_prompt: str = "prompts/quality-validator.prompt.md",
) -> Dict[str, Any]:
    """
    Create a ProtocolSpec from step files.
    
    Scans protocol_root for step files and builds a spec dict.
    
    Args:
        protocol_root: Protocol directory containing step files
        default_engine_id: Default engine ID for steps
        default_qa_policy: Default QA policy ('full', 'basic', 'skip')
        default_qa_prompt: Default QA prompt path
        
    Returns:
        ProtocolSpec dict
    """
    steps = []
    step_files = sorted(protocol_root.glob("step-*.md"))
    
    for i, step_file in enumerate(step_files):
        name = step_file.stem  # e.g., 'step-01-setup'
        
        step_spec = {
            "name": name,
            "type": infer_step_type_from_name(name),
            "prompt_ref": str(step_file.relative_to(protocol_root)),
            "qa_policy": default_qa_policy,
        }
        
        if default_engine_id:
            step_spec["engine_id"] = default_engine_id
        if default_qa_prompt:
            step_spec["qa_prompt"] = default_qa_prompt
        
        steps.append(step_spec)
    
    return {
        "version": "1.0",
        "steps": steps,
    }


def create_steps_from_spec(
    db,
    protocol_run_id: int,
    spec: Dict[str, Any],
    *,
    existing_names: Optional[Set[str]] = None,
) -> List[int]:
    """
    Materialize StepRun rows from a ProtocolSpec.
    
    Skips already-present steps.
    
    Args:
        db: Database instance
        protocol_run_id: Protocol run ID
        spec: ProtocolSpec dict
        existing_names: Optional set of existing step names to skip
        
    Returns:
        List of created step IDs
    """
    existing = existing_names or set()
    steps = spec.get("steps", [])
    created_ids = []
    
    for i, step_spec in enumerate(steps):
        name = step_spec.get("name", f"step-{i:02d}")
        if name in existing:
            continue
        
        step_type = step_spec.get("type") or infer_step_type_from_name(name)
        depends_on = step_spec.get("depends_on", [])
        parallel_group = step_spec.get("parallel_group")
        assigned_agent = step_spec.get("engine_id") or step_spec.get("agent")
        
        step = db.create_step_run(
            protocol_run_id=protocol_run_id,
            step_index=i,
            step_name=name,
            step_type=step_type,
            status=StepStatus.PENDING,
            depends_on=depends_on,
            parallel_group=parallel_group,
            assigned_agent=assigned_agent,
        )
        created_ids.append(step.id)
    
    return created_ids


def get_step_spec(
    template_config: Optional[Dict[str, Any]],
    step_name: str,
) -> Optional[Dict[str, Any]]:
    """
    Retrieve the spec entry for a given step name from a protocol template_config.
    
    Args:
        template_config: Protocol run template_config
        step_name: Step name to look up
        
    Returns:
        Step spec dict or None if not found
    """
    if not template_config:
        return None
    
    protocol_spec = template_config.get(PROTOCOL_SPEC_KEY, {})
    steps = protocol_spec.get("steps", [])
    
    for step in steps:
        if step.get("name") == step_name:
            return step
    
    return None


def validate_step_spec_paths(
    base: Path,
    step_spec: Dict[str, Any],
    workspace: Optional[Path] = None,
) -> List[str]:
    """
    Validate prompt_ref and output paths exist.
    
    When relative, paths are resolved against the protocol base and workspace.
    
    Args:
        base: Protocol base directory
        step_spec: Step specification dict
        workspace: Optional workspace root
        
    Returns:
        List of errors; empty list if valid
    """
    errors = []
    
    prompt_ref = step_spec.get("prompt_ref")
    if prompt_ref:
        resolved = resolve_spec_path(prompt_ref, base, workspace)
        if not resolved.exists():
            errors.append(f"prompt_ref not found: {prompt_ref}")
    
    outputs = step_spec.get("outputs", {})
    for key, path_value in outputs.items():
        if path_value and isinstance(path_value, str):
            resolved = resolve_spec_path(path_value, base, workspace)
            parent = resolved.parent
            if not parent.exists():
                errors.append(f"output parent directory not found: {path_value}")
    
    return errors


def validate_protocol_spec(
    base: Path,
    spec: Dict[str, Any],
    workspace: Optional[Path] = None,
) -> List[str]:
    """
    Validate all steps in a protocol spec relative to a base path.
    
    Args:
        base: Protocol base directory
        spec: ProtocolSpec dict
        workspace: Optional workspace root
        
    Returns:
        List of errors; empty list if valid
    """
    errors = []
    
    # Check version
    version = spec.get("version")
    if not version:
        errors.append("Protocol spec missing version")
    
    # Check steps
    steps = spec.get("steps", [])
    if not steps:
        errors.append("Protocol spec has no steps")
    
    # Validate each step
    for i, step_spec in enumerate(steps):
        name = step_spec.get("name", f"step-{i}")
        step_errors = validate_step_spec_paths(base, step_spec, workspace)
        for err in step_errors:
            errors.append(f"{name}: {err}")
    
    return errors


def update_spec_meta(
    db,
    protocol_run_id: int,
    template_config: Dict[str, Any],
    template_source: Optional[Dict[str, Any]],
    *,
    status: str,
    errors: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Store spec validation metadata on the protocol template_config.
    
    Avoids repeated validation scans. Returns the updated template_config.
    
    Args:
        db: Database instance
        protocol_run_id: Protocol run ID
        template_config: Current template_config
        template_source: Current template_source
        status: Validation status ('valid', 'invalid', 'pending')
        errors: Optional list of validation errors
        
    Returns:
        Updated template_config dict
    """
    meta = {
        "status": status,
        "errors": errors or [],
    }
    
    updated_config = dict(template_config or {})
    updated_config[SPEC_META_KEY] = meta
    
    # Update in database
    db.update_protocol_template(
        protocol_run_id,
        template_config=updated_config,
        template_source=template_source,
    )
    
    return updated_config
