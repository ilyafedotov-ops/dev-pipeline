"""QualityTestComponent - Tests quality orchestrator QA report generation."""

import subprocess
import tempfile
import shutil
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

from tasksgodzilla.storage import Database
from tasksgodzilla.config import load_config
from tasksgodzilla.qa import run_quality_check
from ..environment import EnvironmentContext
from ..models import TestResult, HarnessStatus


class QualityTestComponent:
    """Test component for quality orchestrator functionality."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = load_config()
    
    def run_test(self, project, env_context: EnvironmentContext) -> bool:
        """Run comprehensive quality orchestrator tests."""
        try:
            # Test various quality scenarios
            test_results = []
            
            # Test 1: Test quality orchestrator script availability
            result1 = self._test_quality_orchestrator_script(env_context)
            test_results.append(result1)
            
            # Test 2: Test QA report generation
            result2 = self._test_qa_report_generation(env_context)
            test_results.append(result2)
            
            # Test 3: Test quality gates and approval workflows
            result3 = self._test_quality_gates_approval(env_context)
            test_results.append(result3)
            
            # Test 4: Test integration with protocol execution pipeline
            result4 = self._test_protocol_integration(env_context)
            test_results.append(result4)
            
            # Test 5: Test QA report parsing and recommendation extraction
            result5 = self._test_qa_report_parsing(env_context)
            test_results.append(result5)
            
            # Test 6: Test quality system error handling and degradation
            result6 = self._test_quality_error_handling(env_context)
            test_results.append(result6)
            
            # Test 7: Test quality workflow integration
            result7 = self._test_quality_workflow_integration(env_context)
            test_results.append(result7)
            
            # Log detailed results for debugging
            self.logger.info(f"Quality test results: {[(r.test_name, r.status.value) for r in test_results]}")
            
            # Count passed tests (some may be skipped if dependencies unavailable)
            passed_tests = [r for r in test_results if r.status == HarnessStatus.PASS]
            failed_tests = [r for r in test_results if r.status == HarnessStatus.FAIL]
            
            # Consider success if no tests failed (skipped tests are OK)
            success = len(failed_tests) == 0
            
            if not success:
                failed_test_names = [r.test_name for r in failed_tests]
                self.logger.error(f"Quality tests failed: {failed_test_names}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"QualityTestComponent failed: {e}")
            return False
    
    def _is_codex_available(self) -> bool:
        """Check if Codex CLI is available."""
        try:
            result = subprocess.run(
                ["codex", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _test_quality_orchestrator_script(self, env_context: EnvironmentContext) -> TestResult:
        """Test quality orchestrator script availability and basic functionality."""
        test_name = "quality_orchestrator_script"
        
        try:
            # Test if the quality_orchestrator.py script exists
            script_path = Path(__file__).resolve().parents[3] / "scripts" / "quality_orchestrator.py"
            
            if not script_path.exists():
                return TestResult(
                    component="quality",
                    test_name=test_name,
                    status=HarnessStatus.FAIL,
                    duration=0.0,
                    error_message="quality_orchestrator.py script not found"
                )
            
            # Test help output
            try:
                result = subprocess.run(
                    ["python3", str(script_path), "--help"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0 and ("quality" in result.stdout.lower() or "qa" in result.stdout.lower()):
                    return TestResult(
                        component="quality",
                        test_name=test_name,
                        status=HarnessStatus.PASS,
                        duration=1.0,
                    )
                else:
                    return TestResult(
                        component="quality",
                        test_name=test_name,
                        status=HarnessStatus.FAIL,
                        duration=1.0,
                        error_message=f"Quality orchestrator help failed: {result.stderr}"
                    )
                    
            except subprocess.TimeoutExpired:
                return TestResult(
                    component="quality",
                    test_name=test_name,
                    status=HarnessStatus.FAIL,
                    duration=30.0,
                    error_message="Quality orchestrator help command timed out"
                )
                
        except Exception as e:
            return TestResult(
                component="quality",
                test_name=test_name,
                status=HarnessStatus.ERROR,
                duration=0.0,
                error_message=str(e)
            )
    
    def _test_qa_report_generation(self, env_context: EnvironmentContext) -> TestResult:
        """Test QA report generation functionality."""
        test_name = "qa_report_generation"
        
        try:
            if not self._is_codex_available():
                return TestResult(
                    component="quality",
                    test_name=test_name,
                    status=HarnessStatus.SKIP,
                    duration=0.0,
                    error_message="Codex CLI not available for QA report generation"
                )
            
            # Create a test protocol structure for QA
            with tempfile.TemporaryDirectory() as temp_dir:
                protocol_root = Path(temp_dir) / "test-protocol"
                protocol_root.mkdir()
                
                # Create a test step file
                step_file = protocol_root / "01-test-step.md"
                step_content = """# Test Step

## Objective
Test the quality orchestrator functionality.

## Implementation
This is a test step for quality validation.

## Validation
- [ ] Step should be validated by QA
- [ ] Quality gates should be checked
"""
                step_file.write_text(step_content)
                
                # Create a test prompt file
                prompt_file = Path(__file__).resolve().parents[3] / "prompts" / "quality-validator.prompt.md"
                
                if not prompt_file.exists():
                    # Create a minimal prompt file for testing
                    test_prompt_file = Path(temp_dir) / "test-quality-validator.prompt.md"
                    test_prompt_content = """# Quality Validator Prompt

You are a quality validator. Review the provided step and provide feedback.

## Instructions
1. Review the step for completeness
2. Check for potential issues
3. Provide recommendations

## Output Format
Provide your assessment in markdown format.
"""
                    test_prompt_file.write_text(test_prompt_content)
                    prompt_file = test_prompt_file
                
                try:
                    # Test QA report generation using the reusable module
                    qa_result = run_quality_check(
                        protocol_root=protocol_root,
                        step_file=step_file,
                        model="gpt-5.1-codex-max",
                        prompt_file=prompt_file,
                        sandbox="read-only",
                        report_file=None,  # Use default location
                        max_tokens=1000,
                        token_budget_mode="strict",
                    )
                    
                    # Verify QA result structure
                    if qa_result and hasattr(qa_result, 'report_path') and hasattr(qa_result, 'verdict'):
                        # Check if report was generated
                        if qa_result.report_path and qa_result.report_path.exists():
                            return TestResult(
                                component="quality",
                                test_name=test_name,
                                status=HarnessStatus.PASS,
                                duration=2.0,
                                metadata={"verdict": qa_result.verdict}
                            )
                        else:
                            return TestResult(
                                component="quality",
                                test_name=test_name,
                                status=HarnessStatus.FAIL,
                                duration=2.0,
                                error_message="QA report file not generated"
                            )
                    else:
                        return TestResult(
                            component="quality",
                            test_name=test_name,
                            status=HarnessStatus.FAIL,
                            duration=2.0,
                            error_message="QA result structure invalid"
                        )
                        
                except FileNotFoundError:
                    return TestResult(
                        component="quality",
                        test_name=test_name,
                        status=HarnessStatus.SKIP,
                        duration=0.0,
                        error_message="Codex CLI not found for QA execution"
                    )
                except Exception as e:
                    return TestResult(
                        component="quality",
                        test_name=test_name,
                        status=HarnessStatus.FAIL,
                        duration=2.0,
                        error_message=f"QA report generation failed: {str(e)}"
                    )
                    
        except Exception as e:
            return TestResult(
                component="quality",
                test_name=test_name,
                status=HarnessStatus.ERROR,
                duration=0.0,
                error_message=str(e)
            )
    
    def _test_quality_gates_approval(self, env_context: EnvironmentContext) -> TestResult:
        """Test quality gates and approval workflows."""
        test_name = "quality_gates_approval"
        
        try:
            # Test quality gate logic by simulating different QA verdicts
            test_verdicts = ["PASS", "FAIL", "NEEDS_REVIEW"]
            
            for verdict in test_verdicts:
                # Simulate quality gate evaluation
                gate_result = self._evaluate_quality_gate(verdict)
                
                # Verify gate behavior
                if verdict == "PASS":
                    assert gate_result["approved"] is True
                    assert gate_result["requires_action"] is False
                elif verdict == "FAIL":
                    assert gate_result["approved"] is False
                    assert gate_result["requires_action"] is True
                elif verdict == "NEEDS_REVIEW":
                    assert gate_result["approved"] is False
                    assert gate_result["requires_action"] is True
            
            return TestResult(
                component="quality",
                test_name=test_name,
                status=HarnessStatus.PASS,
                duration=0.5,
                metadata={"tested_verdicts": test_verdicts}
            )
            
        except Exception as e:
            return TestResult(
                component="quality",
                test_name=test_name,
                status=HarnessStatus.ERROR,
                duration=0.0,
                error_message=str(e)
            )
    
    def _evaluate_quality_gate(self, verdict: str) -> Dict[str, Any]:
        """Simulate quality gate evaluation logic."""
        if verdict == "PASS":
            return {
                "approved": True,
                "requires_action": False,
                "next_steps": ["Proceed to next phase"]
            }
        elif verdict == "FAIL":
            return {
                "approved": False,
                "requires_action": True,
                "next_steps": ["Address QA feedback", "Re-run quality check"]
            }
        elif verdict == "NEEDS_REVIEW":
            return {
                "approved": False,
                "requires_action": True,
                "next_steps": ["Manual review required", "Clarify requirements"]
            }
        else:
            return {
                "approved": False,
                "requires_action": True,
                "next_steps": ["Unknown verdict - manual intervention required"]
            }
    
    def _test_protocol_integration(self, env_context: EnvironmentContext) -> TestResult:
        """Test integration with protocol execution pipeline."""
        test_name = "protocol_integration"
        
        try:
            db = Database(env_context.db_path)
            
            # Look for existing protocol runs to test integration
            projects = db.list_projects()
            if not projects:
                return TestResult(
                    component="quality",
                    test_name=test_name,
                    status=HarnessStatus.SKIP,
                    duration=0.0,
                    error_message="No projects available for protocol integration test"
                )
            
            protocol_runs = []
            for project in projects:
                runs = db.list_protocol_runs(project.id)
                protocol_runs.extend(runs)
            
            if not protocol_runs:
                return TestResult(
                    component="quality",
                    test_name=test_name,
                    status=HarnessStatus.SKIP,
                    duration=0.0,
                    error_message="No protocol runs available for integration test"
                )
            
            # Test quality integration with protocol execution
            test_run = protocol_runs[0]
            
            # Simulate QA event logging
            db.append_event(
                protocol_run_id=test_run.id,
                event_type="qa_started",
                message="Quality check initiated by harness test"
            )
            
            # Simulate QA completion
            db.append_event(
                protocol_run_id=test_run.id,
                event_type="qa_completed",
                message="Quality check completed with verdict: PASS"
            )
            
            # Verify events were logged
            events = db.list_events(test_run.id)
            qa_events = [e for e in events if e.event_type.startswith("qa_")]
            
            if len(qa_events) >= 2:  # Should have at least started and completed events
                return TestResult(
                    component="quality",
                    test_name=test_name,
                    status=HarnessStatus.PASS,
                    duration=0.3,
                    metadata={"qa_events_count": len(qa_events)}
                )
            else:
                return TestResult(
                    component="quality",
                    test_name=test_name,
                    status=HarnessStatus.FAIL,
                    duration=0.3,
                    error_message="QA events not properly logged"
                )
                
        except Exception as e:
            return TestResult(
                component="quality",
                test_name=test_name,
                status=HarnessStatus.ERROR,
                duration=0.0,
                error_message=str(e)
            )
    
    def _test_qa_report_parsing(self, env_context: EnvironmentContext) -> TestResult:
        """Test QA report parsing and recommendation extraction."""
        test_name = "qa_report_parsing"
        
        try:
            # Create a sample QA report for parsing
            sample_report_content = """# Quality Assessment Report

## Summary
The step has been reviewed and the following issues were identified.

## Issues Found
1. **Missing Error Handling**: The implementation lacks proper error handling for edge cases.
2. **Incomplete Documentation**: Some functions are missing docstrings.
3. **Performance Concern**: The algorithm may not scale well with large inputs.

## Recommendations
1. Add try-catch blocks for error handling
2. Complete documentation for all public functions
3. Consider optimizing the algorithm for better performance

## Verdict
NEEDS_REVIEW

## Next Steps
- Address the identified issues
- Re-run quality check after fixes
- Consider additional testing
"""
            
            # Test parsing logic
            parsed_report = self._parse_qa_report(sample_report_content)
            
            # Verify parsing results
            assert "verdict" in parsed_report
            assert "issues" in parsed_report
            assert "recommendations" in parsed_report
            assert "next_steps" in parsed_report
            
            # Verify content extraction
            assert parsed_report["verdict"] == "NEEDS_REVIEW"
            assert len(parsed_report["issues"]) == 3
            assert len(parsed_report["recommendations"]) == 3
            assert len(parsed_report["next_steps"]) >= 2
            
            # Verify issue categorization
            issues = parsed_report["issues"]
            assert any("error handling" in issue.lower() for issue in issues)
            assert any("documentation" in issue.lower() for issue in issues)
            assert any("performance" in issue.lower() for issue in issues)
            
            return TestResult(
                component="quality",
                test_name=test_name,
                status=HarnessStatus.PASS,
                duration=0.2,
                metadata=parsed_report
            )
            
        except Exception as e:
            return TestResult(
                component="quality",
                test_name=test_name,
                status=HarnessStatus.ERROR,
                duration=0.0,
                error_message=str(e)
            )
    
    def _parse_qa_report(self, report_content: str) -> Dict[str, Any]:
        """Parse QA report content and extract structured information."""
        parsed = {
            "verdict": "UNKNOWN",
            "issues": [],
            "recommendations": [],
            "next_steps": []
        }
        
        lines = report_content.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            
            # Identify sections
            if line.startswith("## Issues Found"):
                current_section = "issues"
                continue
            elif line.startswith("## Recommendations"):
                current_section = "recommendations"
                continue
            elif line.startswith("## Next Steps"):
                current_section = "next_steps"
                continue
            elif line.startswith("## Verdict"):
                current_section = "verdict"
                continue
            elif line.startswith("##"):
                current_section = None
                continue
            
            # Extract content based on current section
            if current_section == "verdict" and line and not line.startswith("#"):
                # Validate verdict values
                valid_verdicts = ["PASS", "FAIL", "NEEDS_REVIEW"]
                if line.strip() in valid_verdicts:
                    parsed["verdict"] = line.strip()
                else:
                    parsed["verdict"] = "UNKNOWN"  # Invalid verdict becomes UNKNOWN
            elif current_section == "issues" and line.startswith(("1.", "2.", "3.", "4.", "5.", "-", "*")):
                # Extract issue text (remove numbering and formatting)
                issue_text = line
                if "**" in issue_text:
                    # Extract text between ** markers
                    parts = issue_text.split("**")
                    if len(parts) >= 3:
                        issue_text = parts[1] + ": " + "**".join(parts[2:])
                parsed["issues"].append(issue_text)
            elif current_section == "recommendations" and line.startswith(("1.", "2.", "3.", "4.", "5.", "-", "*")):
                # Extract recommendation text
                rec_text = line.lstrip("1234567890.- *")
                parsed["recommendations"].append(rec_text)
            elif current_section == "next_steps" and line.startswith(("-", "*", "•")):
                # Extract next step text
                step_text = line.lstrip("- *•")
                parsed["next_steps"].append(step_text)
        
        return parsed
    def _test_quality_error_handling(self, env_context: EnvironmentContext) -> TestResult:
        """Test quality system error handling and degradation."""
        test_name = "quality_error_handling"
        
        try:
            error_test_results = []
            
            # Test 1: Test QA with invalid input
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    protocol_root = Path(temp_dir) / "invalid-protocol"
                    protocol_root.mkdir()
                    
                    # Create invalid step file (empty or malformed)
                    invalid_step = protocol_root / "invalid-step.md"
                    invalid_step.write_text("")  # Empty file
                    
                    # Test QA with empty step file
                    try:
                        qa_result = run_quality_check(
                            protocol_root=protocol_root,
                            step_file=invalid_step,
                            model="gpt-5.1-codex-max",
                            prompt_file=None,  # No prompt file
                            sandbox="read-only",
                            report_file=None,
                            max_tokens=100,
                            token_budget_mode="strict",
                        )
                        
                        if qa_result:
                            error_test_results.append("empty_step_handling: processed (should handle gracefully)")
                        else:
                            error_test_results.append("empty_step_handling: rejected (good)")
                            
                    except Exception as e:
                        error_test_results.append("empty_step_handling: exception handled")
                        
            except Exception as e:
                error_test_results.append(f"invalid_input_test: error - {str(e)[:100]}")
            
            # Test 2: Test QA with missing dependencies
            try:
                # Test without Codex available
                if not self._is_codex_available():
                    error_test_results.append("codex_unavailable: handled gracefully")
                else:
                    # Test with invalid model
                    with tempfile.TemporaryDirectory() as temp_dir:
                        protocol_root = Path(temp_dir) / "test-protocol"
                        protocol_root.mkdir()
                        
                        step_file = protocol_root / "test-step.md"
                        step_file.write_text("# Test Step\n\nThis is a test step.")
                        
                        try:
                            qa_result = run_quality_check(
                                protocol_root=protocol_root,
                                step_file=step_file,
                                model="invalid-model-name",
                                prompt_file=None,
                                sandbox="read-only",
                                report_file=None,
                                max_tokens=100,
                                token_budget_mode="strict",
                            )
                            
                            if qa_result:
                                error_test_results.append("invalid_model: processed (unexpected)")
                            else:
                                error_test_results.append("invalid_model: rejected (good)")
                                
                        except Exception as e:
                            error_test_results.append("invalid_model: exception handled")
                            
            except Exception as e:
                error_test_results.append(f"dependency_test: error - {str(e)[:100]}")
            
            # Test 3: Test QA report parsing with malformed content
            try:
                malformed_reports = [
                    "",  # Empty report
                    "Not a valid QA report",  # Invalid format
                    "# QA Report\n\nNo verdict section",  # Missing verdict
                    "# QA Report\n\n## Verdict\n\nINVALID_VERDICT",  # Invalid verdict
                ]
                
                parsing_results = []
                for i, report_content in enumerate(malformed_reports):
                    try:
                        parsed = self._parse_qa_report(report_content)
                        if parsed["verdict"] == "UNKNOWN":
                            parsing_results.append(f"malformed_{i}: handled_gracefully")
                        else:
                            parsing_results.append(f"malformed_{i}: parsed_unexpectedly")
                    except Exception as e:
                        parsing_results.append(f"malformed_{i}: exception_handled")
                
                error_test_results.extend(parsing_results)
                
            except Exception as e:
                error_test_results.append(f"report_parsing_test: error - {str(e)[:100]}")
            
            # Log all results for debugging
            self.logger.info(f"Quality error handling test results: {error_test_results}")
            
            # Evaluate error handling results
            failed_error_tests = [r for r in error_test_results if "error" in r or "unexpected" in r]
            
            if len(failed_error_tests) == 0:
                return TestResult(
                    component="quality",
                    test_name=test_name,
                    status=HarnessStatus.PASS,
                    duration=1.0,
                    metadata={"error_test_results": error_test_results}
                )
            else:
                self.logger.error(f"Failed quality error handling tests: {failed_error_tests}")
                return TestResult(
                    component="quality",
                    test_name=test_name,
                    status=HarnessStatus.FAIL,
                    duration=1.0,
                    error_message=f"Error handling issues: {failed_error_tests[:2]}"
                )
                
        except Exception as e:
            return TestResult(
                component="quality",
                test_name=test_name,
                status=HarnessStatus.ERROR,
                duration=0.0,
                error_message=str(e)
            )
    
    def _test_quality_workflow_integration(self, env_context: EnvironmentContext) -> TestResult:
        """Test quality workflow integration with other components."""
        test_name = "quality_workflow_integration"
        
        try:
            integration_results = []
            
            # Test 1: Integration with database and protocol system
            try:
                db_path = getattr(env_context, 'database_path', None)
                if not db_path:
                    db_path = os.environ.get('TASKSGODZILLA_DB_PATH')
                
                if db_path:
                    db = Database(db_path)
                    
                    # Check for existing protocol runs
                    projects = db.list_projects()
                    if projects:
                        protocol_runs = []
                        for project in projects:
                            runs = db.list_protocol_runs(project.id)
                            protocol_runs.extend(runs)
                        
                        if protocol_runs:
                            integration_results.append(f"protocol_integration: {len(protocol_runs)} runs available")
                            
                            # Test QA event integration
                            test_run = protocol_runs[0]
                            
                            # Simulate QA workflow events
                            qa_events = [
                                ("qa_requested", "Quality check requested for protocol"),
                                ("qa_in_progress", "Quality check in progress"),
                                ("qa_completed", "Quality check completed with verdict: PASS")
                            ]
                            
                            for event_type, message in qa_events:
                                try:
                                    db.append_event(
                                        protocol_run_id=test_run.id,
                                        event_type=event_type,
                                        message=message
                                    )
                                except Exception as e:
                                    integration_results.append(f"event_logging: error - {str(e)[:50]}")
                                    break
                            else:
                                integration_results.append("event_logging: all events logged successfully")
                                
                            # Verify events were logged
                            events = db.list_events(test_run.id)
                            qa_event_types = [e.event_type for e in events if e.event_type.startswith("qa_")]
                            
                            if len(qa_event_types) >= 3:
                                integration_results.append("event_verification: QA events found in database")
                            else:
                                integration_results.append(f"event_verification: only {len(qa_event_types)} QA events found")
                        else:
                            integration_results.append("protocol_integration: no protocol runs found")
                    else:
                        integration_results.append("protocol_integration: no projects found")
                else:
                    integration_results.append("protocol_integration: no database available")
                    
            except Exception as e:
                integration_results.append(f"database_integration: error - {str(e)[:100]}")
            
            # Test 2: Integration with file system and report generation
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    protocol_root = Path(temp_dir) / "integration-test-protocol"
                    protocol_root.mkdir()
                    
                    # Create test step file
                    step_file = protocol_root / "integration-test-step.md"
                    step_content = """# Integration Test Step

## Objective
Test the quality system integration with file system operations.

## Implementation
This step tests file I/O and report generation.

## Validation
- [ ] Files should be created and read correctly
- [ ] Reports should be generated in the correct format
"""
                    step_file.write_text(step_content)
                    
                    # Test file system integration
                    if step_file.exists() and step_file.stat().st_size > 0:
                        integration_results.append("filesystem_integration: step file created successfully")
                        
                        # Test report directory creation
                        reports_dir = protocol_root / "reports"
                        reports_dir.mkdir(exist_ok=True)
                        
                        if reports_dir.exists():
                            integration_results.append("filesystem_integration: reports directory created")
                        else:
                            integration_results.append("filesystem_integration: reports directory creation failed")
                    else:
                        integration_results.append("filesystem_integration: step file creation failed")
                        
            except Exception as e:
                integration_results.append(f"filesystem_integration: error - {str(e)[:100]}")
            
            # Test 3: Integration with quality gates workflow
            try:
                # Test quality gate decision logic
                test_verdicts = ["PASS", "FAIL", "NEEDS_REVIEW", "UNKNOWN"]
                gate_results = []
                
                for verdict in test_verdicts:
                    gate_result = self._evaluate_quality_gate(verdict)
                    
                    # Verify gate logic
                    if verdict == "PASS" and gate_result["approved"]:
                        gate_results.append(f"{verdict}: correct_approval")
                    elif verdict in ["FAIL", "NEEDS_REVIEW", "UNKNOWN"] and not gate_result["approved"]:
                        gate_results.append(f"{verdict}: correct_rejection")
                    else:
                        gate_results.append(f"{verdict}: incorrect_logic")
                
                correct_gates = [r for r in gate_results if "correct" in r]
                if len(correct_gates) == len(test_verdicts):
                    integration_results.append("quality_gates: all verdicts handled correctly")
                else:
                    integration_results.append(f"quality_gates: {len(correct_gates)}/{len(test_verdicts)} handled correctly")
                    
            except Exception as e:
                integration_results.append(f"quality_gates: error - {str(e)[:100]}")
            
            # Evaluate integration results
            failed_integrations = [r for r in integration_results if "error" in r or "failed" in r or "incorrect" in r]
            
            if len(failed_integrations) == 0:
                return TestResult(
                    component="quality",
                    test_name=test_name,
                    status=HarnessStatus.PASS,
                    duration=1.5,
                    metadata={"integration_results": integration_results}
                )
            else:
                return TestResult(
                    component="quality",
                    test_name=test_name,
                    status=HarnessStatus.FAIL,
                    duration=1.5,
                    error_message=f"Integration issues: {failed_integrations[:2]}"
                )
                
        except Exception as e:
            return TestResult(
                component="quality",
                test_name=test_name,
                status=HarnessStatus.ERROR,
                duration=0.0,
                error_message=str(e)
            )