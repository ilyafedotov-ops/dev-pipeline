"""
DevGodzilla Bob Engine

Bob AI coding bot CLI-based engine adapter.
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


class BobEngine(CLIEngine):
    """
    Engine adapter for the Bob AI coding bot CLI.

    Uses `bob` command with appropriate model and sandbox settings.
    Supports planning, execution, and QA modes.

    Example:
        engine = BobEngine()
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
            default_model=default_model or os.environ.get("DEVGODZILLA_BOB_MODEL", "bob-default"),
        )

    @property
    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            id="bob",
            display_name="Bob AI Coding Bot",
            kind=EngineKind.CLI,
            default_model=self._default_model,
            description="Bob CLI-based AI coding bot",
            capabilities=["plan", "execute", "qa", "multi-file"],
        )

    def _get_command_name(self) -> str:
        return "bob"

    def _sandbox_to_bob(self, sandbox: SandboxMode) -> str:
        """Convert SandboxMode to Bob sandbox string."""
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
        """Build bob command."""
        model = self._get_model(req)

        cwd = Path(req.working_dir)
        bob_sandbox = self._sandbox_to_bob(sandbox)

        cmd = [
            "bob",
            "--cwd", str(cwd),
            "--sandbox", bob_sandbox,
        ]

        if model:
            cmd.extend(["--model", model])

        # Add optional parameters from extra
        extra = req.extra or {}

        if extra.get("auto_approve"):
            cmd.append("--auto-approve")

        if extra.get("rules_file"):
            cmd.extend(["--rules", str(extra["rules_file"])])

        if extra.get("context"):
            cmd.extend(["--context", str(extra["context"])])

        if extra.get("verbose"):
            cmd.append("--verbose")

        # Read from stdin
        cmd.append("-")

        return cmd

    def check_availability(self) -> bool:
        """
        Check if Bob CLI can run in this environment.

        In addition to the binary being present, Bob typically requires authentication.
        Set `DEVGODZILLA_ASSUME_AGENT_AUTH=1` to bypass the auth check.
        """
        if not super().check_availability():
            return False

        if os.environ.get("DEVGODZILLA_ASSUME_AGENT_AUTH", "").lower() in ("1", "true", "yes", "on"):
            return True

        return bool(os.environ.get("BOB_API_KEY") or os.environ.get("BOB_TOKEN"))


def register_bob_engine(*, default: bool = False) -> BobEngine:
    """
    Register BobEngine in the global registry.

    Returns the registered engine instance.
    """
    engine = BobEngine()
    register_engine(engine, default=default)
    return engine
