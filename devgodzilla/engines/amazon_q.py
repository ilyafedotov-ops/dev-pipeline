"""
DevGodzilla Amazon Q Engine

Amazon Q CLI engine adapter.
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


class AmazonQEngine(CLIEngine):
    """
    Engine adapter for the Amazon Q CLI.
    
    Uses `q` command with appropriate model and sandbox settings.
    Supports planning, execution, and QA modes.
    
    Command directory: `.amazonq/prompts/`
    Format: markdown
    
    Example:
        engine = AmazonQEngine()
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
            default_model=default_model or os.environ.get("DEVGODZILLA_AMAZONQ_MODEL", "amazon-q-developer"),
        )

    @property
    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            id="amazon_q",
            display_name="Amazon Q CLI",
            kind=EngineKind.CLI,
            default_model=self._default_model,
            description="Amazon Q CLI for code generation",
            capabilities=["plan", "execute", "qa", "multi-file"],
        )

    def _get_command_name(self) -> str:
        return "q"

    def _sandbox_to_amazonq(self, sandbox: SandboxMode) -> str:
        """Convert SandboxMode to Amazon Q sandbox string."""
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
        """Build Amazon Q command."""
        model = self._get_model(req)
        
        cwd = Path(req.working_dir)
        amazonq_sandbox = self._sandbox_to_amazonq(sandbox)
        
        cmd = [
            "q",
            "--cwd", str(cwd),
            "--sandbox", amazonq_sandbox,
        ]
        
        if model:
            cmd.extend(["--model", model])
        
        # Add optional parameters from extra
        extra = req.extra or {}
        
        if extra.get("no_confirm"):
            cmd.append("--no-confirm")
        
        if extra.get("prompt_file"):
            cmd.extend(["--file", str(extra["prompt_file"])])
        
        if extra.get("profile"):
            cmd.extend(["--profile", str(extra["profile"])])
        
        if extra.get("region"):
            cmd.extend(["--region", str(extra["region"])])
        
        # Read from stdin
        cmd.append("-")
        
        return cmd

    def check_availability(self) -> bool:
        """
        Check if Amazon Q CLI can run in this environment.

        In addition to the binary being present, Amazon Q typically requires AWS credentials.
        Set `DEVGODZILLA_ASSUME_AGENT_AUTH=true` to bypass the auth check.
        """
        if not super().check_availability():
            return False

        if os.environ.get("DEVGODZILLA_ASSUME_AGENT_AUTH", "").lower() in ("1", "true", "yes", "on"):
            return True

        # Amazon Q uses AWS credentials
        return bool(
            os.environ.get("AWS_ACCESS_KEY_ID")
            or os.environ.get("AWS_PROFILE")
            or os.environ.get("AMAZON_Q_TOKEN")
        )


def register_amazon_q_engine(*, default: bool = False) -> AmazonQEngine:
    """
    Register AmazonQEngine in the global registry.
    
    Returns the registered engine instance.
    """
    engine = AmazonQEngine()
    register_engine(engine, default=default)
    return engine
