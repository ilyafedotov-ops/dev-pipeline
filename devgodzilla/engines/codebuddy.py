"""
DevGodzilla CodeBuddy Engine

CodeBuddy CLI engine adapter.
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


class CodeBuddyEngine(CLIEngine):
    """
    Engine adapter for the CodeBuddy CLI.

    Uses `codebuddy` command with appropriate model and sandbox settings.
    Supports planning, execution, and QA modes.

    Example:
        engine = CodeBuddyEngine()
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
            default_model=default_model or os.environ.get("DEVGODZILLA_CODEBUDDY_MODEL", "codebuddy-default"),
        )

    @property
    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            id="codebuddy",
            display_name="CodeBuddy CLI",
            kind=EngineKind.CLI,
            default_model=self._default_model,
            description="CodeBuddy CLI for code generation and assistance",
            capabilities=["plan", "execute", "qa", "multi-file"],
        )

    def _get_command_name(self) -> str:
        return "codebuddy"

    def _sandbox_to_codebuddy(self, sandbox: SandboxMode) -> str:
        """Convert SandboxMode to CodeBuddy sandbox string."""
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
        """Build codebuddy command."""
        model = self._get_model(req)

        cwd = Path(req.working_dir)
        codebuddy_sandbox = self._sandbox_to_codebuddy(sandbox)

        cmd = [
            "codebuddy",
            "--cwd", str(cwd),
            "--sandbox", codebuddy_sandbox,
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

        # Read from stdin
        cmd.append("-")

        return cmd

    def check_availability(self) -> bool:
        """
        Check if CodeBuddy CLI can run in this environment.

        In addition to the binary being present, CodeBuddy typically requires authentication.
        Set `DEVGODZILLA_ASSUME_AGENT_AUTH=***` to bypass the auth check.
        """
        if not super().check_availability():
            return False

        if os.environ.get("DEVGODZILLA_ASSUME_AGENT_AUTH", "").lower() in ("1", "true", "yes", "on"):
            return True

        return bool(os.environ.get("CODEBUDDY_API_KEY") or os.environ.get("CODEBUDDY_TOKEN"))


def register_codebuddy_engine(*, default: bool = False) -> CodeBuddyEngine:
    """
    Register CodeBuddyEngine in the global registry.

    Returns the registered engine instance.
    """
    engine = CodeBuddyEngine()
    register_engine(engine, default=default)
    return engine
