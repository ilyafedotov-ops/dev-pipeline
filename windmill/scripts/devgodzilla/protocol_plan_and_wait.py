"""
Protocol Plan (DevGodzilla API)

Triggers protocol planning in DevGodzilla and waits until it reaches a stable status.

Args:
    protocol_run_id: Protocol run ID
    timeout_seconds: Max time to wait for planning to finish
    poll_interval_ms: Poll interval for status checks
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict

from ._api import api_json
from . import emit_tasksgodzilla_codex_refs


def main(protocol_run_id: int, timeout_seconds: int = 300, poll_interval_ms: int = 500) -> Dict[str, Any]:
    if os.environ.get("WM_JOB_ID"):
        try:
            emit_tasksgodzilla_codex_refs.main(
                run_kind="devgodzilla.protocol_plan_and_wait",
                protocol_run_id=protocol_run_id,
            )
        except Exception:
            pass
    started = api_json("POST", f"/protocols/{protocol_run_id}/actions/start", body={})
    if started.get("error"):
        return started

    deadline = time.time() + max(1, int(timeout_seconds))
    last: Dict[str, Any] = {}
    while time.time() < deadline:
        last = api_json("GET", f"/protocols/{protocol_run_id}")
        if last.get("error"):
            return last

        status = (last.get("status") or "").lower()
        if status in {"planned", "running", "paused", "blocked", "failed", "cancelled", "completed"}:
            return {"protocol": last, "status": status}

        time.sleep(max(0.05, poll_interval_ms / 1000.0))

    return {"error": "Timeout waiting for protocol planning", "protocol": last}
