"""
DevGodzilla API Helpers (Windmill)

Thin HTTP wrapper used by Windmill scripts to call the DevGodzilla API.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


def get_devgodzilla_api_base_url() -> str:
    try:
        import wmill
        url = wmill.get_variable("g/all/devgodzilla_api_url")
        if url:
            return url.rstrip("/")
    except Exception:
        pass
    url = os.environ.get("DEVGODZILLA_API_URL")
    if url:
        return url.rstrip("/")
    return "http://devgodzilla-api:8000"


def api_json(
    method: str,
    path: str,
    *,
    body: Optional[Dict[str, Any]] = None,
    timeout_seconds: int = 30,
) -> Dict[str, Any]:
    # Guard against None values interpolated into URL path
    if "None" in path:
        return {"error": f"Invalid path parameter (None) in URL path: {path}", "status_code": 400}

    base = get_devgodzilla_api_base_url()
    url = f"{base}{path}"
    headers = {"Content-Type": "application/json"}

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
