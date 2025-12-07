"""
Worker for spec validation/backfill jobs.
"""

from deksdenflow.logging import get_logger, log_extra
from deksdenflow.spec_tools import audit_specs
from deksdenflow.storage import BaseDatabase

log = get_logger(__name__)


def handle_spec_audit_job(payload: dict, db: BaseDatabase) -> list[dict]:
    """
    Validate/backfill specs for a project or protocol and emit events per run.
    Payload keys:
      - project_id (optional)
      - protocol_id (optional)
      - backfill_missing (bool)
    """
    project_id = payload.get("project_id")
    protocol_id = payload.get("protocol_id")
    backfill_missing = bool(payload.get("backfill_missing"))
    results = audit_specs(db, project_id=project_id, protocol_id=protocol_id, backfill_missing=backfill_missing)
    for res in results:
        protocol_id = res.get("protocol_run_id")
        if not protocol_id:
            continue
        message = "Spec audit completed."
        if res.get("errors"):
            message = "Spec audit found errors."
        db.append_event(
            protocol_id,
            "spec_audit",
            message,
            metadata=res,
        )
    audited_protocols = [res.get("protocol_run_id") for res in results if res.get("protocol_run_id")]
    log.info(
        "spec_audit_job",
        extra={
            **log_extra(project_id=project_id, protocol_run_id=payload.get("protocol_id")),
            "backfill": backfill_missing,
            "count": len(results),
            "audited_protocol_run_ids": audited_protocols or None,
        },
    )
    return results
