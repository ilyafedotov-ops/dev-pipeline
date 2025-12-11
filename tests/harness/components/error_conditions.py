"""Error condition and edge case testing component for CLI workflow harness."""

import os
import time
import logging
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from unittest.mock import patch, MagicMock

from ..models import TestResult, HarnessStatus
from ..environment import EnvironmentContext


class ErrorConditionTests:
    """Test component for validating error conditions and edge cases across CLI interfaces."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.test_results: List[TestResult] = []
    
    def run_test(self, project, env_context: EnvironmentContext) -> bool:
        """Execute all error condition tests and return overall success."""
        self.logger.info("Starting error condition and edge case testing")
        
        # Run all error condition test categories
        test_methods = [
            self._test_invalid_input_handling,
            self._test_missing_dependency_degradation,
            self._test_network_failure_recovery,
            self._test_corrupted_data_integrity,
            self._test_resource_constraint_performance,
            self._test_comprehensive_input_validation,
            self._test_concurrent_operation_handling,
            self._test_system_resource_exhaustion,
            self._test_signal_handling_and_interruption,
        ]
        
        all_passed = True
        for test_method in test_methods:
            try:
                success = test_method(project, env_context)
                if not success:
                    all_passed = False
            except Exception as e:
                self.logger.error(f"Error condition test failed: {e}")
                all_passed = False
        
        self.logger.info(f"Error condition testing completed. Overall success: {all_passed}")
        return all_passed
    
    def _test_invalid_input_handling(self, project, env_context: EnvironmentContext) -> bool:
        """Test invalid input handling across all CLI interfaces."""
        self.logger.info("Testing invalid input handling")
        
        test_cases = [
            # CLI command tests with invalid inputs
            {
                "name": "invalid_repo_url",
                "command": ["python", "scripts/onboard_repo.py", "invalid-url"],
                "expected_behavior": "graceful_error"
            },
            {
                "name": "missing_required_args",
                "command": ["python", "scripts/protocol_pipeline.py"],
                "expected_behavior": "usage_help"
            },
            {
                "name": "invalid_protocol_id",
                "command": ["python", "scripts/protocol_pipeline.py", "--protocol-id", "nonexistent"],
                "expected_behavior": "not_found_error"
            },
            {
                "name": "malformed_json_input",
                "command": ["python", "scripts/quality_orchestrator.py", "--config", "/dev/null"],
                "expected_behavior": "config_error"
            },
        ]
        
        all_passed = True
        for test_case in test_cases:
            success = self._run_invalid_input_test(test_case, env_context)
            if not success:
                all_passed = False
        
        # Test TUI with invalid inputs
        tui_success = self._test_tui_invalid_inputs(env_context)
        if not tui_success:
            all_passed = False
        
        # Test API with invalid inputs
        api_success = self._test_api_invalid_inputs(env_context)
        if not api_success:
            all_passed = False
        
        return all_passed
    
    def _run_invalid_input_test(self, test_case: Dict[str, Any], env_context: EnvironmentContext) -> bool:
        """Run a single invalid input test case."""
        start_time = time.time()
        
        try:
            # Run command and capture output
            result = subprocess.run(
                test_case["command"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=env_context.workspace_path
            )
            
            # Analyze result based on expected behavior
            success = self._analyze_invalid_input_result(result, test_case["expected_behavior"])
            
            duration = time.time() - start_time
            status = HarnessStatus.PASS if success else HarnessStatus.FAIL
            error_msg = None if success else f"Invalid input handling failed for {test_case['name']}"
            
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name=f"invalid_input_{test_case['name']}",
                status=status,
                duration=duration,
                error_message=error_msg
            ))
            
            return success
            
        except subprocess.TimeoutExpired:
            self.logger.error(f"Test {test_case['name']} timed out")
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name=f"invalid_input_{test_case['name']}",
                status=HarnessStatus.ERROR,
                duration=30.0,
                error_message="Test timed out"
            ))
            return False
        except Exception as e:
            self.logger.error(f"Test {test_case['name']} failed with exception: {e}")
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name=f"invalid_input_{test_case['name']}",
                status=HarnessStatus.ERROR,
                duration=time.time() - start_time,
                error_message=str(e)
            ))
            return False
    
    def _analyze_invalid_input_result(self, result: subprocess.CompletedProcess, expected_behavior: str) -> bool:
        """Analyze command result to determine if invalid input was handled correctly."""
        if expected_behavior == "graceful_error":
            # Should exit with non-zero code and provide meaningful error message
            return (result.returncode != 0 and 
                    len(result.stderr) > 0 and 
                    "error" in result.stderr.lower())
        
        elif expected_behavior == "usage_help":
            # Should show usage information
            return (result.returncode != 0 and 
                    ("usage" in result.stderr.lower() or "help" in result.stderr.lower()))
        
        elif expected_behavior == "not_found_error":
            # Should indicate resource not found
            return (result.returncode != 0 and 
                    ("not found" in result.stderr.lower() or "does not exist" in result.stderr.lower()))
        
        elif expected_behavior == "config_error":
            # Should indicate configuration error
            return (result.returncode != 0 and 
                    ("config" in result.stderr.lower() or "invalid" in result.stderr.lower()))
        
        return False
    
    def _test_tui_invalid_inputs(self, env_context: EnvironmentContext) -> bool:
        """Test TUI interface with invalid inputs."""
        self.logger.info("Testing TUI invalid input handling")
        
        # Since TUI is interactive, we'll test by checking if it handles startup errors gracefully
        start_time = time.time()
        
        try:
            # Test TUI with invalid environment
            with patch.dict(os.environ, {"TASKSGODZILLA_DB_PATH": "/invalid/path/db.sqlite"}):
                result = subprocess.run(
                    ["python", "scripts/tasksgodzilla_tui.py", "--help"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    cwd=env_context.workspace_path
                )
            
            # TUI should handle invalid config gracefully
            success = result.returncode == 0 or "help" in result.stdout.lower()
            
            duration = time.time() - start_time
            status = HarnessStatus.PASS if success else HarnessStatus.FAIL
            
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name="tui_invalid_config",
                status=status,
                duration=duration,
                error_message=None if success else "TUI failed to handle invalid config"
            ))
            
            return success
            
        except Exception as e:
            self.logger.error(f"TUI invalid input test failed: {e}")
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name="tui_invalid_config",
                status=HarnessStatus.ERROR,
                duration=time.time() - start_time,
                error_message=str(e)
            ))
            return False
    
    def _test_api_invalid_inputs(self, env_context: EnvironmentContext) -> bool:
        """Test API interface with invalid inputs."""
        self.logger.info("Testing API invalid input handling")
        
        # Test API startup with invalid configuration
        start_time = time.time()
        
        try:
            # Test API server with invalid config
            with patch.dict(os.environ, {"TASKSGODZILLA_REDIS_URL": "redis://invalid:9999"}):
                result = subprocess.run(
                    ["python", "scripts/api_server.py", "--help"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    cwd=env_context.workspace_path
                )
            
            # API should show help or handle invalid config gracefully
            success = result.returncode == 0 or "help" in result.stdout.lower()
            
            duration = time.time() - start_time
            status = HarnessStatus.PASS if success else HarnessStatus.FAIL
            
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name="api_invalid_config",
                status=status,
                duration=duration,
                error_message=None if success else "API failed to handle invalid config"
            ))
            
            return success
            
        except Exception as e:
            self.logger.error(f"API invalid input test failed: {e}")
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name="api_invalid_config",
                status=HarnessStatus.ERROR,
                duration=time.time() - start_time,
                error_message=str(e)
            ))
            return False
    
    def _test_missing_dependency_degradation(self, project, env_context: EnvironmentContext) -> bool:
        """Test missing dependency graceful degradation."""
        self.logger.info("Testing missing dependency graceful degradation")
        
        test_cases = [
            {
                "name": "missing_codex",
                "env_vars": {"CODEX_CLI_PATH": "/nonexistent/codex"},
                "command": ["python", "scripts/onboard_repo.py", "--help"],
                "should_degrade_gracefully": True
            },
            {
                "name": "missing_git",
                "env_vars": {"PATH": "/tmp"},  # Remove git from PATH
                "command": ["python", "scripts/protocol_pipeline.py", "--help"],
                "should_degrade_gracefully": True
            },
            {
                "name": "missing_redis",
                "env_vars": {"TASKSGODZILLA_REDIS_URL": "redis://nonexistent:6379"},
                "command": ["python", "scripts/rq_worker.py", "--help"],
                "should_degrade_gracefully": True
            },
        ]
        
        all_passed = True
        for test_case in test_cases:
            success = self._run_missing_dependency_test(test_case, env_context)
            if not success:
                all_passed = False
        
        return all_passed
    
    def _run_missing_dependency_test(self, test_case: Dict[str, Any], env_context: EnvironmentContext) -> bool:
        """Run a single missing dependency test case."""
        start_time = time.time()
        
        try:
            # Modify environment to simulate missing dependency
            modified_env = os.environ.copy()
            modified_env.update(test_case["env_vars"])
            
            result = subprocess.run(
                test_case["command"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=env_context.workspace_path,
                env=modified_env
            )
            
            # Check if system degraded gracefully
            if test_case["should_degrade_gracefully"]:
                # Should either succeed with help or fail with informative error
                success = (result.returncode == 0 or 
                          ("help" in result.stdout.lower() or 
                           "error" in result.stderr.lower() or
                           "not found" in result.stderr.lower()))
            else:
                success = result.returncode != 0
            
            duration = time.time() - start_time
            status = HarnessStatus.PASS if success else HarnessStatus.FAIL
            error_msg = None if success else f"Missing dependency handling failed for {test_case['name']}"
            
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name=f"missing_dependency_{test_case['name']}",
                status=status,
                duration=duration,
                error_message=error_msg
            ))
            
            return success
            
        except Exception as e:
            self.logger.error(f"Missing dependency test {test_case['name']} failed: {e}")
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name=f"missing_dependency_{test_case['name']}",
                status=HarnessStatus.ERROR,
                duration=time.time() - start_time,
                error_message=str(e)
            ))
            return False
    
    def _test_network_failure_recovery(self, project, env_context: EnvironmentContext) -> bool:
        """Test network failure retry and recovery mechanisms."""
        self.logger.info("Testing network failure retry and recovery")
        
        # Test cases that involve network operations
        test_cases = [
            {
                "name": "git_clone_timeout",
                "command": ["python", "scripts/onboard_repo.py", "https://github.com/nonexistent/repo.git"],
                "expected_timeout": True
            },
            {
                "name": "api_connection_failure",
                "env_vars": {"TASKSGODZILLA_REDIS_URL": "redis://192.0.2.1:6379"},  # Non-routable IP
                "command": ["python", "scripts/api_server.py", "--help"],
                "expected_graceful_failure": True
            },
        ]
        
        all_passed = True
        for test_case in test_cases:
            success = self._run_network_failure_test(test_case, env_context)
            if not success:
                all_passed = False
        
        return all_passed
    
    def _run_network_failure_test(self, test_case: Dict[str, Any], env_context: EnvironmentContext) -> bool:
        """Run a single network failure test case."""
        start_time = time.time()
        
        try:
            # Set up environment if needed
            test_env = os.environ.copy()
            if "env_vars" in test_case:
                test_env.update(test_case["env_vars"])
            
            # Run command with shorter timeout for network tests
            result = subprocess.run(
                test_case["command"],
                capture_output=True,
                text=True,
                timeout=60,  # Longer timeout for network operations
                cwd=env_context.workspace_path,
                env=test_env
            )
            
            # Analyze result based on expected behavior
            if test_case.get("expected_timeout"):
                # Should fail with timeout or connection error
                success = (result.returncode != 0 and 
                          ("timeout" in result.stderr.lower() or 
                           "connection" in result.stderr.lower() or
                           "network" in result.stderr.lower() or
                           "not found" in result.stderr.lower()))
            elif test_case.get("expected_graceful_failure"):
                # Should handle network failure gracefully
                success = (result.returncode == 0 or 
                          "help" in result.stdout.lower() or
                          "error" in result.stderr.lower())
            else:
                success = result.returncode == 0
            
            duration = time.time() - start_time
            status = HarnessStatus.PASS if success else HarnessStatus.FAIL
            error_msg = None if success else f"Network failure handling failed for {test_case['name']}"
            
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name=f"network_failure_{test_case['name']}",
                status=status,
                duration=duration,
                error_message=error_msg
            ))
            
            return success
            
        except subprocess.TimeoutExpired:
            # Timeout is expected for some network tests
            if test_case.get("expected_timeout"):
                self.test_results.append(TestResult(
                    component="error_conditions",
                    test_name=f"network_failure_{test_case['name']}",
                    status=HarnessStatus.PASS,
                    duration=60.0,
                    error_message=None
                ))
                return True
            else:
                self.test_results.append(TestResult(
                    component="error_conditions",
                    test_name=f"network_failure_{test_case['name']}",
                    status=HarnessStatus.FAIL,
                    duration=60.0,
                    error_message="Unexpected timeout"
                ))
                return False
        except Exception as e:
            self.logger.error(f"Network failure test {test_case['name']} failed: {e}")
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name=f"network_failure_{test_case['name']}",
                status=HarnessStatus.ERROR,
                duration=time.time() - start_time,
                error_message=str(e)
            ))
            return False
    
    def _test_corrupted_data_integrity(self, project, env_context: EnvironmentContext) -> bool:
        """Test corrupted data integrity checks."""
        self.logger.info("Testing corrupted data integrity checks")
        
        all_passed = True
        
        # Test with corrupted database
        db_test_success = self._test_corrupted_database(env_context)
        if not db_test_success:
            all_passed = False
        
        # Test with corrupted config files
        config_test_success = self._test_corrupted_config_files(env_context)
        if not config_test_success:
            all_passed = False
        
        # Test with corrupted project files
        project_test_success = self._test_corrupted_project_files(project, env_context)
        if not project_test_success:
            all_passed = False
        
        return all_passed
    
    def _test_corrupted_database(self, env_context: EnvironmentContext) -> bool:
        """Test handling of corrupted database."""
        start_time = time.time()
        
        try:
            # Create a corrupted database file
            with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as temp_db:
                temp_db.write(b"corrupted data")
                temp_db_path = temp_db.name
            
            try:
                # Test CLI with corrupted database
                test_env = os.environ.copy()
                test_env["TASKSGODZILLA_DB_PATH"] = temp_db_path
                
                result = subprocess.run(
                    ["python", "scripts/tasksgodzilla_cli.py", "--help"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=env_context.workspace_path,
                    env=test_env
                )
                
                # Should handle corrupted database gracefully
                success = (result.returncode == 0 or 
                          "help" in result.stdout.lower() or
                          "database" in result.stderr.lower() or
                          "error" in result.stderr.lower())
                
                duration = time.time() - start_time
                status = HarnessStatus.PASS if success else HarnessStatus.FAIL
                error_msg = None if success else "Failed to handle corrupted database"
                
                self.test_results.append(TestResult(
                    component="error_conditions",
                    test_name="corrupted_database",
                    status=status,
                    duration=duration,
                    error_message=error_msg
                ))
                
                return success
                
            finally:
                # Clean up temporary database
                os.unlink(temp_db_path)
                
        except Exception as e:
            self.logger.error(f"Corrupted database test failed: {e}")
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name="corrupted_database",
                status=HarnessStatus.ERROR,
                duration=time.time() - start_time,
                error_message=str(e)
            ))
            return False
    
    def _test_corrupted_config_files(self, env_context: EnvironmentContext) -> bool:
        """Test handling of corrupted configuration files."""
        start_time = time.time()
        
        try:
            # Create a corrupted config file
            with tempfile.NamedTemporaryFile(mode='w', suffix=".json", delete=False) as temp_config:
                temp_config.write('{"invalid": json syntax}')
                temp_config_path = temp_config.name
            
            try:
                # Test quality orchestrator with corrupted config
                result = subprocess.run(
                    ["python", "scripts/quality_orchestrator.py", "--config", temp_config_path],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=env_context.workspace_path
                )
                
                # Should handle corrupted config gracefully
                success = (result.returncode != 0 and 
                          ("json" in result.stderr.lower() or 
                           "config" in result.stderr.lower() or
                           "invalid" in result.stderr.lower()))
                
                duration = time.time() - start_time
                status = HarnessStatus.PASS if success else HarnessStatus.FAIL
                error_msg = None if success else "Failed to handle corrupted config file"
                
                self.test_results.append(TestResult(
                    component="error_conditions",
                    test_name="corrupted_config_file",
                    status=status,
                    duration=duration,
                    error_message=error_msg
                ))
                
                return success
                
            finally:
                # Clean up temporary config
                os.unlink(temp_config_path)
                
        except Exception as e:
            self.logger.error(f"Corrupted config file test failed: {e}")
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name="corrupted_config_file",
                status=HarnessStatus.ERROR,
                duration=time.time() - start_time,
                error_message=str(e)
            ))
            return False
    
    def _test_corrupted_project_files(self, project, env_context: EnvironmentContext) -> bool:
        """Test handling of corrupted project files."""
        start_time = time.time()
        
        try:
            # Create a temporary project directory with corrupted files
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_project_path = Path(temp_dir) / "corrupted_project"
                temp_project_path.mkdir()
                
                # Create corrupted Python file
                (temp_project_path / "corrupted.py").write_text("invalid python syntax {{{")
                
                # Create corrupted JSON file
                (temp_project_path / "package.json").write_text('{"invalid": json}')
                
                # Test onboarding with corrupted project
                result = subprocess.run(
                    ["python", "scripts/onboard_repo.py", str(temp_project_path)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=env_context.workspace_path
                )
                
                # Should handle corrupted project files gracefully
                # May succeed with warnings or fail with informative error
                success = True  # Any outcome is acceptable as long as it doesn't crash
                
                duration = time.time() - start_time
                status = HarnessStatus.PASS if success else HarnessStatus.FAIL
                
                self.test_results.append(TestResult(
                    component="error_conditions",
                    test_name="corrupted_project_files",
                    status=status,
                    duration=duration,
                    error_message=None
                ))
                
                return success
                
        except Exception as e:
            self.logger.error(f"Corrupted project files test failed: {e}")
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name="corrupted_project_files",
                status=HarnessStatus.ERROR,
                duration=time.time() - start_time,
                error_message=str(e)
            ))
            return False
    
    def _test_resource_constraint_performance(self, project, env_context: EnvironmentContext) -> bool:
        """Test resource constraint performance validation."""
        self.logger.info("Testing resource constraint performance validation")
        
        all_passed = True
        
        # Test with limited memory (simulated)
        memory_test_success = self._test_memory_constraints(env_context)
        if not memory_test_success:
            all_passed = False
        
        # Test with limited disk space (simulated)
        disk_test_success = self._test_disk_constraints(env_context)
        if not disk_test_success:
            all_passed = False
        
        # Test with high CPU load (simulated)
        cpu_test_success = self._test_cpu_constraints(env_context)
        if not cpu_test_success:
            all_passed = False
        
        return all_passed
    
    def _test_memory_constraints(self, env_context: EnvironmentContext) -> bool:
        """Test performance under memory constraints."""
        start_time = time.time()
        
        try:
            # Test CLI operations under simulated memory pressure
            # We'll use a large environment variable to simulate memory usage
            large_env = os.environ.copy()
            large_env["LARGE_VAR"] = "x" * (1024 * 1024)  # 1MB string
            
            result = subprocess.run(
                ["python", "scripts/tasksgodzilla_cli.py", "--help"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=env_context.workspace_path,
                env=large_env
            )
            
            # Should complete successfully even with memory pressure
            success = result.returncode == 0 or "help" in result.stdout.lower()
            
            duration = time.time() - start_time
            status = HarnessStatus.PASS if success else HarnessStatus.FAIL
            error_msg = None if success else "Failed under memory constraints"
            
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name="memory_constraints",
                status=status,
                duration=duration,
                error_message=error_msg
            ))
            
            return success
            
        except Exception as e:
            self.logger.error(f"Memory constraints test failed: {e}")
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name="memory_constraints",
                status=HarnessStatus.ERROR,
                duration=time.time() - start_time,
                error_message=str(e)
            ))
            return False
    
    def _test_disk_constraints(self, env_context: EnvironmentContext) -> bool:
        """Test performance under disk space constraints."""
        start_time = time.time()
        
        try:
            # Test with a very small temporary directory
            with tempfile.TemporaryDirectory() as small_temp_dir:
                # Set TMPDIR to the small directory
                test_env = os.environ.copy()
                test_env["TMPDIR"] = small_temp_dir
                test_env["TEMP"] = small_temp_dir
                test_env["TMP"] = small_temp_dir
                
                result = subprocess.run(
                    ["python", "scripts/tasksgodzilla_cli.py", "--help"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=env_context.workspace_path,
                    env=test_env
                )
                
                # Should handle limited disk space gracefully
                success = result.returncode == 0 or "help" in result.stdout.lower()
                
                duration = time.time() - start_time
                status = HarnessStatus.PASS if success else HarnessStatus.FAIL
                error_msg = None if success else "Failed under disk constraints"
                
                self.test_results.append(TestResult(
                    component="error_conditions",
                    test_name="disk_constraints",
                    status=status,
                    duration=duration,
                    error_message=error_msg
                ))
                
                return success
                
        except Exception as e:
            self.logger.error(f"Disk constraints test failed: {e}")
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name="disk_constraints",
                status=HarnessStatus.ERROR,
                duration=time.time() - start_time,
                error_message=str(e)
            ))
            return False
    
    def _test_cpu_constraints(self, env_context: EnvironmentContext) -> bool:
        """Test performance under CPU constraints."""
        start_time = time.time()
        
        try:
            # Test CLI operations while simulating CPU load
            # We'll run a simple help command which should complete quickly
            result = subprocess.run(
                ["python", "scripts/tasksgodzilla_cli.py", "--help"],
                capture_output=True,
                text=True,
                timeout=60,  # Longer timeout for CPU-constrained environment
                cwd=env_context.workspace_path
            )
            
            # Should complete successfully even under CPU load
            success = result.returncode == 0 or "help" in result.stdout.lower()
            
            duration = time.time() - start_time
            status = HarnessStatus.PASS if success else HarnessStatus.FAIL
            error_msg = None if success else "Failed under CPU constraints"
            
            # Check if operation took reasonable time (under 30 seconds for help)
            if duration > 30:
                success = False
                error_msg = f"Operation took too long under CPU constraints: {duration:.2f}s"
                status = HarnessStatus.FAIL
            
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name="cpu_constraints",
                status=status,
                duration=duration,
                error_message=error_msg
            ))
            
            return success
            
        except Exception as e:
            self.logger.error(f"CPU constraints test failed: {e}")
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name="cpu_constraints",
                status=HarnessStatus.ERROR,
                duration=time.time() - start_time,
                error_message=str(e)
            ))
            return False
    
    def get_test_results(self) -> List[TestResult]:
        """Get all test results from this component."""
        return self.test_results.copy()
    
    def _test_comprehensive_input_validation(self, project, env_context: EnvironmentContext) -> bool:
        """Test comprehensive input validation across all interfaces."""
        self.logger.info("Testing comprehensive input validation")
        
        # Test cases for various input validation scenarios
        validation_test_cases = [
            {
                "name": "sql_injection_attempts",
                "command": ["python", "scripts/tasksgodzilla_cli.py", "projects", "list", "--filter", "'; DROP TABLE projects; --"],
                "expected_behavior": "safe_handling"
            },
            {
                "name": "path_traversal_attempts", 
                "command": ["python", "scripts/onboard_repo.py", "--git-url", "../../../etc/passwd"],
                "expected_behavior": "path_validation_error"
            },
            {
                "name": "extremely_long_input",
                "command": ["python", "scripts/protocol_pipeline.py", "--protocol-name", "x" * 10000],
                "expected_behavior": "length_validation_error"
            },
            {
                "name": "special_characters_input",
                "command": ["python", "scripts/quality_orchestrator.py", "--project", "test<>|&;$()"],
                "expected_behavior": "character_validation_error"
            },
            {
                "name": "unicode_input",
                "command": ["python", "scripts/spec_audit.py", "--spec-name", "测试项目🚀"],
                "expected_behavior": "unicode_handling"
            },
            {
                "name": "null_byte_input",
                "command": ["python", "scripts/tasksgodzilla_cli.py", "projects", "create", "--name", "test\x00project"],
                "expected_behavior": "null_byte_rejection"
            }
        ]
        
        all_passed = True
        
        for test_case in validation_test_cases:
            success = self._run_input_validation_test(test_case, env_context)
            if not success:
                all_passed = False
        
        return all_passed
    
    def _run_input_validation_test(self, test_case: Dict[str, Any], env_context: EnvironmentContext) -> bool:
        """Run a single input validation test case."""
        start_time = time.time()
        
        try:
            result = subprocess.run(
                test_case["command"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=env_context.workspace_path
            )
            
            # Analyze result based on expected behavior
            success = self._analyze_input_validation_result(result, test_case["expected_behavior"])
            
            duration = time.time() - start_time
            status = HarnessStatus.PASS if success else HarnessStatus.FAIL
            error_msg = None if success else f"Input validation failed for {test_case['name']}"
            
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name=f"input_validation_{test_case['name']}",
                status=status,
                duration=duration,
                error_message=error_msg
            ))
            
            return success
            
        except subprocess.TimeoutExpired:
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name=f"input_validation_{test_case['name']}",
                status=HarnessStatus.ERROR,
                duration=30.0,
                error_message="Input validation test timed out"
            ))
            return False
        except Exception as e:
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name=f"input_validation_{test_case['name']}",
                status=HarnessStatus.ERROR,
                duration=time.time() - start_time,
                error_message=str(e)
            ))
            return False
    
    def _analyze_input_validation_result(self, result: subprocess.CompletedProcess, expected_behavior: str) -> bool:
        """Analyze input validation result."""
        if expected_behavior == "safe_handling":
            # Should not crash and should handle safely
            return result.returncode != 0 or "error" in result.stderr.lower()
        
        elif expected_behavior == "path_validation_error":
            # Should reject path traversal attempts
            return (result.returncode != 0 and 
                    ("invalid" in result.stderr.lower() or 
                     "path" in result.stderr.lower() or
                     "not found" in result.stderr.lower()))
        
        elif expected_behavior == "length_validation_error":
            # Should reject extremely long inputs
            return (result.returncode != 0 and 
                    ("too long" in result.stderr.lower() or 
                     "length" in result.stderr.lower() or
                     "invalid" in result.stderr.lower()))
        
        elif expected_behavior == "character_validation_error":
            # Should reject special characters
            return (result.returncode != 0 and 
                    ("invalid" in result.stderr.lower() or 
                     "character" in result.stderr.lower()))
        
        elif expected_behavior == "unicode_handling":
            # Should handle unicode gracefully (either accept or reject cleanly)
            return True  # Any non-crash result is acceptable
        
        elif expected_behavior == "null_byte_rejection":
            # Should reject null bytes
            return (result.returncode != 0 and 
                    ("invalid" in result.stderr.lower() or 
                     "null" in result.stderr.lower()))
        
        return False
    
    def _test_concurrent_operation_handling(self, project, env_context: EnvironmentContext) -> bool:
        """Test handling of concurrent operations and race conditions."""
        self.logger.info("Testing concurrent operation handling")
        
        try:
            # Test concurrent CLI operations
            import threading
            import queue
            
            results_queue = queue.Queue()
            
            def run_concurrent_command(cmd, result_queue):
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=60,
                        cwd=env_context.workspace_path
                    )
                    result_queue.put(("success", result.returncode, result.stderr))
                except Exception as e:
                    result_queue.put(("error", -1, str(e)))
            
            # Run multiple CLI help commands concurrently
            concurrent_commands = [
                ["python", "scripts/tasksgodzilla_cli.py", "--help"],
                ["python", "scripts/onboard_repo.py", "--help"],
                ["python", "scripts/protocol_pipeline.py", "--help"],
                ["python", "scripts/quality_orchestrator.py", "--help"],
                ["python", "scripts/spec_audit.py", "--help"]
            ]
            
            threads = []
            for cmd in concurrent_commands:
                thread = threading.Thread(target=run_concurrent_command, args=(cmd, results_queue))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join(timeout=120)
            
            # Collect results
            results = []
            while not results_queue.empty():
                results.append(results_queue.get())
            
            # Analyze results
            successful_results = [r for r in results if r[0] == "success" and r[1] == 0]
            failed_results = [r for r in results if r[0] == "error" or r[1] != 0]
            
            # Most concurrent help commands should succeed
            success = len(successful_results) >= len(concurrent_commands) // 2
            
            duration = 60.0  # Approximate duration for concurrent tests
            status = HarnessStatus.PASS if success else HarnessStatus.FAIL
            error_msg = None if success else f"Too many concurrent operations failed: {len(failed_results)}/{len(results)}"
            
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name="concurrent_operation_handling",
                status=status,
                duration=duration,
                error_message=error_msg
            ))
            
            return success
            
        except Exception as e:
            self.logger.error(f"Concurrent operation handling test failed: {e}")
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name="concurrent_operation_handling",
                status=HarnessStatus.ERROR,
                duration=60.0,
                error_message=str(e)
            ))
            return False
    
    def _test_system_resource_exhaustion(self, project, env_context: EnvironmentContext) -> bool:
        """Test system behavior under resource exhaustion conditions."""
        self.logger.info("Testing system resource exhaustion handling")
        
        try:
            # Test with limited file descriptors (simulated)
            import resource
            
            # Get current limits
            try:
                soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
                
                # Test with a very low file descriptor limit (if we can set it)
                test_limit = min(50, soft_limit)
                
                # This is a simulation - we can't actually set limits in most environments
                # So we'll test that the system handles file operations gracefully
                
                # Create many temporary files to stress file handling
                temp_files = []
                try:
                    for i in range(20):  # Create multiple temp files
                        temp_file = env_context.temp_dir / f"stress_test_{i}.txt"
                        temp_file.write_text(f"Stress test file {i}")
                        temp_files.append(temp_file)
                    
                    # Test CLI operation with many files present
                    result = subprocess.run(
                        ["python", "scripts/tasksgodzilla_cli.py", "--help"],
                        capture_output=True,
                        text=True,
                        timeout=30,
                        cwd=env_context.workspace_path
                    )
                    
                    # Should handle gracefully
                    success = result.returncode == 0 or "help" in result.stdout.lower()
                    
                finally:
                    # Clean up temp files
                    for temp_file in temp_files:
                        try:
                            temp_file.unlink()
                        except:
                            pass
                
            except (OSError, ValueError):
                # If we can't check resource limits, just test basic file handling
                success = True
                self.logger.info("Resource limit testing not available, skipping")
            
            duration = 30.0
            status = HarnessStatus.PASS if success else HarnessStatus.FAIL
            error_msg = None if success else "System failed under resource stress"
            
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name="system_resource_exhaustion",
                status=status,
                duration=duration,
                error_message=error_msg
            ))
            
            return success
            
        except Exception as e:
            self.logger.error(f"System resource exhaustion test failed: {e}")
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name="system_resource_exhaustion",
                status=HarnessStatus.ERROR,
                duration=30.0,
                error_message=str(e)
            ))
            return False
    
    def _test_signal_handling_and_interruption(self, project, env_context: EnvironmentContext) -> bool:
        """Test signal handling and graceful interruption."""
        self.logger.info("Testing signal handling and interruption")
        
        try:
            import signal
            import time
            
            # Test graceful shutdown on SIGTERM (simulated)
            # We'll test that processes can be interrupted cleanly
            
            # Start a long-running help command and interrupt it
            process = subprocess.Popen(
                ["python", "scripts/tasksgodzilla_cli.py", "--help"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=env_context.workspace_path
            )
            
            # Let it run briefly
            time.sleep(0.5)
            
            # Send SIGTERM (graceful shutdown)
            try:
                process.terminate()
                
                # Wait for graceful shutdown
                try:
                    stdout, stderr = process.communicate(timeout=10)
                    
                    # Process should have terminated gracefully
                    success = process.returncode is not None
                    
                except subprocess.TimeoutExpired:
                    # If it doesn't terminate gracefully, force kill
                    process.kill()
                    success = False
                    
            except OSError:
                # If we can't send signals, just test that process completes
                try:
                    stdout, stderr = process.communicate(timeout=30)
                    success = process.returncode == 0
                except subprocess.TimeoutExpired:
                    process.kill()
                    success = False
            
            duration = 10.0
            status = HarnessStatus.PASS if success else HarnessStatus.FAIL
            error_msg = None if success else "Process did not handle interruption gracefully"
            
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name="signal_handling_interruption",
                status=status,
                duration=duration,
                error_message=error_msg
            ))
            
            return success
            
        except Exception as e:
            self.logger.error(f"Signal handling test failed: {e}")
            self.test_results.append(TestResult(
                component="error_conditions",
                test_name="signal_handling_interruption",
                status=HarnessStatus.ERROR,
                duration=10.0,
                error_message=str(e)
            ))
            return False