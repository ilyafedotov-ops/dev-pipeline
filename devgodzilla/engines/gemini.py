"""
DevGodzilla Gemini CLI Engine

Engine adapter for Google Gemini CLI tool.
"""

import os
from pathlib import Path
from typing import List, Optional

from devgodzilla.logging import get_logger
from devgodzilla.engines.interface import (
    EngineKind,
    EngineMetadata,
    EngineRequest,
    EngineResult,
    SandboxMode,
)
from devgodzilla.engines.cli_adapter import CLIEngine
from devgodzilla.engines.registry import register_engine

logger = get_logger(__name__)


class GeminiEngine(CLIEngine):
    """
    Engine adapter for the Google Gemini CLI.

    Uses the `gemini` CLI tool to execute coding tasks.
    Supports multimodal inputs and long context.

    Example:
        engine = GeminiEngine(default_model="gemini-2.5-pro")
        result = engine.execute(request)
    """

    def __init__(
        self,
        *,
        default_timeout: int = 300,
        default_model: Optional[str] = None,
    ) -> None:
        super().__init__(
            default_timeout=default_timeout,
            default_model=default_model or os.environ.get(
                "DEVGODZILLA_GEMINI_MODEL", "gemini-2.5-pro"
            ),
        )

    @property
    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            id="gemini-cli",
            display_name="Gemini CLI",
            kind=EngineKind.CLI,
            default_model=self._default_model,
            description="Google Gemini CLI for code generation and review",
            capabilities=[
                "plan", "execute", "qa", "multi-file",
                "multimodal", "long-context",
            ],
        )

    def _get_command_name(self) -> str:
        return "gemini"

    def _build_command(
        self,
        req: EngineRequest,
        sandbox: SandboxMode,
    ) -> List[str]:
        """Build gemini CLI command."""
        model = self._get_model(req)
        cwd = Path(req.working_dir)

        cmd = [
            "gemini",
        ]

        if model:
            cmd.extend(["--model", model])

        # Sandbox mapping – gemini CLI may not have direct equivalents,
        # but we pass a sandbox-hint flag if supported by the tool.
        extra = req.extra or {}

        if extra.get("gemini_flags"):
            cmd.extend(extra["gemini_flags"])

        # Read prompt from stdin
        cmd.append("-")

        return cmd

    def check_availability(self) -> bool:
        """Check if Gemini CLI is available."""
        if not super().check_availability():
            return False

        if os.environ.get("DEVGODZILLA_ASSUME_AGENT_AUTH", "").lower() in (
            "1", "true", "yes", "on",
        ):
            return True

        home = Path.home()
        oauth_creds = home / ".gemini" / "oauth_creds.json"
        google_accounts = home / ".gemini" / "google_accounts.json"
        adc_default = home / ".config" / "gcloud" / "application_default_credentials.json"
        explicit_adc = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

        return bool(
            os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
            or oauth_creds.exists()
            or google_accounts.exists()
            or adc_default.exists()
            or (explicit_adc and Path(explicit_adc).expanduser().exists())
        )


def register_gemini_engine(*, default: bool = False) -> GeminiEngine:
    """
    Register GeminiEngine in the global registry.

    Returns the registered engine instance.
    """
    engine = GeminiEngine()
    register_engine(engine, default=default)
    return engine
