"""
DevGodzilla Auggie Engine

Auggie (Augment) CLI engine adapter.
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


class AuggieEngine(CLIEngine):
    """
    Engine adapter for the Auggie (Augment) CLI.
    
    Uses `augment` command with appropriate model and sandbox settings.
    Supports planning, execution, and QA modes.
    
    Command directory: `.augment/rules/`
    Format: markdown
    
    Example:
        engine = AuggieEngine()
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
            default_model=default_model or os.environ.get("DEVGODZILLA_AUGGIE_MODEL", "augment-default"),
        )

    @property
    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            id="auggie",
            display_name="Auggie (Augment) CLI",
            kind=EngineKind.CLI,
            default_model=self._default_model,
            description="Auggie CLI for code generation",
            capabilities=["plan", "execute", "qa", "multi-file"],
        )

    def _get_command_name(self) -> str:
        return "augment"

    def _sandbox_to_auggie(self, sandbox: SandboxMode) -> str:
        """Convert SandboxMode to Auggie sandbox string."""
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
        """Build augment command."""
        model = self._get_model(req)
        
        cwd = Path(req.working_dir)
        auggie_sandbox = self._sandbox_to_auggie(sandbox)
        
        cmd = [
            "augment",
            "--cwd", str(cwd),
            "--sandbox", auggie_sandbox,
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
        
        # Read from stdin
        cmd.append("-")
        
        return cmd

    def check_availability(self) -> bool:
        """
        Check if Auggie CLI can run in this environment.

        In addition to the binary being present, Auggie typically requires authentication.
        Set `DEVGODZILLA_ASSUME_AGENT_AUTH=true` to bypass the auth check.
        """
        if not super().check_availability():
            return False

        if os.environ.get("DEVGODZILLA_ASSUME_AGENT_AUTH", "").lower() in ("1", "true", "yes", "on"):
            return True

        return bool(os.environ.get("AUGMENT_API_KEY") or os.environ.get("AUGMENT_TOKEN"))


def register_auggie_engine(*, default: bool = False) -> AuggieEngine:
    """
    Register AuggieEngine in the global registry.
    
    Returns the registered engine instance.
    """
    engine = AuggieEngine()
    register_engine(engine, default=default)
    return engine
