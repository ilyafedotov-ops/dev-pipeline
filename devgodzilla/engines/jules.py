"""
DevGodzilla Jules Engine

Google Jules AI coding agent API-based engine adapter.
"""

import os
from typing import Any, Dict, Optional

from devgodzilla.engines.api_engine import (
    APIEngine,
    APIRequestConfig,
    APIResponse,
)
from devgodzilla.engines.interface import (
    EngineKind,
    EngineMetadata,
    EngineRequest,
    EngineResult,
    SandboxMode,
)
from devgodzilla.engines.registry import register_engine
from devgodzilla.logging import get_logger

logger = get_logger(__name__)


class JulesEngine(APIEngine):
    """
    Engine adapter for Google Jules AI coding agent (API-based).

    Uses the Google Jules API endpoint for code generation tasks.
    Supports planning, execution, and QA modes via HTTP requests.

    Example:
        engine = JulesEngine()
        result = engine.execute(request)
    """

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        default_timeout: int = 300,
        max_retries: int = 3,
    ) -> None:
        env_base = base_url or os.environ.get(
            "DEVGODZILLA_JULES_BASE_URL", "https://jules.google/api/v1"
        )
        env_key = api_key or os.environ.get("JULES_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        super().__init__(
            base_url=env_base,
            api_key=env_key,
            default_timeout=default_timeout,
            max_retries=max_retries,
        )
        self._default_model = default_model or os.environ.get(
            "DEVGODZILLA_JULES_MODEL", "jules-default"
        )

    @property
    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            id="jules",
            display_name="Google Jules",
            kind=EngineKind.API,
            default_model=self._default_model,
            description="Google Jules AI coding agent via API",
            capabilities=["plan", "execute", "qa", "multi-file"],
        )

    def _build_request_config(
        self,
        req: EngineRequest,
        sandbox: SandboxMode,
    ) -> APIRequestConfig:
        """Build API request configuration for Jules."""
        base = self._base_url or "https://jules.google/api/v1"
        return APIRequestConfig(
            endpoint=f"{base.rstrip('/')}/execute",
            method="POST",
            headers={
                "X-Jules-Sandbox": sandbox.value,
            },
            timeout=req.timeout or self._default_timeout,
            retries=self._max_retries,
        )

    def _build_request_body(
        self,
        req: EngineRequest,
        sandbox: SandboxMode,
    ) -> Dict[str, Any]:
        """Build request body for Jules API."""
        prompt_text = self.get_prompt_text(req)

        return {
            "prompt": prompt_text,
            "model": req.model or self._default_model,
            "sandbox": sandbox.value,
            "working_dir": req.working_dir,
            "extra": req.extra,
        }

    def _parse_response(
        self,
        response: APIResponse,
        req: EngineRequest,
    ) -> EngineResult:
        """Parse Jules API response into EngineResult."""
        if not response.success:
            return EngineResult(
                success=False,
                error=response.error or "Jules API request failed",
            )

        if not response.data:
            return EngineResult(
                success=False,
                error="Empty response from Jules API",
            )

        try:
            output = response.data.get("output", "")
            error = response.data.get("error")
            success = response.data.get("success", True)
            usage = response.data.get("usage", {})

            return EngineResult(
                success=success and not error,
                stdout=output,
                stderr="",
                error=error,
                tokens_used=usage.get("total_tokens"),
                cost_cents=usage.get("cost_cents"),
                metadata={
                    "model": response.data.get("model"),
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                },
            )

        except Exception as e:
            return EngineResult(
                success=False,
                error=f"Failed to parse Jules API response: {e}",
            )

    def check_availability(self) -> bool:
        """Check if Jules API is available (requires API key and base URL)."""
        if not self._api_key:
            return False
        return super().check_availability()


def register_jules_engine(*, default: bool = False) -> JulesEngine:
    """
    Register JulesEngine in the global registry.

    Returns the registered engine instance.
    """
    engine = JulesEngine()
    register_engine(engine, default=default)
    return engine
