"""
SpecKit Clarify (DevGodzilla API)

Appends clarifications to a SpecKit specification by calling the DevGodzilla API.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ._api import api_json


def main(
    project_id: int,
    spec_path: str,
    entries: Optional[List[Dict[str, str]]] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {"spec_path": spec_path}
    if entries is not None:
        body["entries"] = entries
    if notes:
        body["notes"] = notes
    return api_json("POST", f"/projects/{project_id}/speckit/clarify", body=body)
