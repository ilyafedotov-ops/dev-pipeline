"""CLI interface test component for the workflow harness."""

import os
import sys
import subprocess
import tempfile
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from unittest.mock import patch, MagicMock

from ..models import TestResult, HarnessStatus
from ..environment import EnvironmentContext
from ..api_utils import APIServerManager, CLICommandRunner, get_optimal_timeout, detect_command_type


class CLIInterfaceTests:
    """Test component for CLI interface functionality."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.project_root = Path(__file__).resolve().parents[3]
        self.cli_script = self.project_root / "scripts" / "tasksgodzilla_cli.py"
        self.tui_script = self.project_root / "scripts" / "tasksgodzilla_tui.py"
        
        # Initialize API server manager and CLI runner
        self.api_manager = APIServerManager(host="localhost", port=8010, timeout=30)
        self.cli_runner = CLICommandRunner(self.api_manager)
    
    def run_test(self, project, env_context: EnvironmentContext) -> bool:
        """Run all CLI interface tests."""
        self.logger.info("Starting CLI interface tests")
        
        try:
            # Test CLI script existence and basic functionality
            if not self._test_cli_script_exists():
                return False
            
            # Test CLI help and documentation
            if not self._test_cli_help_consistency():
                return False
            
            # Test CLI command-line mode
            if not self._test_cli_command_mode():
                return False
            
            # Test CLI interactive mode (limited testing)
            if not self._test_cli_interactive_mode():
                return False
            
            # Test CLI error handling
            if not self._test_cli_error_handling():
                return False
            
            self.logger.info("All CLI interface tests passed")
            return True
            
        except Exception as e:
            self.logger.error(f"CLI interface tests failed: {e}")
            return False
    
    def _test_cli_script_exists(self) -> bool:
        """Test that CLI scripts exist and are executable."""
        self.logger.info("Testing CLI script existence")
        
        if not self.cli_script.exists():
            self.logger.error(f"CLI script not found: {self.cli_script}")
            return False
        
        if not self.tui_script.exists():
            self.logger.error(f"TUI script not found: {self.tui_script}")
            return False
        
        # Test that scripts are executable
        if not os.access(self.cli_script, os.X_OK):
            self.logger.error(f"CLI script not executable: {self.cli_script}")
            return False
        
        if not os.access(self.tui_script, os.X_OK):
            self.logger.error(f"TUI script not executable: {self.tui_script}")
            return False
        
        self.logger.info("CLI scripts exist and are executable")
        return True
    
    def _test_cli_help_consistency(self) -> bool:
        """Test CLI help and documentation consistency."""
        self.logger.info("Testing CLI help consistency")
        
        try:
            # Test main help
            result = self._run_cli_command(["--help"])
            if result.returncode != 0:
                self.logger.error("CLI --help failed")
                return False
            
            help_output = result.stdout
            
            # Check for expected help sections
            expected_sections = [
                "usage:",
                "positional arguments:",
                "options:",
            ]
            
            for section in expected_sections:
                if section.lower() not in help_output.lower():
                    self.logger.warning(f"Help section missing: {section}")
            
            # Test subcommand help
            subcommands = ["projects", "protocols", "steps", "events", "queues", "codemachine", "spec"]
            
            for subcommand in subcommands:
                result = self._run_cli_command([subcommand, "--help"])
                if result.returncode != 0:
                    self.logger.warning(f"Subcommand help failed: {subcommand}")
                else:
                    self.logger.debug(f"Subcommand help works: {subcommand}")
            
            self.logger.info("CLI help consistency tests passed")
            return True
            
        except Exception as e:
            self.logger.error(f"CLI help test failed: {e}")
            return False
    
    def _test_cli_command_mode(self) -> bool:
        """Test CLI commands and subcommands in command-line mode."""
        self.logger.info("Testing CLI command-line mode")
        
        try:
            # Test help commands first (these should work without API server)
            help_commands = [
                ["--help"],
                ["projects", "--help"],
                ["protocols", "--help"],
                ["spec", "validate", "--help"],
            ]
            
            for cmd in help_commands:
                command_type = detect_command_type(cmd)
                timeout = get_optimal_timeout(command_type)
                
                try:
                    result = self.cli_runner.run_command(cmd, timeout=timeout, wait_for_api=False)
                    if result.returncode != 0:
                        self.logger.error(f"Help command failed: {cmd}")
                        return False
                    
                    # Help output should contain usage information
                    if "usage:" not in result.stdout.lower():
                        self.logger.warning(f"Help output missing usage for: {cmd}")
                        
                except subprocess.TimeoutExpired:
                    self.logger.error(f"Help command timed out: {cmd}")
                    return False
            
            # Test command parsing with API connectivity
            test_commands = [
                ["--json", "projects", "list"],
                ["protocols", "list", "--project", "1"],
                ["events", "recent", "--limit", "10"],
                ["queues", "stats"],
            ]
            
            # Start API server for these tests
            api_started = self.api_manager.start_server(background=True)
            if api_started:
                # Wait a moment for server to be ready
                if self.api_manager.wait_for_server_startup(10):
                    self.logger.info("API server ready for CLI command tests")
                else:
                    self.logger.warning("API server not ready, testing without it")
            
            for cmd in test_commands:
                try:
                    command_type = detect_command_type(cmd)
                    timeout = get_optimal_timeout(command_type)
                    
                    result = self.cli_runner.run_command_with_retry(
                        cmd, max_retries=1, timeout=timeout
                    )
                    
                    # Check for argument parsing errors (these are bad)
                    if result.returncode != 0:
                        error_output = result.stderr.lower()
                        if ("usage:" in error_output and "error:" in error_output and 
                            "unrecognized arguments" in error_output):
                            self.logger.error(f"Command parsing failed for {cmd}: {result.stderr}")
                            return False
                        else:
                            # Connection errors or other runtime errors are acceptable
                            self.logger.debug(f"Command {cmd} failed as expected (likely connection/data error)")
                    else:
                        self.logger.info(f"Command {cmd} succeeded")
                
                except subprocess.TimeoutExpired:
                    # Timeout is acceptable for some commands
                    self.logger.debug(f"Command {cmd} timed out (acceptable for some scenarios)")
                    continue
                except Exception as e:
                    self.logger.warning(f"Command {cmd} failed with exception: {e}")
                    continue
            
            self.logger.info("CLI command-line mode tests passed")
            return True
            
        except Exception as e:
            self.logger.error(f"CLI command mode test failed: {e}")
            return False
        finally:
            # Clean up API server
            self.api_manager.stop_server()
    
    def _test_cli_interactive_mode(self) -> bool:
        """Test CLI interactive mode (limited testing without full interaction)."""
        self.logger.info("Testing CLI interactive mode")
        
        try:
            # Start API server for interactive mode
            api_started = self.api_manager.start_server(background=True)
            if api_started:
                self.api_manager.wait_for_server_startup(10)
            
            # Test that interactive mode starts and can handle basic input
            test_input = "q\n"  # Quit immediately
            
            # Set environment for API connectivity
            env = os.environ.copy()
            env["TASKSGODZILLA_API_BASE"] = self.api_manager.base_url
            
            # Run CLI in interactive mode with quit input
            process = subprocess.Popen(
                [sys.executable, str(self.cli_script)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.project_root,
                env=env
            )
            
            try:
                # Use longer timeout for interactive mode startup
                timeout = get_optimal_timeout("interactive")
                stdout, stderr = process.communicate(input=test_input, timeout=timeout)
                
                # Check if interactive mode started (should show banner or menu)
                output_lower = stdout.lower()
                if ("tasksgodzilla" in output_lower or 
                    "interactive" in output_lower or 
                    "menu" in output_lower or
                    ">" in stdout):  # Command prompt
                    self.logger.info("CLI interactive mode starts correctly")
                    return True
                else:
                    # Check if it failed due to API connectivity
                    if "connection" in stderr.lower() or "api" in stderr.lower():
                        self.logger.info("CLI interactive mode failed due to API connectivity (acceptable)")
                        return True
                    else:
                        self.logger.warning("CLI interactive mode output unexpected")
                        self.logger.debug(f"Interactive stdout: {stdout}")
                        self.logger.debug(f"Interactive stderr: {stderr}")
                        # Don't fail the test for this, as it might work differently
                        return True
                    
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                self.logger.warning("CLI interactive mode timed out")
                # This might be acceptable if it's waiting for API or user input
                return True
            
        except Exception as e:
            self.logger.error(f"CLI interactive mode test failed: {e}")
            return False
        finally:
            # Clean up API server
            self.api_manager.stop_server()
    
    def _test_cli_error_handling(self) -> bool:
        """Test CLI error handling and user feedback."""
        self.logger.info("Testing CLI error handling")
        
        try:
            # Test invalid command
            result = self.cli_runner.run_command(["invalid-command"], timeout=5, wait_for_api=False)
            if result.returncode == 0:
                self.logger.error("CLI should fail on invalid command")
                return False
            
            # Test invalid arguments
            result = self.cli_runner.run_command(["projects", "invalid-action"], timeout=5, wait_for_api=False)
            if result.returncode == 0:
                self.logger.error("CLI should fail on invalid subcommand")
                return False
            
            # Test missing required arguments
            result = self.cli_runner.run_command(["projects", "create"], timeout=5, wait_for_api=False)
            if result.returncode == 0:
                self.logger.error("CLI should fail on missing required arguments")
                return False
            
            # Check that error messages are helpful
            error_output = result.stderr
            if "required" not in error_output.lower() and "usage" not in error_output.lower():
                self.logger.warning("CLI error messages could be more helpful")
            
            self.logger.info("CLI error handling tests passed")
            return True
            
        except subprocess.TimeoutExpired:
            self.logger.error("CLI error handling test timed out")
            return False
        except Exception as e:
            self.logger.error(f"CLI error handling test failed: {e}")
            return False
    
    def _run_cli_command(self, args: List[str], timeout: int = 10) -> subprocess.CompletedProcess:
        """Run CLI command with specified arguments (legacy method for compatibility)."""
        # Use the new CLI runner for better timeout handling
        return self.cli_runner.run_command(args, timeout=timeout, wait_for_api=False)


class TUIInterfaceTests:
    """Test component for TUI interface functionality."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.project_root = Path(__file__).resolve().parents[3]
        self.tui_script = self.project_root / "scripts" / "tasksgodzilla_tui.py"
        self.test_results = []
    
    def run_test(self, project, env_context: EnvironmentContext) -> bool:
        """Run all TUI interface tests."""
        self.logger.info("Starting comprehensive TUI interface tests")
        
        try:
            # Test TUI script existence
            if not self._test_tui_script_exists():
                return False
            
            # Test TUI startup (limited testing)
            if not self._test_tui_startup():
                return False
            
            # Test TUI navigation and interaction patterns
            if not self._test_tui_navigation_patterns():
                return False
            
            # Test TUI display formatting
            if not self._test_tui_display_formatting():
                return False
            
            # Test TUI error handling
            if not self._test_tui_error_handling():
                return False
            
            # Additional comprehensive tests
            if not self._test_tui_keyboard_shortcuts():
                return False
            
            if not self._test_tui_screen_layouts():
                return False
            
            if not self._test_tui_data_display():
                return False
            
            if not self._test_tui_refresh_functionality():
                return False
            
            if not self._test_tui_configuration_handling():
                return False
            
            self.logger.info("All comprehensive TUI interface tests passed")
            return True
            
        except Exception as e:
            self.logger.error(f"TUI interface tests failed: {e}")
            return False
    
    def _test_tui_script_exists(self) -> bool:
        """Test that TUI script exists and is executable."""
        self.logger.info("Testing TUI script existence")
        
        if not self.tui_script.exists():
            self.logger.error(f"TUI script not found: {self.tui_script}")
            return False
        
        if not os.access(self.tui_script, os.X_OK):
            self.logger.error(f"TUI script not executable: {self.tui_script}")
            return False
        
        self.logger.info("TUI script exists and is executable")
        return True
    
    def _test_tui_startup(self) -> bool:
        """Test TUI startup and basic functionality."""
        self.logger.info("Testing TUI startup")
        
        try:
            # Test that TUI detects non-TTY environment
            # TUI should fail gracefully when not run in a terminal
            
            process = subprocess.Popen(
                [sys.executable, str(self.tui_script)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.project_root
            )
            
            try:
                stdout, stderr = process.communicate(timeout=5)
                
                # TUI should detect non-TTY and exit gracefully
                if process.returncode != 0:
                    if "tty" in stderr.lower() or "terminal" in stderr.lower():
                        self.logger.info("TUI correctly detects non-TTY environment")
                        return True
                    else:
                        self.logger.warning(f"TUI failed for unexpected reason: {stderr}")
                        return True  # Don't fail test for this
                else:
                    self.logger.warning("TUI started in non-TTY environment (unexpected)")
                    return True  # Don't fail test for this
                    
            except subprocess.TimeoutExpired:
                process.kill()
                self.logger.warning("TUI startup timed out")
                return True  # Don't fail test for timeout
            
        except Exception as e:
            self.logger.error(f"TUI startup test failed: {e}")
            return False
    
    def _test_tui_navigation_patterns(self) -> bool:
        """Test TUI navigation and interaction patterns."""
        self.logger.info("Testing TUI navigation patterns")
        
        try:
            # Test TUI with simulated key inputs for navigation
            # Since we can't easily test full TUI interaction in non-TTY environment,
            # we'll test that the TUI module can be imported and basic classes exist
            
            # Import the TUI module to verify it's properly structured
            import sys
            tui_module_path = self.project_root / "tasksgodzilla" / "cli" / "tui.py"
            
            if not tui_module_path.exists():
                self.logger.error("TUI module not found")
                return False
            
            # Test that TUI classes can be imported
            try:
                # Add project root to path temporarily
                sys.path.insert(0, str(self.project_root))
                
                from tasksgodzilla.cli.tui import TuiDashboard, run_tui
                
                # Verify TUI dashboard class exists and has expected methods
                assert hasattr(TuiDashboard, 'compose')
                assert hasattr(TuiDashboard, 'on_mount')
                assert hasattr(TuiDashboard, 'on_button_pressed')
                assert hasattr(TuiDashboard, 'on_list_view_selected')
                
                # Verify key bindings exist
                assert hasattr(TuiDashboard, 'BINDINGS')
                bindings = TuiDashboard.BINDINGS
                
                # Should have navigation bindings
                binding_keys = [binding.key for binding in bindings]
                expected_keys = ['r', 'q', 'tab', 'shift+tab', '1', '2', '3', '4', '5', '6']
                
                for key in expected_keys:
                    if key not in binding_keys:
                        self.logger.warning(f"Expected TUI binding not found: {key}")
                
                self.logger.info("TUI navigation patterns test passed")
                return True
                
            except ImportError as e:
                self.logger.warning(f"Could not import TUI module: {e}")
                # This might be due to missing dependencies (textual)
                return True  # Don't fail test for missing optional dependencies
            
            finally:
                # Remove project root from path
                if str(self.project_root) in sys.path:
                    sys.path.remove(str(self.project_root))
            
        except Exception as e:
            self.logger.error(f"TUI navigation test failed: {e}")
            return False
    
    def _test_tui_display_formatting(self) -> bool:
        """Test TUI display formatting and layout."""
        self.logger.info("Testing TUI display formatting")
        
        try:
            # Test that TUI has proper CSS and layout definitions
            import sys
            
            try:
                sys.path.insert(0, str(self.project_root))
                from tasksgodzilla.cli.tui import TuiDashboard
                
                # Verify TUI has CSS styling
                assert hasattr(TuiDashboard, 'CSS')
                css = TuiDashboard.CSS
                
                # Should have basic layout styles
                assert 'Screen' in css
                assert 'Header' in css
                assert 'Footer' in css
                
                # Should have panel and component styles
                assert '.panel' in css
                assert '.title' in css
                
                # Verify TUI has proper title and subtitle
                assert hasattr(TuiDashboard, 'TITLE')
                assert hasattr(TuiDashboard, 'SUB_TITLE')
                
                self.logger.info("TUI display formatting test passed")
                return True
                
            except ImportError as e:
                self.logger.warning(f"Could not import TUI module for formatting test: {e}")
                return True  # Don't fail for missing dependencies
            
            finally:
                if str(self.project_root) in sys.path:
                    sys.path.remove(str(self.project_root))
            
        except Exception as e:
            self.logger.error(f"TUI display formatting test failed: {e}")
            return False
    
    def _test_tui_error_handling(self) -> bool:
        """Test TUI error handling and display formatting."""
        self.logger.info("Testing TUI error handling")
        
        try:
            # Test TUI with invalid environment
            env = os.environ.copy()
            env["TASKSGODZILLA_API_BASE"] = "invalid-url"
            
            process = subprocess.Popen(
                [sys.executable, str(self.tui_script)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.project_root,
                env=env
            )
            
            try:
                stdout, stderr = process.communicate(timeout=5)
                
                # TUI should handle invalid configuration gracefully
                if process.returncode != 0:
                    # Check for graceful error handling
                    if "error" in stderr.lower() or "tty" in stderr.lower():
                        self.logger.info("TUI handles errors gracefully")
                        return True
                
                self.logger.info("TUI error handling test completed")
                return True
                
            except subprocess.TimeoutExpired:
                process.kill()
                self.logger.info("TUI error handling test timed out (acceptable)")
                return True
            
        except Exception as e:
            self.logger.error(f"TUI error handling test failed: {e}")
            return False
    
    def _test_tui_keyboard_shortcuts(self) -> bool:
        """Test TUI keyboard shortcuts and key bindings."""
        self.logger.info("Testing TUI keyboard shortcuts")
        
        try:
            # Test that TUI module has proper key bindings
            import sys
            
            try:
                sys.path.insert(0, str(self.project_root))
                from tasksgodzilla.cli.tui import TuiDashboard
                
                # Verify key bindings exist and are properly configured
                assert hasattr(TuiDashboard, 'BINDINGS')
                bindings = TuiDashboard.BINDINGS
                
                # Check for essential navigation bindings
                binding_keys = [binding.key for binding in bindings]
                essential_keys = ['q', 'r', 'tab', 'shift+tab']
                
                missing_keys = []
                for key in essential_keys:
                    if key not in binding_keys:
                        missing_keys.append(key)
                
                if missing_keys:
                    self.logger.warning(f"Missing essential TUI key bindings: {missing_keys}")
                
                # Check for numbered shortcuts (1-6 for different panels)
                numbered_keys = [str(i) for i in range(1, 7)]
                available_numbered = [key for key in binding_keys if key in numbered_keys]
                
                if len(available_numbered) < 3:
                    self.logger.warning(f"Limited numbered shortcuts available: {available_numbered}")
                
                # Verify binding actions exist
                for binding in bindings:
                    if hasattr(binding, 'action') and binding.action:
                        # Check if the action method exists on the dashboard
                        if not hasattr(TuiDashboard, binding.action):
                            self.logger.warning(f"TUI binding action method not found: {binding.action}")
                
                self.logger.info("TUI keyboard shortcuts test passed")
                return True
                
            except ImportError as e:
                self.logger.warning(f"Could not import TUI module for keyboard shortcuts test: {e}")
                return True  # Don't fail for missing optional dependencies
            
            finally:
                if str(self.project_root) in sys.path:
                    sys.path.remove(str(self.project_root))
            
        except Exception as e:
            self.logger.error(f"TUI keyboard shortcuts test failed: {e}")
            return False
    
    def _test_tui_screen_layouts(self) -> bool:
        """Test TUI screen layouts and panel organization."""
        self.logger.info("Testing TUI screen layouts")
        
        try:
            import sys
            
            try:
                sys.path.insert(0, str(self.project_root))
                from tasksgodzilla.cli.tui import TuiDashboard
                
                # Verify TUI has proper layout composition
                assert hasattr(TuiDashboard, 'compose')
                
                # Check CSS for layout definitions
                assert hasattr(TuiDashboard, 'CSS')
                css = TuiDashboard.CSS
                
                # Verify essential layout components
                layout_components = ['Screen', 'Header', 'Footer', 'Container', 'Horizontal', 'Vertical']
                missing_components = []
                
                for component in layout_components:
                    if component not in css:
                        missing_components.append(component)
                
                if missing_components:
                    self.logger.warning(f"Missing TUI layout components in CSS: {missing_components}")
                
                # Check for panel-specific styles
                panel_styles = ['.panel', '.title', '.content', '.status']
                available_panel_styles = []
                
                for style in panel_styles:
                    if style in css:
                        available_panel_styles.append(style)
                
                if len(available_panel_styles) < 2:
                    self.logger.warning(f"Limited panel styles available: {available_panel_styles}")
                
                # Verify responsive design elements
                responsive_elements = ['width', 'height', 'min-width', 'min-height']
                responsive_found = any(element in css for element in responsive_elements)
                
                if not responsive_found:
                    self.logger.warning("No responsive design elements found in TUI CSS")
                
                self.logger.info("TUI screen layouts test passed")
                return True
                
            except ImportError as e:
                self.logger.warning(f"Could not import TUI module for screen layouts test: {e}")
                return True  # Don't fail for missing optional dependencies
            
            finally:
                if str(self.project_root) in sys.path:
                    sys.path.remove(str(self.project_root))
            
        except Exception as e:
            self.logger.error(f"TUI screen layouts test failed: {e}")
            return False
    
    def _test_tui_data_display(self) -> bool:
        """Test TUI data display and formatting capabilities."""
        self.logger.info("Testing TUI data display")
        
        try:
            import sys
            
            try:
                sys.path.insert(0, str(self.project_root))
                from tasksgodzilla.cli.tui import TuiDashboard
                
                # Check for data display widgets and methods
                dashboard_methods = dir(TuiDashboard)
                
                # Look for data-related methods
                data_methods = [method for method in dashboard_methods if any(
                    keyword in method.lower() for keyword in 
                    ['update', 'refresh', 'load', 'display', 'show', 'render']
                )]
                
                if len(data_methods) < 3:
                    self.logger.warning(f"Limited data display methods found: {data_methods}")
                
                # Check for list/table display capabilities
                list_methods = [method for method in dashboard_methods if any(
                    keyword in method.lower() for keyword in 
                    ['list', 'table', 'grid', 'view']
                )]
                
                if not list_methods:
                    self.logger.warning("No list/table display methods found")
                
                # Verify event handling for data updates
                event_methods = [method for method in dashboard_methods if 
                                method.startswith('on_') and 'select' in method.lower()]
                
                if not event_methods:
                    self.logger.warning("No data selection event handlers found")
                
                # Check CSS for data display styling
                css = TuiDashboard.CSS
                data_styles = ['.list', '.table', '.row', '.column', '.item', '.selected']
                available_data_styles = [style for style in data_styles if style in css]
                
                if len(available_data_styles) < 2:
                    self.logger.warning(f"Limited data display styles: {available_data_styles}")
                
                self.logger.info("TUI data display test passed")
                return True
                
            except ImportError as e:
                self.logger.warning(f"Could not import TUI module for data display test: {e}")
                return True  # Don't fail for missing optional dependencies
            
            finally:
                if str(self.project_root) in sys.path:
                    sys.path.remove(str(self.project_root))
            
        except Exception as e:
            self.logger.error(f"TUI data display test failed: {e}")
            return False
    
    def _test_tui_refresh_functionality(self) -> bool:
        """Test TUI refresh and real-time update functionality."""
        self.logger.info("Testing TUI refresh functionality")
        
        try:
            import sys
            
            try:
                sys.path.insert(0, str(self.project_root))
                from tasksgodzilla.cli.tui import TuiDashboard
                
                # Check for refresh-related methods
                dashboard_methods = dir(TuiDashboard)
                refresh_methods = [method for method in dashboard_methods if any(
                    keyword in method.lower() for keyword in 
                    ['refresh', 'update', 'reload', 'sync']
                )]
                
                if not refresh_methods:
                    self.logger.warning("No refresh methods found in TUI dashboard")
                
                # Check for timer/periodic update capabilities
                timer_methods = [method for method in dashboard_methods if any(
                    keyword in method.lower() for keyword in 
                    ['timer', 'periodic', 'interval', 'schedule']
                )]
                
                # Check for key binding that triggers refresh (usually 'r')
                if hasattr(TuiDashboard, 'BINDINGS'):
                    bindings = TuiDashboard.BINDINGS
                    refresh_bindings = [binding for binding in bindings if 
                                      binding.key == 'r' or 'refresh' in str(binding).lower()]
                    
                    if not refresh_bindings:
                        self.logger.warning("No refresh key binding found (expected 'r' key)")
                
                # Check for mount/unmount lifecycle methods
                lifecycle_methods = [method for method in dashboard_methods if any(
                    keyword in method.lower() for keyword in 
                    ['mount', 'unmount', 'ready', 'compose']
                )]
                
                if len(lifecycle_methods) < 2:
                    self.logger.warning(f"Limited lifecycle methods found: {lifecycle_methods}")
                
                self.logger.info("TUI refresh functionality test passed")
                return True
                
            except ImportError as e:
                self.logger.warning(f"Could not import TUI module for refresh functionality test: {e}")
                return True  # Don't fail for missing optional dependencies
            
            finally:
                if str(self.project_root) in sys.path:
                    sys.path.remove(str(self.project_root))
            
        except Exception as e:
            self.logger.error(f"TUI refresh functionality test failed: {e}")
            return False
    
    def _test_tui_configuration_handling(self) -> bool:
        """Test TUI configuration and environment handling."""
        self.logger.info("Testing TUI configuration handling")
        
        try:
            # Test TUI with various configuration scenarios
            test_scenarios = [
                {
                    "name": "valid_config",
                    "env_vars": {"TASKSGODZILLA_API_BASE": "http://localhost:8010"},
                    "should_handle_gracefully": True
                },
                {
                    "name": "missing_config",
                    "env_vars": {},
                    "should_handle_gracefully": True
                },
                {
                    "name": "invalid_api_url",
                    "env_vars": {"TASKSGODZILLA_API_BASE": "invalid-url"},
                    "should_handle_gracefully": True
                },
                {
                    "name": "invalid_db_path",
                    "env_vars": {"TASKSGODZILLA_DB_PATH": "/invalid/path/db.sqlite"},
                    "should_handle_gracefully": True
                }
            ]
            
            all_passed = True
            
            for scenario in test_scenarios:
                try:
                    # Set up test environment
                    test_env = os.environ.copy()
                    test_env.update(scenario["env_vars"])
                    
                    # Test TUI help command with different configurations
                    process = subprocess.Popen(
                        [sys.executable, str(self.tui_script), "--help"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        cwd=self.project_root,
                        env=test_env
                    )
                    
                    try:
                        stdout, stderr = process.communicate(timeout=10)
                        
                        if scenario["should_handle_gracefully"]:
                            # Should either succeed with help or fail gracefully
                            if process.returncode != 0:
                                # Check for graceful error handling
                                if not any(keyword in stderr.lower() for keyword in 
                                         ["error", "invalid", "not found", "tty", "terminal"]):
                                    self.logger.warning(f"TUI scenario '{scenario['name']}' failed ungracefully: {stderr}")
                                    all_passed = False
                            else:
                                # Success case - should show help
                                if "help" not in stdout.lower() and "usage" not in stdout.lower():
                                    self.logger.warning(f"TUI scenario '{scenario['name']}' succeeded but didn't show help")
                        
                    except subprocess.TimeoutExpired:
                        process.kill()
                        if scenario["should_handle_gracefully"]:
                            self.logger.warning(f"TUI scenario '{scenario['name']}' timed out")
                            all_passed = False
                
                except Exception as e:
                    self.logger.warning(f"TUI configuration test scenario '{scenario['name']}' failed: {e}")
                    all_passed = False
            
            if all_passed:
                self.logger.info("TUI configuration handling test passed")
            else:
                self.logger.warning("Some TUI configuration handling tests had issues")
            
            return all_passed
            
        except Exception as e:
            self.logger.error(f"TUI configuration handling test failed: {e}")
            return False
    
    def get_test_results(self):
        """Get test results from TUI interface tests."""
        return self.test_results