"""
DevGodzilla Qwen Code Engine

Qwen Code CLI engine adapter.
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


class QwenEngine(CLIEngine):
    """
    Engine adapter for the Qwen Code CLI.
    
    Uses `qwen` command with appropriate model and sandbox settings.
    Supports planning, execution, and QA modes.
    
    Command directory: `.qwen/commands/`
    Format: toml
    
    Example:
        engine = QwenEngine(default_model="qwen-coder")
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
            default_model=default_model or os.environ.get("DEVGODZILLA_QWEN_MODEL", "qwen-coder"),
        )

    @property
    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            id="qwen",
            display_name="Qwen Code CLI",
            kind=EngineKind.CLI,
            default_model=self._default_model,
            description="Qwen Code CLI for code generation",
            capabilities=["plan", "execute", "qa", "multi-file"],
        )

    def _get_command_name(self) -> str:
        return "qwen"

    def _sandbox_to_qwen(self, sandbox: SandboxMode) -> str:
        """Convert SandboxMode to Qwen sandbox string."""
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
        """Build qwen command."""
        model = self._get_model(req)
        
        cwd = Path(req.working_dir)
        qwen_sandbox = self._sandbox_to_qwen(sandbox)
        
        cmd = [
            "qwen",
            "--cwd", str(cwd),
            "--sandbox", qwen_sandbox,
        ]
        
        if model:
            cmd.extend(["--model", model])
        
        # Add optional parameters from extra
        extra = req.extra or {}
        
        if extra.get("auto_approve"):
            cmd.append("--auto-approve")
        
        if extra.get("command_file"):
            cmd.extend(["--file", str(extra["command_file"])])
        
        if extra.get("config"):
            cmd.extend(["--config", str(extra["config"])])
        
        # Read from stdin
        cmd.append("-")
        
        return cmd

    def check_availability(self) -> bool:
        """
        Check if Qwen CLI can run in this environment.

        In addition to the binary being present, Qwen typically requires an API key.
        Set `DEVGODZILLA_ASSUME_AGENT_AUTH=true` to bypass the key check.
        """
        if not super().check_availability():
            return False

        if os.environ.get("DEVGODZILLA_ASSUME_AGENT_AUTH", "").lower() in ("1", "true", "yes", "on"):
            return True

        return bool(os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY"))


def register_qwen_engine(*, default: bool = False) -> QwenEngine:
    """
    Register QwenEngine in the global registry.
    
    Returns the registered engine instance.
    """
    engine = QwenEngine()
    register_engine(engine, default=default)
    return engine
