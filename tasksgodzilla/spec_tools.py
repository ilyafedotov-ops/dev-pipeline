"""
Helpers for validating and backfilling ProtocolSpec across existing runs.
"""

from pathlib import Path
from typing import List, Optional, Tuple

from tasksgodzilla.codemachine import config_to_template_payload, load_codemachine_config
from tasksgodzilla.codemachine.runtime_adapter import is_codemachine_run
from tasksgodzilla.domain import ProtocolRun
from tasksgodzilla.project_setup import local_repo_dir
from tasksgodzilla.spec import (
    PROTOCOL_SPEC_KEY,
    build_spec_from_codemachine_config,
    build_spec_from_protocol_files,
    protocol_spec_hash,
    update_spec_meta,
    validate_protocol_spec,
)
from tasksgodzilla.storage import BaseDatabase


def _workspace_and_protocol_root(run: ProtocolRun, project) -> Tuple[Path, Path]:
    workspace_base = Path(run.worktree_path).expanduser() if run.worktree_path else local_repo_dir(project.git_url, project.name)
    workspace = workspace_base.resolve()
    protocol_root = Path(run.protocol_root).resolve() if run.protocol_root else (workspace / ".protocols" / run.protocol_name)
    return workspace, protocol_root


def audit_protocol_run_spec(
    run: ProtocolRun,
    project,
    db: BaseDatabase,
    *,
    backfill_missing: bool = False,
) -> dict:
    """
    Validate (and optionally backfill) the ProtocolSpec for a given run.
    Returns a summary dict with errors/backfill status for CLI/API reporting.
    """
    workspace_root, protocol_root = _workspace_and_protocol_root(run, project)
    template_config = dict(run.template_config or {})
    spec = template_config.get(PROTOCOL_SPEC_KEY)
    backfilled = False
    errors: List[str] = []
    status: Optional[str] = None

    if spec is None and backfill_missing:
        if is_codemachine_run(run):
            try:
                cfg = load_codemachine_config(workspace_root)
                spec = build_spec_from_codemachine_config(cfg)
                template_payload = config_to_template_payload(cfg)
                template_payload.update(template_config)
                template_payload[PROTOCOL_SPEC_KEY] = spec
                template_config = template_payload
                db.update_protocol_template(run.id, template_config, run.template_source)
                backfilled = True
            except Exception as exc:  # pragma: no cover - defensive guard
                errors.append(f"backfill failed: {exc}")
        else:
            if not protocol_root.exists():
                errors.append(f"protocol_root missing: {protocol_root}")
            else:
                spec = build_spec_from_protocol_files(protocol_root)
                template_config[PROTOCOL_SPEC_KEY] = spec
                db.update_protocol_template(run.id, template_config, run.template_source)
                backfilled = True

    base_for_validation = protocol_root
    if is_codemachine_run(run):
        codemachine_root = protocol_root if protocol_root.name == ".codemachine" else workspace_root / ".codemachine"
        base_for_validation = codemachine_root if codemachine_root.exists() else workspace_root

    spec_hash = None
    if spec:
        errors.extend(validate_protocol_spec(base_for_validation, spec, workspace=workspace_root))
        spec_hash = protocol_spec_hash(spec)
    else:
        errors.append("protocol spec missing")
        status = "missing"

    if spec is not None:
        status = "valid" if not errors else "invalid"

    if status:
        template_config = update_spec_meta(db, run.id, template_config, run.template_source, status=status, errors=errors)

    return {
        "protocol_run_id": run.id,
        "protocol_name": run.protocol_name,
        "project_id": project.id,
        "project_name": project.name,
        "spec_hash": spec_hash,
        "errors": errors,
        "backfilled": backfilled,
        "workspace": str(workspace_root),
        "protocol_root": str(protocol_root),
    }


def audit_specs(
    db: BaseDatabase,
    *,
    project_id: Optional[int] = None,
    protocol_id: Optional[int] = None,
    backfill_missing: bool = False,
) -> List[dict]:
    """
    Iterate protocol runs and audit/backfill their specs. Filters to a project or
    specific protocol when IDs are provided.
    """
    runs: List[tuple[ProtocolRun, object]] = []
    if protocol_id is not None:
        run = db.get_protocol_run(protocol_id)
        project = db.get_project(run.project_id)
        runs.append((run, project))
    elif project_id is not None:
        project = db.get_project(project_id)
        runs.extend((r, project) for r in db.list_protocol_runs(project.id))
    else:
        for project in db.list_projects():
            runs.extend((r, project) for r in db.list_protocol_runs(project.id))

    return [audit_protocol_run_spec(run, project, db, backfill_missing=backfill_missing) for run, project in runs]
