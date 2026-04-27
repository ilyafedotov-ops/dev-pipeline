from __future__ import annotations

from typing import Any

import httpx

from devgodzilla.hermes_bridge.config import BridgeConfig


class DevGodzillaBridgeError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 500, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details or {}


class DevGodzillaClient:
    def __init__(self, config: BridgeConfig) -> None:
        self.config = config

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.config.devgodzilla_api_token:
            headers["Authorization"] = f"Bearer {self.config.devgodzilla_api_token}"
        return headers

    def request(self, method: str, path: str, *, json: dict[str, Any] | None = None) -> Any:
        url = f"{self.config.devgodzilla_base_url}{path}"
        try:
            response = httpx.request(
                method,
                url,
                headers=self._headers(),
                json=json,
                timeout=self.config.timeout_seconds,
            )
        except httpx.RequestError as exc:
            raise DevGodzillaBridgeError(
                "DevGodzilla upstream unavailable",
                status_code=503,
                details={"reason": str(exc), "url": url},
            ) from exc

        if response.is_error:
            detail: Any
            try:
                detail = response.json()
            except ValueError:
                detail = {"detail": response.text}
            raise DevGodzillaBridgeError(
                f"DevGodzilla upstream error {response.status_code}",
                status_code=response.status_code,
                details={"upstream": detail, "url": url},
            )

        if not response.content:
            return None
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()
        return {"content": response.text}

