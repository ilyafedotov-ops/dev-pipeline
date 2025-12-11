"""Test environment management for CLI workflow harness."""

import os
import shutil
import sqlite3
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional, Dict, Any
import subprocess
import sys

from .config import EnvironmentConfig, HarnessProject
from .models import HarnessStatus


class EnvironmentContext:
    """Context for test environment setup."""
    
    def __init__(self, temp_dir: Path, config: EnvironmentConfig):
        self.temp_dir = temp_dir
        self.config = config
        self.projects: dict[str, HarnessProject] = {}
        self.original_env: Dict[str, str] = {}
        self.redis_client = None
        self.database_path: Optional[Path] = None
        # Add workspace_path for components that need it
        self.workspace_path = temp_dir
        
    def cleanup(self) -> None:
        """Clean up temporary resources."""
        # Clean up Redis test data
        if self.redis_client:
            try:
                self.redis_client.flushdb()
                self.redis_client.close()
            except Exception:
                pass  # Ignore cleanup errors
        
        # Clean up temporary directory
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        
        # Restore original environment variables
        for key, value in self.original_env.items():
            if key in os.environ and os.environ[key] != value:
                os.environ[key] = value


class TestEnvironment:
    """Manages test environment setup and cleanup."""
    
    def __init__(self, config: Optional[EnvironmentConfig] = None):
        self.config = config or EnvironmentConfig.from_environment()
        self._context: Optional[EnvironmentContext] = None
    
    @contextmanager
    def setup(self) -> Generator[EnvironmentContext, None, None]:
        """Initialize test environment with databases, Redis, etc."""
        temp_dir = Path(tempfile.mkdtemp(prefix="harness_"))
        context = EnvironmentContext(temp_dir, self.config)
        
        try:
            self._setup_environment_variables(context)
            self._validate_dependencies()
            self._setup_redis_connection(context)
            self._context = context
            yield context
        finally:
            context.cleanup()
            self._context = None
    
    def create_test_project(self, project_type: str = "python", name: str = "test-project") -> HarnessProject:
        """Create realistic test project with Git history."""
        if not self._context:
            raise RuntimeError("Environment not set up. Use setup() context manager.")
        
        # Import here to avoid circular imports
        from .data_generator import TestDataGenerator
        
        generator = TestDataGenerator(self._context.temp_dir)
        
        if project_type == "demo-bootstrap":
            return self._create_demo_bootstrap_project(self._context.temp_dir / name, name)
        elif project_type == "python":
            return generator.create_python_project(name)
        elif project_type == "javascript":
            return generator.create_javascript_project(name)
        elif project_type == "mixed":
            return generator.create_mixed_project(name)
        else:
            raise ValueError(f"Unsupported project type: {project_type}")
    
    def _setup_environment_variables(self, context: EnvironmentContext) -> None:
        """Set up environment variables for test execution."""
        # Set up temporary database
        if not self.config.database_url:
            db_path = context.temp_dir / "test.sqlite"
            self._initialize_database(db_path)
            os.environ["TASKSGODZILLA_DB_PATH"] = str(db_path)
            # Set the database path in the context for components to use
            context.database_path = db_path
        else:
            # Use provided database URL
            os.environ["TASKSGODZILLA_DB_URL"] = self.config.database_url
            # For URL-based databases, we don't set database_path as it's not a file path
        
        # Ensure Redis URL is set
        if self.config.redis_url:
            os.environ["TASKSGODZILLA_REDIS_URL"] = self.config.redis_url
        
        # Set inline worker for tests
        os.environ["TASKSGODZILLA_INLINE_RQ_WORKER"] = "true"
        
        # Disable auto-clone for tests
        os.environ["TASKSGODZILLA_AUTO_CLONE"] = "false"
        
        # Set test-specific configurations
        os.environ["TASKSGODZILLA_LOG_LEVEL"] = "WARNING"  # Reduce log noise in tests
        os.environ["TASKSGODZILLA_TEST_MODE"] = "true"
        
        # Store original environment for cleanup
        context.original_env = dict(os.environ)
    
    def _validate_dependencies(self) -> None:
        """Validate required dependencies are available."""
        validation_errors = []
        
        # Check Redis connectivity
        if self.config.redis_url:
            try:
                import redis
                client = redis.Redis.from_url(self.config.redis_url)
                client.ping()
            except ImportError:
                validation_errors.append("Redis Python client not available (pip install redis)")
            except Exception as e:
                validation_errors.append(f"Redis not available at {self.config.redis_url}: {e}")
        else:
            validation_errors.append("TASKSGODZILLA_REDIS_URL environment variable not set")
        
        # Check Python dependencies
        required_modules = ["tasksgodzilla", "pytest", "hypothesis"]
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                validation_errors.append(f"Required Python module '{module}' not available")
        
        # Check for Codex CLI if configured
        if self.config.codex_available:
            codex_path = os.environ.get("CODEX_CLI_PATH", "codex")
            try:
                result = subprocess.run([codex_path, "--version"], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode != 0:
                    validation_errors.append(f"Codex CLI not working: {result.stderr}")
            except (subprocess.TimeoutExpired, FileNotFoundError):
                validation_errors.append(f"Codex CLI not found at {codex_path}")
        
        # Check Git availability
        try:
            result = subprocess.run(["git", "--version"], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                validation_errors.append("Git not available")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            validation_errors.append("Git command not found")
        
        if validation_errors:
            raise RuntimeError("Environment validation failed:\n" + "\n".join(f"- {error}" for error in validation_errors))
    
    def _create_demo_bootstrap_project(self, project_dir: Path, name: str) -> HarnessProject:
        """Create test project from demo_bootstrap."""
        # Create project directory
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy demo_bootstrap files
        bootstrap_path = Path(__file__).resolve().parents[2] / "demo_bootstrap"
        if bootstrap_path.exists():
            for item in bootstrap_path.iterdir():
                dest = project_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_text(item.read_text(encoding="utf-8"), encoding="utf-8")
        
        return HarnessProject(
            name=name,
            git_url="",
            local_path=project_dir,
            project_type="python",
            has_tests=True,
            has_docs=True,
        )
    

    
    def _initialize_database(self, db_path: Path) -> None:
        """Initialize SQLite database for testing."""
        # Create database directory if it doesn't exist
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create basic database schema for testing
        conn = sqlite3.connect(str(db_path))
        try:
            # Create tables matching the main schema for compatibility
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    git_url TEXT NOT NULL,
                    base_branch TEXT NOT NULL,
                    local_path TEXT,
                    ci_provider TEXT,
                    secrets TEXT,
                    default_models TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS protocol_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id),
                    protocol_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    base_branch TEXT NOT NULL,
                    worktree_path TEXT,
                    protocol_root TEXT,
                    description TEXT,
                    template_config TEXT,
                    template_source TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS step_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    protocol_run_id INTEGER NOT NULL REFERENCES protocol_runs(id),
                    step_index INTEGER NOT NULL,
                    step_name TEXT NOT NULL,
                    step_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    retries INTEGER DEFAULT 0,
                    model TEXT,
                    engine_id TEXT,
                    policy TEXT,
                    runtime_state TEXT,
                    summary TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    protocol_run_id INTEGER NOT NULL REFERENCES protocol_runs(id),
                    step_run_id INTEGER REFERENCES step_runs(id),
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    metadata TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS test_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_id TEXT NOT NULL,
                    component TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
        finally:
            conn.close()
    
    def _setup_redis_connection(self, context: EnvironmentContext) -> None:
        """Set up Redis connection for testing."""
        if self.config.redis_url:
            try:
                import redis
                client = redis.Redis.from_url(self.config.redis_url)
                # Clear any existing test data
                client.flushdb()
                context.redis_client = client
            except Exception as e:
                raise RuntimeError(f"Failed to setup Redis connection: {e}")
    
    def validate_environment_variables(self) -> Dict[str, Any]:
        """Validate all required environment variables are set."""
        required_vars = [
            "TASKSGODZILLA_REDIS_URL",
        ]
        
        optional_vars = [
            "TASKSGODZILLA_DB_URL",
            "TASKSGODZILLA_DB_PATH", 
            "TASKSGODZILLA_API_TOKEN",
            "CODEX_CLI_PATH",
        ]
        
        validation_result = {
            "valid": True,
            "missing_required": [],
            "missing_optional": [],
            "present": {},
        }
        
        # Check required variables
        for var in required_vars:
            value = os.environ.get(var)
            if value:
                validation_result["present"][var] = value
            else:
                validation_result["missing_required"].append(var)
                validation_result["valid"] = False
        
        # Check optional variables
        for var in optional_vars:
            value = os.environ.get(var)
            if value:
                validation_result["present"][var] = value
            else:
                validation_result["missing_optional"].append(var)
        
        return validation_result