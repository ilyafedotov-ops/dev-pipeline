"""
DevGodzilla Engines

Multi-agent execution layer with unified interface for 18+ AI coding agents.
"""

from devgodzilla.engines.interface import (
    Engine,
    EngineKind,
    EngineMetadata,
    EngineRequest,
    EngineResult,
    SandboxMode,
)
from devgodzilla.engines.registry import (
    EngineRegistry,
    EngineNotFoundError,
    get_registry,
    register_engine,
    get_engine,
    get_default_engine,
)
from devgodzilla.engines.cli_adapter import CLIEngine, run_cli_command
from devgodzilla.engines.codex import CodexEngine, register_codex_engine
from devgodzilla.engines.claude_code import ClaudeCodeEngine, register_claude_code_engine
from devgodzilla.engines.opencode import OpenCodeEngine, register_opencode_engine
from devgodzilla.engines.artifacts import Artifact, ArtifactWriter
from devgodzilla.engines.sandbox import (
    SandboxType,
    SandboxConfig,
    SandboxRunner,
    is_sandbox_available,
    get_default_sandbox_type,
    create_sandbox_runner,
)

__all__ = [
    # Interface
    "Engine",
    "EngineKind",
    "EngineMetadata",
    "EngineRequest",
    "EngineResult",
    "SandboxMode",
    # Registry
    "EngineRegistry",
    "EngineNotFoundError",
    "get_registry",
    "register_engine",
    "get_engine",
    "get_default_engine",
    # Adapters
    "CLIEngine",
    "run_cli_command",
    # Engine implementations
    "CodexEngine",
    "register_codex_engine",
    "ClaudeCodeEngine",
    "register_claude_code_engine",
    "OpenCodeEngine",
    "register_opencode_engine",
    # Artifacts
    "Artifact",
    "ArtifactWriter",
    # Sandbox
    "SandboxType",
    "SandboxConfig",
    "SandboxRunner",
    "is_sandbox_available",
    "get_default_sandbox_type",
    "create_sandbox_runner",
]
