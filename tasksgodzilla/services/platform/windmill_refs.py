from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse


@dataclass(frozen=True)
class WindmillJobRef:
    job_id: str
    resource: str  # logs | result | error
    name: Optional[str] = None


def parse_windmill_job_ref(value: str) -> Optional[WindmillJobRef]:
    """
    Parse a Windmill reference encoded as a URI.

    Supported forms:
    - windmill://job/<job_id>
    - windmill://job/<job_id>/logs
    - windmill://job/<job_id>/result
    - windmill://job/<job_id>/error
    """
    if not value:
        return None
    if not value.startswith("windmill://"):
        return None
    parsed = urlparse(value)
    if parsed.scheme != "windmill" or parsed.netloc != "job":
        return None
    path = (parsed.path or "").lstrip("/")
    if not path:
        return None
    parts = [p for p in path.split("/") if p]
    job_id = parts[0]
    resource = "logs"
    if len(parts) >= 2:
        resource = parts[1]
    if resource not in ("logs", "result", "error"):
        return None
    return WindmillJobRef(job_id=job_id, resource=resource)

