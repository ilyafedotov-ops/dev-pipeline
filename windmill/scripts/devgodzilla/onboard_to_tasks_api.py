"""
Onboard GitHub Repo → Spec → Plan → Tasks (DevGodzilla API)

Single-script alternative to the flow-based pipeline. This avoids Windmill JavaScript
`input_transforms` (which require `deno_core`) by performing the orchestration in Python.
"""

from __future__ import annotations

from typing import Any, Dict

from ._api import api_json


def _require_ok(step: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if payload.get("error"):
        raise RuntimeError(f"{step} failed: {payload.get('error')}")
    return payload


def main(
    git_url: str,
    project_name: str,
    branch: str = "main",
    description: str = "",
    constitution_content: str = "",
    feature_request: str = "",
    feature_name: str = "",
) -> Dict[str, Any]:
    created = _require_ok(
        "create_project",
        api_json(
            "POST",
            "/projects",
            body={
                "name": project_name,
                "git_url": git_url,
                "base_branch": branch or "main",
                "description": description or "",
                "auto_onboard": False,
                "auto_discovery": False,
            },
        ),
    )
    project_id = created.get("id")
    if not isinstance(project_id, int):
        raise RuntimeError("create_project failed: missing project id")

    onboard_body: Dict[str, Any] = {"branch": branch or None, "clone_if_missing": True}
    if constitution_content:
        onboard_body["constitution_content"] = constitution_content
    onboarded = _require_ok("onboard_project", api_json("POST", f"/projects/{project_id}/actions/onboard", body=onboard_body))

    if feature_request:
        spec = _require_ok(
            "speckit_specify",
            api_json(
                "POST",
                f"/projects/{project_id}/speckit/specify",
                body={k: v for k, v in {"description": feature_request, "feature_name": feature_name or None}.items() if v},
            ),
        )
        plan = _require_ok("speckit_plan", api_json("POST", f"/projects/{project_id}/speckit/plan", body={"spec_path": spec.get("spec_path")}))
        tasks = _require_ok("speckit_tasks", api_json("POST", f"/projects/{project_id}/speckit/tasks", body={"plan_path": plan.get("plan_path")}))
    else:
        spec = {}
        plan = {}
        tasks = {}

    return {
        "project_id": project_id,
        "create_project": created,
        "onboard_project": onboarded,
        "speckit_specify": spec,
        "speckit_plan": plan,
        "speckit_tasks": tasks,
    }
