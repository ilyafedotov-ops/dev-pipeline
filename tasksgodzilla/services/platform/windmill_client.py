from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import httpx


@dataclass(frozen=True)
class WindmillConfig:
    base_url: str
    token: str
    workspace: str = "starter"
    timeout_seconds: float = 30.0


class WindmillClient:
    def __init__(self, config: WindmillConfig) -> None:
        self._config = config
        self._client = httpx.Client(
            base_url=self._config.base_url.rstrip("/"),
            timeout=self._config.timeout_seconds,
            headers={"Authorization": f"Bearer {self._config.token}"},
        )

    def close(self) -> None:
        self._client.close()

    def _url(self, suffix: str) -> str:
        return f"/api/w/{self._config.workspace}{suffix}"

    def get_job(self, job_id: str) -> dict[str, Any]:
        resp = self._client.get(self._url(f"/jobs/get/{job_id}"))
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, dict) else {"value": data}

    def get_job_logs(self, job_id: str) -> str:
        resp = self._client.get(self._url(f"/jobs/get/{job_id}/logs"))
        resp.raise_for_status()
        return resp.text

    def try_get_job_logs(self, job_id: str) -> Optional[str]:
        try:
            return self.get_job_logs(job_id)
        except Exception:
            return None

