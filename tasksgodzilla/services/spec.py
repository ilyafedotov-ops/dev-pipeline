from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tasksgodzilla.domain import ProtocolRun, StepRun
from tasksgodzilla.logging import get_logger
from tasksgodzilla.project_setup import local_repo_dir
from tasksgodzilla.spec import (
    PROTOCOL_SPEC_KEY,
    build_spec_from_codemachine_config,
    build_spec_from_protocol_files,
    create_steps_from_spec,
    get_step_spec,
    resolve_spec_path,
    update_spec_meta,
    validate_protocol_spec,
)
from tasksgodzilla.storage import BaseDatabase

log = get_logger(__name__)


@dataclass
class SpecService:
    """Service for protocol and step specification management.
    
    This service handles the creation, validation, and resolution of protocol
    specifications and step specifications, including path resolution for prompts,
    outputs, and other resources.
    
    Responsibilities:
    - Build protocol specs from protocol files or CodeMachine configs
    - Validate protocol and step specs against filesystem
    - Create and sync StepRun rows from specs
    - Resolve protocol and workspace paths
    - Resolve step paths (prompts, inputs, outputs)
    - Resolve output paths from step specs
    - Append entries to protocol log files
    - Infer step types from filenames
    
    Spec Structure:
    - Protocol spec: Contains metadata, steps, and global configuration
    - Step spec: Contains prompt_ref, outputs, qa config, engine/model overrides
    
    Path Resolution:
    - Supports absolute paths, workspace-relative paths, and protocol-relative paths
    - Handles .protocols/ directory structure
    - Resolves prompts from workspace or protocol directories
    
    Usage:
        spec_service = SpecService(db)
        
        # Build spec from protocol files
        spec = spec_service.build_from_protocol_files(
            protocol_run_id=123,
            protocol_root=Path("/path/to/.protocols/feature-123")
        )
        
        # Validate spec
        errors = spec_service.validate_and_update_meta(
            protocol_run_id=123,
            protocol_root=Path("/path/to/.protocols/feature-123")
        )
        
        # Create step runs from spec
        created = spec_service.ensure_step_runs(protocol_run_id=123)
        
        # Resolve paths for step execution
        paths = spec_service.resolve_step_paths(
            step_run, protocol_root, workspace_root
        )
    """

    db: BaseDatabase

    def build_from_protocol_files(self, protocol_run_id: int, protocol_root: Path) -> Dict[str, Any]:
        """Create a spec from protocol step files and persist it on the run."""
        run = self.db.get_protocol_run(protocol_run_id)
        spec = build_spec_from_protocol_files(protocol_root)
        template_config = dict(run.template_config or {})
        template_config[PROTOCOL_SPEC_KEY] = spec
        self.db.update_protocol_template(protocol_run_id, template_config, run.template_source)
        log.info(
            "spec_built_from_protocol_files",
            extra={"protocol_run_id": protocol_run_id, "protocol_root": str(protocol_root)},
        )
        return spec

    def build_from_codemachine_config(self, protocol_run_id: int, cfg: Any) -> Dict[str, Any]:
        """Create a spec from a CodeMachine config and persist it on the run."""
        run = self.db.get_protocol_run(protocol_run_id)
        spec = build_spec_from_codemachine_config(cfg)
        template_config = dict(run.template_config or {})
        template_config[PROTOCOL_SPEC_KEY] = spec
        self.db.update_protocol_template(protocol_run_id, template_config, run.template_source)
        log.info(
            "spec_built_from_codemachine",
            extra={"protocol_run_id": protocol_run_id, "has_placeholders": bool(getattr(cfg, "placeholders", None))},
        )
        return spec

    def validate_and_update_meta(
        self,
        protocol_run_id: int,
        protocol_root: Path,
        workspace_root: Optional[Path] = None,
    ) -> List[str]:
        """Validate the spec associated with a protocol run and update meta fields."""
        run = self.db.get_protocol_run(protocol_run_id)
        template_config = dict(run.template_config or {})
        spec = template_config.get(PROTOCOL_SPEC_KEY) or {}

        if workspace_root is None:
            if protocol_root.parent.name == ".protocols":
                workspace_root = protocol_root.parent.parent
            else:
                workspace_root = protocol_root.parent

        errors = validate_protocol_spec(protocol_root, spec, workspace=workspace_root)
        status = "valid" if not errors else "invalid"
        update_spec_meta(self.db, protocol_run_id, template_config, run.template_source, status=status, errors=errors or None)
        log.info(
            "spec_validated",
            extra={"protocol_run_id": protocol_run_id, "status": status, "error_count": len(errors)},
        )
        return errors

    def ensure_step_runs(self, protocol_run_id: int) -> int:
        """Create StepRun rows from the current spec, skipping already-present steps."""
        run = self.db.get_protocol_run(protocol_run_id)
        template_config = dict(run.template_config or {})
        spec = template_config.get(PROTOCOL_SPEC_KEY)
        if not spec:
            return 0
        existing = {s.step_name for s in self.db.list_step_runs(protocol_run_id)}
        created = create_steps_from_spec(protocol_run_id, spec, self.db, existing_names=existing)
        log.info("spec_step_runs_synced", extra={"protocol_run_id": protocol_run_id, "created": created})
        return created

    def get_step_spec(self, protocol_run_id: int, step_name: str) -> Optional[Dict[str, Any]]:
        """Look up a single step spec entry by name."""
        run = self.db.get_protocol_run(protocol_run_id)
        return get_step_spec(run.template_config, step_name)

    def resolve_protocol_paths(self, run: ProtocolRun, project: Any) -> Tuple[Path, Path]:
        """
        Best-effort resolution of workspace/protocol roots for prompt resolution
        before a worktree is loaded.
        
        Returns:
            Tuple of (workspace_root, protocol_root)
        """
        if run.worktree_path:
            workspace_base = Path(run.worktree_path).expanduser()
        elif project.local_path and Path(project.local_path).expanduser().exists():
            workspace_base = Path(project.local_path).expanduser()
        else:
            workspace_base = local_repo_dir(project.git_url, project.name, project_id=project.id)
        
        workspace_root = workspace_base.resolve()
        protocol_root = (
            Path(run.protocol_root).resolve()
            if run.protocol_root
            else (workspace_root / ".protocols" / run.protocol_name)
        )
        
        log.debug(
            "protocol_paths_resolved",
            extra={
                "protocol_run_id": run.id,
                "workspace_root": str(workspace_root),
                "protocol_root": str(protocol_root),
            },
        )
        return workspace_root, protocol_root

    def resolve_step_paths(
        self, step_run: StepRun, protocol_root: Path, workspace_root: Path
    ) -> Dict[str, Path]:
        """
        Resolve all paths for step execution (inputs, outputs, etc).
        
        Returns:
            Dictionary with resolved paths for the step
        """
        run = self.db.get_protocol_run(step_run.protocol_run_id)
        step_spec = get_step_spec(run.template_config, step_run.step_name) or {}
        
        # Resolve prompt path
        prompt_ref = step_spec.get("prompt_ref", step_run.step_name)
        prompt_path = resolve_spec_path(str(prompt_ref), protocol_root, workspace=workspace_root)
        
        # Resolve output paths
        outputs = self.resolve_output_paths(step_spec, protocol_root, workspace_root)
        
        result = {
            "prompt": prompt_path,
            **outputs,
        }
        
        log.debug(
            "step_paths_resolved",
            extra={
                "step_run_id": step_run.id,
                "step_name": step_run.step_name,
                "paths": {k: str(v) for k, v in result.items()},
            },
        )
        return result

    def resolve_output_paths(
        self, step_spec: Dict[str, Any], protocol_root: Path, workspace_root: Optional[Path] = None
    ) -> Dict[str, Path]:
        """
        Resolve output paths from step spec.
        
        Returns:
            Dictionary with resolved output paths
        """
        if workspace_root is None:
            workspace_root = protocol_root.parent.parent if protocol_root.parent.name == ".protocols" else protocol_root.parent
        
        outputs = step_spec.get("outputs", {})
        resolved = {}
        
        for key, value in outputs.items():
            if isinstance(value, str):
                resolved[key] = resolve_spec_path(value, protocol_root, workspace=workspace_root)
            elif isinstance(value, dict):
                # Handle nested output structures
                resolved[key] = {
                    k: resolve_spec_path(v, protocol_root, workspace=workspace_root)
                    if isinstance(v, str)
                    else v
                    for k, v in value.items()
                }
        
        log.debug(
            "output_paths_resolved",
            extra={
                "outputs_count": len(resolved),
                "keys": list(resolved.keys()),
            },
        )
        return resolved

    def sync_step_runs_from_protocol(
        self, protocol_root: Path, protocol_run_id: int
    ) -> int:
        """
        Ensure StepRun rows exist for each step file in the protocol directory.
        Validates the spec and creates step runs from it.
        
        Returns:
            Number of step runs created
        """
        from tasksgodzilla.domain import ProtocolStatus
        from tasksgodzilla.spec import protocol_spec_hash
        
        run = self.db.get_protocol_run(protocol_run_id)
        template_config = dict(run.template_config or {})
        spec = template_config.get(PROTOCOL_SPEC_KEY)
        
        if not spec:
            spec = build_spec_from_protocol_files(protocol_root)
            template_config[PROTOCOL_SPEC_KEY] = spec
            self.db.update_protocol_template(protocol_run_id, template_config, run.template_source)
        
        workspace_root = protocol_root.parent.parent if protocol_root.parent.name == ".protocols" else protocol_root.parent
        validation_errors = validate_protocol_spec(protocol_root, spec, workspace=workspace_root)
        
        if validation_errors:
            for err in validation_errors:
                self.db.append_event(
                    protocol_run_id,
                    "spec_validation_error",
                    err,
                    metadata={"protocol_root": str(protocol_root), "spec_hash": protocol_spec_hash(spec)},
                )
            update_spec_meta(self.db, protocol_run_id, template_config, run.template_source, status="invalid", errors=validation_errors)
            self.db.update_protocol_status(protocol_run_id, ProtocolStatus.BLOCKED)
            return 0
        else:
            update_spec_meta(self.db, protocol_run_id, template_config, run.template_source, status="valid", errors=[])
        
        existing = {s.step_name for s in self.db.list_step_runs(protocol_run_id)}
        created = create_steps_from_spec(protocol_run_id, spec, self.db, existing_names=existing)
        
        log.info(
            "step_runs_synced_from_protocol",
            extra={
                "protocol_run_id": protocol_run_id,
                "created": created,
                "validation_errors": len(validation_errors),
            },
        )
        return created

    def append_protocol_log(self, protocol_root: Path, message: str) -> None:
        """
        Best-effort log.md appender for automatic state notes.
        """
        from datetime import datetime, timezone
        
        log_path = protocol_root / "log.md"
        try:
            if not log_path.exists():
                return
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            entry = f"- {timestamp} - {message}\n"
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(entry)
        except Exception:
            return

    def infer_step_type(self, filename: str) -> str:
        """
        Infer step type from filename.
        
        Returns:
            One of: "setup", "qa", or "work"
        """
        lower = filename.lower()
        if lower.startswith("00-") or "setup" in lower:
            return "setup"
        if "qa" in lower:
            return "qa"
        return "work"
