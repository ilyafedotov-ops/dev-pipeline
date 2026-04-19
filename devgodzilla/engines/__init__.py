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
from devgodzilla.engines.ide import IDEEngine, IDECommand, IDECommandFile
from devgodzilla.engines.api_engine import APIEngine, APIRequestConfig, APIResponse
from devgodzilla.engines.codex import CodexEngine, register_codex_engine
from devgodzilla.engines.gemini import GeminiEngine, register_gemini_engine
from devgodzilla.engines.claude_code import ClaudeCodeEngine, register_claude_code_engine
from devgodzilla.engines.opencode import OpenCodeEngine, register_opencode_engine
from devgodzilla.engines.cursor import CursorEngine, register_cursor_engine
from devgodzilla.engines.windsurf import WindsurfEngine, register_windsurf_engine
from devgodzilla.engines.copilot import (
    CopilotEngine,
    CopilotAPIEngine,
    register_copilot_engine,
    register_copilot_api_engine,
)
from devgodzilla.engines.qoder import QoderEngine, register_qoder_engine
from devgodzilla.engines.qwen import QwenEngine, register_qwen_engine
from devgodzilla.engines.amazon_q import AmazonQEngine, register_amazon_q_engine
from devgodzilla.engines.auggie import AuggieEngine, register_auggie_engine
from devgodzilla.engines.codebuddy import CodeBuddyEngine, register_codebuddy_engine
from devgodzilla.engines.kilo import KiloEngine, register_kilo_engine
from devgodzilla.engines.roo import RooEngine, register_roo_engine
from devgodzilla.engines.amp import AmpEngine, register_amp_engine
from devgodzilla.engines.shai import SHAIEngine, register_shai_engine
from devgodzilla.engines.bob import BobEngine, register_bob_engine
from devgodzilla.engines.jules import JulesEngine, register_jules_engine
from devgodzilla.engines.dummy import DummyEngine
from devgodzilla.engines.artifacts import Artifact, ArtifactWriter
from devgodzilla.engines.sandbox import (
    SandboxType,
    SandboxConfig,
    SandboxRunner,
    is_sandbox_available,
    get_default_sandbox_type,
    create_sandbox_runner,
)
from devgodzilla.engines.block_detector import (
    BlockDetector,
    BlockInfo,
    BlockReason,
    detect_block,
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
    "IDEEngine",
    "IDECommand",
    "IDECommandFile",
    "APIEngine",
    "APIRequestConfig",
    "APIResponse",
    # Engine implementations
    "CodexEngine",
    "register_codex_engine",
    "GeminiEngine",
    "register_gemini_engine",
    "ClaudeCodeEngine",
    "register_claude_code_engine",
    "OpenCodeEngine",
    "register_opencode_engine",
    "CursorEngine",
    "register_cursor_engine",
    "WindsurfEngine",
    "register_windsurf_engine",
    "CopilotEngine",
    "CopilotAPIEngine",
    "register_copilot_engine",
    "register_copilot_api_engine",
    "QoderEngine",
    "register_qoder_engine",
    "QwenEngine",
    "register_qwen_engine",
    "AmazonQEngine",
    "register_amazon_q_engine",
    "AuggieEngine",
    "register_auggie_engine",
    "CodeBuddyEngine",
    "register_codebuddy_engine",
    "KiloEngine",
    "register_kilo_engine",
    "RooEngine",
    "register_roo_engine",
    "AmpEngine",
    "register_amp_engine",
    "SHAIEngine",
    "register_shai_engine",
    "BobEngine",
    "register_bob_engine",
    "JulesEngine",
    "register_jules_engine",
    "DummyEngine",
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
    # Block Detection
    "BlockDetector",
    "BlockInfo",
    "BlockReason",
    "detect_block",
]
