"""
SpecKit Implement (DevGodzilla API)

Initializes an implementation run by calling the DevGodzilla API.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ._api import api_json


def main(project_id: int, spec_path: Optional[str] = None, spec_run_id: Optional[int] = None) -> Dict[str, Any]:
    if not spec_path:
        return {"success": False, "error": f"spec_path is empty — project {project_id} may not be onboarded (no .specify dir or local_path)"}
    body: Dict[str, Any] = {"spec_path": spec_path}
    if spec_run_id is not None:
        body["spec_run_id"] = spec_run_id
    return api_json("POST", f"/projects/{project_id}/speckit/implement", body=body)
