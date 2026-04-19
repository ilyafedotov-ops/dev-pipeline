"""
DevGodzilla Kilo Engine

Kilo lightweight CLI engine adapter.
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


class KiloEngine(CLIEngine):
    """
    Engine adapter for the Kilo CLI.

    Uses `kilo` command with appropriate model and sandbox settings.
    Supports planning, execution, and QA modes.

    Example:
        engine = KiloEngine()
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
            default_model=default_model or os.environ.get("DEVGODZILLA_KILO_MODEL", "kilo-default"),
        )

    @property
    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            id="kilo",
            display_name="Kilo CLI",
            kind=EngineKind.CLI,
            default_model=self._default_model,
            description="Kilo lightweight CLI for code generation",
            capabilities=["plan", "execute", "qa", "multi-file"],
        )

    def _get_command_name(self) -> str:
        return "kilo"

    def _sandbox_to_kilo(self, sandbox: SandboxMode) -> str:
        """Convert SandboxMode to Kilo sandbox string."""
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
        """Build kilo command."""
        model = self._get_model(req)

        cwd = Path(req.working_dir)
        kilo_sandbox = self._sandbox_to_kilo(sandbox)

        cmd = [
            "kilo",
            "--cwd", str(cwd),
            "--sandbox", kilo_sandbox,
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
        Check if Kilo CLI can run in this environment.

        In addition to the binary being present, Kilo typically requires authentication.
        Set `DEVGODZILLA_ASSUME_AGENT_AUTH=***` to bypass the auth check.
        """
        if not super().check_availability():
            return False

        if os.environ.get("DEVGODZILLA_ASSUME_AGENT_AUTH", "").lower() in ("1", "true", "yes", "on"):
            return True

        return bool(os.environ.get("KILO_API_KEY") or os.environ.get("KILO_TOKEN"))


def register_kilo_engine(*, default: bool = False) -> KiloEngine:
    """
    Register KiloEngine in the global registry.

    Returns the registered engine instance.
    """
    engine = KiloEngine()
    register_engine(engine, default=default)
    return engine
