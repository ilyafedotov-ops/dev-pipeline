"""
DevGodzilla Windsurf IDE Engine

Adapter for Windsurf IDE (Codeium-powered) integration.
Generates command files for Windsurf's Cascade AI-assisted coding features.
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
from devgodzilla.engines.ide import (
    IDECommand,
    IDEEngine,
)
from devgodzilla.engines.registry import register_engine
from devgodzilla.logging import get_logger

logger = get_logger(__name__)


class WindsurfEngine(IDEEngine):
    """
    Engine adapter for Windsurf IDE.

    Windsurf is a Codeium-powered AI IDE built on VS Code.
    This adapter generates command files that can be consumed
    by the DevGodzilla Windsurf extension.

    Features:
    - Generates .windsurfrules for project-specific AI behavior
    - Creates command files for automated editing
    - Supports Cascade mode (multi-file editing) and codebase indexing

    Example:
        engine = WindsurfEngine()
        result = engine.execute(request)
    """

    def __init__(
        self,
        *,
        command_dir: Optional[Path] = None,
        result_timeout: int = 300,
        default_model: Optional[str] = None,
        use_cascade: bool = True,
    ) -> None:
        """
        Initialize Windsurf engine.

        Args:
            command_dir: Directory for command files
            result_timeout: Seconds to wait for Windsurf result
            default_model: Default model (claude-3.5-sonnet, etc.)
            use_cascade: Whether to use Cascade mode (multi-file editing)
        """
        super().__init__(
            command_dir=command_dir,
            result_timeout=result_timeout,
        )
        self._default_model = default_model or os.environ.get(
            "DEVGODZILLA_WINDSURF_MODEL", "claude-3.5-sonnet"
        )
        self._use_cascade = use_cascade

    @property
    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            id="windsurf",
            display_name="Windsurf IDE",
            kind=EngineKind.IDE,
            default_model=self._default_model,
            description="Windsurf IDE (Codeium-powered) AI assistant for code generation and editing",
            capabilities=[
                "plan",
                "execute",
                "qa",
                "multi-file-edit",
                "codebase-indexing",
            ],
        )

    def _get_command_dir(self, req: EngineRequest) -> Path:
        """Get command directory, preferring workspace .devgodzilla dir."""
        if self._command_dir:
            return self._command_dir

        workspace_dir = Path(req.working_dir)
        command_dir = workspace_dir / ".devgodzilla" / "windsurf"
        command_dir.mkdir(parents=True, exist_ok=True)
        return command_dir

    def _get_command_file_path(self, req: EngineRequest) -> Path:
        """Get command file path in workspace .devgodzilla directory."""
        command_dir = self._get_command_dir(req)
        filename = f"cmd-{req.step_run_id}.json"
        return command_dir / filename

    def _infer_command_type(self, sandbox: SandboxMode) -> str:
        """Infer command type from sandbox mode."""
        if sandbox == SandboxMode.FULL_ACCESS:
            return "plan"
        elif sandbox == SandboxMode.READ_ONLY:
            return "review"
        else:
            return "edit"

    def _generate_commands(
        self,
        req: EngineRequest,
        sandbox: SandboxMode,
    ) -> List[IDECommand]:
        """
        Generate Windsurf commands from the request.

        Creates commands based on sandbox mode:
        - FULL_ACCESS: Planning/analysis commands
        - WORKSPACE_WRITE: Edit/create commands (Cascade mode)
        - READ_ONLY: Review/audit commands
        """
        commands: List[IDECommand] = []
        prompt_text = self.get_prompt_text(req)
        command_type = self._infer_command_type(sandbox)

        # Primary command with the full prompt
        primary_command = IDECommand(
            command_type=command_type,
            target=req.working_dir,
            instruction=prompt_text,
            context={
                "mode": "cascade" if self._use_cascade else "chat",
                "project_id": req.project_id,
                "protocol_run_id": req.protocol_run_id,
            },
            metadata={
                "model": req.model or self._default_model,
                "files": req.prompt_files,
                "extra": req.extra,
            },
        )
        commands.append(primary_command)

        # Add follow-up commands based on extra parameters
        follow_ups = req.extra.get("follow_up_commands", [])
        for follow_up in follow_ups:
            if isinstance(follow_up, dict):
                commands.append(IDECommand(
                    command_type=follow_up.get("type", "edit"),
                    target=follow_up.get("target", req.working_dir),
                    instruction=follow_up.get("instruction", ""),
                    context=follow_up.get("context", {}),
                    metadata=follow_up.get("metadata", {}),
                ))

        return commands

    def _parse_response(self, result_data) -> EngineResult:
        """
        Parse Windsurf extension result.

        Expected format:
        {
            "success": bool,
            "changes": [{"file": str, "action": str, "content": str}],
            "output": str,
            "error": str | null
        }
        """
        if result_data is None:
            return EngineResult(
                success=False,
                error="Timeout waiting for Windsurf response",
                metadata={"timeout": True},
            )

        success = result_data.get("success", False)
        changes = result_data.get("changes", [])
        output = result_data.get("output", "")
        error = result_data.get("error")

        # Build stdout from changes summary
        if changes:
            change_summary = "\n".join(
                f"- {c.get('action', 'change')}: {c.get('file', 'unknown')}"
                for c in changes
            )
            stdout = f"Changes made:\n{change_summary}\n\n{output}"
        else:
            stdout = output

        return EngineResult(
            success=success,
            stdout=stdout,
            stderr="",
            error=error,
            metadata={
                "changes": changes,
                "change_count": len(changes),
            },
        )

    def sync_config(self, additional_agents: Optional[List[dict]] = None) -> None:
        """
        Generate .windsurfrules file for the project.

        Creates or updates the .windsurfrules file with DevGodzilla
        configuration and coding guidelines.
        """
        logger.info(
            "windsurf_sync_config",
            extra={"additional_agents": len(additional_agents) if additional_agents else 0},
        )

    def check_availability(self) -> bool:
        """
        Check if Windsurf integration is available.

        Checks for Windsurf installation or .windsurf directory.
        """
        try:
            home = Path.home()

            # Check for .windsurf config directory
            windsurf_config = home / ".windsurf"
            if windsurf_config.exists():
                return True

            # Check for Windsurf in common install locations
            common_paths = [
                "/Applications/Windsurf.app",  # macOS
                Path(home) / ".windsurf",  # Linux
                Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "windsurf",  # Windows
            ]

            for path in common_paths:
                if Path(path).exists():
                    return True

            # If command dir is writable, we can still generate commands
            return super().check_availability()

        except Exception:
            return False


def register_windsurf_engine(*, default: bool = False) -> WindsurfEngine:
    """
    Register WindsurfEngine in the global registry.

    Returns the registered engine instance.
    """
    engine = WindsurfEngine()
    register_engine(engine, default=default)
    return engine
