"""
DevGodzilla SHAI Engine

SHAI AI assistant CLI-based engine adapter.
"""

import os
from pathlib import Path
from typing import List, Optional

from devgodzilla.engines.interface import (
    EngineKind,
    EngineMetadata,
    EngineRequest,
    EngineResult,
    SandboxMode,
)
from devgodzilla.engines.cli_adapter import CLIEngine
from devgodzilla.engines.registry import register_engine
from devgodzilla.logging import get_logger

logger = get_logger(__name__)


class SHAIEngine(CLIEngine):
    """
    Engine adapter for the SHAI AI assistant CLI.

    Uses `shai` command with appropriate model and sandbox settings.
    Supports planning, execution, and QA modes.

    Example:
        engine = SHAIEngine()
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
            default_model=default_model or os.environ.get("DEVGODZILLA_SHAI_MODEL", "shai-default"),
        )

    @property
    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            id="shai",
            display_name="SHAI AI Assistant",
            kind=EngineKind.CLI,
            default_model=self._default_model,
            description="SHAI CLI-based AI assistant for code generation",
            capabilities=["plan", "execute", "qa", "multi-file"],
        )

    def _get_command_name(self) -> str:
        return "shai"

    def _sandbox_to_shai(self, sandbox: SandboxMode) -> str:
        """Convert SandboxMode to SHAI sandbox string."""
        mapping = {
            SandboxMode.FULL_ACCESS: "full-access",
            SandboxMode.WORKSPACE_WRITE: "workspace-write",
            SandboxMode.READ_ONLY: "read-only",
        }
        return mapping.get(sandbox, "workspace-write")

    def _build_command(
        self,
        req: EngineRequest,
        sandbox: SandboxMode,
    ) -> List[str]:
        """Build shai command."""
        model = self._get_model(req)

        cwd = Path(req.working_dir)
        shai_sandbox = self._sandbox_to_shai(sandbox)

        cmd = [
            "shai",
            "--cwd", str(cwd),
            "--sandbox", shai_sandbox,
        ]

        if model:
            cmd.extend(["--model", model])

        # Add optional parameters from extra
        extra = req.extra or {}

        if extra.get("auto_approve"):
            cmd.append("--auto-approve")

        if extra.get("config"):
            cmd.extend(["--config", str(extra["config"])])

        if extra.get("context"):
            cmd.extend(["--context", str(extra["context"])])

        if extra.get("verbose"):
            cmd.append("--verbose")

        # Read from stdin
        cmd.append("-")

        return cmd

    def check_availability(self) -> bool:
        """
        Check if SHAI CLI can run in this environment.

        In addition to the binary being present, SHAI typically requires authentication.
        Set `DEVGODZILLA_ASSUME_AGENT_AUTH=1` to bypass the auth check.
        """
        if not super().check_availability():
            return False

        if os.environ.get("DEVGODZILLA_ASSUME_AGENT_AUTH", "").lower() in ("1", "true", "yes", "on"):
            return True

        return bool(os.environ.get("SHAI_API_KEY") or os.environ.get("SHAI_TOKEN"))


def register_shai_engine(*, default: bool = False) -> SHAIEngine:
    """
    Register SHAIEngine in the global registry.

    Returns the registered engine instance.
    """
    engine = SHAIEngine()
    register_engine(engine, default=default)
    return engine
