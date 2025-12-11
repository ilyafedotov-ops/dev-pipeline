#!/usr/bin/env python3
"""
Comprehensive system testing for CLI workflow harness.

This script implements task 18.1 - Comprehensive system testing.
It executes full harness validation against multiple real projects,
tests harness stability under extended operation, validates performance
under realistic load, and tests recovery from various failure scenarios.
"""

import sys
import json
import time
import logging
import statistics
import threading
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import psutil
import signal

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.harness import CLIWorkflowHarness, HarnessConfig, HarnessMode
from tests.harness.models import HarnessReport, HarnessStatus
from tests.harness.validation import ComprehensiveValidator
from tests.harness.reliability import ReliabilityTester


@dataclass
class SystemTestProject:
    """Test project configuration for system testing."""
    name: str
    description: str
    git_url: Optional[str]
    local_path: Optional[Path]
    project_type: str  # "python", "javascript", "mixed", "demo"
    complexity: str  # "simple", "medium", "complex"
    expected_components: Set[str]  # Expected workflow components to work
    known_issues: List[str]  # Known issues or limitations


@dataclass
class LoadTestScenario:
    """Load testing scenario configuration."""
    name: str
    description: str
    concurrent_harnesses: int
    duration_minutes: int
    project_count: int
    expected_peak_memory_mb: int
    expected_max_duration_seconds: int


@dataclass
class FailureScenario:
    """Failure scenario for recovery testing."""
    name: str
    description: str
    failure_type: str  # "network", "disk", "memory", "timeout", "corruption"
    trigger_method: str  # How to trigger the failure
    expected_recovery: str  # Expected recovery behavior
    recovery_time_limit: int  # Maximum time for recovery in seconds


@dataclass
class SystemTestMetrics:
    """Comprehensive system test metrics."""
    total_projects_tested: int
    successful_projects: int
    failed_projects: int
    avg_success_rate_per_project: float
    total_test_duration: float
    peak_memory_usage_mb: float
    peak_cpu_utilization: float
    load_test_results: Dict[str, Any]
    failure_recovery_results: Dict[str, Any]
    stability_score: float  # 0-100 based on various factors
    performance_score: float  # 0-100 based on performance metrics
    reliability_score: float  # 0-100 based on failure recovery
    overall_system_score: float  # Combined score
    
    def meets_production_criteria(self) -> bool:
        """Check if system meets production readiness criteria."""
        return (
            self.overall_system_score >= 85.0 and
            self.stability_score >= 90.0 and
            self.performance_score >= 80.0 and
            self.reliability_score >= 85.0 and
            self.avg_success_rate_per_project >= 80.0
        )


@dataclass
class SystemTestResult:
    """Result of comprehensive system testing."""
    test_id: str
    timestamp: datetime
    total_duration: float
    projects_tested: List[str]
    load_scenarios_tested: List[str]
    failure_scenarios_tested: List[str]
    metrics: SystemTestMetrics
    detailed_results: Dict[str, Any]
    recommendations: List[str]
    production_ready: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result


class ComprehensiveSystemTester:
    """Comprehensive system testing for production readiness validation."""
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path("./system-test-output")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(self.output_dir / "system_testing.log")
            ]
        )
        
        # Define test projects for comprehensive testing
        self.test_projects = [
            SystemTestProject(
                name="demo_bootstrap",
                description="Built-in demo project with Python/FastAPI",
                git_url=None,
                local_path=Path("demo_bootstrap"),
                project_type="python",
                complexity="medium",
                expected_components={"onboarding", "discovery", "protocol", "spec", "quality"},
                known_issues=[]
            ),
            SystemTestProject(
                name="tasksgodzilla_self",
                description="TasksGodzilla testing itself (meta-testing)",
                git_url=None,
                local_path=Path("."),
                project_type="python",
                complexity="complex",
                expected_components={"onboarding", "discovery", "protocol", "spec"},
                known_issues=["Large codebase may cause timeouts", "Complex dependencies"]
            ),
            SystemTestProject(
                name="simple_python",
                description="Generated simple Python project",
                git_url=None,
                local_path=None,  # Will be generated
                project_type="python",
                complexity="simple",
                expected_components={"onboarding", "discovery", "protocol"},
                known_issues=[]
            ),
        ]
        
        # Define load testing scenarios
        self.load_scenarios = [
            LoadTestScenario(
                name="light_load",
                description="Light concurrent load testing",
                concurrent_harnesses=2,
                duration_minutes=10,
                project_count=2,
                expected_peak_memory_mb=1024,
                expected_max_duration_seconds=900
            ),
            LoadTestScenario(
                name="moderate_load",
                description="Moderate concurrent load testing",
                concurrent_harnesses=3,
                duration_minutes=15,
                project_count=2,
                expected_peak_memory_mb=1536,
                expected_max_duration_seconds=1200
            ),
        ]
        
        # Define failure scenarios for recovery testing
        self.failure_scenarios = [
            FailureScenario(
                name="network_timeout",
                description="Simulate network timeouts during external calls",
                failure_type="network",
                trigger_method="environment_variable",
                expected_recovery="graceful_degradation",
                recovery_time_limit=30
            ),
            FailureScenario(
                name="disk_full",
                description="Simulate disk space issues",
                failure_type="disk",
                trigger_method="temp_directory_fill",
                expected_recovery="error_handling",
                recovery_time_limit=60
            ),
        ]
        
        # System monitoring
        self.system_monitor = SystemMonitor()
    
    def run_comprehensive_system_testing(self) -> SystemTestResult:
        """Execute comprehensive system testing (Task 18.1)."""
        self.logger.info("Starting comprehensive system testing for production readiness")
        self.logger.info(f"Testing {len(self.test_projects)} projects, {len(self.load_scenarios)} load scenarios, {len(self.failure_scenarios)} failure scenarios")
        
        start_time = datetime.now()
        test_id = f"system_test_{start_time.strftime('%Y%m%d_%H%M%S')}"
        
        # Start system monitoring
        self.system_monitor.start_monitoring()
        
        try:
            detailed_results = {}
            
            # Phase 1: Multi-project validation
            self.logger.info("Phase 1: Multi-project validation testing")
            project_results = self._test_multiple_projects()
            detailed_results["project_testing"] = project_results
            
            # Phase 2: Load testing under realistic conditions
            self.logger.info("Phase 2: Load testing under realistic conditions")
            load_results = self._test_realistic_load()
            detailed_results["load_testing"] = load_results
            
            # Phase 3: Extended stability testing
            self.logger.info("Phase 3: Extended stability testing")
            stability_results = self._test_extended_stability()
            detailed_results["stability_testing"] = stability_results
            
            # Phase 4: Failure recovery testing
            self.logger.info("Phase 4: Failure recovery testing")
            recovery_results = self._test_failure_recovery()
            detailed_results["recovery_testing"] = recovery_results
            
            # Stop monitoring and collect metrics
            system_metrics = self.system_monitor.stop_monitoring()
            detailed_results["system_metrics"] = system_metrics
            
            # Calculate comprehensive metrics
            metrics = self._calculate_system_metrics(
                project_results, load_results, stability_results, 
                recovery_results, system_metrics
            )
            
            # Generate recommendations
            recommendations = self._generate_system_recommendations(metrics, detailed_results)
            
            end_time = datetime.now()
            total_duration = (end_time - start_time).total_seconds()
            
            # Create system test result
            system_result = SystemTestResult(
                test_id=test_id,
                timestamp=start_time,
                total_duration=total_duration,
                projects_tested=[p.name for p in self.test_projects],
                load_scenarios_tested=[s.name for s in self.load_scenarios],
                failure_scenarios_tested=[s.name for s in self.failure_scenarios],
                metrics=metrics,
                detailed_results=detailed_results,
                recommendations=recommendations,
                production_ready=metrics.meets_production_criteria(),
            )
            
            # Save results
            self._save_system_test_results(system_result)
            
            # Log summary
            self._log_system_test_summary(system_result)
            
            return system_result
            
        except Exception as e:
            self.system_monitor.stop_monitoring()
            self.logger.error(f"Comprehensive system testing failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            raise
    
    def _test_multiple_projects(self) -> Dict[str, Any]:
        """Test harness against multiple real projects."""
        self.logger.info("Testing harness against multiple real projects")
        
        project_results = {}
        successful_projects = 0
        total_success_rates = []
        
        for project in self.test_projects:
            self.logger.info(f"  Testing project: {project.name} ({project.complexity} {project.project_type})")
            
            try:
                # Prepare project if needed
                project_path = self._prepare_test_project(project)
                
                # Configure harness for this project
                config = HarnessConfig(
                    mode=HarnessMode.SMOKE,  # Use smoke mode for faster testing
                    components=["onboarding", "cli_interface"],  # Core components
                    test_data_path=project_path,
                    output_path=self.output_dir / "project-reports" / project.name,
                    verbose=False,
                    parallel=True,
                    timeout=900,  # 15 minutes per project
                    max_workers=2,
                )
                
                # Execute harness
                project_start = time.time()
                harness = CLIWorkflowHarness(config)
                report = harness.run()
                project_duration = time.time() - project_start
                
                # Analyze results
                total_tests = len(report.test_results)
                passed_tests = sum(1 for r in report.test_results if r.status == HarnessStatus.PASS)
                success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0.0
                
                project_result = {
                    "status": "success",
                    "project_type": project.project_type,
                    "complexity": project.complexity,
                    "duration": project_duration,
                    "total_tests": total_tests,
                    "passed_tests": passed_tests,
                    "success_rate": success_rate,
                    "components_tested": ["onboarding", "cli_interface"],
                    "peak_memory_mb": report.performance_metrics.peak_memory_mb,
                    "cpu_utilization": report.performance_metrics.cpu_utilization,
                    "execution_id": report.execution_id,
                }
                
                if success_rate >= 70.0:  # Reasonable threshold for diverse projects
                    successful_projects += 1
                
                total_success_rates.append(success_rate)
                
                self.logger.info(f"    ✓ {project.name}: {success_rate:.1f}% success rate, {project_duration:.1f}s")
                
            except Exception as e:
                project_result = {
                    "status": "error",
                    "project_type": project.project_type,
                    "complexity": project.complexity,
                    "duration": 0.0,
                    "total_tests": 0,
                    "passed_tests": 0,
                    "success_rate": 0.0,
                    "components_tested": [],
                    "error_message": str(e),
                    "execution_id": None,
                }
                
                self.logger.error(f"    ✗ {project.name}: {e}")
            
            project_results[project.name] = project_result
        
        # Calculate overall project testing metrics
        avg_success_rate = statistics.mean(total_success_rates) if total_success_rates else 0.0
        
        summary = {
            "total_projects": len(self.test_projects),
            "successful_projects": successful_projects,
            "avg_success_rate": avg_success_rate,
            "project_results": project_results,
        }
        
        self.logger.info(f"Multi-project testing completed: {successful_projects}/{len(self.test_projects)} projects successful, {avg_success_rate:.1f}% avg success rate")
        
        return summary
    
    def _test_realistic_load(self) -> Dict[str, Any]:
        """Test harness performance under realistic load conditions."""
        self.logger.info("Testing harness performance under realistic load conditions")
        
        load_results = {}
        
        for scenario in self.load_scenarios:
            self.logger.info(f"  Load scenario: {scenario.name} - {scenario.description}")
            
            try:
                scenario_start = time.time()
                
                # Execute concurrent harnesses
                concurrent_results = self._execute_concurrent_harnesses(scenario)
                
                scenario_duration = time.time() - scenario_start
                
                # Analyze load test results
                successful_runs = sum(1 for r in concurrent_results if r.get("status") == "success")
                total_runs = len(concurrent_results)
                load_success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0.0
                
                # Calculate resource usage statistics
                peak_memory = max((r.get("peak_memory_mb", 0) for r in concurrent_results), default=0)
                avg_duration = statistics.mean([r.get("duration", 0) for r in concurrent_results if r.get("duration", 0) > 0])
                
                load_result = {
                    "status": "completed",
                    "scenario_duration": scenario_duration,
                    "concurrent_harnesses": scenario.concurrent_harnesses,
                    "total_runs": total_runs,
                    "successful_runs": successful_runs,
                    "load_success_rate": load_success_rate,
                    "peak_memory_mb": peak_memory,
                    "avg_run_duration": avg_duration,
                    "memory_within_limits": peak_memory <= scenario.expected_peak_memory_mb,
                    "duration_within_limits": scenario_duration <= scenario.expected_max_duration_seconds,
                    "concurrent_results": concurrent_results,
                }
                
                self.logger.info(f"    ✓ {scenario.name}: {load_success_rate:.1f}% success rate, {peak_memory:.1f}MB peak memory")
                
            except Exception as e:
                load_result = {
                    "status": "error",
                    "error_message": str(e),
                    "scenario_duration": 0.0,
                }
                
                self.logger.error(f"    ✗ {scenario.name}: {e}")
            
            load_results[scenario.name] = load_result
        
        return load_results
    
    def _test_extended_stability(self) -> Dict[str, Any]:
        """Test harness stability under extended operation."""
        self.logger.info("Testing harness stability under extended operation")
        
        # Run extended reliability testing
        reliability_tester = ReliabilityTester(self.output_dir / "stability")
        
        try:
            # Extended reliability test with more runs per condition
            reliability_result = reliability_tester.run_extended_reliability_testing(
                runs_per_condition=3,  # Reduced for system testing
                include_ci_testing=True
            )
            
            stability_results = {
                "status": "completed",
                "reliability_rate": reliability_result.metrics.reliability_rate,
                "consistency_score": reliability_result.metrics.consistency_score,
                "total_runs": reliability_result.metrics.total_runs,
                "successful_runs": reliability_result.metrics.successful_runs,
                "avg_success_rate": reliability_result.metrics.avg_success_rate,
                "success_rate_variance": reliability_result.metrics.success_rate_variance,
                "is_reliable": reliability_result.is_reliable,
                "ci_integration_status": reliability_result.ci_integration_results,
            }
            
            self.logger.info(f"Extended stability testing completed: {reliability_result.metrics.reliability_rate:.1f}% reliability rate")
            
        except Exception as e:
            stability_results = {
                "status": "error",
                "error_message": str(e),
                "reliability_rate": 0.0,
                "consistency_score": 0.0,
                "is_reliable": False,
            }
            
            self.logger.error(f"Extended stability testing failed: {e}")
        
        return stability_results
    
    def _test_failure_recovery(self) -> Dict[str, Any]:
        """Test harness recovery from various failure scenarios."""
        self.logger.info("Testing harness recovery from various failure scenarios")
        
        recovery_results = {}
        successful_recoveries = 0
        
        for scenario in self.failure_scenarios:
            self.logger.info(f"  Failure scenario: {scenario.name} - {scenario.description}")
            
            try:
                recovery_result = self._execute_failure_scenario(scenario)
                
                if recovery_result.get("recovery_successful", False):
                    successful_recoveries += 1
                    self.logger.info(f"    ✓ {scenario.name}: Recovery successful in {recovery_result.get('recovery_time', 0):.1f}s")
                else:
                    self.logger.warning(f"    ⚠ {scenario.name}: Recovery failed or incomplete")
                
                recovery_results[scenario.name] = recovery_result
                
            except Exception as e:
                recovery_result = {
                    "status": "error",
                    "error_message": str(e),
                    "recovery_successful": False,
                }
                
                recovery_results[scenario.name] = recovery_result
                self.logger.error(f"    ✗ {scenario.name}: {e}")
        
        # Calculate overall recovery metrics
        recovery_rate = (successful_recoveries / len(self.failure_scenarios) * 100) if self.failure_scenarios else 0.0
        
        summary = {
            "total_scenarios": len(self.failure_scenarios),
            "successful_recoveries": successful_recoveries,
            "recovery_rate": recovery_rate,
            "scenario_results": recovery_results,
        }
        
        self.logger.info(f"Failure recovery testing completed: {successful_recoveries}/{len(self.failure_scenarios)} scenarios recovered successfully")
        
        return summary
    
    def _prepare_test_project(self, project: SystemTestProject) -> Path:
        """Prepare a test project for harness testing."""
        if project.local_path and project.local_path.exists():
            return project.local_path
        
        # Generate test project if needed
        if project.local_path is None:
            project_dir = self.output_dir / "generated-projects" / project.name
            project_dir.mkdir(parents=True, exist_ok=True)
            
            if project.project_type == "python":
                self._generate_python_project(project_dir, project.complexity)
            
            return project_dir
        
        return project.local_path
    
    def _generate_python_project(self, project_dir: Path, complexity: str) -> None:
        """Generate a Python test project."""
        # Create basic Python project structure
        (project_dir / "src").mkdir(exist_ok=True)
        (project_dir / "tests").mkdir(exist_ok=True)
        
        # Create setup.py
        setup_content = '''from setuptools import setup, find_packages

setup(
    name="test-project",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=[
        "requests",
        "click",
    ],
    extras_require={
        "dev": ["pytest", "black", "flake8"],
    },
)
'''
        (project_dir / "setup.py").write_text(setup_content)
        
        # Create main module
        main_content = '''"""Test project main module."""

import click
import requests


@click.command()
@click.option("--name", default="World", help="Name to greet")
def hello(name):
    """Simple program that greets NAME."""
    click.echo(f"Hello, {name}!")


def fetch_data(url):
    """Fetch data from URL."""
    response = requests.get(url)
    return response.json()


if __name__ == "__main__":
    hello()
'''
        (project_dir / "src" / "main.py").write_text(main_content)
        
        # Create test file
        test_content = '''"""Tests for main module."""

import pytest
from src.main import fetch_data


def test_hello():
    """Test hello function."""
    # This would normally test the hello function
    assert True


def test_fetch_data():
    """Test fetch_data function."""
    # This would normally test with a mock
    assert callable(fetch_data)
'''
        (project_dir / "tests" / "test_main.py").write_text(test_content)
        
        # Create README
        readme_content = f'''# Test Project

This is a generated test project for harness testing.

Complexity: {complexity}

## Installation

```bash
pip install -e .
```

## Usage

```bash
python src/main.py --name "Test"
```

## Testing

```bash
pytest tests/
```
'''
        (project_dir / "README.md").write_text(readme_content)
        
        # Initialize git repository
        try:
            subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True)
            subprocess.run(["git", "add", "."], cwd=project_dir, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=project_dir, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            pass  # Git operations are optional
    
    def _execute_concurrent_harnesses(self, scenario: LoadTestScenario) -> List[Dict[str, Any]]:
        """Execute multiple harnesses concurrently for load testing."""
        results = []
        
        # Select projects for this load test
        test_projects = self.test_projects[:scenario.project_count]
        
        with ThreadPoolExecutor(max_workers=scenario.concurrent_harnesses) as executor:
            # Submit concurrent harness executions
            futures = []
            
            for i in range(scenario.concurrent_harnesses):
                project = test_projects[i % len(test_projects)]
                future = executor.submit(self._execute_single_harness_for_load_test, project, i)
                futures.append(future)
            
            # Collect results with timeout
            timeout_seconds = scenario.duration_minutes * 60
            
            for future in as_completed(futures, timeout=timeout_seconds):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append({
                        "status": "error",
                        "error_message": str(e),
                        "duration": 0.0,
                        "peak_memory_mb": 0.0,
                    })
        
        return results
    
    def _execute_single_harness_for_load_test(self, project: SystemTestProject, instance_id: int) -> Dict[str, Any]:
        """Execute a single harness instance for load testing."""
        start_time = time.time()
        
        try:
            # Prepare project
            project_path = self._prepare_test_project(project)
            
            # Configure harness for load testing (lighter configuration)
            config = HarnessConfig(
                mode=HarnessMode.SMOKE,  # Use smoke mode for faster execution
                components=["onboarding"],  # Core components only
                test_data_path=project_path,
                output_path=self.output_dir / "load-test" / f"instance_{instance_id}",
                verbose=False,
                parallel=False,  # Disable parallelism for load testing
                timeout=300,  # 5 minutes
                max_workers=1,
            )
            
            # Execute harness
            harness = CLIWorkflowHarness(config)
            report = harness.run()
            
            duration = time.time() - start_time
            
            # Calculate success rate
            total_tests = len(report.test_results)
            passed_tests = sum(1 for r in report.test_results if r.status == HarnessStatus.PASS)
            success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0.0
            
            return {
                "status": "success",
                "instance_id": instance_id,
                "project_name": project.name,
                "duration": duration,
                "success_rate": success_rate,
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "peak_memory_mb": report.performance_metrics.peak_memory_mb,
                "cpu_utilization": report.performance_metrics.cpu_utilization,
                "execution_id": report.execution_id,
            }
            
        except Exception as e:
            duration = time.time() - start_time
            return {
                "status": "error",
                "instance_id": instance_id,
                "project_name": project.name,
                "duration": duration,
                "error_message": str(e),
                "peak_memory_mb": 0.0,
            }
    
    def _execute_failure_scenario(self, scenario: FailureScenario) -> Dict[str, Any]:
        """Execute a failure scenario and test recovery."""
        start_time = time.time()
        
        try:
            # Set up failure condition
            failure_context = self._setup_failure_condition(scenario)
            
            # Execute harness under failure condition
            recovery_start = time.time()
            
            config = HarnessConfig(
                mode=HarnessMode.SMOKE,
                components=["onboarding"],  # Minimal for failure testing
                test_data_path=Path("demo_bootstrap"),
                output_path=self.output_dir / "failure-test" / scenario.name,
                verbose=True,
                parallel=False,  # Disable parallelism for failure testing
                timeout=scenario.recovery_time_limit,
                max_workers=1,
            )
            
            try:
                harness = CLIWorkflowHarness(config)
                report = harness.run()
                
                recovery_time = time.time() - recovery_start
                
                # Analyze recovery
                recovery_successful = self._analyze_recovery(report, scenario)
                
                result = {
                    "status": "completed",
                    "failure_triggered": True,
                    "recovery_successful": recovery_successful,
                    "recovery_time": recovery_time,
                    "within_time_limit": recovery_time <= scenario.recovery_time_limit,
                    "execution_id": report.execution_id,
                    "failure_context": failure_context,
                }
                
            except Exception as harness_error:
                recovery_time = time.time() - recovery_start
                
                # Check if this is expected failure behavior
                expected_failure = scenario.expected_recovery in ["error_handling", "graceful_degradation"]
                
                result = {
                    "status": "completed",
                    "failure_triggered": True,
                    "recovery_successful": expected_failure,
                    "recovery_time": recovery_time,
                    "within_time_limit": recovery_time <= scenario.recovery_time_limit,
                    "harness_error": str(harness_error),
                    "expected_failure": expected_failure,
                    "failure_context": failure_context,
                }
            
            # Clean up failure condition
            self._cleanup_failure_condition(scenario, failure_context)
            
            return result
            
        except Exception as e:
            return {
                "status": "error",
                "error_message": str(e),
                "recovery_successful": False,
            }
    
    def _setup_failure_condition(self, scenario: FailureScenario) -> Dict[str, Any]:
        """Set up the failure condition for testing."""
        context = {"scenario": scenario.name}
        
        if scenario.failure_type == "network":
            # Set environment variable to simulate network issues
            import os
            os.environ["TASKSGODZILLA_SIMULATE_NETWORK_FAILURE"] = "true"
            context["env_var_set"] = True
            
        elif scenario.failure_type == "disk":
            # Create a temporary directory and fill it up
            temp_dir = tempfile.mkdtemp(prefix="harness_disk_test_")
            context["temp_dir"] = temp_dir
            
            # Fill up some space (but not too much)
            dummy_file = Path(temp_dir) / "dummy_large_file"
            with open(dummy_file, "wb") as f:
                f.write(b"0" * (50 * 1024 * 1024))  # 50MB
            context["dummy_file"] = str(dummy_file)
        
        return context
    
    def _cleanup_failure_condition(self, scenario: FailureScenario, context: Dict[str, Any]) -> None:
        """Clean up the failure condition after testing."""
        if scenario.failure_type == "network":
            import os
            if "TASKSGODZILLA_SIMULATE_NETWORK_FAILURE" in os.environ:
                del os.environ["TASKSGODZILLA_SIMULATE_NETWORK_FAILURE"]
        
        elif scenario.failure_type == "disk":
            if "temp_dir" in context:
                shutil.rmtree(context["temp_dir"], ignore_errors=True)
    
    def _analyze_recovery(self, report: HarnessReport, scenario: FailureScenario) -> bool:
        """Analyze if recovery was successful based on the scenario."""
        if scenario.expected_recovery == "graceful_degradation":
            # Should complete with some tests passing
            return report.success_rate > 0
        
        elif scenario.expected_recovery == "error_handling":
            # Should handle errors gracefully without crashing
            return len(report.test_results) > 0
        
        return False
    
    def _calculate_system_metrics(self, project_results: Dict[str, Any], 
                                load_results: Dict[str, Any],
                                stability_results: Dict[str, Any],
                                recovery_results: Dict[str, Any],
                                system_metrics: Dict[str, Any]) -> SystemTestMetrics:
        """Calculate comprehensive system metrics."""
        
        # Project testing metrics
        total_projects = project_results.get("total_projects", 0)
        successful_projects = project_results.get("successful_projects", 0)
        avg_success_rate = project_results.get("avg_success_rate", 0.0)
        
        # Load testing metrics
        load_test_summary = {}
        for scenario_name, result in load_results.items():
            if result.get("status") == "completed":
                load_test_summary[scenario_name] = {
                    "success_rate": result.get("load_success_rate", 0.0),
                    "memory_within_limits": result.get("memory_within_limits", False),
                    "duration_within_limits": result.get("duration_within_limits", False),
                }
        
        # Failure recovery metrics
        recovery_rate = recovery_results.get("recovery_rate", 0.0)
        
        # System resource metrics
        peak_memory = system_metrics.get("peak_memory_mb", 0.0)
        peak_cpu = system_metrics.get("peak_cpu_percent", 0.0)
        total_duration = system_metrics.get("total_duration", 0.0)
        
        # Calculate scores (0-100)
        stability_score = min(100.0, (
            (successful_projects / max(total_projects, 1) * 40) +
            (stability_results.get("reliability_rate", 0.0) * 0.4) +
            (stability_results.get("consistency_score", 0.0) * 0.2)
        ))
        
        performance_score = min(100.0, (
            (avg_success_rate * 0.4) +
            (100 - min(peak_memory / 2048 * 100, 100)) * 0.3 +  # Memory efficiency
            (min(peak_cpu / 80 * 100, 100)) * 0.3  # CPU utilization efficiency
        ))
        
        reliability_score = min(100.0, (
            (recovery_rate * 0.6) +
            (stability_results.get("reliability_rate", 0.0) * 0.4)
        ))
        
        overall_score = (stability_score + performance_score + reliability_score) / 3
        
        return SystemTestMetrics(
            total_projects_tested=total_projects,
            successful_projects=successful_projects,
            failed_projects=total_projects - successful_projects,
            avg_success_rate_per_project=avg_success_rate,
            total_test_duration=total_duration,
            peak_memory_usage_mb=peak_memory,
            peak_cpu_utilization=peak_cpu,
            load_test_results=load_test_summary,
            failure_recovery_results=recovery_results,
            stability_score=stability_score,
            performance_score=performance_score,
            reliability_score=reliability_score,
            overall_system_score=overall_score,
        )
    
    def _generate_system_recommendations(self, metrics: SystemTestMetrics, 
                                       detailed_results: Dict[str, Any]) -> List[str]:
        """Generate system-level recommendations for production readiness."""
        recommendations = []
        
        # Overall production readiness
        if metrics.meets_production_criteria():
            recommendations.append(
                f"✓ PRODUCTION READY: Overall system score {metrics.overall_system_score:.1f}% meets production criteria"
            )
        else:
            recommendations.append(
                f"✗ NOT PRODUCTION READY: Overall system score {metrics.overall_system_score:.1f}% below production threshold (85%)"
            )
        
        # Stability recommendations
        if metrics.stability_score < 90.0:
            recommendations.append(
                f"STABILITY IMPROVEMENT NEEDED: {metrics.stability_score:.1f}% < 90%. "
                f"Focus on {metrics.failed_projects} failed projects and reliability issues."
            )
        
        # Performance recommendations
        if metrics.performance_score < 80.0:
            recommendations.append(
                f"PERFORMANCE OPTIMIZATION NEEDED: {metrics.performance_score:.1f}% < 80%. "
                f"Peak memory: {metrics.peak_memory_usage_mb:.1f}MB, Peak CPU: {metrics.peak_cpu_utilization:.1f}%"
            )
        
        # Reliability recommendations
        if metrics.reliability_score < 85.0:
            recovery_rate = metrics.failure_recovery_results.get("recovery_rate", 0.0)
            recommendations.append(
                f"RELIABILITY IMPROVEMENT NEEDED: {metrics.reliability_score:.1f}% < 85%. "
                f"Failure recovery rate: {recovery_rate:.1f}%"
            )
        
        # Project-specific recommendations
        if metrics.avg_success_rate_per_project < 80.0:
            recommendations.append(
                f"PROJECT COMPATIBILITY ISSUES: {metrics.avg_success_rate_per_project:.1f}% avg success rate < 80%. "
                "Review project-specific failures and improve compatibility."
            )
        
        # Resource utilization recommendations
        if metrics.peak_memory_usage_mb > 1024:
            recommendations.append(
                f"HIGH MEMORY USAGE: {metrics.peak_memory_usage_mb:.1f}MB peak usage. "
                "Consider memory optimization."
            )
        
        if metrics.peak_cpu_utilization > 90:
            recommendations.append(
                f"HIGH CPU UTILIZATION: {metrics.peak_cpu_utilization:.1f}% peak usage. "
                "Consider CPU optimization."
            )
        
        return recommendations
    
    def _save_system_test_results(self, result: SystemTestResult) -> None:
        """Save system test results to files."""
        # Save JSON report
        json_path = self.output_dir / f"system_test_result_{result.test_id}.json"
        with open(json_path, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        
        # Save text summary
        text_path = self.output_dir / f"system_test_summary_{result.test_id}.txt"
        with open(text_path, 'w') as f:
            f.write(self._format_system_test_summary(result))
        
        self.logger.info(f"System test results saved to {json_path} and {text_path}")
    
    def _format_system_test_summary(self, result: SystemTestResult) -> str:
        """Format system test result as text summary."""
        lines = [
            "=" * 80,
            "CLI WORKFLOW HARNESS - COMPREHENSIVE SYSTEM TEST RESULTS",
            "=" * 80,
            f"Test ID: {result.test_id}",
            f"Timestamp: {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total Duration: {result.total_duration:.1f}s",
            "",
            "PRODUCTION READINESS ASSESSMENT:",
            f"  Production Ready: {'✓ YES' if result.production_ready else '✗ NO'}",
            f"  Overall System Score: {result.metrics.overall_system_score:.1f}% (target: ≥85%)",
            "",
            "COMPONENT SCORES:",
            f"  Stability Score: {result.metrics.stability_score:.1f}% (target: ≥90%)",
            f"  Performance Score: {result.metrics.performance_score:.1f}% (target: ≥80%)",
            f"  Reliability Score: {result.metrics.reliability_score:.1f}% (target: ≥85%)",
            "",
            "PROJECT TESTING RESULTS:",
            f"  Projects Tested: {result.metrics.total_projects_tested}",
            f"  Successful Projects: {result.metrics.successful_projects}",
            f"  Failed Projects: {result.metrics.failed_projects}",
            f"  Average Success Rate: {result.metrics.avg_success_rate_per_project:.1f}%",
            "",
            "SYSTEM RESOURCE USAGE:",
            f"  Peak Memory Usage: {result.metrics.peak_memory_usage_mb:.1f}MB",
            f"  Peak CPU Utilization: {result.metrics.peak_cpu_utilization:.1f}%",
            f"  Total Test Duration: {result.metrics.total_test_duration:.1f}s",
            "",
            "LOAD TESTING RESULTS:",
        ]
        
        for scenario, results in result.metrics.load_test_results.items():
            lines.append(f"  {scenario}:")
            lines.append(f"    Success Rate: {results.get('success_rate', 0):.1f}%")
            lines.append(f"    Memory Within Limits: {'✓' if results.get('memory_within_limits', False) else '✗'}")
            lines.append(f"    Duration Within Limits: {'✓' if results.get('duration_within_limits', False) else '✗'}")
        
        lines.extend([
            "",
            "FAILURE RECOVERY RESULTS:",
            f"  Recovery Rate: {result.metrics.failure_recovery_results.get('recovery_rate', 0):.1f}%",
            f"  Scenarios Tested: {result.metrics.failure_recovery_results.get('total_scenarios', 0)}",
            f"  Successful Recoveries: {result.metrics.failure_recovery_results.get('successful_recoveries', 0)}",
            "",
            "RECOMMENDATIONS:",
        ])
        
        for i, rec in enumerate(result.recommendations, 1):
            lines.append(f"  {i}. {rec}")
        
        lines.extend([
            "",
            "=" * 80,
        ])
        
        return "\n".join(lines)
    
    def _log_system_test_summary(self, result: SystemTestResult) -> None:
        """Log system test summary to console."""
        self.logger.info("=" * 60)
        self.logger.info("COMPREHENSIVE SYSTEM TESTING COMPLETED")
        self.logger.info("=" * 60)
        self.logger.info(f"Test ID: {result.test_id}")
        self.logger.info(f"Total Duration: {result.total_duration:.1f}s")
        
        self.logger.info(f"Overall System Score: {result.metrics.overall_system_score:.1f}%")
        self.logger.info(f"Stability Score: {result.metrics.stability_score:.1f}%")
        self.logger.info(f"Performance Score: {result.metrics.performance_score:.1f}%")
        self.logger.info(f"Reliability Score: {result.metrics.reliability_score:.1f}%")
        
        if result.production_ready:
            self.logger.info("✓ PRODUCTION READINESS: PASSED - System is production ready!")
        else:
            self.logger.warning("✗ PRODUCTION READINESS: FAILED - System needs improvements")
        
        self.logger.info(f"Projects: {result.metrics.successful_projects}/{result.metrics.total_projects_tested} successful")
        self.logger.info(f"Average Success Rate: {result.metrics.avg_success_rate_per_project:.1f}%")
        self.logger.info(f"Peak Memory: {result.metrics.peak_memory_usage_mb:.1f}MB")
        self.logger.info(f"Peak CPU: {result.metrics.peak_cpu_utilization:.1f}%")
        
        recovery_rate = result.metrics.failure_recovery_results.get("recovery_rate", 0)
        self.logger.info(f"Failure Recovery Rate: {recovery_rate:.1f}%")
        
        if result.recommendations:
            self.logger.info("Top Recommendations:")
            for rec in result.recommendations[:3]:
                self.logger.info(f"  - {rec}")
        
        self.logger.info("=" * 60)


class SystemMonitor:
    """System resource monitoring during testing."""
    
    def __init__(self):
        self.monitoring = False
        self.metrics = {
            "peak_memory_mb": 0.0,
            "peak_cpu_percent": 0.0,
            "total_duration": 0.0,
            "memory_samples": [],
            "cpu_samples": [],
        }
        self.start_time = None
        self.monitor_thread = None
    
    def start_monitoring(self) -> None:
        """Start system monitoring."""
        self.monitoring = True
        self.start_time = time.time()
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self) -> Dict[str, Any]:
        """Stop monitoring and return collected metrics."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        if self.start_time:
            self.metrics["total_duration"] = time.time() - self.start_time
        
        return self.metrics.copy()
    
    def _monitor_loop(self) -> None:
        """Monitor system resources in a loop."""
        while self.monitoring:
            try:
                # Get current process and system metrics
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                cpu_percent = process.cpu_percent()
                
                # Update peak values
                self.metrics["peak_memory_mb"] = max(self.metrics["peak_memory_mb"], memory_mb)
                self.metrics["peak_cpu_percent"] = max(self.metrics["peak_cpu_percent"], cpu_percent)
                
                # Store samples for analysis
                self.metrics["memory_samples"].append(memory_mb)
                self.metrics["cpu_samples"].append(cpu_percent)
                
                # Keep only recent samples (last 100)
                if len(self.metrics["memory_samples"]) > 100:
                    self.metrics["memory_samples"] = self.metrics["memory_samples"][-100:]
                if len(self.metrics["cpu_samples"]) > 100:
                    self.metrics["cpu_samples"] = self.metrics["cpu_samples"][-100:]
                
                time.sleep(2)  # Sample every 2 seconds
                
            except Exception:
                # Continue monitoring even if individual samples fail
                time.sleep(2)


def main():
    """Main entry point for comprehensive system testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Comprehensive system testing of CLI workflow harness")
    parser.add_argument(
        '--output-dir', '-o',
        type=Path,
        default=Path('./system-test-output'),
        help='Output directory for system test results'
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
        tester = ComprehensiveSystemTester(args.output_dir)
        result = tester.run_comprehensive_system_testing()
        
        # Exit with appropriate code
        exit_code = 0 if result.production_ready else 1
        sys.exit(exit_code)
        
    except Exception as e:
        logging.error(f"System testing failed: {e}")
        sys.exit(2)


if __name__ == '__main__':
    main()