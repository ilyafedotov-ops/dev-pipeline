"""
DevGodzilla Engine Interface

Defines the common interface for AI coding agent engines.
Supports CLI, API, and IDE-based agents.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from devgodzilla.logging import get_logger

logger = get_logger(__name__)


class EngineKind(str, Enum):
    """Type of engine adapter."""
    CLI = "cli"       # Command-line agents (Codex, Claude Code, etc.)
    API = "api"       # API-based agents
    IDE = "ide"       # IDE-integrated agents (Cursor, Copilot)


class SandboxMode(str, Enum):
    """Sandbox security modes."""
    FULL_ACCESS = "full-access"       # Full filesystem access (planning)
    WORKSPACE_WRITE = "workspace-write"  # Write to workspace only (execution)
    READ_ONLY = "read-only"           # Read-only (QA)


@dataclass
class EngineMetadata:
    """Metadata about an engine."""
    id: str
    display_name: str
    kind: EngineKind
    default_model: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)


@dataclass
class EngineRequest:
    """Request to execute a task with an engine."""
    project_id: int
    protocol_run_id: int
    step_run_id: int
    
    # Model configuration
    model: Optional[str] = None
    
    # Prompt/task
    prompt_text: Optional[str] = None
    prompt_files: List[str] = field(default_factory=list)
    
    # Working directory
    working_dir: str = "."
    
    # Sandbox mode
    sandbox: SandboxMode = SandboxMode.WORKSPACE_WRITE
    
    # Timeout in seconds
    timeout: Optional[int] = None
    
    # Additional parameters
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EngineResult:
    """Result from an engine execution."""
    success: bool
    stdout: str = ""
    stderr: str = ""
    
    # Cost tracking
    tokens_used: Optional[int] = None
    cost_cents: Optional[int] = None
    
    # Execution details
    duration_seconds: Optional[float] = None
    exit_code: Optional[int] = None
    
    # Additional data
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Error details if failed
    error: Optional[str] = None


class Engine(ABC):
    """
    Abstract base class for AI coding engines.
    
    All engines must implement plan, execute, and qa methods.
    The sync_config method is optional for engines that support
    configuration synchronization.
    
    Example implementation:
        class MyEngine(Engine):
            @property
            def metadata(self) -> EngineMetadata:
                return EngineMetadata(
                    id="my-engine",
                    display_name="My Engine",
                    kind=EngineKind.CLI,
                )
            
            def plan(self, req: EngineRequest) -> EngineResult:
                # Planning implementation
                ...
            
            def execute(self, req: EngineRequest) -> EngineResult:
                # Execution implementation
                ...
            
            def qa(self, req: EngineRequest) -> EngineResult:
                # QA implementation
                ...
    """

    @property
    @abstractmethod
    def metadata(self) -> EngineMetadata:
        """Engine metadata."""
        ...

    @abstractmethod
    def plan(self, req: EngineRequest) -> EngineResult:
        """
        Execute a planning task.
        
        Typically runs with full filesystem access.
        """
        ...

    @abstractmethod
    def execute(self, req: EngineRequest) -> EngineResult:
        """
        Execute a coding task.
        
        Typically runs with workspace-write sandbox.
        """
        ...

    @abstractmethod
    def qa(self, req: EngineRequest) -> EngineResult:
        """
        Execute a QA/review task.
        
        Typically runs in read-only mode.
        """
        ...

    def sync_config(self, additional_agents: Optional[List[Dict[str, Any]]] = None) -> None:
        """
        Synchronize engine configuration.
        
        Optional method for engines that support dynamic configuration.
        """
        pass

    def check_availability(self) -> bool:
        """
        Check if the engine is available and properly configured.
        
        Returns True if the engine can accept requests.
        """
        return True

    def get_prompt_text(self, req: EngineRequest) -> str:
        """
        Get the full prompt text from a request.
        
        Combines prompt_text and prompt_files.
        """
        parts = []
        
        if req.prompt_text:
            parts.append(req.prompt_text)
        
        for path in req.prompt_files:
            try:
                parts.append(Path(path).read_text(encoding="utf-8"))
            except Exception:
                continue
        
        return "\n".join(parts)
