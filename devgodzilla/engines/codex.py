"""
DevGodzilla Codex Engine

OpenAI Codex CLI engine adapter.
"""

import os
import subprocess
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


class CodexEngine(CLIEngine):
    """
    Engine adapter for the OpenAI Codex CLI.
    
    Uses `codex exec` command with appropriate model and sandbox settings.
    Supports planning, execution, and QA modes.
    
    Example:
        engine = CodexEngine(default_model="o4-mini")
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
            default_model=default_model or os.environ.get("DEVGODZILLA_CODEX_MODEL", "o4-mini"),
        )

    @property
    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            id="codex",
            display_name="OpenAI Codex CLI",
            kind=EngineKind.CLI,
            default_model=self._default_model,
            description="OpenAI's Codex CLI for code generation",
            capabilities=["plan", "execute", "qa", "multi-file"],
        )

    def _get_command_name(self) -> str:
        return "codex"

    def _sandbox_to_codex(self, sandbox: SandboxMode) -> str:
        """Convert SandboxMode to Codex sandbox string."""
        mapping = {
            SandboxMode.FULL_ACCESS: "danger-full-access",
            SandboxMode.WORKSPACE_WRITE: "workspace-write",
            SandboxMode.READ_ONLY: "read-only",
        }
        return mapping.get(sandbox, "workspace-write")

    def _build_command(
        self,
        req: EngineRequest,
        sandbox: SandboxMode,
    ) -> List[str]:
        """Build codex exec command."""
        model = self._get_model(req)
        if not model:
            raise ValueError("Codex requires a model")
        
        cwd = Path(req.working_dir)
        codex_sandbox = self._sandbox_to_codex(sandbox)
        
        cmd = [
            "codex",
            "exec",
            "-m", model,
            "--cd", str(cwd),
            "--sandbox", codex_sandbox,
            "--dangerously-bypass-approvals-and-sandbox",
            "--skip-git-repo-check",
        ]
        
        # Add optional parameters from extra
        extra = req.extra or {}
        
        if extra.get("output_schema"):
            cmd.extend(["--output-schema", str(extra["output_schema"])])
        
        if extra.get("output_last_message"):
            cmd.extend(["--output-last-message", str(extra["output_last_message"])])

        reasoning_effort = str(extra.get("reasoning_effort") or "").strip()
        if reasoning_effort:
            cmd.extend(["-c", f'model_reasoning_effort="{reasoning_effort}"'])

        # Read from stdin
        cmd.append("-")
        
        return cmd

    def check_availability(self) -> bool:
        """
        Check if Codex CLI can run in this environment.

        In addition to the binary being present, Codex typically requires an API key.
        Set `DEVGODZILLA_ASSUME_AGENT_AUTH=true` to bypass the key check (e.g. local
        configs/credential helpers).
        """
        if not super().check_availability():
            return False

        if os.environ.get("DEVGODZILLA_ASSUME_AGENT_AUTH", "").lower() in ("1", "true", "yes", "on"):
            return True

        if os.environ.get("OPENAI_API_KEY"):
            return True

        try:
            result = subprocess.run(
                ["codex", "login", "status"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except Exception:
            return False

        status_text = ((result.stdout or "") + "\n" + (result.stderr or "")).strip().lower()
        return result.returncode == 0 and "not logged in" not in status_text


def register_codex_engine(*, default: bool = True) -> CodexEngine:
    """
    Register CodexEngine in the global registry.
    
    Returns the registered engine instance.
    """
    engine = CodexEngine()
    register_engine(engine, default=default)
    return engine
