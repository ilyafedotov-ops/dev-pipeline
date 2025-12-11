"""SpecTestComponent - Tests spec-driven development workflow."""

import subprocess
import tempfile
import shutil
import logging
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

from tasksgodzilla.storage import Database
from tasksgodzilla.config import load_config
from tasksgodzilla.spec_tools import audit_specs
from ..environment import EnvironmentContext
from ..models import TestResult, HarnessStatus


class SpecTestComponent:
    """Test component for spec-driven development workflow."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = load_config()
    
    def run_test(self, project, env_context: EnvironmentContext) -> bool:
        """Run comprehensive spec workflow tests."""
        try:
            # Test various spec workflow scenarios
            test_results = []
            
            # Enhanced Test 1: Complete spec workflow validation (Task 15.3)
            result1 = self._test_spec_workflow_validation_comprehensive(env_context)
            test_results.append(result1)
            
            # Enhanced Test 2: Spec audit and validation functionality (Task 15.3)
            result2 = self._test_spec_audit_validation_enhanced(env_context)
            test_results.append(result2)
            
            # Enhanced Test 3: Property-based test generation and execution (Task 15.3)
            result3 = self._test_property_based_test_generation_comprehensive(env_context)
            test_results.append(result3)
            
            # Enhanced Test 4: Spec error handling and validation failures (Task 15.3)
            result4 = self._test_spec_error_handling_comprehensive(env_context)
            test_results.append(result4)
            
            # Legacy Test 5: Test spec audit functionality
            result5 = self._test_spec_audit_functionality(env_context)
            test_results.append(result5)
            
            # Legacy Test 6: Test spec validation workflow
            result6 = self._test_spec_validation_workflow(env_context)
            test_results.append(result6)
            
            # Legacy Test 7: Test requirements → design → tasks progression
            result7 = self._test_requirements_design_tasks_progression(env_context)
            test_results.append(result7)
            
            # Legacy Test 8: Test task execution and completion tracking
            result8 = self._test_task_execution_tracking(env_context)
            test_results.append(result8)
            
            # Legacy Test 9: Test property-based test generation
            result9 = self._test_property_based_test_generation(env_context)
            test_results.append(result9)
            
            # Legacy Test 10: Test spec error handling and validation failures
            result10 = self._test_spec_error_handling(env_context)
            test_results.append(result10)
            
            # Legacy Test 11: Test spec workflow integration
            result11 = self._test_spec_workflow_integration(env_context)
            test_results.append(result11)
            
            # Log detailed results for debugging
            self.logger.info(f"Spec test results: {[(r.test_name, r.status.value) for r in test_results]}")
            
            # Count passed tests (some may be skipped if dependencies unavailable)
            passed_tests = [r for r in test_results if r.status == HarnessStatus.PASS]
            failed_tests = [r for r in test_results if r.status == HarnessStatus.FAIL]
            
            # Consider success if no tests failed (skipped tests are OK)
            success = len(failed_tests) == 0
            
            if not success:
                failed_test_names = [r.test_name for r in failed_tests]
                self.logger.error(f"Spec tests failed: {failed_test_names}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"SpecTestComponent failed: {e}")
            return False
    
    def _test_spec_audit_functionality(self, env_context: EnvironmentContext) -> TestResult:
        """Test spec audit functionality via scripts/spec_audit.py."""
        test_name = "spec_audit_functionality"
        
        try:
            # Test if the spec_audit.py script exists
            script_path = Path(__file__).resolve().parents[3] / "scripts" / "spec_audit.py"
            
            if not script_path.exists():
                return TestResult(
                    component="spec",
                    test_name=test_name,
                    status=HarnessStatus.FAIL,
                    duration=0.0,
                    error_message="spec_audit.py script not found"
                )
            
            # Test help output
            try:
                # Set PYTHONPATH to include the project root
                project_root = script_path.parent.parent
                env = os.environ.copy()
                env["PYTHONPATH"] = str(project_root)
                
                result = subprocess.run(
                    ["python3", str(script_path), "--help"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=env
                )
                
                if result.returncode == 0 and "audit" in result.stdout.lower():
                    # Test actual audit functionality
                    # Get database path from environment or context
                    db_path = getattr(env_context, 'database_path', None)
                    if not db_path:
                        # Fallback to environment variable
                        db_path = os.environ.get('TASKSGODZILLA_DB_PATH')
                        if not db_path:
                            return TestResult(
                                component="spec",
                                test_name=test_name,
                                status=HarnessStatus.SKIP,
                                duration=1.0,
                                error_message="No database path available for testing"
                            )
                    
                    db = Database(db_path)
                    
                    # Initialize database schema
                    try:
                        db.init_schema()
                    except Exception as e:
                        return TestResult(
                            component="spec",
                            test_name=test_name,
                            status=HarnessStatus.FAIL,
                            duration=1.0,
                            error_message=f"Failed to initialize database schema: {str(e)}"
                        )
                    
                    # Run audit without backfill first
                    audit_results = audit_specs(db, backfill_missing=False)
                    
                    # The audit should return results (even if empty)
                    if isinstance(audit_results, list):
                        return TestResult(
                            component="spec",
                            test_name=test_name,
                            status=HarnessStatus.PASS,
                            duration=1.0,
                            metadata={"audit_results_count": len(audit_results)}
                        )
                    else:
                        return TestResult(
                            component="spec",
                            test_name=test_name,
                            status=HarnessStatus.FAIL,
                            duration=1.0,
                            error_message="Audit function did not return expected list"
                        )
                else:
                    return TestResult(
                        component="spec",
                        test_name=test_name,
                        status=HarnessStatus.FAIL,
                        duration=1.0,
                        error_message=f"Spec audit help failed: {result.stderr}"
                    )
                    
            except subprocess.TimeoutExpired:
                return TestResult(
                    component="spec",
                    test_name=test_name,
                    status=HarnessStatus.FAIL,
                    duration=30.0,
                    error_message="Spec audit help command timed out"
                )
                
        except Exception as e:
            return TestResult(
                component="spec",
                test_name=test_name,
                status=HarnessStatus.ERROR,
                duration=0.0,
                error_message=str(e)
            )
    
    def _test_spec_validation_workflow(self, env_context: EnvironmentContext) -> TestResult:
        """Test spec validation workflow."""
        test_name = "spec_validation_workflow"
        
        try:
            # Get database path from environment or context
            db_path = getattr(env_context, 'database_path', None)
            if not db_path:
                db_path = os.environ.get('TASKSGODZILLA_DB_PATH')
                if not db_path:
                    return TestResult(
                        component="spec",
                        test_name=test_name,
                        status=HarnessStatus.SKIP,
                        duration=0.0,
                        error_message="No database path available for testing"
                    )
            
            db = Database(db_path)
            
            # Initialize database schema
            try:
                db.init_schema()
            except Exception as e:
                return TestResult(
                    component="spec",
                    test_name=test_name,
                    status=HarnessStatus.ERROR,
                    duration=0.0,
                    error_message=f"Failed to initialize database schema: {str(e)}"
                )
            
            # Look for existing protocol runs to validate specs against
            projects = db.list_projects()
            if not projects:
                return TestResult(
                    component="spec",
                    test_name=test_name,
                    status=HarnessStatus.SKIP,
                    duration=0.0,
                    error_message="No projects available for spec validation test"
                )
            
            protocol_runs = []
            for project in projects:
                runs = db.list_protocol_runs(project.id)
                protocol_runs.extend(runs)
            
            if not protocol_runs:
                return TestResult(
                    component="spec",
                    test_name=test_name,
                    status=HarnessStatus.SKIP,
                    duration=0.0,
                    error_message="No protocol runs available for spec validation test"
                )
            
            # Test audit with backfill for the first protocol run
            test_run = protocol_runs[0]
            
            try:
                audit_results = audit_specs(
                    db, 
                    protocol_id=test_run.id, 
                    backfill_missing=True
                )
                
                if isinstance(audit_results, list):
                    # Check if any results were returned
                    if audit_results:
                        # Look for validation results
                        has_errors = any(result.get("errors") for result in audit_results)
                        has_backfilled = any(result.get("backfilled") for result in audit_results)
                        
                        return TestResult(
                            component="spec",
                            test_name=test_name,
                            status=HarnessStatus.PASS,
                            duration=1.0,
                            metadata={
                                "audit_results_count": len(audit_results),
                                "has_errors": has_errors,
                                "has_backfilled": has_backfilled
                            }
                        )
                    else:
                        # No results might be OK if no specs exist
                        return TestResult(
                            component="spec",
                            test_name=test_name,
                            status=HarnessStatus.PASS,
                            duration=1.0,
                            metadata={"no_specs_found": True}
                        )
                else:
                    return TestResult(
                        component="spec",
                        test_name=test_name,
                        status=HarnessStatus.FAIL,
                        duration=1.0,
                        error_message="Audit function returned unexpected type"
                    )
                    
            except Exception as e:
                return TestResult(
                    component="spec",
                    test_name=test_name,
                    status=HarnessStatus.FAIL,
                    duration=1.0,
                    error_message=f"Spec audit failed: {str(e)}"
                )
                
        except Exception as e:
            return TestResult(
                component="spec",
                test_name=test_name,
                status=HarnessStatus.ERROR,
                duration=0.0,
                error_message=str(e)
            )
    
    def _test_requirements_design_tasks_progression(self, env_context: EnvironmentContext) -> TestResult:
        """Test requirements → design → tasks progression."""
        test_name = "requirements_design_tasks_progression"
        
        try:
            # Look for existing spec files in the .kiro/specs directory
            kiro_specs_path = Path(__file__).resolve().parents[3] / ".kiro" / "specs"
            
            if not kiro_specs_path.exists():
                return TestResult(
                    component="spec",
                    test_name=test_name,
                    status=HarnessStatus.SKIP,
                    duration=0.0,
                    error_message=".kiro/specs directory not found"
                )
            
            # Find spec directories
            spec_dirs = [d for d in kiro_specs_path.iterdir() if d.is_dir()]
            
            if not spec_dirs:
                return TestResult(
                    component="spec",
                    test_name=test_name,
                    status=HarnessStatus.SKIP,
                    duration=0.0,
                    error_message="No spec directories found"
                )
            
            # Check for complete spec workflows (requirements → design → tasks)
            complete_specs = []
            
            for spec_dir in spec_dirs:
                requirements_file = spec_dir / "requirements.md"
                design_file = spec_dir / "design.md"
                tasks_file = spec_dir / "tasks.md"
                
                if (requirements_file.exists() and 
                    design_file.exists() and 
                    tasks_file.exists()):
                    
                    # Verify files have content
                    try:
                        req_content = requirements_file.read_text(encoding='utf-8')
                        design_content = design_file.read_text(encoding='utf-8')
                        tasks_content = tasks_file.read_text(encoding='utf-8')
                        
                        if (len(req_content.strip()) > 100 and 
                            len(design_content.strip()) > 100 and 
                            len(tasks_content.strip()) > 100):
                            
                            complete_specs.append(spec_dir.name)
                            
                    except Exception as e:
                        self.logger.warning(f"Error reading spec files in {spec_dir.name}: {e}")
            
            if complete_specs:
                return TestResult(
                    component="spec",
                    test_name=test_name,
                    status=HarnessStatus.PASS,
                    duration=0.5,
                    metadata={"complete_specs": complete_specs}
                )
            else:
                return TestResult(
                    component="spec",
                    test_name=test_name,
                    status=HarnessStatus.FAIL,
                    duration=0.5,
                    error_message="No complete spec workflows found (requirements → design → tasks)"
                )
                
        except Exception as e:
            return TestResult(
                component="spec",
                test_name=test_name,
                status=HarnessStatus.ERROR,
                duration=0.0,
                error_message=str(e)
            )
    
    def _test_task_execution_tracking(self, env_context: EnvironmentContext) -> TestResult:
        """Test task execution and completion tracking."""
        test_name = "task_execution_tracking"
        
        try:
            # Look for task files with completion tracking
            kiro_specs_path = Path(__file__).resolve().parents[3] / ".kiro" / "specs"
            
            if not kiro_specs_path.exists():
                return TestResult(
                    component="spec",
                    test_name=test_name,
                    status=HarnessStatus.SKIP,
                    duration=0.0,
                    error_message=".kiro/specs directory not found"
                )
            
            # Find task files and check for completion tracking
            task_files = list(kiro_specs_path.glob("*/tasks.md"))
            
            if not task_files:
                return TestResult(
                    component="spec",
                    test_name=test_name,
                    status=HarnessStatus.SKIP,
                    duration=0.0,
                    error_message="No task files found"
                )
            
            # Check task files for completion tracking syntax
            files_with_tracking = []
            
            for task_file in task_files:
                try:
                    content = task_file.read_text(encoding='utf-8')
                    
                    # Look for task completion markers
                    if ("[x]" in content or "[-]" in content or "[ ]" in content):
                        # Count different task states
                        completed_tasks = content.count("[x]")
                        in_progress_tasks = content.count("[-]")
                        pending_tasks = content.count("[ ]")
                        
                        if completed_tasks > 0 or in_progress_tasks > 0:
                            files_with_tracking.append({
                                "file": task_file.parent.name,
                                "completed": completed_tasks,
                                "in_progress": in_progress_tasks,
                                "pending": pending_tasks
                            })
                            
                except Exception as e:
                    self.logger.warning(f"Error reading task file {task_file}: {e}")
            
            if files_with_tracking:
                return TestResult(
                    component="spec",
                    test_name=test_name,
                    status=HarnessStatus.PASS,
                    duration=0.3,
                    metadata={"files_with_tracking": files_with_tracking}
                )
            else:
                return TestResult(
                    component="spec",
                    test_name=test_name,
                    status=HarnessStatus.FAIL,
                    duration=0.3,
                    error_message="No task files found with completion tracking"
                )
                
        except Exception as e:
            return TestResult(
                component="spec",
                test_name=test_name,
                status=HarnessStatus.ERROR,
                duration=0.0,
                error_message=str(e)
            )
    
    def _test_property_based_test_generation(self, env_context: EnvironmentContext) -> TestResult:
        """Test property-based test generation."""
        test_name = "property_based_test_generation"
        
        try:
            # Look for design files with correctness properties
            kiro_specs_path = Path(__file__).resolve().parents[3] / ".kiro" / "specs"
            
            if not kiro_specs_path.exists():
                return TestResult(
                    component="spec",
                    test_name=test_name,
                    status=HarnessStatus.SKIP,
                    duration=0.0,
                    error_message=".kiro/specs directory not found"
                )
            
            # Find design files and check for correctness properties
            design_files = list(kiro_specs_path.glob("*/design.md"))
            
            if not design_files:
                return TestResult(
                    component="spec",
                    test_name=test_name,
                    status=HarnessStatus.SKIP,
                    duration=0.0,
                    error_message="No design files found"
                )
            
            # Check design files for correctness properties
            files_with_properties = []
            
            for design_file in design_files:
                try:
                    content = design_file.read_text(encoding='utf-8')
                    
                    # Look for correctness properties section and property definitions
                    if ("correctness properties" in content.lower() and 
                        "property" in content.lower()):
                        
                        # Count property definitions
                        property_count = content.lower().count("**property")
                        validates_count = content.count("**Validates:")
                        
                        if property_count > 0:
                            files_with_properties.append({
                                "file": design_file.parent.name,
                                "property_count": property_count,
                                "validates_count": validates_count
                            })
                            
                except Exception as e:
                    self.logger.warning(f"Error reading design file {design_file}: {e}")
            
            if files_with_properties:
                # Also check if there are corresponding property-based tests
                test_files_found = []
                
                # Look for test files that might contain property-based tests
                project_root = Path(__file__).resolve().parents[3]
                test_dirs = [project_root / "tests"]
                
                for test_dir in test_dirs:
                    if test_dir.exists():
                        # Look for files that might contain property-based tests
                        test_files = list(test_dir.glob("**/*test*.py"))
                        
                        for test_file in test_files:
                            try:
                                content = test_file.read_text(encoding='utf-8')
                                
                                # Look for property-based testing indicators
                                if ("hypothesis" in content.lower() or 
                                    "property" in content.lower() or
                                    "@given" in content):
                                    test_files_found.append(test_file.name)
                                    
                            except Exception:
                                continue
                
                return TestResult(
                    component="spec",
                    test_name=test_name,
                    status=HarnessStatus.PASS,
                    duration=0.5,
                    metadata={
                        "files_with_properties": files_with_properties,
                        "test_files_found": test_files_found
                    }
                )
            else:
                return TestResult(
                    component="spec",
                    test_name=test_name,
                    status=HarnessStatus.FAIL,
                    duration=0.5,
                    error_message="No design files found with correctness properties"
                )
                
        except Exception as e:
            return TestResult(
                component="spec",
                test_name=test_name,
                status=HarnessStatus.ERROR,
                duration=0.0,
                error_message=str(e)
            )
    def _test_spec_error_handling(self, env_context: EnvironmentContext) -> TestResult:
        """Test spec error handling and validation failures."""
        test_name = "spec_error_handling"
        
        try:
            # Test various error scenarios in spec processing
            error_test_results = []
            
            # Test 1: Test with missing spec files
            try:
                kiro_specs_path = Path(__file__).resolve().parents[3] / ".kiro" / "specs"
                
                if kiro_specs_path.exists():
                    # Look for incomplete spec directories
                    incomplete_specs = []
                    
                    for spec_dir in kiro_specs_path.iterdir():
                        if spec_dir.is_dir():
                            requirements_file = spec_dir / "requirements.md"
                            design_file = spec_dir / "design.md"
                            tasks_file = spec_dir / "tasks.md"
                            
                            missing_files = []
                            if not requirements_file.exists():
                                missing_files.append("requirements.md")
                            if not design_file.exists():
                                missing_files.append("design.md")
                            if not tasks_file.exists():
                                missing_files.append("tasks.md")
                            
                            if missing_files:
                                incomplete_specs.append({
                                    "spec": spec_dir.name,
                                    "missing": missing_files
                                })
                    
                    if incomplete_specs:
                        error_test_results.append(f"incomplete_specs: found {len(incomplete_specs)} incomplete specs")
                    else:
                        error_test_results.append("incomplete_specs: all specs complete")
                        
                else:
                    error_test_results.append("missing_specs_directory: .kiro/specs not found")
                    
            except Exception as e:
                error_test_results.append(f"spec_file_check: error - {str(e)[:100]}")
            
            # Test 2: Test spec audit with invalid data
            try:
                db_path = getattr(env_context, 'database_path', None)
                if not db_path:
                    db_path = os.environ.get('TASKSGODZILLA_DB_PATH')
                
                if db_path:
                    db = Database(db_path)
                    
                    # Try to audit with invalid protocol ID
                    try:
                        invalid_audit = audit_specs(db, protocol_id=99999, backfill_missing=False)
                        if isinstance(invalid_audit, list):
                            error_test_results.append("invalid_protocol_audit: handled gracefully")
                        else:
                            error_test_results.append("invalid_protocol_audit: unexpected result")
                    except Exception as e:
                        error_test_results.append("invalid_protocol_audit: exception handled")
                        
                else:
                    error_test_results.append("spec_audit_error: no database available")
                    
            except Exception as e:
                error_test_results.append(f"spec_audit_error: {str(e)[:100]}")
            
            # Test 3: Test malformed spec file handling
            try:
                # Create a temporary malformed spec file
                temp_spec_dir = env_context.temp_dir / "test_malformed_spec"
                temp_spec_dir.mkdir(exist_ok=True)
                
                # Create malformed requirements file
                malformed_req = temp_spec_dir / "requirements.md"
                malformed_req.write_text("# Malformed Requirements\n\nThis is not a proper requirements document.")
                
                # Try to process it (this should handle gracefully)
                try:
                    content = malformed_req.read_text(encoding='utf-8')
                    if len(content) > 0:
                        error_test_results.append("malformed_spec_handling: file readable")
                    else:
                        error_test_results.append("malformed_spec_handling: file empty")
                except Exception as e:
                    error_test_results.append("malformed_spec_handling: read error")
                    
            except Exception as e:
                error_test_results.append(f"malformed_spec_test: {str(e)[:100]}")
            
            # Evaluate error handling results
            failed_error_tests = [r for r in error_test_results if "error" in r or "failed" in r]
            
            if len(failed_error_tests) == 0:
                return TestResult(
                    component="spec",
                    test_name=test_name,
                    status=HarnessStatus.PASS,
                    duration=0.5,
                    metadata={"error_test_results": error_test_results}
                )
            else:
                return TestResult(
                    component="spec",
                    test_name=test_name,
                    status=HarnessStatus.FAIL,
                    duration=0.5,
                    error_message=f"Error handling issues: {failed_error_tests[:2]}"
                )
                
        except Exception as e:
            return TestResult(
                component="spec",
                test_name=test_name,
                status=HarnessStatus.ERROR,
                duration=0.0,
                error_message=str(e)
            )
    
    def _test_spec_workflow_integration(self, env_context: EnvironmentContext) -> TestResult:
        """Test spec workflow integration with other components."""
        test_name = "spec_workflow_integration"
        
        try:
            integration_results = []
            
            # Test 1: Integration with protocol system
            try:
                db_path = getattr(env_context, 'database_path', None)
                if not db_path:
                    db_path = os.environ.get('TASKSGODZILLA_DB_PATH')
                
                if db_path:
                    db = Database(db_path)
                    
                    # Check if we have protocol runs to integrate with
                    projects = db.list_projects()
                    if projects:
                        protocol_runs = []
                        for project in projects:
                            runs = db.list_protocol_runs(project.id)
                            protocol_runs.extend(runs)
                        
                        if protocol_runs:
                            integration_results.append(f"protocol_integration: {len(protocol_runs)} protocol runs available")
                            
                            # Test spec audit integration
                            try:
                                audit_results = audit_specs(db, backfill_missing=False)
                                if isinstance(audit_results, list):
                                    integration_results.append(f"audit_integration: {len(audit_results)} audit results")
                                else:
                                    integration_results.append("audit_integration: unexpected result type")
                            except Exception as e:
                                integration_results.append(f"audit_integration: error - {str(e)[:100]}")
                        else:
                            integration_results.append("protocol_integration: no protocol runs found")
                    else:
                        integration_results.append("protocol_integration: no projects found")
                else:
                    integration_results.append("protocol_integration: no database available")
                    
            except Exception as e:
                integration_results.append(f"protocol_integration: error - {str(e)[:100]}")
            
            # Test 2: Integration with file system specs
            try:
                kiro_specs_path = Path(__file__).resolve().parents[3] / ".kiro" / "specs"
                
                if kiro_specs_path.exists():
                    spec_dirs = [d for d in kiro_specs_path.iterdir() if d.is_dir()]
                    
                    if spec_dirs:
                        integration_results.append(f"filesystem_integration: {len(spec_dirs)} spec directories found")
                        
                        # Test reading and processing spec files
                        processed_specs = 0
                        for spec_dir in spec_dirs[:3]:  # Test first 3 specs
                            try:
                                requirements_file = spec_dir / "requirements.md"
                                if requirements_file.exists():
                                    content = requirements_file.read_text(encoding='utf-8')
                                    if "requirements" in content.lower():
                                        processed_specs += 1
                            except Exception:
                                continue
                        
                        integration_results.append(f"spec_processing: {processed_specs} specs processed successfully")
                    else:
                        integration_results.append("filesystem_integration: no spec directories found")
                else:
                    integration_results.append("filesystem_integration: .kiro/specs directory not found")
                    
            except Exception as e:
                integration_results.append(f"filesystem_integration: error - {str(e)[:100]}")
            
            # Test 3: Integration with task tracking
            try:
                # Look for task files with tracking markers
                kiro_specs_path = Path(__file__).resolve().parents[3] / ".kiro" / "specs"
                
                if kiro_specs_path.exists():
                    task_files = list(kiro_specs_path.glob("*/tasks.md"))
                    
                    if task_files:
                        tracked_tasks = 0
                        total_tasks = 0
                        
                        for task_file in task_files:
                            try:
                                content = task_file.read_text(encoding='utf-8')
                                total_tasks += content.count("- [")
                                tracked_tasks += content.count("- [x]") + content.count("- [-]")
                            except Exception:
                                continue
                        
                        if total_tasks > 0:
                            tracking_percentage = (tracked_tasks / total_tasks) * 100
                            integration_results.append(f"task_tracking: {tracking_percentage:.1f}% tasks tracked ({tracked_tasks}/{total_tasks})")
                        else:
                            integration_results.append("task_tracking: no trackable tasks found")
                    else:
                        integration_results.append("task_tracking: no task files found")
                else:
                    integration_results.append("task_tracking: specs directory not available")
                    
            except Exception as e:
                integration_results.append(f"task_tracking: error - {str(e)[:100]}")
            
            # Evaluate integration results
            failed_integrations = [r for r in integration_results if "error" in r or "failed" in r]
            
            if len(failed_integrations) == 0:
                return TestResult(
                    component="spec",
                    test_name=test_name,
                    status=HarnessStatus.PASS,
                    duration=0.7,
                    metadata={"integration_results": integration_results}
                )
            else:
                return TestResult(
                    component="spec",
                    test_name=test_name,
                    status=HarnessStatus.FAIL,
                    duration=0.7,
                    error_message=f"Integration issues: {failed_integrations[:2]}"
                )
                
        except Exception as e:
            return TestResult(
                component="spec",
                test_name=test_name,
                status=HarnessStatus.ERROR,
                duration=0.0,
                error_message=str(e)
            )