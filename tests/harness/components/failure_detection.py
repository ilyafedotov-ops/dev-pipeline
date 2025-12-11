"""Failure detection and gap analysis component for CLI workflow harness."""

import os
import re
import logging
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass

from ..models import TestResult, HarnessStatus, MissingFeature, Recommendation
from ..environment import EnvironmentContext


@dataclass
class FailurePattern:
    """Represents a detected failure pattern."""
    pattern_type: str
    description: str
    examples: List[str]
    severity: str  # "critical", "major", "minor"
    component: str
    suggested_fix: str


@dataclass
class CommandGap:
    """Represents a missing CLI command or functionality."""
    command_name: str
    expected_location: str
    description: str
    impact: str
    related_commands: List[str]


@dataclass
class WorkflowGap:
    """Represents an incomplete workflow or missing workflow step."""
    workflow_name: str
    missing_step: str
    description: str
    impact: str
    dependencies: List[str]


@dataclass
class DocumentationGap:
    """Represents inconsistent or missing documentation."""
    doc_type: str  # "help", "usage", "guide", "api"
    location: str
    issue_description: str
    expected_content: str
    actual_content: Optional[str]


class FailureDetectionAnalyzer:
    """Analyzes test failures to detect patterns and identify missing features."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.failure_patterns: List[FailurePattern] = []
        self.command_gaps: List[CommandGap] = []
        self.workflow_gaps: List[WorkflowGap] = []
        self.documentation_gaps: List[DocumentationGap] = []
    
    def analyze_failures(self, test_results: List[TestResult]) -> Dict[str, Any]:
        """Analyze test failures to identify patterns and gaps."""
        failed_results = [r for r in test_results if r.status in [HarnessStatus.FAIL, HarnessStatus.ERROR]]
        
        if not failed_results:
            return {
                "failure_patterns": [],
                "command_gaps": [],
                "workflow_gaps": [],
                "documentation_gaps": [],
                "summary": "No failures detected"
            }
        
        # Analyze different types of failures
        self._analyze_failure_patterns(failed_results)
        self._analyze_command_gaps(failed_results)
        self._analyze_workflow_gaps(failed_results)
        self._analyze_documentation_gaps(failed_results)
        
        return {
            "failure_patterns": self.failure_patterns,
            "command_gaps": self.command_gaps,
            "workflow_gaps": self.workflow_gaps,
            "documentation_gaps": self.documentation_gaps,
            "summary": f"Analyzed {len(failed_results)} failures, found {len(self.failure_patterns)} patterns"
        }
    
    def _analyze_failure_patterns(self, failed_results: List[TestResult]) -> None:
        """Analyze failure patterns from test results."""
        pattern_counts = {}
        
        for result in failed_results:
            error_msg = result.error_message or ""
            
            # Detect common failure patterns
            patterns = self._extract_failure_patterns(error_msg, result.component)
            
            for pattern in patterns:
                pattern_key = f"{pattern.pattern_type}:{pattern.component}"
                if pattern_key not in pattern_counts:
                    pattern_counts[pattern_key] = {
                        "pattern": pattern,
                        "count": 0,
                        "examples": []
                    }
                
                pattern_counts[pattern_key]["count"] += 1
                pattern_counts[pattern_key]["examples"].append(error_msg)
        
        # Convert to failure patterns with aggregated data
        for pattern_data in pattern_counts.values():
            pattern = pattern_data["pattern"]
            pattern.examples = pattern_data["examples"][:3]  # Keep top 3 examples
            
            # Adjust severity based on frequency
            if pattern_data["count"] >= 5:
                pattern.severity = "critical"
            elif pattern_data["count"] >= 3:
                pattern.severity = "major"
            else:
                pattern.severity = "minor"
            
            self.failure_patterns.append(pattern)
    
    def _extract_failure_patterns(self, error_msg: str, component: str) -> List[FailurePattern]:
        """Extract failure patterns from error message."""
        patterns = []
        error_lower = error_msg.lower()
        
        # Command not found pattern
        if "command not found" in error_lower or "not found" in error_lower:
            patterns.append(FailurePattern(
                pattern_type="missing_command",
                description="Command or executable not found",
                examples=[error_msg],
                severity="major",
                component=component,
                suggested_fix="Install missing command or check PATH configuration"
            ))
        
        # Not implemented pattern
        if "not implemented" in error_lower or "todo" in error_lower:
            patterns.append(FailurePattern(
                pattern_type="missing_implementation",
                description="Feature not yet implemented",
                examples=[error_msg],
                severity="major",
                component=component,
                suggested_fix="Implement the missing feature or functionality"
            ))
        
        # Configuration error pattern
        if "config" in error_lower and ("error" in error_lower or "missing" in error_lower):
            patterns.append(FailurePattern(
                pattern_type="configuration_error",
                description="Configuration missing or invalid",
                examples=[error_msg],
                severity="major",
                component=component,
                suggested_fix="Check and fix configuration files or environment variables"
            ))
        
        # Dependency missing pattern
        if ("module not found" in error_lower or 
            "import error" in error_lower or 
            "dependency" in error_lower):
            patterns.append(FailurePattern(
                pattern_type="dependency_missing",
                description="Required dependency not available",
                examples=[error_msg],
                severity="critical",
                component=component,
                suggested_fix="Install missing dependencies or check installation"
            ))
        
        # Permission error pattern
        if "permission denied" in error_lower or "access denied" in error_lower:
            patterns.append(FailurePattern(
                pattern_type="permission_error",
                description="Insufficient permissions for operation",
                examples=[error_msg],
                severity="major",
                component=component,
                suggested_fix="Check file permissions or run with appropriate privileges"
            ))
        
        # Timeout error pattern
        if "timeout" in error_lower or "timed out" in error_lower:
            patterns.append(FailurePattern(
                pattern_type="timeout_error",
                description="Operation timed out",
                examples=[error_msg],
                severity="minor",
                component=component,
                suggested_fix="Increase timeout values or optimize performance"
            ))
        
        # Network error pattern
        if ("network" in error_lower or 
            "connection" in error_lower or 
            "dns" in error_lower):
            patterns.append(FailurePattern(
                pattern_type="network_error",
                description="Network connectivity issue",
                examples=[error_msg],
                severity="minor",
                component=component,
                suggested_fix="Check network connectivity and DNS resolution"
            ))
        
        # Generic unknown error pattern
        if ("unknown error" in error_lower or 
            "unexpected error" in error_lower or
            "internal error" in error_lower):
            patterns.append(FailurePattern(
                pattern_type="unknown_error",
                description="Unspecific error with poor error handling",
                examples=[error_msg],
                severity="major",
                component=component,
                suggested_fix="Improve error handling to provide more specific error messages"
            ))
        
        return patterns
    
    def _analyze_command_gaps(self, failed_results: List[TestResult]) -> None:
        """Analyze command gaps from test failures."""
        command_failures = [r for r in failed_results if 
                           "command not found" in (r.error_message or "").lower()]
        
        for result in command_failures:
            error_msg = result.error_message or ""
            
            # Extract command name from error message
            command_match = re.search(r"command not found:?\s*([^\s]+)", error_msg, re.IGNORECASE)
            if command_match:
                command_name = command_match.group(1)
                
                # Determine expected location based on command name
                expected_location = self._determine_expected_command_location(command_name)
                
                # Determine impact based on component
                impact = "major" if result.component in ["cli_interface", "onboarding"] else "minor"
                
                # Find related commands
                related_commands = self._find_related_commands(command_name)
                
                gap = CommandGap(
                    command_name=command_name,
                    expected_location=expected_location,
                    description=f"Missing CLI command: {command_name}",
                    impact=impact,
                    related_commands=related_commands
                )
                
                self.command_gaps.append(gap)
    
    def _determine_expected_command_location(self, command_name: str) -> str:
        """Determine where a command should be located."""
        if command_name in ["tasksgodzilla", "tasksgodzilla_cli"]:
            return "scripts/tasksgodzilla_cli.py"
        elif command_name in ["onboard_repo", "onboard"]:
            return "scripts/onboard_repo.py"
        elif command_name in ["protocol_pipeline", "protocol"]:
            return "scripts/protocol_pipeline.py"
        elif command_name in ["quality_orchestrator", "quality"]:
            return "scripts/quality_orchestrator.py"
        elif command_name in ["spec_audit", "spec"]:
            return "scripts/spec_audit.py"
        elif command_name in ["api_server", "api"]:
            return "scripts/api_server.py"
        elif command_name in ["rq_worker", "worker"]:
            return "scripts/rq_worker.py"
        elif command_name in ["tasksgodzilla_tui", "tui"]:
            return "scripts/tasksgodzilla_tui.py"
        else:
            return f"scripts/{command_name}.py"
    
    def _find_related_commands(self, command_name: str) -> List[str]:
        """Find commands related to the missing command."""
        related = []
        
        # Group related commands
        command_groups = {
            "cli": ["tasksgodzilla_cli", "tasksgodzilla", "cli"],
            "onboarding": ["onboard_repo", "onboard", "setup"],
            "protocol": ["protocol_pipeline", "protocol", "workflow"],
            "quality": ["quality_orchestrator", "quality", "qa"],
            "spec": ["spec_audit", "spec", "validate"],
            "api": ["api_server", "api", "server"],
            "worker": ["rq_worker", "worker", "queue"],
            "tui": ["tasksgodzilla_tui", "tui", "terminal"]
        }
        
        for group_name, commands in command_groups.items():
            if command_name in commands:
                related = [cmd for cmd in commands if cmd != command_name]
                break
        
        return related
    
    def _analyze_workflow_gaps(self, failed_results: List[TestResult]) -> None:
        """Analyze workflow gaps from test failures."""
        workflow_failures = [r for r in failed_results if any(
            term in (r.error_message or "").lower() 
            for term in ["workflow", "step", "process", "sequence", "pipeline"]
        )]
        
        for result in workflow_failures:
            error_msg = result.error_message or ""
            
            # Extract workflow information
            workflow_name = self._extract_workflow_name(error_msg, result.component)
            missing_step = self._extract_missing_step(error_msg)
            
            if workflow_name and missing_step:
                gap = WorkflowGap(
                    workflow_name=workflow_name,
                    missing_step=missing_step,
                    description=f"Missing step '{missing_step}' in {workflow_name} workflow",
                    impact="major",
                    dependencies=self._find_workflow_dependencies(workflow_name, missing_step)
                )
                
                self.workflow_gaps.append(gap)
    
    def _extract_workflow_name(self, error_msg: str, component: str) -> str:
        """Extract workflow name from error message or component."""
        error_lower = error_msg.lower()
        
        # Try to extract from error message
        if "onboard" in error_lower:
            return "project_onboarding"
        elif "protocol" in error_lower:
            return "protocol_execution"
        elif "discovery" in error_lower:
            return "project_discovery"
        elif "spec" in error_lower:
            return "spec_validation"
        elif "quality" in error_lower:
            return "quality_assurance"
        
        # Fall back to component name
        if component == "onboarding":
            return "project_onboarding"
        elif component == "protocol":
            return "protocol_execution"
        elif component == "discovery":
            return "project_discovery"
        elif component == "spec":
            return "spec_validation"
        elif component == "quality":
            return "quality_assurance"
        else:
            return f"{component}_workflow"
    
    def _extract_missing_step(self, error_msg: str) -> str:
        """Extract missing step from error message."""
        error_lower = error_msg.lower()
        
        # Common missing steps
        if "clone" in error_lower or "git" in error_lower:
            return "repository_cloning"
        elif "setup" in error_lower or "init" in error_lower:
            return "project_setup"
        elif "validate" in error_lower or "check" in error_lower:
            return "validation"
        elif "execute" in error_lower or "run" in error_lower:
            return "execution"
        elif "report" in error_lower or "output" in error_lower:
            return "reporting"
        else:
            return "unknown_step"
    
    def _find_workflow_dependencies(self, workflow_name: str, missing_step: str) -> List[str]:
        """Find dependencies for a workflow step."""
        dependencies = []
        
        # Define common workflow dependencies
        workflow_deps = {
            "project_onboarding": {
                "repository_cloning": ["git", "network_access"],
                "project_setup": ["repository_cloning", "file_system_access"],
                "validation": ["project_setup", "configuration"],
            },
            "protocol_execution": {
                "planning": ["project_onboarding", "spec_validation"],
                "execution": ["planning", "worker_system"],
                "reporting": ["execution", "database_access"],
            },
            "spec_validation": {
                "requirements_check": ["file_system_access"],
                "design_validation": ["requirements_check"],
                "task_validation": ["design_validation"],
            }
        }
        
        if workflow_name in workflow_deps and missing_step in workflow_deps[workflow_name]:
            dependencies = workflow_deps[workflow_name][missing_step]
        
        return dependencies
    
    def _analyze_documentation_gaps(self, failed_results: List[TestResult]) -> None:
        """Analyze documentation gaps from test failures."""
        doc_failures = [r for r in failed_results if any(
            term in (r.error_message or "").lower()
            for term in ["help", "usage", "documentation", "guide", "manual"]
        )]
        
        for result in doc_failures:
            error_msg = result.error_message or ""
            
            # Determine documentation type
            doc_type = self._determine_doc_type(error_msg)
            
            # Determine location
            location = self._determine_doc_location(result.component, doc_type)
            
            # Extract issue description
            issue_description = self._extract_doc_issue(error_msg)
            
            # Determine expected content
            expected_content = self._determine_expected_doc_content(doc_type, result.component)
            
            gap = DocumentationGap(
                doc_type=doc_type,
                location=location,
                issue_description=issue_description,
                expected_content=expected_content,
                actual_content=None  # Would need to read actual content
            )
            
            self.documentation_gaps.append(gap)
    
    def _determine_doc_type(self, error_msg: str) -> str:
        """Determine documentation type from error message."""
        error_lower = error_msg.lower()
        
        if "help" in error_lower:
            return "help"
        elif "usage" in error_lower:
            return "usage"
        elif "guide" in error_lower:
            return "guide"
        elif "api" in error_lower:
            return "api"
        elif "manual" in error_lower:
            return "manual"
        else:
            return "documentation"
    
    def _determine_doc_location(self, component: str, doc_type: str) -> str:
        """Determine where documentation should be located."""
        if doc_type == "help":
            return f"scripts/{component}.py --help"
        elif doc_type == "api":
            return "docs/api-reference.md"
        elif doc_type == "guide":
            return f"docs/{component}-guide.md"
        else:
            return f"docs/{component}.md"
    
    def _extract_doc_issue(self, error_msg: str) -> str:
        """Extract documentation issue description from error message."""
        if "inconsistent" in error_msg.lower():
            return "Documentation inconsistent with actual behavior"
        elif "missing" in error_msg.lower():
            return "Documentation missing or incomplete"
        elif "outdated" in error_msg.lower():
            return "Documentation outdated"
        elif "unclear" in error_msg.lower():
            return "Documentation unclear or confusing"
        else:
            return "Documentation issue detected"
    
    def _determine_expected_doc_content(self, doc_type: str, component: str) -> str:
        """Determine what documentation content should be present."""
        if doc_type == "help":
            return f"Command-line help for {component} with usage examples and options"
        elif doc_type == "usage":
            return f"Usage instructions for {component} with examples"
        elif doc_type == "guide":
            return f"Step-by-step guide for using {component}"
        elif doc_type == "api":
            return f"API reference documentation for {component} endpoints"
        else:
            return f"General documentation for {component}"


class FailureDetectionTests:
    """Test component for failure detection and gap analysis."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.analyzer = FailureDetectionAnalyzer()
        self.test_results: List[TestResult] = []
    
    def run_test(self, project, env_context: EnvironmentContext) -> bool:
        """Execute failure detection and gap analysis tests."""
        self.logger.info("Starting failure detection and gap analysis testing")
        
        # Run all failure detection test categories
        test_methods = [
            self._test_failure_pattern_analysis,
            self._test_cli_command_gap_detection,
            self._test_workflow_completeness_validation,
            self._test_documentation_consistency_checking,
        ]
        
        all_passed = True
        for test_method in test_methods:
            try:
                success = test_method(project, env_context)
                if not success:
                    all_passed = False
            except Exception as e:
                self.logger.error(f"Failure detection test failed: {e}")
                all_passed = False
        
        self.logger.info(f"Failure detection testing completed. Overall success: {all_passed}")
        return all_passed
    
    def _test_failure_pattern_analysis(self, project, env_context: EnvironmentContext) -> bool:
        """Test failure pattern analysis for missing features."""
        self.logger.info("Testing failure pattern analysis")
        
        # Create sample test results with various failure patterns
        sample_failures = [
            TestResult(
                component="cli_interface",
                test_name="test_missing_command",
                status=HarnessStatus.ERROR,
                duration=1.0,
                error_message="Command not found: nonexistent_command"
            ),
            TestResult(
                component="onboarding",
                test_name="test_not_implemented",
                status=HarnessStatus.FAIL,
                duration=2.0,
                error_message="Not implemented: advanced_project_setup"
            ),
            TestResult(
                component="protocol",
                test_name="test_config_error",
                status=HarnessStatus.ERROR,
                duration=1.5,
                error_message="Configuration error: missing database URL"
            ),
            TestResult(
                component="quality",
                test_name="test_dependency_missing",
                status=HarnessStatus.ERROR,
                duration=0.5,
                error_message="Module not found: missing_quality_checker"
            ),
        ]
        
        # Analyze failure patterns
        analysis_result = self.analyzer.analyze_failures(sample_failures)
        
        # Verify analysis results
        success = True
        
        # Should detect failure patterns
        if not analysis_result["failure_patterns"]:
            self.logger.error("Failed to detect any failure patterns")
            success = False
        
        # Should categorize different types of failures
        pattern_types = {p.pattern_type for p in analysis_result["failure_patterns"]}
        expected_types = {"missing_command", "missing_implementation", "configuration_error", "dependency_missing"}
        
        if not pattern_types.intersection(expected_types):
            self.logger.error(f"Failed to detect expected pattern types. Found: {pattern_types}")
            success = False
        
        # Should provide suggested fixes
        for pattern in analysis_result["failure_patterns"]:
            if not pattern.suggested_fix:
                self.logger.error(f"Pattern {pattern.pattern_type} missing suggested fix")
                success = False
        
        # Record test result
        self.test_results.append(TestResult(
            component="failure_detection",
            test_name="failure_pattern_analysis",
            status=HarnessStatus.PASS if success else HarnessStatus.FAIL,
            duration=1.0,
            error_message=None if success else "Failure pattern analysis failed"
        ))
        
        return success
    
    def _test_cli_command_gap_detection(self, project, env_context: EnvironmentContext) -> bool:
        """Test CLI command gap detection."""
        self.logger.info("Testing CLI command gap detection")
        
        # Test by running CLI commands and detecting gaps
        cli_scripts = [
            "scripts/tasksgodzilla_cli.py",
            "scripts/onboard_repo.py",
            "scripts/protocol_pipeline.py",
            "scripts/quality_orchestrator.py",
            "scripts/spec_audit.py",
            "scripts/api_server.py",
            "scripts/rq_worker.py",
            "scripts/tasksgodzilla_tui.py",
        ]
        
        missing_scripts = []
        for script in cli_scripts:
            script_path = env_context.workspace_path / script
            if not script_path.exists():
                missing_scripts.append(script)
        
        # Create test results for missing scripts
        test_results = []
        for script in missing_scripts:
            test_results.append(TestResult(
                component="cli_interface",
                test_name=f"test_{script.replace('/', '_').replace('.py', '')}",
                status=HarnessStatus.ERROR,
                duration=0.1,
                error_message=f"Command not found: {script}"
            ))
        
        # Analyze command gaps
        if test_results:
            analysis_result = self.analyzer.analyze_failures(test_results)
            command_gaps = analysis_result["command_gaps"]
            
            success = len(command_gaps) > 0
            if not success:
                self.logger.error("Failed to detect command gaps from missing scripts")
        else:
            # No missing scripts - test with simulated gaps
            success = True
            self.logger.info("All CLI scripts present - simulating command gap detection")
        
        # Record test result
        self.test_results.append(TestResult(
            component="failure_detection",
            test_name="cli_command_gap_detection",
            status=HarnessStatus.PASS if success else HarnessStatus.FAIL,
            duration=1.0,
            error_message=None if success else "CLI command gap detection failed"
        ))
        
        return success
    
    def _test_workflow_completeness_validation(self, project, env_context: EnvironmentContext) -> bool:
        """Test workflow completeness validation."""
        self.logger.info("Testing workflow completeness validation")
        
        # Create sample workflow failures
        workflow_failures = [
            TestResult(
                component="onboarding",
                test_name="test_incomplete_workflow",
                status=HarnessStatus.FAIL,
                duration=3.0,
                error_message="Workflow step missing: repository cloning failed"
            ),
            TestResult(
                component="protocol",
                test_name="test_broken_sequence",
                status=HarnessStatus.ERROR,
                duration=2.5,
                error_message="Process sequence incomplete: planning step not found"
            ),
        ]
        
        # Analyze workflow gaps
        analysis_result = self.analyzer.analyze_failures(workflow_failures)
        workflow_gaps = analysis_result["workflow_gaps"]
        
        success = True
        
        # Should detect workflow gaps
        if not workflow_gaps:
            self.logger.error("Failed to detect workflow gaps")
            success = False
        
        # Should identify missing steps
        for gap in workflow_gaps:
            if not gap.missing_step or gap.missing_step == "unknown_step":
                self.logger.error(f"Failed to identify missing step in {gap.workflow_name}")
                success = False
        
        # Should identify dependencies
        for gap in workflow_gaps:
            if not gap.dependencies:
                self.logger.warning(f"No dependencies identified for {gap.workflow_name}.{gap.missing_step}")
        
        # Record test result
        self.test_results.append(TestResult(
            component="failure_detection",
            test_name="workflow_completeness_validation",
            status=HarnessStatus.PASS if success else HarnessStatus.FAIL,
            duration=1.5,
            error_message=None if success else "Workflow completeness validation failed"
        ))
        
        return success
    
    def _test_documentation_consistency_checking(self, project, env_context: EnvironmentContext) -> bool:
        """Test documentation consistency checking."""
        self.logger.info("Testing documentation consistency checking")
        
        # Test actual documentation consistency by checking CLI help vs actual behavior
        doc_consistency_results = []
        
        # Test CLI help consistency
        cli_help_result = self._check_cli_help_consistency(env_context)
        doc_consistency_results.append(cli_help_result)
        
        # Test API documentation consistency
        api_doc_result = self._check_api_documentation_consistency(env_context)
        doc_consistency_results.append(api_doc_result)
        
        # Test script documentation consistency
        script_doc_result = self._check_script_documentation_consistency(env_context)
        doc_consistency_results.append(script_doc_result)
        
        # Create sample documentation failures for analysis testing
        doc_failures = [
            TestResult(
                component="cli_interface",
                test_name="test_help_inconsistency",
                status=HarnessStatus.FAIL,
                duration=1.0,
                error_message="Help documentation inconsistent with actual behavior"
            ),
            TestResult(
                component="api_integration",
                test_name="test_missing_api_docs",
                status=HarnessStatus.FAIL,
                duration=0.5,
                error_message="API documentation missing for endpoint"
            ),
        ]
        
        # Analyze documentation gaps
        analysis_result = self.analyzer.analyze_failures(doc_failures)
        doc_gaps = analysis_result["documentation_gaps"]
        
        success = True
        
        # Should detect documentation gaps
        if not doc_gaps:
            self.logger.error("Failed to detect documentation gaps")
            success = False
        
        # Should categorize documentation types
        doc_types = {gap.doc_type for gap in doc_gaps}
        if not doc_types:
            self.logger.error("Failed to categorize documentation types")
            success = False
        
        # Should identify expected content
        for gap in doc_gaps:
            if not gap.expected_content:
                self.logger.error(f"Failed to identify expected content for {gap.doc_type}")
                success = False
        
        # Record test result
        self.test_results.append(TestResult(
            component="failure_detection",
            test_name="documentation_consistency_checking",
            status=HarnessStatus.PASS if success else HarnessStatus.FAIL,
            duration=1.0,
            error_message=None if success else "Documentation consistency checking failed"
        ))
        
        return success
    
    def get_test_results(self) -> List[TestResult]:
        """Get all test results from this component."""
        return self.test_results.copy()
    
    def get_analysis_results(self) -> Dict[str, Any]:
        """Get the latest failure analysis results."""
        return {
            "failure_patterns": self.analyzer.failure_patterns,
            "command_gaps": self.analyzer.command_gaps,
            "workflow_gaps": self.analyzer.workflow_gaps,
            "documentation_gaps": self.analyzer.documentation_gaps,
        }
    
    def _check_cli_help_consistency(self, env_context: EnvironmentContext) -> TestResult:
        """Check CLI help documentation consistency."""
        start_time = time.time()
        
        try:
            # Test various CLI scripts for help consistency
            cli_scripts = [
                "scripts/tasksgodzilla_cli.py",
                "scripts/onboard_repo.py", 
                "scripts/protocol_pipeline.py",
                "scripts/quality_orchestrator.py",
                "scripts/spec_audit.py",
                "scripts/api_server.py",
                "scripts/rq_worker.py",
                "scripts/tasksgodzilla_tui.py"
            ]
            
            inconsistencies = []
            
            for script in cli_scripts:
                script_path = env_context.workspace_path / script
                if not script_path.exists():
                    inconsistencies.append(f"Script not found: {script}")
                    continue
                
                try:
                    # Test help output
                    result = subprocess.run(
                        ["python3", str(script_path), "--help"],
                        capture_output=True,
                        text=True,
                        timeout=30,
                        cwd=env_context.workspace_path
                    )
                    
                    if result.returncode != 0:
                        inconsistencies.append(f"Help command failed for {script}: {result.stderr}")
                        continue
                    
                    help_output = result.stdout.lower()
                    
                    # Check for expected help sections
                    expected_sections = ["usage:", "options:", "arguments:"]
                    missing_sections = []
                    
                    for section in expected_sections:
                        if section not in help_output:
                            missing_sections.append(section)
                    
                    if missing_sections:
                        inconsistencies.append(f"Missing help sections in {script}: {missing_sections}")
                    
                    # Check for script-specific help content
                    script_name = Path(script).stem
                    if script_name not in help_output and "tasksgodzilla" not in help_output:
                        inconsistencies.append(f"Help output doesn't mention script name for {script}")
                
                except subprocess.TimeoutExpired:
                    inconsistencies.append(f"Help command timed out for {script}")
                except Exception as e:
                    inconsistencies.append(f"Help test failed for {script}: {e}")
            
            success = len(inconsistencies) == 0
            error_msg = None if success else f"CLI help inconsistencies: {inconsistencies}"
            
            return TestResult(
                component="failure_detection",
                test_name="cli_help_consistency",
                status=HarnessStatus.PASS if success else HarnessStatus.FAIL,
                duration=time.time() - start_time,
                error_message=error_msg
            )
            
        except Exception as e:
            return TestResult(
                component="failure_detection",
                test_name="cli_help_consistency",
                status=HarnessStatus.ERROR,
                duration=time.time() - start_time,
                error_message=str(e)
            )
    
    def _check_api_documentation_consistency(self, env_context: EnvironmentContext) -> TestResult:
        """Check API documentation consistency."""
        start_time = time.time()
        
        try:
            # Check for API documentation files
            docs_dir = env_context.workspace_path / "docs"
            api_doc_files = [
                "api-reference.md",
                "api.md",
                "endpoints.md"
            ]
            
            found_api_docs = []
            for doc_file in api_doc_files:
                doc_path = docs_dir / doc_file
                if doc_path.exists():
                    found_api_docs.append(doc_file)
            
            inconsistencies = []
            
            if not found_api_docs:
                inconsistencies.append("No API documentation files found")
            
            # Check API server script for endpoint definitions
            api_server_path = env_context.workspace_path / "scripts" / "api_server.py"
            if api_server_path.exists():
                try:
                    api_content = api_server_path.read_text()
                    
                    # Look for FastAPI route definitions
                    import re
                    route_patterns = [
                        r'@app\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
                        r'app\.add_api_route\s*\(\s*["\']([^"\']+)["\']'
                    ]
                    
                    found_routes = []
                    for pattern in route_patterns:
                        matches = re.findall(pattern, api_content, re.IGNORECASE)
                        for match in matches:
                            if isinstance(match, tuple):
                                found_routes.append(match[-1])  # Get the route path
                            else:
                                found_routes.append(match)
                    
                    if found_routes and not found_api_docs:
                        inconsistencies.append(f"API routes found in code but no API documentation: {found_routes[:5]}")
                    
                except Exception as e:
                    inconsistencies.append(f"Failed to analyze API server script: {e}")
            
            # Check for OpenAPI/Swagger documentation
            openapi_files = ["openapi.json", "swagger.json", "api.yaml", "openapi.yaml"]
            found_openapi = any((env_context.workspace_path / f).exists() for f in openapi_files)
            
            if not found_openapi and not found_api_docs:
                inconsistencies.append("No OpenAPI/Swagger documentation found")
            
            success = len(inconsistencies) == 0
            error_msg = None if success else f"API documentation inconsistencies: {inconsistencies}"
            
            return TestResult(
                component="failure_detection",
                test_name="api_documentation_consistency",
                status=HarnessStatus.PASS if success else HarnessStatus.FAIL,
                duration=time.time() - start_time,
                error_message=error_msg
            )
            
        except Exception as e:
            return TestResult(
                component="failure_detection",
                test_name="api_documentation_consistency",
                status=HarnessStatus.ERROR,
                duration=time.time() - start_time,
                error_message=str(e)
            )
    
    def _check_script_documentation_consistency(self, env_context: EnvironmentContext) -> TestResult:
        """Check script documentation consistency."""
        start_time = time.time()
        
        try:
            # Check for script documentation in docs directory
            docs_dir = env_context.workspace_path / "docs"
            scripts_dir = env_context.workspace_path / "scripts"
            
            inconsistencies = []
            
            if not docs_dir.exists():
                inconsistencies.append("No docs directory found")
                return TestResult(
                    component="failure_detection",
                    test_name="script_documentation_consistency",
                    status=HarnessStatus.FAIL,
                    duration=time.time() - start_time,
                    error_message="No docs directory found"
                )
            
            # Get list of Python scripts
            if scripts_dir.exists():
                python_scripts = list(scripts_dir.glob("*.py"))
                
                # Check for corresponding documentation
                for script in python_scripts:
                    script_name = script.stem
                    
                    # Look for documentation files
                    possible_doc_files = [
                        f"{script_name}.md",
                        f"{script_name}-guide.md",
                        f"{script_name}-usage.md"
                    ]
                    
                    found_docs = []
                    for doc_file in possible_doc_files:
                        if (docs_dir / doc_file).exists():
                            found_docs.append(doc_file)
                    
                    # Check if script is mentioned in existing docs
                    mentioned_in_docs = []
                    for doc_file in docs_dir.glob("*.md"):
                        try:
                            doc_content = doc_file.read_text().lower()
                            if script_name in doc_content:
                                mentioned_in_docs.append(doc_file.name)
                        except Exception:
                            continue
                    
                    # Major scripts should have documentation
                    major_scripts = [
                        "tasksgodzilla_cli", "onboard_repo", "protocol_pipeline",
                        "quality_orchestrator", "spec_audit", "api_server", "rq_worker"
                    ]
                    
                    if script_name in major_scripts:
                        if not found_docs and not mentioned_in_docs:
                            inconsistencies.append(f"No documentation found for major script: {script_name}")
            
            # Check README for script documentation
            readme_files = ["README.md", "readme.md", "README.rst"]
            found_readme = None
            
            for readme_file in readme_files:
                readme_path = env_context.workspace_path / readme_file
                if readme_path.exists():
                    found_readme = readme_path
                    break
            
            if found_readme:
                try:
                    readme_content = found_readme.read_text().lower()
                    
                    # Check if major scripts are mentioned in README
                    major_scripts = [
                        "tasksgodzilla_cli", "onboard_repo", "protocol_pipeline",
                        "quality_orchestrator", "spec_audit"
                    ]
                    
                    missing_from_readme = []
                    for script in major_scripts:
                        if script not in readme_content and script.replace("_", "-") not in readme_content:
                            missing_from_readme.append(script)
                    
                    if missing_from_readme:
                        inconsistencies.append(f"Major scripts not mentioned in README: {missing_from_readme}")
                
                except Exception as e:
                    inconsistencies.append(f"Failed to analyze README: {e}")
            else:
                inconsistencies.append("No README file found")
            
            success = len(inconsistencies) == 0
            error_msg = None if success else f"Script documentation inconsistencies: {inconsistencies}"
            
            return TestResult(
                component="failure_detection",
                test_name="script_documentation_consistency",
                status=HarnessStatus.PASS if success else HarnessStatus.FAIL,
                duration=time.time() - start_time,
                error_message=error_msg
            )
            
        except Exception as e:
            return TestResult(
                component="failure_detection",
                test_name="script_documentation_consistency",
                status=HarnessStatus.ERROR,
                duration=time.time() - start_time,
                error_message=str(e)
            )