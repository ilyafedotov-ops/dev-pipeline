"""
Worker entry point for ingesting CodeMachine workspaces.
"""

from pathlib import Path

from tasksgodzilla.codemachine import ConfigError, config_to_template_payload, load_codemachine_config
from tasksgodzilla.domain import ProtocolStatus
from tasksgodzilla.logging import get_logger, log_extra
from tasksgodzilla.spec import (
    PROTOCOL_SPEC_KEY,
    build_spec_from_codemachine_config,
    create_steps_from_spec,
    protocol_spec_hash,
    update_spec_meta,
    validate_protocol_spec,
)
from tasksgodzilla.storage import BaseDatabase

log = get_logger(__name__)


def import_codemachine_workspace(
    project_id: int,
    protocol_run_id: int,
    workspace_path: str,
    db: BaseDatabase,
) -> dict:
    """
    Read `.codemachine` config, persist the template graph to the protocol run,
    and materialize step runs from main agents.
    """
    root = Path(workspace_path)
    cfg = load_codemachine_config(root)
    protocol_spec = build_spec_from_codemachine_config(cfg)
    base_for_validation = root / ".codemachine" if (root / ".codemachine").exists() else root
    validation_errors = validate_protocol_spec(base_for_validation, protocol_spec, workspace=root)
    if validation_errors:
        db.append_event(
            protocol_run_id,
            "spec_validation_error",
            "CodeMachine spec validation failed.",
            metadata={"errors": validation_errors},
        )
        template_cfg = config_to_template_payload(cfg)
        template_cfg[PROTOCOL_SPEC_KEY] = protocol_spec
        update_spec_meta(db, protocol_run_id, template_cfg, cfg.template, status="invalid", errors=validation_errors)
        db.update_protocol_status(protocol_run_id, ProtocolStatus.BLOCKED)
        return {"errors": validation_errors}
    template_payload = config_to_template_payload(cfg)
    template_payload[PROTOCOL_SPEC_KEY] = protocol_spec
    update_spec_meta(db, protocol_run_id, template_payload, cfg.template, status="valid", errors=[])

    db.update_protocol_template(protocol_run_id, template_config=template_payload, template_source=cfg.template)
    existing = {s.step_name for s in db.list_step_runs(protocol_run_id)}
    created = create_steps_from_spec(protocol_run_id, protocol_spec, db, existing_names=existing)
    db.update_protocol_status(protocol_run_id, ProtocolStatus.PLANNED)
    db.append_event(
        protocol_run_id,
        "codemachine_imported",
        f"Imported CodeMachine workspace with {created} step(s).",
        metadata={
            "workspace": str(root),
            "steps_created": created,
            "template": cfg.template,
            "spec_hash": protocol_spec_hash(protocol_spec),
            "spec_validated": True,
        },
    )
    return {"steps_created": created, "workspace": str(root)}


def handle_import_job(payload: dict, db: BaseDatabase) -> None:
    run_id = payload["protocol_run_id"]
    project_id = payload["project_id"]
    workspace = payload["workspace_path"]
    try:
        import_codemachine_workspace(project_id, run_id, workspace, db)
    except ConfigError as exc:
        db.append_event(run_id, "codemachine_import_failed", f"Config error: {exc}")
        db.update_protocol_status(run_id, ProtocolStatus.BLOCKED)
        log.warning(
            "CodeMachine import failed",
            extra={
                **log_extra(job_id=payload.get("job_id"), project_id=project_id, protocol_run_id=run_id),
                "workspace_path": workspace,
                "error": str(exc),
                "error_type": exc.__class__.__name__,
            },
        )
        raise
    except Exception as exc:  # pragma: no cover - best effort
        db.append_event(run_id, "codemachine_import_failed", f"Unexpected error: {exc}")
        db.update_protocol_status(run_id, ProtocolStatus.BLOCKED)
        log.warning(
            "CodeMachine import failed",
            extra={
                **log_extra(job_id=payload.get("job_id"), project_id=project_id, protocol_run_id=run_id),
                "workspace_path": workspace,
                "error": str(exc),
                "error_type": exc.__class__.__name__,
            },
        )
        raise
