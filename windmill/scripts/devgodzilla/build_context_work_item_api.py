"""
Build Work Item Context (DevGodzilla API)

Refresh the ContextPack for a task-cycle work item.
"""

from __future__ import annotations

from typing import Any, Dict

from ._api import api_json


def main(work_item_id: int, refresh: bool = False) -> Dict[str, Any]:
    return api_json("POST", f"/work-items/{work_item_id}/build-context", body={"refresh": bool(refresh)})
