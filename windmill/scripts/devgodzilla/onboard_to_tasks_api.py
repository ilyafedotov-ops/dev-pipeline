"""
Onboard GitHub Repo → Spec → Plan → Tasks (DevGodzilla API)

Thin adapter that delegates orchestration to the backend.
"""

from __future__ import annotations

from typing import Any, Dict

from ._api import api_json


def main(
    git_url: str,
    project_name: str,
    branch: str = "main",
    description: str = "",
    constitution_content: str = "",
    feature_request: str = "",
    feature_name: str = "",
    clarification_entries: list[dict[str, str]] | None = None,
    clarification_notes: str = "",
    run_discovery_agent: bool = False,
    discovery_pipeline: bool = True,
    discovery_engine_id: str = "",
    discovery_model: str = "",
    clone_if_missing: bool = True,
) -> Dict[str, Any]:
    return api_json(
        "POST",
        "/projects/actions/onboard-to-tasks",
        body={
            "git_url": git_url,
            "project_name": project_name,
            "branch": branch or "main",
            "description": description or "",
            "constitution_content": constitution_content or "",
            "feature_request": feature_request or "",
            "feature_name": feature_name or "",
            "clarification_entries": clarification_entries or [],
            "clarification_notes": clarification_notes or "",
            "run_discovery_agent": bool(run_discovery_agent),
            "discovery_pipeline": bool(discovery_pipeline),
            "discovery_engine_id": discovery_engine_id or "",
            "discovery_model": discovery_model or "",
            "clone_if_missing": bool(clone_if_missing),
        },
    )
