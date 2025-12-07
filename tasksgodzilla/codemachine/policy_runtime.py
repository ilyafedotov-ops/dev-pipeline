"""
Runtime helpers for applying CodeMachine-style loop/trigger policies to StepRuns.

These utilities are intentionally minimal: they interpret loop policies (stepBack)
and update StepRun/runtime state plus events so the console can show what
decision was taken. Execution/routing (e.g., queueing the next step) is handled
by callers.
"""

from typing import Dict, List, Optional, Sequence, Tuple

from tasksgodzilla.domain import StepRun, StepStatus
from tasksgodzilla.logging import get_logger
from tasksgodzilla.storage import BaseDatabase

log = get_logger(__name__)


def _policy_list(policy_field: Optional[object]) -> List[dict]:
    if not policy_field:
        return []
    if isinstance(policy_field, list):
        return [p for p in policy_field if isinstance(p, dict)]
    if isinstance(policy_field, dict):
        return [policy_field]
    return []


def _normalized_conditions(policy: dict) -> List[str]:
    """
    Collect stringified condition tokens from a policy.
    Supports `condition`, `conditions`, and common nested keys (on/reason/event/when).
    """
    tokens: List[str] = []

    def _add(value: object) -> None:
        if value is None:
            return
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                tokens.append(stripped.lower())
        elif isinstance(value, (list, tuple, set)):
            for entry in value:
                _add(entry)
        elif isinstance(value, dict):
            for key in ("on", "reason", "event", "when", "name"):
                _add(value.get(key))

    _add(policy.get("condition"))
    _add(policy.get("conditions"))
    return tokens


def _conditions_allow(policy: dict, reason: Optional[str]) -> bool:
    """
    Evaluate policy conditions against the provided reason.
    Empty conditions always allow; otherwise a case-insensitive string match is required.
    """
    expected = _normalized_conditions(policy)
    if not expected:
        return True
    reason_val = (reason or "").strip().lower()
    return bool(reason_val) and reason_val in expected


def _loop_counts(state: Dict[str, object], module_id: str) -> int:
    loop_state = state.get("loop_counts") or {}
    if isinstance(loop_state, dict):
        try:
            return int(loop_state.get(module_id, 0))
        except Exception:
            return 0
    return 0


def _coerce_int(value: Optional[object], default: int) -> int:
    try:
        return int(value) if value is not None else default
    except Exception:
        return default


def _agent_id_from_step_name(step_name: str) -> str:
    if "-" in step_name:
        tail = step_name.split("-", 1)[1]
    else:
        tail = step_name
    if "." in tail:
        tail = tail.rsplit(".", 1)[0]
    return tail


def apply_loop_policies(step: StepRun, db: BaseDatabase, reason: str = "qa_failed") -> Optional[dict]:
    """
    Apply the first eligible loop policy attached to the step.

    Behavior:
    - Resets target step(s) to PENDING, starting from the computed target index.
    - Updates loop counters in runtime_state so repeated iterations are bounded.
    - Emits events so the console can surface loop decisions and limits.

    Returns a dict with details when a policy is applied, or None if no action was taken.
    """
    policies = _policy_list(step.policy)
    if not policies:
        return None

    for policy in policies:
        if (policy.get("behavior") or "").lower() != "loop":
            continue
        module_id = str(policy.get("module_id") or policy.get("id") or "loop")
        if not _conditions_allow(policy, reason):
            db.append_event(
                protocol_run_id=step.protocol_run_id,
                step_run_id=step.id,
                event_type="loop_condition_skipped",
                message=f"Loop policy {module_id} skipped; condition not met.",
                metadata={"policy": policy, "reason": reason, "conditions": _normalized_conditions(policy)},
            )
            log.info(
                "loop_condition_skipped",
                extra={
                    "protocol_run_id": step.protocol_run_id,
                    "step_run_id": step.id,
                    "module_id": module_id,
                    "reason": reason,
                },
            )
            continue
        max_iterations = policy.get("max_iterations")
        step_back = _coerce_int(policy.get("step_back"), 1)
        if step_back <= 0:
            step_back = 1
        skip_steps = set(policy.get("skip_steps") or [])

        state = dict(step.runtime_state or {})
        current_iterations = _loop_counts(state, module_id)
        if isinstance(max_iterations, (int, float)) and current_iterations >= int(max_iterations):
            db.append_event(
                protocol_run_id=step.protocol_run_id,
                step_run_id=step.id,
                event_type="loop_limit_reached",
                message=f"Loop limit reached for module {module_id}.",
                metadata={
                    "policy": policy,
                    "iterations": current_iterations,
                    "max_iterations": max_iterations,
                    "reason": reason,
                },
            )
            log.info(
                "loop_limit_reached",
                extra={
                    "protocol_run_id": step.protocol_run_id,
                    "step_run_id": step.id,
                    "module_id": module_id,
                    "iterations": current_iterations,
                    "max_iterations": max_iterations,
                },
            )
            continue

        target_index = max(0, step.step_index - step_back)
        while target_index in skip_steps and target_index > 0:
            target_index -= 1

        steps = sorted(db.list_step_runs(step.protocol_run_id), key=lambda s: s.step_index)
        to_reset: Sequence[StepRun] = [
            s for s in steps if s.step_index >= target_index and s.step_index not in skip_steps and s.status != StepStatus.CANCELLED
        ]
        loop_counts = dict(state.get("loop_counts") or {})
        loop_counts[module_id] = current_iterations + 1
        new_state: Dict[str, object] = dict(state)
        new_state["loop_counts"] = loop_counts
        new_state["last_action"] = "loop_step_back"
        new_state["last_policy_module_id"] = module_id
        new_state["last_target_step_index"] = target_index

        reset_indices: List[int] = []
        for s in to_reset:
            summary = f"Looped via {module_id} ({loop_counts[module_id]}/{max_iterations or '∞'})"
            runtime_state = new_state if s.id == step.id else None
            db.update_step_status(
                s.id,
                StepStatus.PENDING,
                summary=summary,
                runtime_state=runtime_state,
            )
            reset_indices.append(s.step_index)

        db.append_event(
            protocol_run_id=step.protocol_run_id,
            step_run_id=step.id,
            event_type="loop_decision",
            message=f"Looping back to step index {target_index} via module {module_id}.",
            metadata={
                "policy": policy,
                "runtime_state": new_state,
                "target_step_index": target_index,
                "steps_reset": reset_indices,
                "iterations": loop_counts[module_id],
                "max_iterations": max_iterations,
                "reason": reason,
            },
        )
        log.info(
            "loop_decision",
            extra={
                "protocol_run_id": step.protocol_run_id,
                "step_run_id": step.id,
                "module_id": module_id,
                "target_index": target_index,
                "iterations": loop_counts[module_id],
            },
        )
        return {
            "applied": True,
            "policy": policy,
            "target_step_index": target_index,
            "steps_reset": reset_indices,
            "iterations": loop_counts[module_id],
            "max_iterations": max_iterations,
            "runtime_state": new_state,
            "reason": reason,
        }

    return None


def apply_trigger_policies(step: StepRun, db: BaseDatabase, reason: str = "qa_passed") -> Optional[dict]:
    """
    Apply the first eligible trigger policy attached to the step.

    Behavior:
    - Finds the target agent/step by agent id.
    - Marks the target step as pending (if not terminal) and records runtime_state.
    - Emits trigger events for observability, including skips/missing targets.
    """
    policies = _policy_list(step.policy)
    if not policies:
        return None

    source_state = step.runtime_state or {}
    source_depth = 0
    try:
        source_depth = int(source_state.get("inline_trigger_depth", 0)) if isinstance(source_state, dict) else 0
    except Exception:
        source_depth = 0
    inline_depth = source_depth + 1

    steps = db.list_step_runs(step.protocol_run_id)
    steps_by_agent: Dict[str, Tuple[int, StepRun]] = {
        _agent_id_from_step_name(s.step_name): (s.step_index, s) for s in steps
    }

    for policy in policies:
        if (policy.get("behavior") or "").lower() != "trigger":
            continue
        module_id = str(policy.get("module_id") or policy.get("id") or "trigger")
        if not _conditions_allow(policy, reason):
            db.append_event(
                protocol_run_id=step.protocol_run_id,
                step_run_id=step.id,
                event_type="trigger_condition_skipped",
                message=f"Trigger policy {module_id} skipped; condition not met.",
                metadata={"policy": policy, "reason": reason, "conditions": _normalized_conditions(policy)},
            )
            log.info(
                "trigger_condition_skipped",
                extra={
                    "protocol_run_id": step.protocol_run_id,
                    "step_run_id": step.id,
                    "module_id": module_id,
                    "reason": reason,
                },
            )
            continue
        target_agent = policy.get("trigger_agent_id") or policy.get("target_agent_id") or policy.get("targetAgentId")
        if not target_agent:
            continue

        target_entry = steps_by_agent.get(str(target_agent))
        if not target_entry:
            db.append_event(
                protocol_run_id=step.protocol_run_id,
                step_run_id=step.id,
                event_type="trigger_missing_target",
                message=f"Trigger target agent {target_agent} not found.",
                metadata={"policy": policy, "reason": reason},
            )
            continue

        target_index, target_step = target_entry
        if target_step.status in (StepStatus.COMPLETED, StepStatus.CANCELLED):
            db.append_event(
                protocol_run_id=step.protocol_run_id,
                step_run_id=step.id,
                event_type="trigger_skipped",
                message=f"Trigger skipped; target {target_agent} already terminal.",
                metadata={"policy": policy, "target_status": target_step.status, "reason": reason},
            )
            continue

        new_state = dict(target_step.runtime_state or {})
        new_state["last_triggered_by"] = step.step_name
        new_state["inline_trigger_depth"] = inline_depth
        db.update_step_status(
            target_step.id,
            StepStatus.PENDING,
            summary=f"Triggered by {step.step_name}",
            runtime_state=new_state,
        )
        db.append_event(
            protocol_run_id=step.protocol_run_id,
            step_run_id=step.id,
            event_type="trigger_decision",
            message=f"Triggering agent {target_agent} via policy on {step.step_name}.",
            metadata={
                "policy": policy,
                "reason": reason,
                "target_step_index": target_index,
                "target_step_id": target_step.id,
                "inline_depth": inline_depth,
            },
        )
        log.info(
            "trigger_decision",
            extra={
                "protocol_run_id": step.protocol_run_id,
                "step_run_id": step.id,
                "target_agent": target_agent,
                "target_index": target_index,
                "inline_depth": inline_depth,
            },
        )
        return {
            "applied": True,
            "policy": policy,
            "target_step_index": target_index,
            "target_step_id": target_step.id,
            "reason": reason,
            "inline_depth": inline_depth,
        }

    return None
