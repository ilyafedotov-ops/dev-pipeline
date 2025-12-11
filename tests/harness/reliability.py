#!/usr/bin/env python3
"""
Extended reliability testing for CLI workflow harness.

This script implements task 17.2 - Run extended reliability testing.
It executes multiple test runs to validate:
- Harness stability under different conditions
- Memory usage and performance metrics consistency
- CI integration and automation reliability
"""

import sys
import json
import time
import logging
import statistics
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.harness import CLIWorkflowHarness, HarnessConfig, HarnessMode
from tests.harness.models import HarnessReport, HarnessStatus


@dataclass
class ReliabilityMetrics:
    """Metrics for reliability analysis."""
    total_runs: int
    successful_runs: int
    failed_runs: int
    error_runs: int
    reliability_rate: float
    avg_success_rate: float
    success_rate_variance: float
    avg_duration: float
    duration_variance: float
    avg_memory_usage: float
    memory_variance: float
    avg_parallel_efficiency: float
    efficiency_variance: float
    consistency_score: float  # Overall consistency metric
    
    def is_reliable(self) -> bool:
        """Check if harness meets reliability criteria."""
        return (
            self.reliability_rate >= 95.0 and  # 95% of runs should complete successfully
            self.consistency_score >= 80.0 and  # 80% consistency in metrics
            self.success_rate_variance < 10.0  # Success rate should not vary by more than 10%
        )


@dataclass
class ReliabilityCondition:
    """Test condition for reliability testing."""
    name: str
    description: str
    config_overrides: Dict[str, Any]
    expected_impact: str  # "none", "minor", "moderate", "major"


@dataclass
class ReliabilityResult:
    """Result of extended reliability testing."""
    test_id: str
    timestamp: datetime
    total_duration: float
    conditions_tested: List[str]
    metrics: ReliabilityMetrics
    run_results: List[Dict[str, Any]]
    performance_analysis: Dict[str, Any]
    stability_analysis: Dict[str, Any]
    ci_integration_results: Dict[str, Any]
    recommendations: List[str]
    is_reliable: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result


class ReliabilityTester:
    """Extended reliability testing for harness stability and consistency."""
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path("./reliability-output")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(self.output_dir / "reliability.log")
            ]
        )
        
        # Define test conditions for reliability testing
        self.test_conditions = [
            ReliabilityCondition(
                name="baseline",
                description="Standard configuration baseline",
                config_overrides={},
                expected_impact="none"
            ),
            ReliabilityCondition(
                name="high_parallelism",
                description="Maximum parallel workers",
                config_overrides={"max_workers": 8, "parallel": True},
                expected_impact="minor"
            ),
            ReliabilityCondition(
                name="low_timeout",
                description="Reduced timeout for stress testing",
                config_overrides={"timeout": 600},  # 10 minutes
                expected_impact="moderate"
            ),
            ReliabilityCondition(
                name="sequential_only",
                description="Disable parallel execution",
                config_overrides={"parallel": False, "max_workers": 1},
                expected_impact="minor"
            ),
            ReliabilityCondition(
                name="verbose_logging",
                description="Maximum logging verbosity",
                config_overrides={"verbose": True},
                expected_impact="minor"
            ),
        ]
    
    def run_extended_reliability_testing(self, 
                                       runs_per_condition: int = 3,
                                       include_ci_testing: bool = True) -> ReliabilityResult:
        """Execute extended reliability testing (Task 17.2)."""
        self.logger.info("Starting extended reliability testing")
        self.logger.info(f"Testing {len(self.test_conditions)} conditions with {runs_per_condition} runs each")
        
        start_time = datetime.now()
        test_id = f"reliability_{start_time.strftime('%Y%m%d_%H%M%S')}"
        
        all_run_results = []
        conditions_tested = []
        
        try:
            # Test each condition multiple times
            for condition in self.test_conditions:
                self.logger.info(f"Testing condition: {condition.name} - {condition.description}")
                conditions_tested.append(condition.name)
                
                condition_results = self._test_condition_reliability(
                    condition, runs_per_condition
                )
                all_run_results.extend(condition_results)
                
                # Brief pause between conditions to allow system recovery
                time.sleep(5)
            
            # Test CI integration if requested
            ci_integration_results = {}
            if include_ci_testing:
                ci_integration_results = self._test_ci_integration()
            
            # Analyze results
            metrics = self._calculate_reliability_metrics(all_run_results)
            performance_analysis = self._analyze_performance_consistency(all_run_results)
            stability_analysis = self._analyze_stability(all_run_results)
            recommendations = self._generate_reliability_recommendations(
                metrics, performance_analysis, stability_analysis
            )
            
            end_time = datetime.now()
            total_duration = (end_time - start_time).total_seconds()
            
            # Create reliability result
            reliability_result = ReliabilityResult(
                test_id=test_id,
                timestamp=start_time,
                total_duration=total_duration,
                conditions_tested=conditions_tested,
                metrics=metrics,
                run_results=all_run_results,
                performance_analysis=performance_analysis,
                stability_analysis=stability_analysis,
                ci_integration_results=ci_integration_results,
                recommendations=recommendations,
                is_reliable=metrics.is_reliable(),
            )
            
            # Save results
            self._save_reliability_results(reliability_result)
            
            # Log summary
            self._log_reliability_summary(reliability_result)
            
            return reliability_result
            
        except Exception as e:
            self.logger.error(f"Extended reliability testing failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            raise
    
    def _test_condition_reliability(self, condition: ReliabilityCondition, 
                                  num_runs: int) -> List[Dict[str, Any]]:
        """Test reliability under a specific condition."""
        results = []
        
        for run_num in range(num_runs):
            self.logger.info(f"  Run {run_num + 1}/{num_runs} for condition '{condition.name}'")
            
            run_start = datetime.now()
            
            try:
                # Create configuration with condition overrides
                base_config = {
                    "mode": HarnessMode.SMOKE,  # Use smoke mode for faster reliability testing
                    "components": ["onboarding", "cli_interface"],  # Core components only
                    "test_data_path": Path("./tests/harness/data"),
                    "output_path": self.output_dir / "harness-reports" / condition.name,
                    "verbose": False,
                    "parallel": True,
                    "timeout": 900,  # 15 minutes default
                    "max_workers": 4,
                }
                
                # Apply condition overrides
                base_config.update(condition.config_overrides)
                
                config = HarnessConfig(**base_config)
                
                # Execute harness
                harness = CLIWorkflowHarness(config)
                report = harness.run()
                
                run_end = datetime.now()
                run_duration = (run_end - run_start).total_seconds()
                
                # Extract key metrics
                total_tests = len(report.test_results)
                passed_tests = sum(1 for r in report.test_results if r.status == HarnessStatus.PASS)
                success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0.0
                
                run_result = {
                    "condition": condition.name,
                    "run_number": run_num + 1,
                    "start_time": run_start.isoformat(),
                    "end_time": run_end.isoformat(),
                    "duration": run_duration,
                    "status": "success",
                    "execution_id": report.execution_id,
                    "total_tests": total_tests,
                    "passed_tests": passed_tests,
                    "success_rate": success_rate,
                    "peak_memory_mb": report.performance_metrics.peak_memory_mb,
                    "cpu_utilization": report.performance_metrics.cpu_utilization,
                    "parallel_efficiency": getattr(report.performance_metrics, 'parallel_efficiency', 0.0) * 100,
                    "performance_violations": len(getattr(report.performance_metrics, 'threshold_violations', [])),
                    "error_message": None,
                }
                
                results.append(run_result)
                
                self.logger.info(f"    ✓ Success: {success_rate:.1f}% success rate, {run_duration:.1f}s duration")
                
            except Exception as e:
                run_end = datetime.now()
                run_duration = (run_end - run_start).total_seconds()
                
                error_result = {
                    "condition": condition.name,
                    "run_number": run_num + 1,
                    "start_time": run_start.isoformat(),
                    "end_time": run_end.isoformat(),
                    "duration": run_duration,
                    "status": "error",
                    "execution_id": None,
                    "total_tests": 0,
                    "passed_tests": 0,
                    "success_rate": 0.0,
                    "peak_memory_mb": 0.0,
                    "cpu_utilization": 0.0,
                    "parallel_efficiency": 0.0,
                    "performance_violations": 0,
                    "error_message": str(e),
                }
                
                results.append(error_result)
                
                self.logger.error(f"    ✗ Error: {e}")
        
        return results
    
    def _test_ci_integration(self) -> Dict[str, Any]:
        """Test CI integration and automation."""
        self.logger.info("Testing CI integration and automation")
        
        ci_results = {
            "ci_mode_test": None,
            "exit_code_test": None,
            "machine_readable_output": None,
            "ci_script_integration": None,
        }
        
        try:
            # Test CI mode execution
            self.logger.info("  Testing CI mode execution")
            ci_config = HarnessConfig(
                mode=HarnessMode.CI,
                components=["onboarding"],  # Minimal for CI testing
                test_data_path=Path("./tests/harness/data"),
                output_path=self.output_dir / "ci-test",
                verbose=False,
                parallel=True,
                timeout=600,  # 10 minutes
                max_workers=2,
            )
            
            harness = CLIWorkflowHarness(ci_config)
            report = harness.run()
            
            ci_results["ci_mode_test"] = {
                "status": "success",
                "execution_id": report.execution_id,
                "success_rate": report.success_rate,
                "duration": report.performance_metrics.total_duration,
                "exit_code": harness.get_ci_exit_code(),
            }
            
            self.logger.info(f"    ✓ CI mode test completed: {report.success_rate:.1f}% success rate")
            
        except Exception as e:
            ci_results["ci_mode_test"] = {
                "status": "error",
                "error_message": str(e),
            }
            self.logger.error(f"    ✗ CI mode test failed: {e}")
        
        # Test machine-readable output generation
        try:
            self.logger.info("  Testing machine-readable output generation")
            
            # Check if CI reports were generated
            ci_output_dir = self.output_dir / "ci-test"
            junit_files = list(ci_output_dir.glob("**/junit_*.xml"))
            json_files = list(ci_output_dir.glob("**/ci_report_*.json"))
            
            ci_results["machine_readable_output"] = {
                "status": "success" if junit_files and json_files else "partial",
                "junit_files_found": len(junit_files),
                "json_files_found": len(json_files),
                "junit_files": [str(f) for f in junit_files],
                "json_files": [str(f) for f in json_files],
            }
            
            if junit_files and json_files:
                self.logger.info(f"    ✓ Machine-readable output: {len(junit_files)} JUnit, {len(json_files)} JSON files")
            else:
                self.logger.warning(f"    ⚠ Partial machine-readable output: {len(junit_files)} JUnit, {len(json_files)} JSON files")
                
        except Exception as e:
            ci_results["machine_readable_output"] = {
                "status": "error",
                "error_message": str(e),
            }
            self.logger.error(f"    ✗ Machine-readable output test failed: {e}")
        
        # Test CI script integration
        try:
            self.logger.info("  Testing CI script integration")
            
            # Check if CI scripts exist and are executable
            ci_scripts_dir = Path("scripts/ci")
            expected_scripts = ["bootstrap.sh", "test.sh", "lint.sh", "typecheck.sh", "build.sh"]
            
            script_status = {}
            for script_name in expected_scripts:
                script_path = ci_scripts_dir / script_name
                script_status[script_name] = {
                    "exists": script_path.exists(),
                    "executable": script_path.is_file() and script_path.stat().st_mode & 0o111,
                }
            
            ci_results["ci_script_integration"] = {
                "status": "success",
                "scripts_checked": len(expected_scripts),
                "scripts_found": sum(1 for s in script_status.values() if s["exists"]),
                "scripts_executable": sum(1 for s in script_status.values() if s["executable"]),
                "script_details": script_status,
            }
            
            found_count = ci_results["ci_script_integration"]["scripts_found"]
            self.logger.info(f"    ✓ CI script integration: {found_count}/{len(expected_scripts)} scripts found")
            
        except Exception as e:
            ci_results["ci_script_integration"] = {
                "status": "error",
                "error_message": str(e),
            }
            self.logger.error(f"    ✗ CI script integration test failed: {e}")
        
        return ci_results
    
    def _calculate_reliability_metrics(self, run_results: List[Dict[str, Any]]) -> ReliabilityMetrics:
        """Calculate reliability metrics from all run results."""
        total_runs = len(run_results)
        successful_runs = sum(1 for r in run_results if r["status"] == "success")
        failed_runs = sum(1 for r in run_results if r["status"] == "failed")
        error_runs = sum(1 for r in run_results if r["status"] == "error")
        
        reliability_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0.0
        
        # Calculate metrics for successful runs only
        successful_results = [r for r in run_results if r["status"] == "success"]
        
        if successful_results:
            success_rates = [r["success_rate"] for r in successful_results]
            durations = [r["duration"] for r in successful_results]
            memory_usages = [r["peak_memory_mb"] for r in successful_results]
            parallel_efficiencies = [r["parallel_efficiency"] for r in successful_results]
            
            avg_success_rate = statistics.mean(success_rates)
            success_rate_variance = statistics.variance(success_rates) if len(success_rates) > 1 else 0.0
            
            avg_duration = statistics.mean(durations)
            duration_variance = statistics.variance(durations) if len(durations) > 1 else 0.0
            
            avg_memory_usage = statistics.mean(memory_usages)
            memory_variance = statistics.variance(memory_usages) if len(memory_usages) > 1 else 0.0
            
            avg_parallel_efficiency = statistics.mean(parallel_efficiencies)
            efficiency_variance = statistics.variance(parallel_efficiencies) if len(parallel_efficiencies) > 1 else 0.0
            
            # Calculate consistency score (lower variance = higher consistency)
            # Normalize variances and calculate overall consistency
            normalized_success_variance = min(success_rate_variance / 100, 1.0)  # Normalize to 0-1
            normalized_duration_variance = min(duration_variance / (avg_duration ** 2), 1.0)
            normalized_memory_variance = min(memory_variance / (avg_memory_usage ** 2), 1.0)
            normalized_efficiency_variance = min(efficiency_variance / 100, 1.0)
            
            avg_normalized_variance = (
                normalized_success_variance + normalized_duration_variance + 
                normalized_memory_variance + normalized_efficiency_variance
            ) / 4
            
            consistency_score = (1.0 - avg_normalized_variance) * 100  # Convert to percentage
            
        else:
            # No successful runs
            avg_success_rate = 0.0
            success_rate_variance = 0.0
            avg_duration = 0.0
            duration_variance = 0.0
            avg_memory_usage = 0.0
            memory_variance = 0.0
            avg_parallel_efficiency = 0.0
            efficiency_variance = 0.0
            consistency_score = 0.0
        
        return ReliabilityMetrics(
            total_runs=total_runs,
            successful_runs=successful_runs,
            failed_runs=failed_runs,
            error_runs=error_runs,
            reliability_rate=reliability_rate,
            avg_success_rate=avg_success_rate,
            success_rate_variance=success_rate_variance,
            avg_duration=avg_duration,
            duration_variance=duration_variance,
            avg_memory_usage=avg_memory_usage,
            memory_variance=memory_variance,
            avg_parallel_efficiency=avg_parallel_efficiency,
            efficiency_variance=efficiency_variance,
            consistency_score=consistency_score,
        )
    
    def _analyze_performance_consistency(self, run_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze performance consistency across runs."""
        successful_results = [r for r in run_results if r["status"] == "success"]
        
        if not successful_results:
            return {"status": "no_successful_runs"}
        
        # Group results by condition
        by_condition = {}
        for result in successful_results:
            condition = result["condition"]
            if condition not in by_condition:
                by_condition[condition] = []
            by_condition[condition].append(result)
        
        # Analyze each condition
        condition_analysis = {}
        for condition, results in by_condition.items():
            if len(results) > 1:
                success_rates = [r["success_rate"] for r in results]
                durations = [r["duration"] for r in results]
                memory_usages = [r["peak_memory_mb"] for r in results]
                
                condition_analysis[condition] = {
                    "runs": len(results),
                    "success_rate_consistency": {
                        "mean": statistics.mean(success_rates),
                        "stdev": statistics.stdev(success_rates) if len(success_rates) > 1 else 0.0,
                        "min": min(success_rates),
                        "max": max(success_rates),
                    },
                    "duration_consistency": {
                        "mean": statistics.mean(durations),
                        "stdev": statistics.stdev(durations) if len(durations) > 1 else 0.0,
                        "min": min(durations),
                        "max": max(durations),
                    },
                    "memory_consistency": {
                        "mean": statistics.mean(memory_usages),
                        "stdev": statistics.stdev(memory_usages) if len(memory_usages) > 1 else 0.0,
                        "min": min(memory_usages),
                        "max": max(memory_usages),
                    },
                }
            else:
                condition_analysis[condition] = {
                    "runs": len(results),
                    "note": "insufficient_runs_for_analysis"
                }
        
        # Overall consistency assessment
        overall_consistency = "good"
        consistency_issues = []
        
        for condition, analysis in condition_analysis.items():
            if "success_rate_consistency" in analysis:
                if analysis["success_rate_consistency"]["stdev"] > 10.0:
                    consistency_issues.append(f"{condition}: high success rate variance")
                    overall_consistency = "poor"
                elif analysis["success_rate_consistency"]["stdev"] > 5.0:
                    consistency_issues.append(f"{condition}: moderate success rate variance")
                    if overall_consistency == "good":
                        overall_consistency = "moderate"
        
        return {
            "status": "analyzed",
            "overall_consistency": overall_consistency,
            "consistency_issues": consistency_issues,
            "condition_analysis": condition_analysis,
        }
    
    def _analyze_stability(self, run_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze harness stability across different conditions."""
        # Failure analysis
        failed_results = [r for r in run_results if r["status"] in ["failed", "error"]]
        failure_patterns = {}
        
        for result in failed_results:
            condition = result["condition"]
            if condition not in failure_patterns:
                failure_patterns[condition] = []
            failure_patterns[condition].append({
                "run_number": result["run_number"],
                "error_message": result.get("error_message", "unknown"),
                "duration": result["duration"],
            })
        
        # Stability assessment
        total_runs = len(run_results)
        failed_runs = len(failed_results)
        stability_rate = ((total_runs - failed_runs) / total_runs * 100) if total_runs > 0 else 0.0
        
        stability_level = "excellent" if stability_rate >= 95 else \
                         "good" if stability_rate >= 90 else \
                         "moderate" if stability_rate >= 80 else "poor"
        
        # Memory stability analysis
        successful_results = [r for r in run_results if r["status"] == "success"]
        memory_stability = "unknown"
        
        if successful_results:
            memory_usages = [r["peak_memory_mb"] for r in successful_results]
            if memory_usages:
                memory_range = max(memory_usages) - min(memory_usages)
                avg_memory = statistics.mean(memory_usages)
                memory_variation = (memory_range / avg_memory * 100) if avg_memory > 0 else 0
                
                memory_stability = "excellent" if memory_variation < 10 else \
                                 "good" if memory_variation < 25 else \
                                 "moderate" if memory_variation < 50 else "poor"
        
        return {
            "stability_rate": stability_rate,
            "stability_level": stability_level,
            "total_runs": total_runs,
            "failed_runs": failed_runs,
            "failure_patterns": failure_patterns,
            "memory_stability": memory_stability,
            "memory_variation_percent": memory_variation if 'memory_variation' in locals() else 0,
        }
    
    def _generate_reliability_recommendations(self, metrics: ReliabilityMetrics,
                                            performance_analysis: Dict[str, Any],
                                            stability_analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on reliability analysis."""
        recommendations = []
        
        # Reliability rate recommendations
        if metrics.reliability_rate < 95.0:
            recommendations.append(
                f"RELIABILITY BELOW TARGET: {metrics.reliability_rate:.1f}% < 95%. "
                f"Address {metrics.failed_runs + metrics.error_runs} failed/error runs."
            )
        else:
            recommendations.append(
                f"RELIABILITY TARGET MET: {metrics.reliability_rate:.1f}% >= 95%"
            )
        
        # Consistency recommendations
        if metrics.consistency_score < 80.0:
            recommendations.append(
                f"CONSISTENCY BELOW TARGET: {metrics.consistency_score:.1f}% < 80%. "
                "Reduce variance in performance metrics."
            )
        else:
            recommendations.append(
                f"CONSISTENCY TARGET MET: {metrics.consistency_score:.1f}% >= 80%"
            )
        
        # Success rate variance recommendations
        if metrics.success_rate_variance > 10.0:
            recommendations.append(
                f"HIGH SUCCESS RATE VARIANCE: {metrics.success_rate_variance:.1f}% > 10%. "
                "Investigate inconsistent test behavior."
            )
        
        # Performance consistency recommendations
        if performance_analysis.get("overall_consistency") == "poor":
            recommendations.append(
                "POOR PERFORMANCE CONSISTENCY: Review condition-specific performance issues."
            )
        
        # Stability recommendations
        stability_level = stability_analysis.get("stability_level", "unknown")
        if stability_level in ["moderate", "poor"]:
            recommendations.append(
                f"STABILITY ISSUES: {stability_level.upper()} stability level. "
                f"Review failure patterns: {len(stability_analysis.get('failure_patterns', {}))} conditions affected."
            )
        
        # Memory stability recommendations
        memory_stability = stability_analysis.get("memory_stability", "unknown")
        if memory_stability in ["moderate", "poor"]:
            memory_variation = stability_analysis.get("memory_variation_percent", 0)
            recommendations.append(
                f"MEMORY INSTABILITY: {memory_variation:.1f}% variation in memory usage. "
                "Investigate memory leaks or inconsistent cleanup."
            )
        
        # Specific condition recommendations
        if performance_analysis.get("consistency_issues"):
            recommendations.append(
                f"CONDITION-SPECIFIC ISSUES: {len(performance_analysis['consistency_issues'])} conditions "
                "show consistency problems. Review individual condition analysis."
            )
        
        return recommendations
    
    def _save_reliability_results(self, result: ReliabilityResult) -> None:
        """Save reliability results to files."""
        # Save JSON report
        json_path = self.output_dir / f"reliability_result_{result.test_id}.json"
        with open(json_path, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        
        # Save text summary
        text_path = self.output_dir / f"reliability_summary_{result.test_id}.txt"
        with open(text_path, 'w') as f:
            f.write(self._format_reliability_summary(result))
        
        self.logger.info(f"Reliability results saved to {json_path} and {text_path}")
    
    def _format_reliability_summary(self, result: ReliabilityResult) -> str:
        """Format reliability result as text summary."""
        lines = [
            "=" * 80,
            "CLI WORKFLOW HARNESS - EXTENDED RELIABILITY TESTING RESULTS",
            "=" * 80,
            f"Test ID: {result.test_id}",
            f"Timestamp: {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total Duration: {result.total_duration:.1f}s",
            f"Conditions Tested: {', '.join(result.conditions_tested)}",
            "",
            "RELIABILITY ASSESSMENT:",
            f"  Is Reliable: {'✓ YES' if result.is_reliable else '✗ NO'}",
            f"  Reliability Rate: {result.metrics.reliability_rate:.1f}% (target: ≥95%)",
            f"  Consistency Score: {result.metrics.consistency_score:.1f}% (target: ≥80%)",
            f"  Success Rate Variance: {result.metrics.success_rate_variance:.1f}% (target: <10%)",
            "",
            "RUN STATISTICS:",
            f"  Total Runs: {result.metrics.total_runs}",
            f"  Successful Runs: {result.metrics.successful_runs}",
            f"  Failed Runs: {result.metrics.failed_runs}",
            f"  Error Runs: {result.metrics.error_runs}",
            "",
            "PERFORMANCE METRICS:",
            f"  Average Success Rate: {result.metrics.avg_success_rate:.1f}%",
            f"  Average Duration: {result.metrics.avg_duration:.1f}s",
            f"  Average Memory Usage: {result.metrics.avg_memory_usage:.1f}MB",
            f"  Average Parallel Efficiency: {result.metrics.avg_parallel_efficiency:.1f}%",
            "",
            "STABILITY ANALYSIS:",
            f"  Stability Level: {result.stability_analysis.get('stability_level', 'unknown').upper()}",
            f"  Memory Stability: {result.stability_analysis.get('memory_stability', 'unknown').upper()}",
            "",
            "RECOMMENDATIONS:",
        ]
        
        for i, rec in enumerate(result.recommendations, 1):
            lines.append(f"  {i}. {rec}")
        
        lines.extend([
            "",
            "=" * 80,
        ])
        
        return "\n".join(lines)
    
    def _log_reliability_summary(self, result: ReliabilityResult) -> None:
        """Log reliability summary to console."""
        self.logger.info("=" * 60)
        self.logger.info("EXTENDED RELIABILITY TESTING COMPLETED")
        self.logger.info("=" * 60)
        self.logger.info(f"Test ID: {result.test_id}")
        self.logger.info(f"Total Duration: {result.total_duration:.1f}s")
        self.logger.info(f"Conditions Tested: {len(result.conditions_tested)}")
        self.logger.info(f"Total Runs: {result.metrics.total_runs}")
        
        self.logger.info(f"Reliability Rate: {result.metrics.reliability_rate:.1f}% (target: ≥95%)")
        self.logger.info(f"Consistency Score: {result.metrics.consistency_score:.1f}% (target: ≥80%)")
        self.logger.info(f"Success Rate Variance: {result.metrics.success_rate_variance:.1f}% (target: <10%)")
        
        if result.is_reliable:
            self.logger.info("✓ RELIABILITY ASSESSMENT: PASSED - Harness is reliable!")
        else:
            self.logger.warning("✗ RELIABILITY ASSESSMENT: FAILED - Reliability issues detected")
        
        stability_level = result.stability_analysis.get("stability_level", "unknown")
        self.logger.info(f"Stability Level: {stability_level.upper()}")
        
        if result.recommendations:
            self.logger.info("Top Recommendations:")
            for rec in result.recommendations[:3]:
                self.logger.info(f"  - {rec}")
        
        self.logger.info("=" * 60)


def main():
    """Main entry point for extended reliability testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Extended reliability testing of CLI workflow harness")
    parser.add_argument(
        '--output-dir', '-o',
        type=Path,
        default=Path('./reliability-output'),
        help='Output directory for reliability results'
    )
    parser.add_argument(
        '--runs-per-condition', '-r',
        type=int,
        default=3,
        help='Number of runs per test condition (default: 3)'
    )
    parser.add_argument(
        '--skip-ci-testing',
        action='store_true',
        help='Skip CI integration testing'
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
        tester = ReliabilityTester(args.output_dir)
        result = tester.run_extended_reliability_testing(
            runs_per_condition=args.runs_per_condition,
            include_ci_testing=not args.skip_ci_testing
        )
        
        # Exit with appropriate code
        exit_code = 0 if result.is_reliable else 1
        sys.exit(exit_code)
        
    except Exception as e:
        logging.error(f"Reliability testing failed: {e}")
        sys.exit(2)


if __name__ == '__main__':
    main()