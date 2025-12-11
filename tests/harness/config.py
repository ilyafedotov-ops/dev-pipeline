"""Configuration management for CLI workflow harness."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional


class HarnessMode(Enum):
    """Test execution modes for the harness."""
    FULL = "full"  # Execute all workflow tests end-to-end
    COMPONENT = "component"  # Test individual CLI scripts in isolation
    SMOKE = "smoke"  # Execute minimal set of critical path tests
    REGRESSION = "regression"  # Focus on previously failing scenarios
    DEVELOPMENT = "development"  # Provide verbose output and debugging
    CI = "ci"  # Non-interactive mode for continuous integration


@dataclass
class HarnessConfig:
    """Configuration for harness execution."""
    mode: HarnessMode
    components: List[str]
    test_data_path: Path
    output_path: Path
    verbose: bool = False
    parallel: bool = False
    timeout: int = 1800  # 30 minutes default
    max_workers: int = 4
    
    @classmethod
    def create_default(cls, mode: HarnessMode = HarnessMode.SMOKE) -> "HarnessConfig":
        """Create default configuration for the specified mode."""
        return cls(
            mode=mode,
            components=[],
            test_data_path=Path("tests/harness/data"),
            output_path=Path("tests/harness/output"),
            verbose=mode == HarnessMode.DEVELOPMENT,
            parallel=mode in (HarnessMode.CI, HarnessMode.FULL),
            timeout=300 if mode == HarnessMode.SMOKE else 1800,
        )


@dataclass
class HarnessProject:
    """Test project configuration and metadata."""
    name: str
    git_url: str
    local_path: Path
    project_type: str  # "python", "javascript", "mixed", etc.
    has_tests: bool = False
    has_docs: bool = False
    has_ci: bool = False
    
    @classmethod
    def from_demo_bootstrap(cls, workspace_path: Path) -> "HarnessProject":
        """Create test project from demo_bootstrap."""
        return cls(
            name="demo-bootstrap",
            git_url="",  # Local project
            local_path=workspace_path,
            project_type="python",
            has_tests=True,
            has_docs=True,
            has_ci=False,
        )


@dataclass
class EnvironmentConfig:
    """Environment configuration for test execution."""
    database_url: Optional[str] = None
    redis_url: Optional[str] = None
    codex_available: bool = False
    api_token: Optional[str] = None
    temp_dir: Optional[Path] = None
    
    @classmethod
    def from_environment(cls) -> "EnvironmentConfig":
        """Create configuration from environment variables."""
        import os
        return cls(
            database_url=os.environ.get("TASKSGODZILLA_DB_URL") or os.environ.get("TASKSGODZILLA_DB_PATH"),
            redis_url=os.environ.get("TASKSGODZILLA_REDIS_URL", "redis://localhost:6379/15"),
            codex_available=bool(os.environ.get("CODEX_CLI_PATH")),
            api_token=os.environ.get("TASKSGODZILLA_API_TOKEN"),
        )