"""
TasksGodzilla API Helpers (Windmill)

Thin HTTP wrapper used by Windmill scripts to call the TasksGodzilla API.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


def get_tasksgodzilla_api_base_url() -> str:
    return os.environ.get("TASKSGODZILLA_API_URL", "http://tasksgodzilla-api:8011").rstrip("/")


def get_tasksgodzilla_api_token() -> Optional[str]:
    return os.environ.get("TASKSGODZILLA_API_TOKEN")


def api_json(
    method: str,
    path: str,
    *,
    body: Optional[Dict[str, Any]] = None,
    timeout_seconds: int = 30,
) -> Dict[str, Any]:
    base = get_tasksgodzilla_api_base_url()
    url = f"{base}{path}"
    headers = {"Content-Type": "application/json"}
    token = get_tasksgodzilla_api_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8") if e.fp else ""
        try:
            payload = json.loads(raw) if raw else {"message": str(e)}
        except Exception:
            payload = {"message": raw or str(e)}
        return {"error": payload.get("detail") or payload.get("message") or str(e), "status_code": e.code}
    except Exception as e:
        return {"error": str(e)}

