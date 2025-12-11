#!/usr/bin/env python3
"""
Comprehensive validation script for CLI workflow harness.

This script implements task 17.1 - Run comprehensive validation after fixes.
It executes the full harness mode with all components and validates:
- Success rate improvement (target >80%)
- Parallel execution efficiency improvement (target >70%)
- Performance analysis and reporting
"""

import sys
import json
import logging
import statistics
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.harness import CLIWorkflowHarness, HarnessConfig, HarnessMode
from tests.harness.models import HarnessReport, HarnessStatus


@dataclass
class ValidationMetrics:
    """Metrics for validation analysis."""
    success_rate: float
    parallel_efficiency: float
    total_duration: float
    peak_memory_mb: float
    cpu_utilization: float
    total_tests: int
    passed_tests: int
    failed_tests: int
    error_tests: int
    critical_failures: int
    performance_violations: int
    
    def meets_targets(self) -> bool:
        """Check if metrics meet target thresholds."""
        return (
            self.success_rate >= 80.0 and
            self.parallel_efficiency >= 70.0
        )


@dataclass
class ValidationResult:
    """Result of comprehensive validation."""
    execution_id: str
    timestamp: datetime
    mode: str
    metrics: ValidationMetrics
    performance_analysis: Dict[str, Any]
    recommendations: List[str]
    meets_targets: bool
    detailed_report_path: Path
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        result['detailed_report_path'] = str(self.detailed_report_path)
        return result


class ComprehensiveValidator:
    """Comprehensive validation of harness fixes and improvements."""
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path("./validation-output")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(self.output_dir / "validation.log")
            ]
        )
    
    def run_comprehensive_validation(self) -> ValidationResult:
        """Execute comprehensive validation after fixes (Task 17.1)."""
        self.logger.info("Starting comprehensive validation after fixes")
        self.logger.info("Target metrics: Success rate >80%, Parallel efficiency >70%")
        
        start_time = datetime.now()
        
        # Create harness configuration for full validation
        config = HarnessConfig(
            mode=HarnessMode.FULL,
            components=[],  # All components
            test_data_path=Path("./tests/harness/data"),
            output_path=self.output_dir / "harness-reports",
            verbose=True,
            parallel=True,
            timeout=1800,  # 30 minutes
            max_workers=4,
        )
        
        try:
            # Execute full harness with all components
            self.logger.info("Executing full harness mode with all components")
            harness = CLIWorkflowHarness(config)
            report = harness.run()
            
            # Analyze results
            metrics = self._analyze_harness_results(report)
            performance_analysis = self._analyze_performance(report)
            recommendations = self._generate_validation_recommendations(metrics, performance_analysis)
            
            # Create validation result
            validation_result = ValidationResult(
                execution_id=report.execution_id,
                timestamp=start_time,
                mode=report.mode,
                metrics=metrics,
                performance_analysis=performance_analysis,
                recommendations=recommendations,
                meets_targets=metrics.meets_targets(),
                detailed_report_path=self.output_dir / "harness-reports" / f"report_{report.execution_id}.json"
            )
            
            # Save validation results
            self._save_validation_results(validation_result)
            
            # Log summary
            self._log_validation_summary(validation_result)
            
            return validation_result
            
        except Exception as e:
            self.logger.error(f"Comprehensive validation failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            raise
    
    def _analyze_harness_results(self, report: HarnessReport) -> ValidationMetrics:
        """Analyze harness results to extract key metrics."""
        # Calculate basic test metrics
        total_tests = len(report.test_results)
        passed_tests = sum(1 for r in report.test_results if r.status == HarnessStatus.PASS)
        failed_tests = sum(1 for r in report.test_results if r.status == HarnessStatus.FAIL)
        error_tests = sum(1 for r in report.test_results if r.status == HarnessStatus.ERROR)
        
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0.0
        
        # Count critical failures (errors and failures in core components)
        core_components = {"onboarding", "discovery", "protocol", "spec", "quality"}
        critical_failures = sum(
            1 for r in report.test_results 
            if r.status in [HarnessStatus.FAIL, HarnessStatus.ERROR] and r.component in core_components
        )
        
        # Extract performance metrics
        perf_metrics = report.performance_metrics
        parallel_efficiency = getattr(perf_metrics, 'parallel_efficiency', 0.0) * 100  # Convert to percentage
        
        # Count performance violations
        performance_violations = len(getattr(perf_metrics, 'threshold_violations', []))
        
        return ValidationMetrics(
            success_rate=success_rate,
            parallel_efficiency=parallel_efficiency,
            total_duration=perf_metrics.total_duration,
            peak_memory_mb=perf_metrics.peak_memory_mb,
            cpu_utilization=perf_metrics.cpu_utilization,
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            error_tests=error_tests,
            critical_failures=critical_failures,
            performance_violations=performance_violations,
        )
    
    def _analyze_performance(self, report: HarnessReport) -> Dict[str, Any]:
        """Analyze performance characteristics in detail."""
        perf_metrics = report.performance_metrics
        
        # Component performance analysis
        component_durations = {}
        component_success_rates = {}
        
        for result in report.test_results:
            component = result.component
            if component not in component_durations:
                component_durations[component] = []
                component_success_rates[component] = {'passed': 0, 'total': 0}
            
            component_durations[component].append(result.duration)
            component_success_rates[component]['total'] += 1
            if result.status == HarnessStatus.PASS:
                component_success_rates[component]['passed'] += 1
        
        # Calculate component statistics
        component_stats = {}
        for component, durations in component_durations.items():
            success_data = component_success_rates[component]
            component_stats[component] = {
                'avg_duration': statistics.mean(durations),
                'max_duration': max(durations),
                'min_duration': min(durations),
                'success_rate': (success_data['passed'] / success_data['total'] * 100) if success_data['total'] > 0 else 0,
                'test_count': success_data['total']
            }
        
        # Performance trend analysis
        performance_trends = {
            'slowest_components': sorted(
                component_stats.items(), 
                key=lambda x: x[1]['avg_duration'], 
                reverse=True
            )[:5],
            'least_reliable_components': sorted(
                component_stats.items(),
                key=lambda x: x[1]['success_rate']
            )[:5],
        }
        
        # Resource utilization analysis
        resource_analysis = {
            'memory_efficiency': 'good' if perf_metrics.peak_memory_mb < 1024 else 'needs_improvement',
            'cpu_efficiency': 'good' if 20 <= perf_metrics.cpu_utilization <= 80 else 'needs_improvement',
            'duration_efficiency': 'good' if perf_metrics.total_duration < 900 else 'needs_improvement',  # 15 minutes
        }
        
        return {
            'component_stats': component_stats,
            'performance_trends': performance_trends,
            'resource_analysis': resource_analysis,
            'threshold_violations': getattr(perf_metrics, 'threshold_violations', []),
            'performance_recommendations': getattr(perf_metrics, 'performance_recommendations', []),
        }
    
    def _generate_validation_recommendations(self, metrics: ValidationMetrics, 
                                           performance_analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []
        
        # Success rate recommendations
        if metrics.success_rate < 80.0:
            recommendations.append(
                f"SUCCESS RATE BELOW TARGET: {metrics.success_rate:.1f}% < 80%. "
                f"Focus on fixing {metrics.failed_tests + metrics.error_tests} failing tests."
            )
            
            # Identify most problematic components
            component_stats = performance_analysis['component_stats']
            problematic = [
                comp for comp, stats in component_stats.items() 
                if stats['success_rate'] < 80
            ]
            if problematic:
                recommendations.append(
                    f"Priority components for fixes: {', '.join(problematic)}"
                )
        else:
            recommendations.append(
                f"SUCCESS RATE TARGET MET: {metrics.success_rate:.1f}% >= 80%"
            )
        
        # Parallel efficiency recommendations
        if metrics.parallel_efficiency < 70.0:
            recommendations.append(
                f"PARALLEL EFFICIENCY BELOW TARGET: {metrics.parallel_efficiency:.1f}% < 70%. "
                "Consider optimizing task isolation and reducing dependencies."
            )
        else:
            recommendations.append(
                f"PARALLEL EFFICIENCY TARGET MET: {metrics.parallel_efficiency:.1f}% >= 70%"
            )
        
        # Performance recommendations
        if metrics.performance_violations > 0:
            recommendations.append(
                f"PERFORMANCE VIOLATIONS: {metrics.performance_violations} threshold violations detected. "
                "Review performance analysis for details."
            )
        
        # Resource utilization recommendations
        resource_analysis = performance_analysis['resource_analysis']
        if resource_analysis['memory_efficiency'] == 'needs_improvement':
            recommendations.append(
                f"HIGH MEMORY USAGE: {metrics.peak_memory_mb:.1f}MB peak usage. "
                "Consider memory optimization."
            )
        
        if resource_analysis['cpu_efficiency'] == 'needs_improvement':
            recommendations.append(
                f"CPU UTILIZATION ISSUE: {metrics.cpu_utilization:.1f}% utilization. "
                "Optimize for 20-80% range."
            )
        
        # Component-specific recommendations
        slowest_components = performance_analysis['performance_trends']['slowest_components']
        if slowest_components:
            slowest_name, slowest_stats = slowest_components[0]
            if slowest_stats['avg_duration'] > 60:  # More than 1 minute average
                recommendations.append(
                    f"SLOW COMPONENT: '{slowest_name}' averages {slowest_stats['avg_duration']:.1f}s. "
                    "Consider optimization."
                )
        
        # Critical failure recommendations
        if metrics.critical_failures > 0:
            recommendations.append(
                f"CRITICAL FAILURES: {metrics.critical_failures} failures in core components. "
                "These should be prioritized for immediate fixes."
            )
        
        return recommendations
    
    def _save_validation_results(self, result: ValidationResult) -> None:
        """Save validation results to files."""
        # Save JSON report
        json_path = self.output_dir / f"validation_result_{result.execution_id}.json"
        with open(json_path, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        
        # Save text summary
        text_path = self.output_dir / f"validation_summary_{result.execution_id}.txt"
        with open(text_path, 'w') as f:
            f.write(self._format_text_summary(result))
        
        self.logger.info(f"Validation results saved to {json_path} and {text_path}")
    
    def _format_text_summary(self, result: ValidationResult) -> str:
        """Format validation result as text summary."""
        lines = [
            "=" * 80,
            "CLI WORKFLOW HARNESS - COMPREHENSIVE VALIDATION RESULTS",
            "=" * 80,
            f"Execution ID: {result.execution_id}",
            f"Timestamp: {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Mode: {result.mode}",
            "",
            "TARGET VALIDATION:",
            f"  Meets Targets: {'✓ YES' if result.meets_targets else '✗ NO'}",
            f"  Success Rate: {result.metrics.success_rate:.1f}% (target: ≥80%)",
            f"  Parallel Efficiency: {result.metrics.parallel_efficiency:.1f}% (target: ≥70%)",
            "",
            "TEST RESULTS:",
            f"  Total Tests: {result.metrics.total_tests}",
            f"  Passed: {result.metrics.passed_tests}",
            f"  Failed: {result.metrics.failed_tests}",
            f"  Errors: {result.metrics.error_tests}",
            f"  Critical Failures: {result.metrics.critical_failures}",
            "",
            "PERFORMANCE METRICS:",
            f"  Total Duration: {result.metrics.total_duration:.1f}s",
            f"  Peak Memory: {result.metrics.peak_memory_mb:.1f}MB",
            f"  CPU Utilization: {result.metrics.cpu_utilization:.1f}%",
            f"  Performance Violations: {result.metrics.performance_violations}",
            "",
            "RECOMMENDATIONS:",
        ]
        
        for i, rec in enumerate(result.recommendations, 1):
            lines.append(f"  {i}. {rec}")
        
        lines.extend([
            "",
            f"Detailed Report: {result.detailed_report_path}",
            "=" * 80,
        ])
        
        return "\n".join(lines)
    
    def _log_validation_summary(self, result: ValidationResult) -> None:
        """Log validation summary to console."""
        self.logger.info("=" * 60)
        self.logger.info("COMPREHENSIVE VALIDATION COMPLETED")
        self.logger.info("=" * 60)
        self.logger.info(f"Execution ID: {result.execution_id}")
        self.logger.info(f"Success Rate: {result.metrics.success_rate:.1f}% (target: ≥80%)")
        self.logger.info(f"Parallel Efficiency: {result.metrics.parallel_efficiency:.1f}% (target: ≥70%)")
        self.logger.info(f"Total Duration: {result.metrics.total_duration:.1f}s")
        self.logger.info(f"Peak Memory: {result.metrics.peak_memory_mb:.1f}MB")
        
        if result.meets_targets:
            self.logger.info("✓ VALIDATION PASSED - All targets met!")
        else:
            self.logger.warning("✗ VALIDATION FAILED - Targets not met")
            
        self.logger.info(f"Critical Failures: {result.metrics.critical_failures}")
        self.logger.info(f"Performance Violations: {result.metrics.performance_violations}")
        
        if result.recommendations:
            self.logger.info("Top Recommendations:")
            for rec in result.recommendations[:3]:
                self.logger.info(f"  - {rec}")
        
        self.logger.info("=" * 60)


def main():
    """Main entry point for comprehensive validation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Comprehensive validation of CLI workflow harness")
    parser.add_argument(
        '--output-dir', '-o',
        type=Path,
        default=Path('./validation-output'),
        help='Output directory for validation results'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        validator = ComprehensiveValidator(args.output_dir)
        result = validator.run_comprehensive_validation()
        
        # Exit with appropriate code
        exit_code = 0 if result.meets_targets else 1
        sys.exit(exit_code)
        
    except Exception as e:
        logging.error(f"Validation failed: {e}")
        sys.exit(2)


if __name__ == '__main__':
    main()