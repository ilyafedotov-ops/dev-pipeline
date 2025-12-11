"""Test reporting and analysis for CLI workflow harness."""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple
from collections import defaultdict, Counter

from .models import (
    TestResult, WorkflowResult, HarnessReport, MissingFeature, 
    Recommendation, PerformanceMetrics, HarnessStatus
)
from .components.failure_detection import FailureDetectionAnalyzer


class TestReporter:
    """Generates comprehensive reports and recommendations."""
    
    def __init__(self, output_path: Path):
        self.output_path = output_path
        self.output_path.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self.failure_analyzer = FailureDetectionAnalyzer()
        
        # Failure pattern matchers for categorization
        self.failure_patterns = {
            'missing_command': [
                r'command not found',
                r'no such file or directory',
                r'executable not found',
                r'script.*not found',
            ],
            'missing_implementation': [
                r'not implemented',
                r'todo.*implement',
                r'placeholder.*implementation',
                r'method.*not.*implemented',
            ],
            'configuration_error': [
                r'configuration.*error',
                r'missing.*environment.*variable',
                r'invalid.*config',
                r'connection.*refused',
                r'database.*error',
            ],
            'dependency_missing': [
                r'module.*not.*found',
                r'import.*error',
                r'no module named',
                r'package.*not.*installed',
            ],
            'permission_error': [
                r'permission.*denied',
                r'access.*denied',
                r'unauthorized',
                r'forbidden',
            ],
            'timeout_error': [
                r'timeout',
                r'timed.*out',
                r'operation.*timeout',
            ],
            'network_error': [
                r'network.*error',
                r'connection.*error',
                r'dns.*resolution',
                r'host.*unreachable',
            ],
        }
    
    def generate_report(self, 
                       execution_id: str,
                       mode: str,
                       test_results: List[TestResult],
                       workflow_results: List[WorkflowResult],
                       performance_metrics: PerformanceMetrics,
                       start_time: datetime,
                       end_time: datetime) -> HarnessReport:
        """Generate comprehensive test report."""
        
        missing_features = self.identify_missing_features(test_results)
        recommendations = self.generate_recommendations(test_results, missing_features)
        
        report = HarnessReport(
            execution_id=execution_id,
            mode=mode,
            start_time=start_time,
            end_time=end_time,
            test_results=test_results,
            workflow_results=workflow_results,
            missing_features=missing_features,
            recommendations=recommendations,
            performance_metrics=performance_metrics,
            environment_info=self._collect_environment_info(),
        )
        
        self._save_report(report)
        return report
    
    def categorize_failures(self, test_results: List[TestResult]) -> Dict[str, List[TestResult]]:
        """Categorize test failures by type for better analysis."""
        categorized_failures = defaultdict(list)
        
        for result in test_results:
            if result.status in [HarnessStatus.FAIL, HarnessStatus.ERROR]:
                category = self._classify_failure(result)
                categorized_failures[category].append(result)
        
        return dict(categorized_failures)
    
    def _classify_failure(self, result: TestResult) -> str:
        """Classify a single test failure based on error message patterns."""
        if not result.error_message:
            return 'unknown_failure'
        
        error_msg = result.error_message.lower()
        
        for category, patterns in self.failure_patterns.items():
            for pattern in patterns:
                if re.search(pattern, error_msg, re.IGNORECASE):
                    return category
        
        return 'unknown_failure'
    
    def identify_missing_features(self, test_results: List[TestResult]) -> List[MissingFeature]:
        """Analyze failures to identify missing functionality with enhanced pattern detection."""
        # Use the failure detection analyzer for comprehensive analysis
        analysis_result = self.failure_analyzer.analyze_failures(test_results)
        
        missing_features = []
        
        # Convert failure patterns to missing features
        for pattern in analysis_result["failure_patterns"]:
            missing_features.append(MissingFeature(
                feature_name=pattern.pattern_type.replace("_", " ").title(),
                component=pattern.component,
                description=pattern.description,
                impact=pattern.severity,
                related_tests=[]  # Pattern examples are stored differently
            ))
        
        # Convert command gaps to missing features
        for gap in analysis_result["command_gaps"]:
            missing_features.append(MissingFeature(
                feature_name=f"CLI Command: {gap.command_name}",
                component="cli_interface",
                description=gap.description,
                impact=gap.impact,
                related_tests=[]
            ))
        
        # Convert workflow gaps to missing features
        for gap in analysis_result["workflow_gaps"]:
            missing_features.append(MissingFeature(
                feature_name=f"Workflow Step: {gap.missing_step}",
                component=gap.workflow_name,
                description=gap.description,
                impact=gap.impact,
                related_tests=[]
            ))
        
        # Convert documentation gaps to missing features
        for gap in analysis_result["documentation_gaps"]:
            missing_features.append(MissingFeature(
                feature_name=f"Documentation: {gap.doc_type}",
                component=gap.location,
                description=gap.issue_description,
                impact="minor",  # Documentation gaps are typically minor
                related_tests=[]
            ))
        
        # Also run the original analysis for backward compatibility
        original_features = self._identify_missing_features_original(test_results)
        missing_features.extend(original_features)
        
        # Remove duplicates and sort by impact
        unique_features = self._deduplicate_features(missing_features)
        return sorted(unique_features, key=lambda f: self._impact_priority(f.impact))
    
    def _identify_missing_features_original(self, test_results: List[TestResult]) -> List[MissingFeature]:
        """Original missing features analysis for backward compatibility."""
        missing_features = []
        
        # Categorize failures for better analysis
        categorized_failures = self.categorize_failures(test_results)
        
        # Group failures by component
        failures_by_component = defaultdict(list)
        for result in test_results:
            if result.status in [HarnessStatus.FAIL, HarnessStatus.ERROR]:
                failures_by_component[result.component].append(result)
        
        # Analyze failure patterns by component
        for component, failures in failures_by_component.items():
            component_features = self._analyze_component_failures(component, failures, categorized_failures)
            missing_features.extend(component_features)
        
        # Analyze cross-component patterns
        cross_component_features = self._analyze_cross_component_patterns(categorized_failures)
        missing_features.extend(cross_component_features)
        
        return missing_features
    
    def _analyze_component_failures(self, component: str, failures: List[TestResult], 
                                  categorized_failures: Dict[str, List[TestResult]]) -> List[MissingFeature]:
        """Analyze failures within a single component."""
        features = []
        
        # Multiple failures suggest systemic issues
        if len(failures) > 2:
            features.append(MissingFeature(
                feature_name=f"{component}_core_functionality",
                component=component,
                description=f"Multiple test failures ({len(failures)}) in {component} suggest missing core functionality",
                impact="major",
                related_tests=[f.test_name for f in failures],
            ))
        
        # Analyze specific failure types
        component_failures_by_type = defaultdict(list)
        for failure in failures:
            failure_type = self._classify_failure(failure)
            component_failures_by_type[failure_type].append(failure)
        
        for failure_type, type_failures in component_failures_by_type.items():
            if failure_type == 'missing_command':
                features.append(MissingFeature(
                    feature_name=f"{component}_cli_commands",
                    component=component,
                    description=f"CLI commands not implemented for {component}",
                    impact="critical",
                    related_tests=[f.test_name for f in type_failures],
                ))
            elif failure_type == 'missing_implementation':
                features.append(MissingFeature(
                    feature_name=f"{component}_implementation",
                    component=component,
                    description=f"Core implementation missing for {component}",
                    impact="major",
                    related_tests=[f.test_name for f in type_failures],
                ))
            elif failure_type == 'configuration_error':
                features.append(MissingFeature(
                    feature_name=f"{component}_configuration",
                    component=component,
                    description=f"Configuration setup missing for {component}",
                    impact="major",
                    related_tests=[f.test_name for f in type_failures],
                ))
            elif failure_type == 'dependency_missing':
                features.append(MissingFeature(
                    feature_name=f"{component}_dependencies",
                    component=component,
                    description=f"Required dependencies missing for {component}",
                    impact="major",
                    related_tests=[f.test_name for f in type_failures],
                ))
        
        return features
    
    def _analyze_cross_component_patterns(self, categorized_failures: Dict[str, List[TestResult]]) -> List[MissingFeature]:
        """Analyze patterns that affect multiple components."""
        features = []
        
        # Check for system-wide issues
        if 'configuration_error' in categorized_failures and len(categorized_failures['configuration_error']) > 2:
            affected_components = list(set(f.component for f in categorized_failures['configuration_error']))
            features.append(MissingFeature(
                feature_name="system_configuration",
                component="system",
                description=f"System-wide configuration issues affecting {len(affected_components)} components",
                impact="critical",
                related_tests=[f.test_name for f in categorized_failures['configuration_error']],
            ))
        
        if 'dependency_missing' in categorized_failures and len(categorized_failures['dependency_missing']) > 1:
            affected_components = list(set(f.component for f in categorized_failures['dependency_missing']))
            features.append(MissingFeature(
                feature_name="system_dependencies",
                component="system",
                description=f"Missing system dependencies affecting {len(affected_components)} components",
                impact="major",
                related_tests=[f.test_name for f in categorized_failures['dependency_missing']],
            ))
        
        return features
    
    def _deduplicate_features(self, features: List[MissingFeature]) -> List[MissingFeature]:
        """Remove duplicate missing features based on feature name and component."""
        seen = set()
        unique_features = []
        
        for feature in features:
            key = (feature.feature_name, feature.component)
            if key not in seen:
                seen.add(key)
                unique_features.append(feature)
        
        return unique_features
    
    def _impact_priority(self, impact: str) -> int:
        """Convert impact string to priority number for sorting."""
        priority_map = {"critical": 1, "major": 2, "minor": 3}
        return priority_map.get(impact, 4)
    
    def generate_recommendations(self, 
                               test_results: List[TestResult], 
                               missing_features: List[MissingFeature]) -> List[Recommendation]:
        """Generate prioritized recommendations for fixes with enhanced analysis."""
        recommendations = []
        
        # Analyze test results for patterns
        categorized_failures = self.categorize_failures(test_results)
        performance_issues = self._identify_performance_issues(test_results)
        
        # Generate recommendations based on missing features
        for feature in missing_features:
            rec = self._create_feature_recommendation(feature)
            if rec:
                recommendations.append(rec)
        
        # Generate recommendations based on failure patterns
        for category, failures in categorized_failures.items():
            rec = self._create_pattern_recommendation(category, failures)
            if rec:
                recommendations.append(rec)
        
        # Generate performance recommendations
        for perf_issue in performance_issues:
            recommendations.append(perf_issue)
        
        # Generate workflow recommendations
        workflow_recs = self._generate_workflow_recommendations(test_results)
        recommendations.extend(workflow_recs)
        
        # Deduplicate and prioritize
        unique_recommendations = self._deduplicate_recommendations(recommendations)
        return sorted(unique_recommendations, key=lambda r: (r.priority, r.category))
    
    def _create_feature_recommendation(self, feature: MissingFeature) -> Recommendation:
        """Create recommendation for a missing feature."""
        if feature.impact == "critical":
            return Recommendation(
                priority=1,
                category="implement",
                description=f"CRITICAL: Implement {feature.feature_name} in {feature.component} - {feature.description}",
                estimated_effort="high",
                related_components=[feature.component],
            )
        elif feature.impact == "major":
            return Recommendation(
                priority=2,
                category="fix",
                description=f"Fix {feature.feature_name} in {feature.component} - {feature.description}",
                estimated_effort="medium",
                related_components=[feature.component],
            )
        elif feature.impact == "minor":
            return Recommendation(
                priority=3,
                category="improve",
                description=f"Improve {feature.feature_name} in {feature.component} - {feature.description}",
                estimated_effort="low",
                related_components=[feature.component],
            )
        return None
    
    def _create_pattern_recommendation(self, category: str, failures: List[TestResult]) -> Recommendation:
        """Create recommendation based on failure pattern."""
        if not failures:
            return None
        
        affected_components = list(set(f.component for f in failures))
        
        if category == 'missing_command':
            return Recommendation(
                priority=1,
                category="implement",
                description=f"Implement missing CLI commands affecting {len(affected_components)} components",
                estimated_effort="high",
                related_components=affected_components,
            )
        elif category == 'configuration_error':
            return Recommendation(
                priority=1,
                category="fix",
                description=f"Fix configuration issues affecting {len(affected_components)} components",
                estimated_effort="medium",
                related_components=affected_components,
            )
        elif category == 'dependency_missing':
            return Recommendation(
                priority=2,
                category="fix",
                description=f"Install missing dependencies for {len(affected_components)} components",
                estimated_effort="low",
                related_components=affected_components,
            )
        elif category == 'timeout_error':
            return Recommendation(
                priority=2,
                category="improve",
                description=f"Optimize performance to reduce timeouts in {len(affected_components)} components",
                estimated_effort="medium",
                related_components=affected_components,
            )
        elif category == 'network_error':
            return Recommendation(
                priority=3,
                category="improve",
                description=f"Improve network error handling in {len(affected_components)} components",
                estimated_effort="medium",
                related_components=affected_components,
            )
        
        return None
    
    def _identify_performance_issues(self, test_results: List[TestResult]) -> List[Recommendation]:
        """Identify performance-related issues and recommendations."""
        recommendations = []
        
        # Find slow tests
        slow_tests = [r for r in test_results if r.duration > 30.0]  # Tests taking more than 30 seconds
        if slow_tests:
            slow_components = list(set(t.component for t in slow_tests))
            recommendations.append(Recommendation(
                priority=3,
                category="improve",
                description=f"Optimize slow tests in {len(slow_components)} components (avg: {sum(t.duration for t in slow_tests)/len(slow_tests):.1f}s)",
                estimated_effort="medium",
                related_components=slow_components,
            ))
        
        # Find components with many failures
        failure_counts = Counter(r.component for r in test_results if r.status != HarnessStatus.PASS)
        high_failure_components = [comp for comp, count in failure_counts.items() if count > 2]
        if high_failure_components:
            recommendations.append(Recommendation(
                priority=2,
                category="fix",
                description=f"Address high failure rates in components: {', '.join(high_failure_components)}",
                estimated_effort="high",
                related_components=high_failure_components,
            ))
        
        return recommendations
    
    def _generate_workflow_recommendations(self, test_results: List[TestResult]) -> List[Recommendation]:
        """Generate recommendations for workflow improvements."""
        recommendations = []
        
        # Check for missing workflow components
        tested_components = set(r.component for r in test_results)
        expected_components = {"onboarding", "discovery", "protocol", "spec", "quality"}
        missing_components = expected_components - tested_components
        
        if missing_components:
            recommendations.append(Recommendation(
                priority=2,
                category="implement",
                description=f"Implement missing workflow components: {', '.join(missing_components)}",
                estimated_effort="high",
                related_components=list(missing_components),
            ))
        
        # Check for incomplete workflows
        workflow_components = ["onboarding", "discovery", "protocol", "spec", "quality"]
        workflow_results = {comp: any(r.component == comp and r.status == HarnessStatus.PASS 
                                    for r in test_results) for comp in workflow_components}
        
        incomplete_workflow = [comp for comp, passed in workflow_results.items() if not passed]
        if len(incomplete_workflow) > 1:
            recommendations.append(Recommendation(
                priority=1,
                category="fix",
                description=f"Complete end-to-end workflow by fixing: {', '.join(incomplete_workflow)}",
                estimated_effort="high",
                related_components=incomplete_workflow,
            ))
        
        return recommendations
    
    def _deduplicate_recommendations(self, recommendations: List[Recommendation]) -> List[Recommendation]:
        """Remove duplicate recommendations based on description similarity."""
        unique_recommendations = []
        seen_descriptions = set()
        
        for rec in recommendations:
            # Simple deduplication based on description
            if rec.description not in seen_descriptions:
                seen_descriptions.add(rec.description)
                unique_recommendations.append(rec)
        
        return unique_recommendations
    
    def _collect_environment_info(self) -> Dict[str, Any]:
        """Collect environment information for the report."""
        import os
        import platform
        
        return {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "environment_variables": {
                key: value for key, value in os.environ.items() 
                if key.startswith("TASKSGODZILLA_")
            },
        }
    
    def _save_report(self, report: HarnessReport) -> None:
        """Save report to files."""
        # Save JSON report
        json_path = self.output_path / f"report_{report.execution_id}.json"
        with open(json_path, 'w') as f:
            json.dump(self._serialize_report(report), f, indent=2, default=str)
        
        # Save human-readable report
        text_path = self.output_path / f"report_{report.execution_id}.txt"
        with open(text_path, 'w') as f:
            f.write(self._format_text_report(report))
    
    def save_ci_report(self, report: HarnessReport, format_type: str = "junit") -> Path:
        """Save CI-specific machine-readable report."""
        if format_type == "junit":
            return self._save_junit_report(report)
        elif format_type == "json":
            return self._save_ci_json_report(report)
        else:
            raise ValueError(f"Unsupported CI report format: {format_type}")
    
    def _save_junit_report(self, report: HarnessReport) -> Path:
        """Save JUnit XML report for CI systems."""
        import xml.etree.ElementTree as ET
        
        # Create root testsuite element
        testsuite = ET.Element("testsuite")
        testsuite.set("name", f"cli-workflow-harness-{report.mode}")
        testsuite.set("tests", str(report.total_tests))
        testsuite.set("failures", str(report.failed_tests))
        testsuite.set("errors", str(sum(1 for r in report.test_results if r.status == HarnessStatus.ERROR)))
        testsuite.set("time", str(report.performance_metrics.total_duration))
        testsuite.set("timestamp", report.start_time.isoformat())
        
        # Add test cases
        for result in report.test_results:
            testcase = ET.SubElement(testsuite, "testcase")
            testcase.set("classname", f"harness.{result.component}")
            testcase.set("name", result.test_name)
            testcase.set("time", str(result.duration))
            
            if result.status == HarnessStatus.FAIL:
                failure = ET.SubElement(testcase, "failure")
                failure.set("message", result.error_message or "Test failed")
                failure.text = result.error_message or "No error details available"
            elif result.status == HarnessStatus.ERROR:
                error = ET.SubElement(testcase, "error")
                error.set("message", result.error_message or "Test error")
                error.text = result.error_message or "No error details available"
            elif result.status == HarnessStatus.SKIP:
                skipped = ET.SubElement(testcase, "skipped")
                skipped.set("message", result.error_message or "Test skipped")
        
        # Add workflow results as additional test cases
        for workflow in report.workflow_results:
            for step in workflow.steps:
                testcase = ET.SubElement(testsuite, "testcase")
                testcase.set("classname", f"workflow.{workflow.workflow_name}")
                testcase.set("name", step.test_name)
                testcase.set("time", str(step.duration))
                
                if step.status == HarnessStatus.FAIL:
                    failure = ET.SubElement(testcase, "failure")
                    failure.set("message", step.error_message or "Workflow step failed")
                    failure.text = step.error_message or "No error details available"
                elif step.status == HarnessStatus.ERROR:
                    error = ET.SubElement(testcase, "error")
                    error.set("message", step.error_message or "Workflow step error")
                    error.text = step.error_message or "No error details available"
        
        # Add system properties
        properties = ET.SubElement(testsuite, "properties")
        for key, value in report.environment_info.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    prop = ET.SubElement(properties, "property")
                    prop.set("name", f"{key}.{sub_key}")
                    prop.set("value", str(sub_value))
            else:
                prop = ET.SubElement(properties, "property")
                prop.set("name", key)
                prop.set("value", str(value))
        
        # Save to file
        junit_path = self.output_path / f"junit_{report.execution_id}.xml"
        tree = ET.ElementTree(testsuite)
        tree.write(junit_path, encoding='utf-8', xml_declaration=True)
        
        self.logger.info(f"JUnit report saved to: {junit_path}")
        return junit_path
    
    def _save_ci_json_report(self, report: HarnessReport) -> Path:
        """Save CI-optimized JSON report."""
        ci_report = {
            "harness_version": "1.0.0",
            "execution_id": report.execution_id,
            "mode": report.mode,
            "timestamp": report.start_time.isoformat(),
            "duration": report.performance_metrics.total_duration,
            "summary": {
                "total_tests": report.total_tests,
                "passed": report.passed_tests,
                "failed": report.failed_tests,
                "errors": sum(1 for r in report.test_results if r.status == HarnessStatus.ERROR),
                "skipped": sum(1 for r in report.test_results if r.status == HarnessStatus.SKIP),
                "success_rate": report.success_rate,
            },
            "performance": {
                "total_duration": report.performance_metrics.total_duration,
                "peak_memory_mb": report.performance_metrics.peak_memory_mb,
                "cpu_utilization": report.performance_metrics.cpu_utilization,
                "parallel_efficiency": getattr(report.performance_metrics, 'parallel_efficiency', 0.0),
            },
            "components": self._generate_component_summary(report.test_results),
            "critical_issues": [
                {
                    "type": "missing_feature",
                    "severity": f.impact,
                    "component": f.component,
                    "description": f.description,
                }
                for f in report.missing_features if f.impact == "critical"
            ],
            "recommendations": [
                {
                    "priority": r.priority,
                    "category": r.category,
                    "description": r.description,
                    "effort": r.estimated_effort,
                    "components": r.related_components,
                }
                for r in report.recommendations[:10]  # Top 10 recommendations
            ],
            "environment": report.environment_info,
        }
        
        # Add exit code for CI systems
        ci_report["exit_code"] = 0 if report.success_rate >= 80 else 1
        
        # Save to file
        ci_json_path = self.output_path / f"ci_report_{report.execution_id}.json"
        with open(ci_json_path, 'w') as f:
            json.dump(ci_report, f, indent=2, default=str)
        
        self.logger.info(f"CI JSON report saved to: {ci_json_path}")
        return ci_json_path
    
    def _generate_component_summary(self, test_results: List[TestResult]) -> Dict[str, Any]:
        """Generate component-level summary for CI report."""
        component_summary = {}
        
        # Group results by component
        results_by_component = defaultdict(list)
        for result in test_results:
            results_by_component[result.component].append(result)
        
        for component, results in results_by_component.items():
            passed = sum(1 for r in results if r.status == HarnessStatus.PASS)
            failed = sum(1 for r in results if r.status == HarnessStatus.FAIL)
            errors = sum(1 for r in results if r.status == HarnessStatus.ERROR)
            total_duration = sum(r.duration for r in results)
            
            component_summary[component] = {
                "total_tests": len(results),
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "success_rate": (passed / len(results)) * 100 if results else 0,
                "duration": total_duration,
                "status": "pass" if failed == 0 and errors == 0 else "fail",
            }
        
        return component_summary
    
    def _serialize_report(self, report: HarnessReport) -> Dict[str, Any]:
        """Serialize report to JSON-compatible format."""
        return {
            "execution_id": report.execution_id,
            "mode": report.mode,
            "start_time": report.start_time.isoformat(),
            "end_time": report.end_time.isoformat(),
            "summary": {
                "total_tests": report.total_tests,
                "passed_tests": report.passed_tests,
                "failed_tests": report.failed_tests,
                "success_rate": report.success_rate,
            },
            "test_results": [
                {
                    "component": r.component,
                    "test_name": r.test_name,
                    "status": r.status.value,
                    "duration": r.duration,
                    "error_message": r.error_message,
                }
                for r in report.test_results
            ],
            "missing_features": [
                {
                    "feature_name": f.feature_name,
                    "component": f.component,
                    "description": f.description,
                    "impact": f.impact,
                }
                for f in report.missing_features
            ],
            "recommendations": [
                {
                    "priority": r.priority,
                    "category": r.category,
                    "description": r.description,
                    "estimated_effort": r.estimated_effort,
                }
                for r in report.recommendations
            ],
            "performance_metrics": {
                "total_duration": report.performance_metrics.total_duration,
                "peak_memory_mb": report.performance_metrics.peak_memory_mb,
                "cpu_utilization": report.performance_metrics.cpu_utilization,
            },
            "environment_info": report.environment_info,
        }
    
    def _format_text_report(self, report: HarnessReport) -> str:
        """Format comprehensive human-readable text report."""
        lines = [
            "CLI Workflow Harness Report",
            "=" * 50,
            f"Execution ID: {report.execution_id}",
            f"Mode: {report.mode}",
            f"Start Time: {report.start_time}",
            f"End Time: {report.end_time}",
            f"Duration: {(report.end_time - report.start_time).total_seconds():.2f}s",
            "",
            "Test Summary",
            "-" * 20,
            f"Total Tests: {report.total_tests}",
            f"Passed: {report.passed_tests}",
            f"Failed: {report.failed_tests}",
            f"Errors: {sum(1 for r in report.test_results if r.status == HarnessStatus.ERROR)}",
            f"Success Rate: {report.success_rate:.1f}%",
            "",
        ]
        
        # Performance metrics
        lines.extend([
            "Performance Metrics",
            "-" * 20,
            f"Total Duration: {report.performance_metrics.total_duration:.2f}s",
            f"Peak Memory: {report.performance_metrics.peak_memory_mb:.1f} MB",
            f"CPU Utilization: {report.performance_metrics.cpu_utilization:.1f}%",
            f"Parallel Efficiency: {report.performance_metrics.parallel_efficiency:.1f}%",
            "",
        ])
        
        # Test results by component
        if report.test_results:
            lines.extend([
                "Test Results by Component",
                "-" * 30,
            ])
            
            results_by_component = defaultdict(list)
            for result in report.test_results:
                results_by_component[result.component].append(result)
            
            for component, results in sorted(results_by_component.items()):
                passed = sum(1 for r in results if r.status == HarnessStatus.PASS)
                failed = sum(1 for r in results if r.status == HarnessStatus.FAIL)
                errors = sum(1 for r in results if r.status == HarnessStatus.ERROR)
                total_duration = sum(r.duration for r in results)
                
                lines.append(f"{component}:")
                lines.append(f"  Tests: {len(results)} (P:{passed}, F:{failed}, E:{errors})")
                lines.append(f"  Duration: {total_duration:.2f}s")
                
                # Show failed tests
                failed_tests = [r for r in results if r.status in [HarnessStatus.FAIL, HarnessStatus.ERROR]]
                if failed_tests:
                    lines.append("  Failed Tests:")
                    for test in failed_tests:
                        error_summary = test.error_message[:100] + "..." if test.error_message and len(test.error_message) > 100 else test.error_message
                        lines.append(f"    - {test.test_name}: {error_summary}")
                lines.append("")
        
        # Workflow results
        if report.workflow_results:
            lines.extend([
                "Workflow Results",
                "-" * 20,
            ])
            for workflow in report.workflow_results:
                lines.append(f"{workflow.workflow_name}: {workflow.overall_status.value}")
                lines.append(f"  Steps: {len(workflow.steps)} (Passed: {workflow.passed_steps}, Failed: {workflow.failed_steps})")
                lines.append(f"  Duration: {workflow.duration:.2f}s")
                
                # Show failed steps
                failed_steps = [s for s in workflow.steps if s.status != HarnessStatus.PASS]
                if failed_steps:
                    lines.append("  Failed Steps:")
                    for step in failed_steps:
                        lines.append(f"    - {step.test_name}: {step.status.value}")
                lines.append("")
        
        # Missing features with detailed analysis
        if report.missing_features:
            lines.extend([
                f"Missing Features ({len(report.missing_features)})",
                "-" * 30,
            ])
            
            # Group by impact
            features_by_impact = defaultdict(list)
            for feature in report.missing_features:
                features_by_impact[feature.impact].append(feature)
            
            for impact in ["critical", "major", "minor"]:
                if impact in features_by_impact:
                    lines.append(f"{impact.upper()} Issues:")
                    for feature in features_by_impact[impact]:
                        lines.append(f"  - {feature.feature_name} ({feature.component})")
                        lines.append(f"    {feature.description}")
                        if feature.related_tests:
                            lines.append(f"    Related tests: {', '.join(feature.related_tests[:3])}")
                    lines.append("")
        
        # Recommendations with priorities and next steps
        if report.recommendations:
            lines.extend([
                f"Actionable Recommendations ({len(report.recommendations)})",
                "-" * 40,
            ])
            
            # Group by priority
            recs_by_priority = defaultdict(list)
            for rec in report.recommendations:
                recs_by_priority[rec.priority].append(rec)
            
            for priority in sorted(recs_by_priority.keys()):
                lines.append(f"Priority {priority} ({len(recs_by_priority[priority])} items):")
                for rec in recs_by_priority[priority]:
                    lines.append(f"  [{rec.category.upper()}] {rec.description}")
                    lines.append(f"    Effort: {rec.estimated_effort}")
                    if rec.related_components:
                        lines.append(f"    Components: {', '.join(rec.related_components)}")
                lines.append("")
        
        # Environment information
        if report.environment_info:
            lines.extend([
                "Environment Information",
                "-" * 25,
                f"Platform: {report.environment_info.get('platform', 'Unknown')}",
                f"Python Version: {report.environment_info.get('python_version', 'Unknown')}",
            ])
            
            env_vars = report.environment_info.get('environment_variables', {})
            if env_vars:
                lines.append("Environment Variables:")
                for key, value in env_vars.items():
                    # Mask sensitive values
                    display_value = "***" if "token" in key.lower() or "password" in key.lower() else value
                    lines.append(f"  {key}: {display_value}")
            lines.append("")
        
        # Summary and next steps
        lines.extend([
            "Summary and Next Steps",
            "-" * 25,
        ])
        
        if report.success_rate >= 90:
            lines.append("✅ Excellent! Most tests are passing.")
        elif report.success_rate >= 70:
            lines.append("⚠️  Good progress, but some issues need attention.")
        elif report.success_rate >= 50:
            lines.append("❌ Significant issues detected. Focus on critical fixes.")
        else:
            lines.append("🚨 Major problems detected. Immediate attention required.")
        
        # Priority actions
        critical_recs = [r for r in report.recommendations if r.priority == 1]
        if critical_recs:
            lines.append(f"\nImmediate Actions Required ({len(critical_recs)}):")
            for rec in critical_recs[:5]:  # Show top 5
                lines.append(f"  • {rec.description}")
        
        lines.extend([
            "",
            f"Report generated at: {datetime.now()}",
            f"Full details saved to: {self.output_path}",
        ])
        
        return "\n".join(lines)
    
    def generate_recommendations_from_failures(self, failed_results: List[TestResult]) -> List[Recommendation]:
        """Generate recommendations specifically from failed test results."""
        # Use the failure analyzer to get detailed analysis
        analysis_result = self.failure_analyzer.analyze_failures(failed_results)
        
        recommendations = []
        
        # Generate recommendations from failure patterns
        for pattern in analysis_result["failure_patterns"]:
            if pattern.severity == "critical":
                priority = 1
                effort = "high"
            elif pattern.severity == "major":
                priority = 2
                effort = "medium"
            else:
                priority = 3
                effort = "low"
            
            recommendations.append(Recommendation(
                priority=priority,
                category="fix",
                description=f"Fix {pattern.pattern_type.replace('_', ' ')}: {pattern.suggested_fix}",
                estimated_effort=effort,
                related_components=[pattern.component]
            ))
        
        # Generate recommendations from command gaps
        for gap in analysis_result["command_gaps"]:
            recommendations.append(Recommendation(
                priority=1 if gap.impact == "major" else 2,
                category="implement",
                description=f"Implement missing CLI command: {gap.command_name} at {gap.expected_location}",
                estimated_effort="medium",
                related_components=["cli_interface"]
            ))
        
        # Generate recommendations from workflow gaps
        for gap in analysis_result["workflow_gaps"]:
            recommendations.append(Recommendation(
                priority=2,
                category="implement",
                description=f"Implement missing workflow step: {gap.missing_step} in {gap.workflow_name}",
                estimated_effort="high",
                related_components=[gap.workflow_name]
            ))
        
        # Generate recommendations from documentation gaps
        for gap in analysis_result["documentation_gaps"]:
            recommendations.append(Recommendation(
                priority=3,
                category="improve",
                description=f"Fix documentation issue: {gap.issue_description} at {gap.location}",
                estimated_effort="low",
                related_components=["documentation"]
            ))
        
        return recommendations