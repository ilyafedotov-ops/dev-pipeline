"""
Shared helpers for protocol/step state transitions that are reused by API handlers
and workers.
"""

from deksdenflow.domain import ProtocolStatus, StepStatus
from deksdenflow.logging import get_logger, log_extra
from deksdenflow.storage import BaseDatabase

log = get_logger(__name__)


def maybe_complete_protocol(protocol_run_id: int, db: BaseDatabase) -> bool:
    """
    Mark a protocol as completed if all step runs are in a terminal state.
    Returns True if the protocol was transitioned.
    """
    run = db.get_protocol_run(protocol_run_id)
    if run.status in (ProtocolStatus.COMPLETED, ProtocolStatus.CANCELLED, ProtocolStatus.FAILED, ProtocolStatus.BLOCKED):
        return False

    steps = db.list_step_runs(protocol_run_id)
    if not steps:
        return False

    terminal = {StepStatus.COMPLETED, StepStatus.CANCELLED}
    if any(step.status not in terminal for step in steps):
        return False

    run = db.update_protocol_status(protocol_run_id, ProtocolStatus.COMPLETED)
    db.append_event(protocol_run_id, "protocol_completed", "All steps completed; protocol closed.")
    log.info("protocol_completed", extra=log_extra(protocol_run_id=run.id, project_id=run.project_id))
    return True
