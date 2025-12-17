"""
Step Run QA (DevGodzilla API)

Runs QA gates for a single step via DevGodzilla API.

Args:
    step_run_id: Step run ID
    gates: Optional list of gate IDs (lint, type, test)
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from ._api import api_json
from . import emit_tasksgodzilla_codex_refs


def main(step_run_id: int, gates: Optional[List[str]] = None) -> Dict[str, Any]:
    if os.environ.get("WM_JOB_ID"):
        try:
            emit_tasksgodzilla_codex_refs.main(
                run_kind="devgodzilla.step_run_qa_api",
                step_run_id=step_run_id,
                params={"gates": gates} if gates else None,
            )
        except Exception:
            pass
    payload: Dict[str, Any] = {}
    if gates:
        payload["gates"] = gates
    return api_json("POST", f"/steps/{step_run_id}/actions/qa", body=payload)
