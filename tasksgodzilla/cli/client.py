import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from tasksgodzilla.errors import TasksGodzillaError


class APIClientError(TasksGodzillaError):
    """Raised when the API returns an error response."""

    category = "api"
    retryable = False


@dataclass
class APIClient:
    base_url: str
    token: Optional[str] = None
    project_token: Optional[str] = None
    transport: Optional[httpx.BaseTransport] = None

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self.project_token:
            headers["X-Project-Token"] = self.project_token
        return headers

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = path if path.startswith("http") else path.lstrip("/")
        headers = self._headers()
        if self.transport and hasattr(self.transport, "handle_async_request"):
            try:
                import anyio  # type: ignore
            except ImportError as exc:  # pragma: no cover - missing optional dep
                raise APIClientError("anyio is required for async transports. Install anyio or run without custom transport.") from exc

            async def _do_request() -> httpx.Response:
                async with httpx.AsyncClient(
                    base_url=self.base_url.rstrip("/"),
                    headers=headers,
                    transport=self.transport,
                    timeout=20.0,
                ) as client:
                    return await client.request(method, url, **kwargs)

            resp = anyio.run(_do_request)
        else:
            with httpx.Client(
                base_url=self.base_url.rstrip("/"),
                headers=headers,
                transport=self.transport,
                timeout=20.0,
            ) as client:
                resp = client.request(method, url, **kwargs)
        if not resp.is_success:
            detail = resp.text
            try:
                data = resp.json()
                detail = data.get("detail") or detail
            except Exception:
                pass
            raise APIClientError(f"{resp.status_code} {resp.reason_phrase}: {detail}")
        return resp

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        resp = self.request("GET", path, params=params)
        return self._maybe_json(resp)

    def post(self, path: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        kwargs: Dict[str, Any] = {}
        if payload is not None:
            kwargs["json"] = payload
        resp = self.request("POST", path, **kwargs)
        return self._maybe_json(resp)

    @staticmethod
    def _maybe_json(resp: httpx.Response) -> Any:
        ctype = resp.headers.get("content-type", "")
        if "application/json" in ctype:
            return resp.json()
        try:
            return json.loads(resp.text)
        except Exception:
            return resp.text
