"""
SpecKit Analyze (DevGodzilla API)

Generates an analysis report by calling the DevGodzilla API.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ._api import api_json


def main(
    project_id: int,
    spec_path: str,
    plan_path: Optional[str] = None,
    tasks_path: Optional[str] = None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {"spec_path": spec_path}
    if plan_path:
        body["plan_path"] = plan_path
    if tasks_path:
        body["tasks_path"] = tasks_path
    return api_json("POST", f"/projects/{project_id}/speckit/analyze", body=body)
