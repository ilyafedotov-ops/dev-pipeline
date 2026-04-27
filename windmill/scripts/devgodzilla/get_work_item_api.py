"""
Get Work Item (DevGodzilla API)

Fetch a single projected task-cycle work item by id.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ._api import api_json


def main(work_item_id: Optional[int] = None) -> Dict[str, Any]:
    if not work_item_id:
        return {"work_item": None, "error": None}

    payload = api_json("GET", f"/work-items/{work_item_id}")
    if payload.get("error"):
        return {"work_item": None, "error": payload["error"], "status_code": payload.get("status_code")}
    return {"work_item": payload, "error": None}
