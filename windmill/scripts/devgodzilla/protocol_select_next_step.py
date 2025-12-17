"""
Protocol Select Next Step (DevGodzilla API)

Selects the next runnable step for a protocol.

Args:
    protocol_run_id: Protocol run ID

Returns:
    step_run_id: Next step ID or null
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from ._api import api_json
from . import emit_tasksgodzilla_codex_refs


def main(protocol_run_id: int) -> Dict[str, Any]:
    if os.environ.get("WM_JOB_ID"):
        try:
            emit_tasksgodzilla_codex_refs.main(
                run_kind="devgodzilla.protocol_select_next_step",
                protocol_run_id=protocol_run_id,
            )
        except Exception:
            pass
    res = api_json("POST", f"/protocols/{protocol_run_id}/actions/run_next_step", body={})
    if res.get("error"):
        return res
    step_run_id: Optional[int] = res.get("step_run_id")
    return {"step_run_id": step_run_id}
