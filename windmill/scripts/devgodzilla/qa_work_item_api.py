"""
QA Work Item (DevGodzilla API)

Run QA gates for a task-cycle work item.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ._api import api_json


def main(work_item_id: int, gates: Optional[List[str]] = None) -> Dict[str, Any]:
    body: Dict[str, Any] = {}
    if gates:
        body["gates"] = gates
    return api_json("POST", f"/work-items/{work_item_id}/actions/qa", body=body)
