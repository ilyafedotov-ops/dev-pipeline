"""
DevGodzilla Sandbox Utilities

Utilities for sandboxed execution of AI coding engines.
Provides security isolation for step execution.
"""

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from devgodzilla.logging import get_logger

logger = get_logger(__name__)


class SandboxType(str, Enum):
    """Type of sandbox to use."""
    NONE = "none"          # No sandboxing
    NSJAIL = "nsjail"      # nsjail-based sandboxing
    DOCKER = "docker"      # Docker container
    FIREJAIL = "firejail"  # Firejail sandboxing


@dataclass
class SandboxConfig:
    """Configuration for sandbox execution."""
    sandbox_type: SandboxType = SandboxType.NONE
    
    # Filesystem access
    read_only_paths: List[Path] = field(default_factory=list)
    read_write_paths: List[Path] = field(default_factory=list)
    
    # Resource limits
    max_memory_mb: int = 4096
    max_cpu_time_seconds: int = 300
    max_file_size_mb: int = 100
    max_processes: int = 100
    
    # Network
    allow_network: bool = False
    
    # nsjail specific
    nsjail_path: str = "/usr/bin/nsjail"
    
    # Docker specific
    docker_image: str = "python:3.12-slim"
    
    # Additional options
    extra_args: List[str] = field(default_factory=list)


def is_sandbox_available(sandbox_type: SandboxType) -> bool:
    """Check if a sandbox type is available on this system."""
    if sandbox_type == SandboxType.NONE:
        return True
    elif sandbox_type == SandboxType.NSJAIL:
        return shutil.which("nsjail") is not None
    elif sandbox_type == SandboxType.DOCKER:
        return shutil.which("docker") is not None
    elif sandbox_type == SandboxType.FIREJAIL:
        return shutil.which("firejail") is not None
    return False


def get_default_sandbox_type() -> SandboxType:
    """Get the best available sandbox type."""
    env_sandbox = os.environ.get("DEVGODZILLA_SANDBOX_TYPE")
    if env_sandbox:
        try:
            sandbox_type = SandboxType(env_sandbox.lower())
            if is_sandbox_available(sandbox_type):
                return sandbox_type
        except ValueError:
            pass
    
    # Check available sandboxes in order of preference
    for sandbox_type in [SandboxType.NSJAIL, SandboxType.FIREJAIL, SandboxType.DOCKER]:
        if is_sandbox_available(sandbox_type):
            return sandbox_type
    
    return SandboxType.NONE


class SandboxRunner:
    """
    Runs commands in a sandboxed environment.
    
    Supports multiple sandbox backends:
    - nsjail (preferred for security)
    - firejail (lighter weight)
    - docker (most portable)
    - none (no sandboxing)
    
    Example:
        runner = SandboxRunner(SandboxConfig(
            sandbox_type=SandboxType.NSJAIL,
            read_write_paths=[workspace_dir],
        ))
        
        result = runner.run(
            cmd=["python", "script.py"],
            cwd=workspace_dir,
        )
    """

    def __init__(self, config: Optional[SandboxConfig] = None) -> None:
        self.config = config or SandboxConfig()

    def run(
        self,
        cmd: List[str],
        *,
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        input_text: Optional[str] = None,
        timeout: Optional[int] = None,
        capture_output: bool = True,
    ) -> subprocess.CompletedProcess:
        """
        Run a command in the sandbox.
        
        Args:
            cmd: Command and arguments
            cwd: Working directory
            env: Environment variables
            input_text: Input to send to stdin
            timeout: Timeout in seconds
            capture_output: Whether to capture stdout/stderr
            
        Returns:
            CompletedProcess with results
        """
        if self.config.sandbox_type == SandboxType.NONE:
            return self._run_unsandboxed(
                cmd, cwd=cwd, env=env, input_text=input_text,
                timeout=timeout, capture_output=capture_output,
            )
        elif self.config.sandbox_type == SandboxType.NSJAIL:
            return self._run_nsjail(
                cmd, cwd=cwd, env=env, input_text=input_text,
                timeout=timeout, capture_output=capture_output,
            )
        elif self.config.sandbox_type == SandboxType.FIREJAIL:
            return self._run_firejail(
                cmd, cwd=cwd, env=env, input_text=input_text,
                timeout=timeout, capture_output=capture_output,
            )
        elif self.config.sandbox_type == SandboxType.DOCKER:
            return self._run_docker(
                cmd, cwd=cwd, env=env, input_text=input_text,
                timeout=timeout, capture_output=capture_output,
            )
        else:
            raise ValueError(f"Unknown sandbox type: {self.config.sandbox_type}")

    def _run_unsandboxed(
        self,
        cmd: List[str],
        **kwargs,
    ) -> subprocess.CompletedProcess:
        """Run command without sandboxing."""
        proc_env = os.environ.copy()
        if kwargs.get("env"):
            proc_env.update(kwargs["env"])
        
        return subprocess.run(
            cmd,
            cwd=kwargs.get("cwd"),
            env=proc_env,
            input=kwargs.get("input_text"),
            timeout=kwargs.get("timeout"),
            capture_output=kwargs.get("capture_output", True),
            text=True,
        )

    def _run_nsjail(
        self,
        cmd: List[str],
        **kwargs,
    ) -> subprocess.CompletedProcess:
        """Run command in nsjail sandbox."""
        nsjail_cmd = [
            self.config.nsjail_path,
            "--mode", "once",
            "--time_limit", str(self.config.max_cpu_time_seconds),
            "--rlimit_as", str(self.config.max_memory_mb),
            "--rlimit_fsize", str(self.config.max_file_size_mb),
            "--rlimit_nproc", str(self.config.max_processes),
        ]
        
        # Add read-only binds
        for path in self.config.read_only_paths:
            nsjail_cmd.extend(["-R", str(path)])
        
        # Add read-write binds
        cwd = kwargs.get("cwd") or Path.cwd()
        nsjail_cmd.extend(["-B", str(cwd)])
        for path in self.config.read_write_paths:
            nsjail_cmd.extend(["-B", str(path)])
        
        # Network
        if not self.config.allow_network:
            nsjail_cmd.append("--disable_clone_newnet")
        
        # Add extra args
        nsjail_cmd.extend(self.config.extra_args)
        
        # Add the actual command
        nsjail_cmd.append("--")
        nsjail_cmd.extend(cmd)
        
        return self._run_unsandboxed(nsjail_cmd, **kwargs)

    def _run_firejail(
        self,
        cmd: List[str],
        **kwargs,
    ) -> subprocess.CompletedProcess:
        """Run command in firejail sandbox."""
        firejail_cmd = ["firejail", "--quiet"]
        
        # Resource limits
        firejail_cmd.extend(["--rlimit-as", str(self.config.max_memory_mb * 1024 * 1024)])
        
        # Network
        if not self.config.allow_network:
            firejail_cmd.append("--net=none")
        
        # Add extra args
        firejail_cmd.extend(self.config.extra_args)
        
        # Add the actual command
        firejail_cmd.extend(cmd)
        
        return self._run_unsandboxed(firejail_cmd, **kwargs)

    def _run_docker(
        self,
        cmd: List[str],
        **kwargs,
    ) -> subprocess.CompletedProcess:
        """Run command in docker container."""
        docker_cmd = [
            "docker", "run", "--rm",
            "--memory", f"{self.config.max_memory_mb}m",
            "--cpus", "1",
        ]
        
        # Network
        if not self.config.allow_network:
            docker_cmd.append("--network=none")
        
        # Mount working directory
        cwd = kwargs.get("cwd") or Path.cwd()
        docker_cmd.extend(["-v", f"{cwd}:/workspace", "-w", "/workspace"])
        
        # Mount read-write paths
        for path in self.config.read_write_paths:
            docker_cmd.extend(["-v", f"{path}:{path}"])
        
        # Mount read-only paths
        for path in self.config.read_only_paths:
            docker_cmd.extend(["-v", f"{path}:{path}:ro"])
        
        # Add extra args
        docker_cmd.extend(self.config.extra_args)
        
        # Add image and command
        docker_cmd.append(self.config.docker_image)
        docker_cmd.extend(cmd)
        
        return self._run_unsandboxed(docker_cmd, **kwargs)


def create_sandbox_runner(
    workspace_dir: Path,
    *,
    sandbox_type: Optional[SandboxType] = None,
    allow_network: bool = False,
) -> SandboxRunner:
    """
    Create a sandbox runner with sensible defaults.
    
    Args:
        workspace_dir: Working directory to allow writes
        sandbox_type: Override sandbox type
        allow_network: Whether to allow network access
        
    Returns:
        Configured SandboxRunner
    """
    config = SandboxConfig(
        sandbox_type=sandbox_type or get_default_sandbox_type(),
        read_write_paths=[workspace_dir],
        allow_network=allow_network,
    )
    return SandboxRunner(config)
