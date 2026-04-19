"""
DevGodzilla Roo Engine

Roo AI coding agent CLI engine adapter.
"""

import os
import shutil
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


class RooEngine(CLIEngine):
    """
    Engine adapter for the Roo CLI.

    Uses `roo` (or `roo-cli`) command with appropriate model and sandbox settings.
    Supports planning, execution, and QA modes.

    Example:
        engine = RooEngine()
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
            default_model=default_model or os.environ.get("DEVGODZILLA_ROO_MODEL", "roo-default"),
        )
        self._cli_name: Optional[str] = None

    @property
    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            id="roo",
            display_name="Roo CLI",
            kind=EngineKind.CLI,
            default_model=self._default_model,
            description="Roo AI coding agent CLI",
            capabilities=["plan", "execute", "qa", "multi-file"],
        )

    def _get_command_name(self) -> str:
        """Return the CLI command name, preferring 'roo' but falling back to 'roo-cli'."""
        if self._cli_name is not None:
            return self._cli_name
        if shutil.which("roo"):
            self._cli_name = "roo"
        elif shutil.which("roo-cli"):
            self._cli_name = "roo-cli"
        else:
            self._cli_name = "roo"
        return self._cli_name

    def _sandbox_to_roo(self, sandbox: SandboxMode) -> str:
        """Convert SandboxMode to Roo sandbox string."""
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
        """Build roo command."""
        model = self._get_model(req)

        cwd = Path(req.working_dir)
        roo_sandbox = self._sandbox_to_roo(sandbox)
        cmd_name = self._get_command_name()

        cmd = [
            cmd_name,
            "--cwd", str(cwd),
            "--sandbox", roo_sandbox,
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
        Check if Roo CLI can run in this environment.

        Tries both `roo` and `roo-cli` command names.
        Set `DEVGODZILLA_ASSUME_AGENT_AUTH=***` to bypass the auth check.
        """
        # Reset cached CLI name so we re-discover
        self._cli_name = None

        if shutil.which("roo") or shutil.which("roo-cli"):
            if os.environ.get("DEVGODZILLA_ASSUME_AGENT_AUTH", "").lower() in ("1", "true", "yes", "on"):
                return True
            return bool(os.environ.get("ROO_API_KEY") or os.environ.get("ROO_TOKEN"))

        return False


def register_roo_engine(*, default: bool = False) -> RooEngine:
    """
    Register RooEngine in the global registry.

    Returns the registered engine instance.
    """
    engine = RooEngine()
    register_engine(engine, default=default)
    return engine
