"""
SpecKit Checklist (DevGodzilla API)

Generates a SpecKit checklist by calling the DevGodzilla API.
"""

from __future__ import annotations

from typing import Any, Dict

from ._api import api_json


def main(project_id: int, spec_path: str) -> Dict[str, Any]:
    return api_json("POST", f"/projects/{project_id}/speckit/checklist", body={"spec_path": spec_path})
