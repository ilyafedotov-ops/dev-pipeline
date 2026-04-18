"""
DevGodzilla CLI Adapter

Adapter for executing CLI-based AI coding agents.
Handles process spawning, output capture, and timeout management.
"""

import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from devgodzilla.engines.interface import (
    Engine,
    EngineMetadata,
    EngineRequest,
    EngineResult,
    SandboxMode,
)
from devgodzilla.logging import get_logger

logger = get_logger(__name__)


def run_cli_command(
    cmd: List[str],
    *,
    cwd: Optional[Path] = None,
    input_text: Optional[str] = None,
    timeout: Optional[int] = None,
    env: Optional[Dict[str, str]] = None,
    capture_output: bool = True,
    on_output: Optional[Callable[[str, str], None]] = None,
    tracker_execution_id: Optional[str] = None,
) -> EngineResult:
    """
    Run a CLI command and capture output.
    
    Args:
        cmd: Command and arguments
        cwd: Working directory
        input_text: Text to send to stdin
        timeout: Timeout in seconds
        env: Environment variables (merged with os.environ)
        capture_output: Whether to capture stdout/stderr
        
    Returns:
        EngineResult with success, stdout, stderr
    """
    start_time = time.time()
    
    # Build environment
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)

    logger.debug(
        "cli_command_start",
        extra={"cmd": cmd[:3], "cwd": str(cwd) if cwd else None},
    )

    try:
        if on_output:
            capture = True
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdin=subprocess.PIPE if input_text is not None else None,
                stdout=subprocess.PIPE if capture else None,
                stderr=subprocess.PIPE if capture else None,
                text=True,
                env=proc_env,
                bufsize=1,
            )
            if tracker_execution_id:
                try:
                    from devgodzilla.services.cli_execution_tracker import get_execution_tracker

                    get_execution_tracker().set_pid(tracker_execution_id, proc.pid)
                except Exception as exc:  # noqa: BLE001
                    logger.debug(
                        "cli_command_set_pid_failed",
                        extra={"execution_id": tracker_execution_id, "error": str(exc)},
                    )

            if input_text is not None and proc.stdin:
                try:
                    proc.stdin.write(input_text)
                except BrokenPipeError:
                    pass
                finally:
                    proc.stdin.close()

            stdout_chunks: List[str] = []
            stderr_chunks: List[str] = []

            def _read_stream(stream, sink: List[str], source: str) -> None:
                for line in iter(stream.readline, ""):
                    sink.append(line)
                    try:
                        on_output(source, line)
                    except Exception as e:
                        logger.warning(
                            "cli_command_output_callback_failed",
                            extra={"source": source, "error": str(e)},
                        )
                stream.close()

            threads: List[threading.Thread] = []
            if proc.stdout:
                t = threading.Thread(target=_read_stream, args=(proc.stdout, stdout_chunks, "stdout"), daemon=True)
                t.start()
                threads.append(t)
            if proc.stderr:
                t = threading.Thread(target=_read_stream, args=(proc.stderr, stderr_chunks, "stderr"), daemon=True)
                t.start()
                threads.append(t)

            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                duration = time.time() - start_time
                for t in threads:
                    t.join(timeout=0.2)
                return EngineResult(
                    success=False,
                    stdout="".join(stdout_chunks),
                    stderr="".join(stderr_chunks),
                    duration_seconds=duration,
                    error=f"Command timed out after {timeout}s",
                    metadata={"cmd": cmd[0], "timeout": True},
                )

            duration = time.time() - start_time
            for t in threads:
                t.join(timeout=0.2)

            return EngineResult(
                success=proc.returncode == 0,
                stdout="".join(stdout_chunks),
                stderr="".join(stderr_chunks),
                exit_code=proc.returncode,
                duration_seconds=duration,
                metadata={"cmd": cmd[0]},
            )

        proc = subprocess.run(
            cmd,
            cwd=cwd,
            input=input_text,
            timeout=timeout,
            capture_output=capture_output,
            text=True,
            env=proc_env,
        )

        duration = time.time() - start_time

        return EngineResult(
            success=proc.returncode == 0,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            exit_code=proc.returncode,
            duration_seconds=duration,
            metadata={"cmd": cmd[0]},
        )
        
    except subprocess.TimeoutExpired as e:
        duration = time.time() - start_time
        return EngineResult(
            success=False,
            stdout=e.stdout or "" if hasattr(e, "stdout") else "",
            stderr=e.stderr or "" if hasattr(e, "stderr") else "",
            duration_seconds=duration,
            error=f"Command timed out after {timeout}s",
            metadata={"cmd": cmd[0], "timeout": True},
        )
        
    except Exception as e:
        duration = time.time() - start_time
        return EngineResult(
            success=False,
            stdout="",
            stderr=str(e),
            duration_seconds=duration,
            error=str(e),
            metadata={"cmd": cmd[0] if cmd else None},
        )


class CLIEngine(Engine):
    """
    Base class for CLI-based AI coding agents.
    
    Provides common functionality for agents that are invoked via command line.
    Subclasses should implement _build_command() to construct the CLI command.
    
    Example:
        class MyCliEngine(CLIEngine):
            @property
            def metadata(self) -> EngineMetadata:
                return EngineMetadata(id="my-agent", ...)
            
            def _build_command(
                self,
                req: EngineRequest,
                sandbox: SandboxMode,
            ) -> List[str]:
                return ["my-agent", "--model", req.model, ...]
    """

    def __init__(
        self,
        *,
        default_timeout: int = 600,  # Increased for real agent operations
        default_model: Optional[str] = None,
    ) -> None:
        self._default_timeout = default_timeout
        self._default_model = default_model

    @property
    def metadata(self) -> EngineMetadata:
        """Override in subclass."""
        raise NotImplementedError

    def _build_command(
        self,
        req: EngineRequest,
        sandbox: SandboxMode,
    ) -> List[str]:
        """
        Build the CLI command for the agent.
        
        Override in subclass.
        """
        raise NotImplementedError

    def _get_timeout(self, req: EngineRequest) -> int:
        """Get timeout from request or default."""
        if req.timeout:
            return req.timeout
        return req.extra.get("timeout_seconds", self._default_timeout)

    def _get_model(self, req: EngineRequest) -> Optional[str]:
        """Get model from request, metadata, or default."""
        return req.model or self.metadata.default_model or self._default_model

    def _run(
        self,
        req: EngineRequest,
        sandbox: SandboxMode,
    ) -> EngineResult:
        """Execute the CLI command."""
        cmd = self._build_command(req, sandbox)
        prompt_text = self.get_prompt_text(req)
        
        timeout = self._get_timeout(req)
        cwd = Path(req.working_dir)
        
        logger.info(
            "cli_engine_run",
            extra={
                "engine_id": self.metadata.id,
                "sandbox": sandbox.value,
                "step_run_id": req.step_run_id,
            },
        )
        
        log_callback = None
        if req.extra:
            candidate = req.extra.get("log_callback")
            if callable(candidate):
                log_callback = candidate

        result = run_cli_command(
            cmd,
            cwd=cwd,
            input_text=prompt_text,
            timeout=timeout,
            env=req.extra.get("env"),
            on_output=log_callback,
        )
        
        # Add engine info to metadata
        result.metadata["engine_id"] = self.metadata.id
        result.metadata["sandbox"] = sandbox.value
        
        return result

    def plan(self, req: EngineRequest) -> EngineResult:
        """Execute planning with full access."""
        return self._run(req, SandboxMode.FULL_ACCESS)

    def execute(self, req: EngineRequest) -> EngineResult:
        """Execute coding with workspace-write sandbox."""
        return self._run(req, SandboxMode.WORKSPACE_WRITE)

    def qa(self, req: EngineRequest) -> EngineResult:
        """Execute QA in read-only mode."""
        return self._run(req, SandboxMode.READ_ONLY)

    # Common system paths where agent CLIs may be installed
    _SYSTEM_CLI_PATHS = [
        "/usr/local/bin",
        "/usr/bin",
        "/snap/bin",
    ]

    @classmethod
    def _extra_cli_dirs(cls) -> list[str]:
        """Return user-local bin dirs that may not be on PATH in all contexts."""
        import os
        home = os.path.expanduser("~")
        dirs = [
            os.path.join(home, ".local", "bin"),
            os.path.join(home, ".hermes", "node", "bin"),
            os.path.join(home, "bin"),
        ]
        # Also honour npm/pnpm global bins if set
        for key in ("NPM_CONFIG_PREFIX", "PNPM_HOME"):
            val = os.environ.get(key)
            if val:
                dirs.append(val)
        return dirs

    def check_availability(self) -> bool:
        """Check if the CLI tool is available."""
        import shutil
        cmd_name = self._get_command_name()

        # Fast path – check current PATH
        if shutil.which(cmd_name):
            return True

        # Slow path – scan common locations the binary might live in even when
        # PATH is narrowed (e.g. inside a venv where activate clobbered PATH).
        for d in self._SYSTEM_CLI_PATHS + self._extra_cli_dirs():
            candidate = os.path.join(d, cmd_name)  # type: ignore[name-defined]  # noqa: F821
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return True
        return False

    def _get_command_name(self) -> str:
        """Get the main command name for availability check."""
        return self.metadata.id
