"""
DevGodzilla OpenCode Engine

OpenCode CLI engine adapter.
Supports both CLI and API execution modes.
"""

import os
import tempfile
from pathlib import Path
from typing import List, Optional

from devgodzilla.engines.interface import (
    EngineKind,
    EngineMetadata,
    EngineRequest,
    EngineResult,
    SandboxMode,
)
from devgodzilla.engines.cli_adapter import CLIEngine, run_cli_command
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
        env_model = os.environ.get("DEVGODZILLA_OPENCODE_MODEL")
        resolved_default_model = default_model or (env_model.strip() if env_model else "") or "zai-coding-plan/glm-4.6"
        super().__init__(
            default_timeout=default_timeout,
            default_model=resolved_default_model,
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

    def _write_prompt_file(self, req: EngineRequest) -> Optional[Path]:
        prompt_text = self.get_prompt_text(req).strip()
        if not prompt_text:
            return None

        path = Path(tempfile.mkdtemp(prefix="devgodzilla-opencode-")) / "prompt.md"
        path.write_text(prompt_text, encoding="utf-8")
        return path

    def _build_command(
        self,
        req: EngineRequest,
        sandbox: SandboxMode,
    ) -> List[str]:
        """
        Build opencode command.

        DevGodzilla uses the headless `opencode run` subcommand.
        """
        cmd: List[str] = ["opencode", "run"]

        # Model if specified
        model = self._get_model(req)
        if model:
            cmd.extend(["--model", model])

        # Add optional parameters from extra
        extra = req.extra or {}

        # Output/log format
        output_format = extra.get("output_format")
        if output_format:
            # Keep compatibility with older callers that passed "text".
            resolved = "json" if str(output_format).lower() == "json" else "default"
            cmd.extend(["--format", resolved])

        prompt_file = extra.get("_devgodzilla_prompt_file")
        if isinstance(prompt_file, str) and prompt_file.strip():
            cmd.extend(["--file", prompt_file])
            # Use -- to separate file args from message (prevents message being treated as file)
            cmd.extend(["--", "Execute the task described in the attached prompt file."])
        else:
            # Fallback: if no prompt file, use inline prompt
            cmd.append(req.prompt_text or "Complete the coding task.")

        return cmd

    def _run_opencode(
        self,
        req: EngineRequest,
        sandbox: SandboxMode,
    ) -> EngineResult:
        cwd = Path(req.working_dir)
        timeout = self._get_timeout(req)

        prompt_file = self._write_prompt_file(req)
        original_extra = req.extra
        try:
            extra = dict(req.extra or {})
            if prompt_file:
                extra["_devgodzilla_prompt_file"] = str(prompt_file)

            req.extra = extra
            cmd = self._build_command(req, sandbox)
            result = run_cli_command(
                cmd,
                cwd=cwd,
                input_text=None,
                timeout=timeout,
                env=req.extra.get("env"),
            )
            result.metadata["engine_id"] = self.metadata.id
            result.metadata["sandbox"] = sandbox.value
            return result
        finally:
            req.extra = original_extra
            # Best-effort cleanup; never fail the run due to tmp cleanup issues.
            try:
                if prompt_file and prompt_file.exists():
                    prompt_file.unlink(missing_ok=True)
                if prompt_file and prompt_file.parent.exists():
                    prompt_file.parent.rmdir()
            except Exception:
                pass

    def plan(self, req: EngineRequest) -> EngineResult:
        return self._run_opencode(req, SandboxMode.FULL_ACCESS)

    def execute(self, req: EngineRequest) -> EngineResult:
        return self._run_opencode(req, SandboxMode.WORKSPACE_WRITE)

    def qa(self, req: EngineRequest) -> EngineResult:
        return self._run_opencode(req, SandboxMode.READ_ONLY)


def register_opencode_engine(*, default: bool = False) -> OpenCodeEngine:
    """
    Register OpenCodeEngine in the global registry.
    
    Returns the registered engine instance.
    """
    engine = OpenCodeEngine()
    register_engine(engine, default=default)
    return engine
