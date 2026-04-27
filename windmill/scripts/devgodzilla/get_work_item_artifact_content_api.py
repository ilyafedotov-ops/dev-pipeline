"""
Get Work Item Artifact Content (DevGodzilla API)

Reads task-cycle artifact content for a projected work item.
"""

from __future__ import annotations

from typing import Any, Dict

from ._api import api_json


def main(
    work_item_id: int,
    artifact_key: str,
    max_bytes: int = 200_000,
) -> Dict[str, Any]:
    return api_json(
        "GET",
        f"/work-items/{work_item_id}/artifacts/{artifact_key}/content?max_bytes={max(1, int(max_bytes))}",
    )
