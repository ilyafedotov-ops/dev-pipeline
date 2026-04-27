"""
Implement Work Item (DevGodzilla API)

Run the owner implementation step for a task-cycle work item.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ._api import api_json


def main(work_item_id: int, owner_agent: Optional[str] = None) -> Dict[str, Any]:
    body: Dict[str, Any] = {}
    if owner_agent:
        body["owner_agent"] = owner_agent
    return api_json("POST", f"/work-items/{work_item_id}/actions/implement", body=body)
