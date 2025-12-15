"""
DevGodzilla Claude Code Engine

Anthropic Claude Code (claude) CLI engine adapter.
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


class ClaudeCodeEngine(CLIEngine):
    """
    Engine adapter for the Claude Code CLI.
    
    Uses the `claude` command with appropriate settings.
    
    Example:
        engine = ClaudeCodeEngine()
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
            default_model=default_model or os.environ.get("DEVGODZILLA_CLAUDE_MODEL", "claude-sonnet-4-20250514"),
        )

    @property
    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            id="claude-code",
            display_name="Claude Code CLI",
            kind=EngineKind.CLI,
            default_model=self._default_model,
            description="Anthropic's Claude Code CLI for code generation",
            capabilities=["plan", "execute", "qa", "multi-file", "reasoning"],
        )

    def _get_command_name(self) -> str:
        return "claude"

    def _build_command(
        self,
        req: EngineRequest,
        sandbox: SandboxMode,
    ) -> List[str]:
        """Build claude command."""
        cwd = Path(req.working_dir)
        
        cmd = [
            "claude",
            "--print",  # Print output to stdout
            "--dangerously-skip-permissions",  # Skip permission prompts
        ]
        
        # Add working directory
        if cwd.exists():
            cmd.extend(["--cwd", str(cwd)])
        
        # Add optional parameters from extra
        extra = req.extra or {}
        
        # Model override
        model = self._get_model(req)
        if model:
            cmd.extend(["--model", model])
        
        # Output format
        if extra.get("output_format"):
            cmd.extend(["--output-format", extra["output_format"]])
        
        # Max tokens
        if extra.get("max_tokens"):
            cmd.extend(["--max-tokens", str(extra["max_tokens"])])
        
        return cmd


def register_claude_code_engine(*, default: bool = False) -> ClaudeCodeEngine:
    """
    Register ClaudeCodeEngine in the global registry.
    
    Returns the registered engine instance.
    """
    engine = ClaudeCodeEngine()
    register_engine(engine, default=default)
    return engine
