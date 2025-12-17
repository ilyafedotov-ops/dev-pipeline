"""
Step Execute (DevGodzilla API)

Executes a single step via DevGodzilla API.

Args:
    step_run_id: Step run ID
"""

from __future__ import annotations

import os
from typing import Any, Dict

from ._api import api_json
from . import emit_tasksgodzilla_codex_refs


def main(step_run_id: int) -> Dict[str, Any]:
    if os.environ.get("WM_JOB_ID"):
        try:
            emit_tasksgodzilla_codex_refs.main(
                run_kind="devgodzilla.step_execute_api",
                step_run_id=step_run_id,
            )
        except Exception:
            pass
    return api_json("POST", f"/steps/{step_run_id}/actions/execute", body={})
