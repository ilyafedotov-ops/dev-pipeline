"""
Emit TasksGodzilla Codex run refs (Windmill)

Registers/updates a Codex run in TasksGodzilla so the web UI can:
- stream logs from Windmill via `windmill://job/<job_id>/logs`
- preview job result/error via artifacts with `windmill://job/<job_id>/{result,error}`

This script is safe to call multiple times (idempotent upserts).
"""

from __future__ import annotations

import os
from typing import Any, Optional

from ._tasksgodzilla_api import api_json


def _wm_job_id() -> str:
    job_id = os.environ.get("WM_JOB_ID")
    if not job_id:
        raise RuntimeError("WM_JOB_ID not set (this script must run inside Windmill)")
    return job_id


def main(
    *,
    run_id: Optional[str] = None,
    job_type: str = "windmill",
    run_kind: Optional[str] = None,
    project_id: Optional[int] = None,
    protocol_run_id: Optional[int] = None,
    step_run_id: Optional[int] = None,
    params: Optional[dict[str, Any]] = None,
    attach_default_artifacts: bool = True,
) -> dict:
    wm_job_id = _wm_job_id()
    effective_run_id = run_id or wm_job_id

    log_ref = f"windmill://job/{wm_job_id}/logs"
    result_ref = f"windmill://job/{wm_job_id}/result"
    error_ref = f"windmill://job/{wm_job_id}/error"

    run_payload: dict[str, Any] = {
        "job_type": job_type,
        "run_id": effective_run_id,
        "log_path": log_ref,
    }
    if run_kind is not None:
        run_payload["run_kind"] = run_kind
    if project_id is not None:
        run_payload["project_id"] = project_id
    if protocol_run_id is not None:
        run_payload["protocol_run_id"] = protocol_run_id
    if step_run_id is not None:
        run_payload["step_run_id"] = step_run_id
    if params is not None:
        run_payload["params"] = params

    run_resp = api_json("POST", "/codex/runs/start", body=run_payload)
    if run_resp.get("error"):
        return {"status": "error", "stage": "run_start", "response": run_resp}

    artifacts = []
    if attach_default_artifacts:
        for name, kind, path in (
            ("windmill.logs", "log", log_ref),
            ("windmill.result", "result", result_ref),
            ("windmill.error", "error", error_ref),
        ):
            resp = api_json(
                "POST",
                f"/codex/runs/{effective_run_id}/artifacts/upsert",
                body={"name": name, "kind": kind, "path": path},
            )
            artifacts.append(resp)

    return {
        "status": "ok",
        "run_id": effective_run_id,
        "windmill_job_id": wm_job_id,
        "log_path": log_ref,
        "artifacts": artifacts,
    }

