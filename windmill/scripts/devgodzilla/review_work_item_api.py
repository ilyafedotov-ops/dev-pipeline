"""
Review Work Item (DevGodzilla API)

Run the review stage for a task-cycle work item.
"""

from __future__ import annotations

from typing import Any, Dict

from ._api import api_json


def main(work_item_id: int) -> Dict[str, Any]:
    return api_json("POST", f"/work-items/{work_item_id}/actions/review", body={})
