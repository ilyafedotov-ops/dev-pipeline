"""API utilities for CLI workflow harness - handles server startup detection and retry mechanisms."""

import time
import requests
import subprocess
import logging
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from contextlib import contextmanager


class APIServerManager:
    """Manages API server startup, health checking, and shutdown for testing."""
    
    def __init__(self, host: str = "localhost", port: int = 8010, timeout: int = 30):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://{host}:{port}"
        self.health_url = f"{self.base_url}/health"
        self.logger = logging.getLogger(__name__)
        self._server_process: Optional[subprocess.Popen] = None
        self._startup_thread: Optional[threading.Thread] = None
        
    def is_server_running(self) -> bool:
        """Check if API server is running and responding."""
        try:
            response = requests.get(self.health_url, timeout=2)
            return response.status_code == 200
        except (requests.RequestException, requests.Timeout):
            return False
    
    def wait_for_server_startup(self, max_wait: int = 30) -> bool:
        """Wait for API server to start up and become ready."""
        self.logger.info(f"Waiting for API server at {self.base_url} (max {max_wait}s)")
        
        start_time = time.time()
        while time.time() - start_time < max_wait:
            if self.is_server_running():
                self.logger.info(f"API server is ready at {self.base_url}")
                return True
            
            time.sleep(0.5)  # Check every 500ms
        
        self.logger.warning(f"API server did not start within {max_wait}s")
        return False
    
    def start_server(self, background: bool = True) -> bool:
        """Start the API server process."""
        if self.is_server_running():
            self.logger.info("API server already running")
            return True
        
        project_root = Path(__file__).resolve().parents[2]
        api_script = project_root / "scripts" / "api_server.py"
        
        if not api_script.exists():
            self.logger.error(f"API server script not found: {api_script}")
            return False
        
        try:
            self.logger.info(f"Starting API server at {self.host}:{self.port}")
            
            # Start server process
            self._server_process = subprocess.Popen(
                ["python3", str(api_script), "--host", self.host, "--port", str(self.port)],
                cwd=project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if background:
                # Wait for startup in background thread
                self._startup_thread = threading.Thread(
                    target=self._wait_for_startup_background,
                    daemon=True
                )
                self._startup_thread.start()
                
                # Give it a moment to start
                time.sleep(1)
                return True
            else:
                # Wait for startup synchronously
                return self.wait_for_server_startup(self.timeout)
                
        except Exception as e:
            self.logger.error(f"Failed to start API server: {e}")
            return False
    
    def _wait_for_startup_background(self) -> None:
        """Wait for server startup in background thread."""
        if self.wait_for_server_startup(self.timeout):
            self.logger.info("API server startup completed in background")
        else:
            self.logger.error("API server failed to start in background")
    
    def stop_server(self) -> None:
        """Stop the API server process."""
        if self._server_process:
            try:
                self.logger.info("Stopping API server")
                self._server_process.terminate()
                
                # Wait for graceful shutdown
                try:
                    self._server_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.logger.warning("API server did not stop gracefully, killing")
                    self._server_process.kill()
                    self._server_process.wait()
                
                self._server_process = None
                self.logger.info("API server stopped")
                
            except Exception as e:
                self.logger.error(f"Error stopping API server: {e}")
    
    @contextmanager
    def managed_server(self):
        """Context manager for API server lifecycle."""
        try:
            if self.start_server(background=False):
                yield self
            else:
                raise RuntimeError("Failed to start API server")
        finally:
            self.stop_server()


class RetryableAPIClient:
    """API client with retry mechanisms and timeout handling."""
    
    def __init__(self, base_url: str, max_retries: int = 3, retry_delay: float = 1.0):
        self.base_url = base_url.rstrip('/')
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        
        # Set reasonable timeouts
        self.session.timeout = (5, 30)  # (connect, read) timeouts
    
    def get(self, endpoint: str, **kwargs) -> requests.Response:
        """GET request with retry logic."""
        return self._request_with_retry('GET', endpoint, **kwargs)
    
    def post(self, endpoint: str, **kwargs) -> requests.Response:
        """POST request with retry logic."""
        return self._request_with_retry('POST', endpoint, **kwargs)
    
    def put(self, endpoint: str, **kwargs) -> requests.Response:
        """PUT request with retry logic."""
        return self._request_with_retry('PUT', endpoint, **kwargs)
    
    def delete(self, endpoint: str, **kwargs) -> requests.Response:
        """DELETE request with retry logic."""
        return self._request_with_retry('DELETE', endpoint, **kwargs)
    
    def _request_with_retry(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make HTTP request with retry logic."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                self.logger.debug(f"API {method} {url} (attempt {attempt + 1})")
                
                response = self.session.request(method, url, **kwargs)
                
                # Log response for debugging
                self.logger.debug(f"API response: {response.status_code}")
                
                return response
                
            except (requests.ConnectionError, requests.Timeout) as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    self.logger.warning(f"API request failed (attempt {attempt + 1}): {e}")
                    time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                else:
                    self.logger.error(f"API request failed after {self.max_retries + 1} attempts: {e}")
            
            except Exception as e:
                # Don't retry for other exceptions (e.g., HTTP errors)
                self.logger.error(f"API request error: {e}")
                raise
        
        # If we get here, all retries failed
        raise last_exception


class CLICommandRunner:
    """Runs CLI commands with improved timeout handling and API connectivity."""
    
    def __init__(self, api_manager: Optional[APIServerManager] = None):
        self.api_manager = api_manager
        self.logger = logging.getLogger(__name__)
        self.project_root = Path(__file__).resolve().parents[2]
        self.cli_script = self.project_root / "scripts" / "tasksgodzilla_cli.py"
    
    def run_command(self, args: list, timeout: int = 30, 
                   wait_for_api: bool = True) -> subprocess.CompletedProcess:
        """Run CLI command with improved timeout and API handling."""
        
        # Ensure API server is available if needed
        if wait_for_api and self.api_manager:
            if not self.api_manager.is_server_running():
                self.logger.info("Starting API server for CLI command")
                if not self.api_manager.start_server(background=False):
                    self.logger.warning("Failed to start API server, command may fail")
        
        # Prepare command
        cmd = ["python3", str(self.cli_script)] + args
        
        # Set environment with API configuration
        import os
        env = os.environ.copy()
        if self.api_manager:
            env["TASKSGODZILLA_API_BASE"] = self.api_manager.base_url
        
        try:
            self.logger.debug(f"Running CLI command: {' '.join(args)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.project_root,
                env=env
            )
            
            self.logger.debug(f"CLI command completed: rc={result.returncode}")
            return result
            
        except subprocess.TimeoutExpired as e:
            self.logger.warning(f"CLI command timed out after {timeout}s: {args}")
            raise
    
    def run_command_with_retry(self, args: list, max_retries: int = 2, 
                              timeout: int = 30) -> subprocess.CompletedProcess:
        """Run CLI command with retry logic for transient failures."""
        
        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                return self.run_command(args, timeout=timeout)
                
            except subprocess.TimeoutExpired as e:
                last_exception = e
                
                if attempt < max_retries:
                    self.logger.warning(f"CLI command timed out (attempt {attempt + 1}), retrying...")
                    time.sleep(2)  # Brief delay before retry
                else:
                    self.logger.error(f"CLI command failed after {max_retries + 1} attempts")
        
        raise last_exception
    
    def test_api_connectivity(self) -> bool:
        """Test API connectivity with CLI commands."""
        try:
            # Try a simple command that should work quickly
            result = self.run_command(["--help"], timeout=5, wait_for_api=False)
            return result.returncode == 0
        except Exception:
            return False


def get_optimal_timeout(command_type: str) -> int:
    """Get optimal timeout for different types of CLI commands."""
    timeout_map = {
        "help": 5,           # Help commands should be fast
        "list": 15,          # List commands are usually quick
        "create": 60,        # Create commands can be slower
        "update": 30,        # Update commands are moderate
        "delete": 15,        # Delete commands are usually quick
        "status": 10,        # Status commands should be quick
        "interactive": 300,  # Interactive mode needs longer timeout
        "default": 30,       # Default timeout
    }
    
    return timeout_map.get(command_type, timeout_map["default"])


def detect_command_type(args: list) -> str:
    """Detect command type from CLI arguments for optimal timeout."""
    if not args:
        return "help"
    
    if "--help" in args or "-h" in args:
        return "help"
    
    if len(args) >= 2:
        action = args[1].lower()
        if action in ["list", "ls"]:
            return "list"
        elif action in ["create", "add"]:
            return "create"
        elif action in ["update", "edit", "modify"]:
            return "update"
        elif action in ["delete", "remove", "rm"]:
            return "delete"
        elif action in ["status", "info", "show"]:
            return "status"
    
    return "default"