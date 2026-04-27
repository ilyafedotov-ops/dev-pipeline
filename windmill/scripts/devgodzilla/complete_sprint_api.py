"""
Complete Sprint (DevGodzilla API)

Thin adapter that delegates to the DevGodzilla sprint-complete endpoint.
"""

from __future__ import annotations

from typing import Any, Dict

from ._api import api_json


def main(sprint_id: int) -> Dict[str, Any]:
    """Complete a sprint and finalize metrics."""
    return api_json("POST", f"/sprints/{sprint_id}/actions/complete", body={})
