"""
DevGodzilla Qoder Engine

Qoder CLI engine adapter.
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


class QoderEngine(CLIEngine):
    """
    Engine adapter for the Qoder CLI.
    
    Uses `qoder` command with appropriate model and sandbox settings.
    Supports planning, execution, and QA modes.
    
    Command directory: `.qoder/commands/`
    Format: markdown
    
    Example:
        engine = QoderEngine(default_model="qoder-default")
        result = engine.execute(request)
    """

    def __init__(
        self,
        *,
        default_timeout: int = 180,
        default_model: Optional[str] = None,
    ) -> None:
        super().__init__(
            default_timeout=default_timeout,
            default_model=default_model or os.environ.get("DEVGODZILLA_QODER_MODEL", "qoder-default"),
        )

    @property
    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            id="qoder",
            display_name="Qoder CLI",
            kind=EngineKind.CLI,
            default_model=self._default_model,
            description="Qoder CLI for code generation",
            capabilities=["plan", "execute", "qa", "multi-file"],
        )

    def _get_command_name(self) -> str:
        return "qoder"

    def _build_command(
        self,
        req: EngineRequest,
        sandbox: SandboxMode,
    ) -> List[str]:
        """Build qoder command."""
        model = self._get_model(req)
        
        cwd = Path(req.working_dir)
        
        cmd = [
            "qoder",
            "--cwd", str(cwd),
        ]
        
        if model:
            cmd.extend(["--model", model])
        
        # Add optional parameters from extra
        extra = req.extra or {}
        
        if extra.get("sandbox") or sandbox != SandboxMode.WORKSPACE_WRITE:
            sandbox_arg = {
                SandboxMode.FULL_ACCESS: "full-access",
                SandboxMode.WORKSPACE_WRITE: "workspace-write",
                SandboxMode.READ_ONLY: "read-only",
            }.get(sandbox, "workspace-write")
            cmd.extend(["--sandbox", sandbox_arg])
        
        if extra.get("no_confirm"):
            cmd.append("--no-confirm")
        
        if extra.get("command_file"):
            cmd.extend(["--file", str(extra["command_file"])])
        
        # Read from stdin
        cmd.append("-")
        
        return cmd

    def check_availability(self) -> bool:
        """
        Check if Qoder CLI can run in this environment.

        In addition to the binary being present, Qoder typically requires authentication.
        Set `DEVGODZILLA_ASSUME_AGENT_AUTH=true` to bypass the auth check.
        """
        if not super().check_availability():
            return False

        if os.environ.get("DEVGODZILLA_ASSUME_AGENT_AUTH", "").lower() in ("1", "true", "yes", "on"):
            return True

        # Qoder may use various auth methods
        return bool(os.environ.get("QODER_API_KEY") or os.environ.get("QODER_TOKEN"))


def register_qoder_engine(*, default: bool = False) -> QoderEngine:
    """
    Register QoderEngine in the global registry.
    
    Returns the registered engine instance.
    """
    engine = QoderEngine()
    register_engine(engine, default=default)
    return engine
