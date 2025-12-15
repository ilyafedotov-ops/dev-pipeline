"""
DevGodzilla OpenCode Engine

OpenCode CLI engine adapter.
Supports both CLI and API execution modes.
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


class OpenCodeEngine(CLIEngine):
    """
    Engine adapter for the OpenCode CLI.
    
    OpenCode provides a unified interface to multiple AI models.
    Uses the `opencode` command with appropriate settings.
    
    Example:
        engine = OpenCodeEngine()
        result = engine.execute(request)
    """

    def __init__(
        self,
        *,
        default_timeout: int = 300,
        default_model: Optional[str] = None,
        prefer_cli: bool = True,
    ) -> None:
        super().__init__(
            default_timeout=default_timeout,
            default_model=default_model or os.environ.get("DEVGODZILLA_OPENCODE_MODEL"),
        )
        self.prefer_cli = prefer_cli

    @property
    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            id="opencode",
            display_name="OpenCode CLI",
            kind=EngineKind.CLI,
            default_model=self._default_model,
            description="OpenCode CLI for multi-model code generation",
            capabilities=["plan", "execute", "qa", "multi-model"],
        )

    def _get_command_name(self) -> str:
        return "opencode"

    def _build_command(
        self,
        req: EngineRequest,
        sandbox: SandboxMode,
    ) -> List[str]:
        """Build opencode command."""
        cwd = Path(req.working_dir)
        
        cmd = [
            "opencode",
            "--yes",  # Auto-approve
            "--quiet",
        ]
        
        # Add working directory
        if cwd.exists():
            cmd.extend(["--cwd", str(cwd)])
        
        # Add model if specified
        model = self._get_model(req)
        if model:
            cmd.extend(["--model", model])
        
        # Add optional parameters from extra
        extra = req.extra or {}
        
        # Output format
        if extra.get("output_format"):
            cmd.extend(["--output-format", extra["output_format"]])
        
        # Max tokens
        if extra.get("max_tokens"):
            cmd.extend(["--max-tokens", str(extra["max_tokens"])])
        
        # Temperature
        if extra.get("temperature") is not None:
            cmd.extend(["--temperature", str(extra["temperature"])])
        
        return cmd


def register_opencode_engine(*, default: bool = False) -> OpenCodeEngine:
    """
    Register OpenCodeEngine in the global registry.
    
    Returns the registered engine instance.
    """
    engine = OpenCodeEngine()
    register_engine(engine, default=default)
    return engine
