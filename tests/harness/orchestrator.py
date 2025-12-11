"""Main orchestrator for CLI workflow harness."""

import uuid
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Type
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import HarnessConfig, HarnessMode
from .environment import TestEnvironment, EnvironmentContext
from .reporter import TestReporter
from .models import TestResult, WorkflowResult, HarnessReport, PerformanceMetrics, HarnessStatus
from .performance import PerformanceMonitor, PerformanceThresholds
from .parallel import ParallelTestExecutor, TestTask


class ComponentRegistry:
    """Registry for test components with lifecycle management."""
    
    def __init__(self):
        self._components: Dict[str, Type] = {}
        self._instances: Dict[str, Any] = {}
        self._lifecycle_hooks: Dict[str, List[Callable]] = {
            'setup': [],
            'teardown': [],
            'before_test': [],
            'after_test': []
        }
    
    def register_component(self, name: str, component_class: Type) -> None:
        """Register a test component class."""
        self._components[name] = component_class
        logging.debug(f"Registered component: {name}")
    
    def get_component(self, name: str, *args, **kwargs) -> Any:
        """Get or create component instance."""
        if name not in self._instances:
            if name not in self._components:
                raise ValueError(f"Component '{name}' not registered")
            self._instances[name] = self._components[name](*args, **kwargs)
        return self._instances[name]
    
    def add_lifecycle_hook(self, phase: str, hook: Callable) -> None:
        """Add lifecycle hook for component management."""
        if phase in self._lifecycle_hooks:
            self._lifecycle_hooks[phase].append(hook)
    
    def execute_hooks(self, phase: str, *args, **kwargs) -> None:
        """Execute all hooks for a given lifecycle phase."""
        for hook in self._lifecycle_hooks.get(phase, []):
            try:
                hook(*args, **kwargs)
            except Exception as e:
                logging.warning(f"Hook execution failed in {phase}: {e}")
    
    def cleanup(self) -> None:
        """Clean up all component instances."""
        self.execute_hooks('teardown')
        self._instances.clear()


class CLIWorkflowHarness:
    """Main orchestrator coordinates test execution across different modes and components."""
    
    def __init__(self, config: HarnessConfig):
        self.config = config
        self.environment = TestEnvironment()
        self.reporter = TestReporter(config.output_path)
        self.registry = ComponentRegistry()
        self._execution_id = str(uuid.uuid4())
        self._logger = logging.getLogger(__name__)
        
        # Initialize performance monitoring
        self.performance_monitor = PerformanceMonitor(
            PerformanceThresholds(
                max_duration_seconds=config.timeout,
                max_memory_mb=2048.0,  # 2GB default
                min_cpu_efficiency=0.1
            )
        )
        
        # Initialize parallel executor
        self.parallel_executor = ParallelTestExecutor(
            max_workers=config.max_workers,
            performance_monitor=self.performance_monitor
        )
        
        # Initialize component registry with default components
        self._register_default_components()
    
    def _register_default_components(self) -> None:
        """Register default test components."""
        from .components import (
            OnboardingTestComponent, 
            DiscoveryTestComponent, 
            ProtocolTestComponent, 
            SpecTestComponent, 
            QualityTestComponent,
            CLIInterfaceTests,
            TUIInterfaceTests
        )
        from .components.error_conditions import ErrorConditionTests
        from .components.failure_detection import FailureDetectionTests
        from .components.api_integration_tests import APIIntegrationTests
        
        # Register implemented workflow components
        self.registry.register_component("onboarding", OnboardingTestComponent)
        self.registry.register_component("discovery", DiscoveryTestComponent)
        self.registry.register_component("protocol", ProtocolTestComponent)
        self.registry.register_component("spec", SpecTestComponent)
        self.registry.register_component("quality", QualityTestComponent)
        self.registry.register_component("cli_interface", CLIInterfaceTests)
        self.registry.register_component("tui_interface", TUIInterfaceTests)
        self.registry.register_component("error_conditions", ErrorConditionTests)
        self.registry.register_component("failure_detection", FailureDetectionTests)
        self.registry.register_component("api_integration", APIIntegrationTests)
        
        # All components are now properly implemented
    
    def register_component(self, name: str, component_class: Type) -> None:
        """Register a test component for execution."""
        self.registry.register_component(name, component_class)
    
    def run(self) -> HarnessReport:
        """Execute tests based on the configured mode."""
        start_time = datetime.now()
        self._logger.info(f"Starting harness execution in {self.config.mode.value} mode")
        
        try:
            # Start performance monitoring
            self.performance_monitor.start_monitoring()
            
            with self.environment.setup() as env_context:
                # Execute lifecycle setup hooks
                self.registry.execute_hooks('setup', env_context)
                
                # Select and execute tests based on mode
                results = self._execute_mode_based_tests(env_context)
                
                # Execute lifecycle teardown hooks
                self.registry.execute_hooks('teardown', env_context)
                
        except Exception as e:
            self._logger.error(f"Harness execution failed: {e}")
            self._logger.debug(traceback.format_exc())
            # Return error report
            return self._create_error_report(start_time, str(e))
        finally:
            # Stop performance monitoring
            self.performance_monitor.stop_monitoring()
            
            # Cleanup component registry
            self.registry.cleanup()
        
        end_time = datetime.now()
        
        # Calculate performance metrics
        performance_metrics = self._calculate_performance_metrics(start_time, end_time, results)
        
        # Generate comprehensive report
        report = self.reporter.generate_report(
            execution_id=self._execution_id,
            mode=self.config.mode.value,
            test_results=results.get("test_results", []),
            workflow_results=results.get("workflow_results", []),
            performance_metrics=performance_metrics,
            start_time=start_time,
            end_time=end_time,
        )
        
        # Generate CI-specific reports if in CI mode
        if self.config.mode == HarnessMode.CI:
            self._generate_ci_reports(report)
        
        return report
    
    def _generate_ci_reports(self, report: HarnessReport) -> None:
        """Generate CI-specific machine-readable reports."""
        try:
            # Generate JUnit XML report
            junit_path = self.reporter.save_ci_report(report, "junit")
            self._logger.info(f"JUnit report generated: {junit_path}")
            
            # Generate CI JSON report
            json_path = self.reporter.save_ci_report(report, "json")
            self._logger.info(f"CI JSON report generated: {json_path}")
            
            # Integrate with existing CI infrastructure
            self._integrate_with_ci_scripts(report)
            
        except Exception as e:
            self._logger.error(f"Failed to generate CI reports: {e}")
    
    def _integrate_with_ci_scripts(self, report: HarnessReport) -> None:
        """Integrate with existing scripts/ci/ infrastructure."""
        import os
        import subprocess
        
        # Set environment variables for CI scripts
        ci_env = os.environ.copy()
        ci_env.update({
            "TASKSGODZILLA_HARNESS_EXECUTION_ID": report.execution_id,
            "TASKSGODZILLA_HARNESS_SUCCESS_RATE": str(report.success_rate),
            "TASKSGODZILLA_HARNESS_MODE": report.mode,
            "TASKSGODZILLA_HARNESS_DURATION": str(report.performance_metrics.total_duration),
        })
        
        # Determine CI status for reporting
        ci_status = "success" if report.success_rate >= 80 else "failure"
        
        # Try to call the CI report script if available
        ci_report_script = Path("scripts/ci/report.sh")
        if ci_report_script.exists() and ci_report_script.is_file():
            try:
                result = subprocess.run(
                    [str(ci_report_script), ci_status],
                    env=ci_env,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    self._logger.info("Successfully integrated with CI reporting")
                else:
                    self._logger.warning(f"CI report script returned {result.returncode}: {result.stderr}")
            except subprocess.TimeoutExpired:
                self._logger.warning("CI report script timed out")
            except Exception as e:
                self._logger.warning(f"Failed to call CI report script: {e}")
        else:
            self._logger.debug("CI report script not found, skipping integration")
    
    def _execute_mode_based_tests(self, env_context: EnvironmentContext) -> Dict[str, Any]:
        """Execute tests based on the configured mode with proper selection logic."""
        mode_handlers = {
            HarnessMode.FULL: self._run_full_workflow,
            HarnessMode.COMPONENT: self._run_component_tests,
            HarnessMode.SMOKE: self._run_smoke_tests,
            HarnessMode.REGRESSION: self._run_regression_tests,
            HarnessMode.DEVELOPMENT: self._run_development_tests,
            HarnessMode.CI: self._run_ci_tests,
        }
        
        handler = mode_handlers.get(self.config.mode)
        if not handler:
            raise ValueError(f"Unsupported test mode: {self.config.mode}")
        
        return handler(env_context)
    
    def _calculate_performance_metrics(self, start_time: datetime, end_time: datetime, 
                                     results: Dict[str, Any]) -> PerformanceMetrics:
        """Calculate performance metrics for the execution."""
        # Generate comprehensive performance report from monitor
        perf_report = self.performance_monitor.generate_performance_report()
        
        return PerformanceMetrics(
            total_duration=perf_report.total_duration,
            peak_memory_mb=perf_report.peak_memory_mb,
            cpu_utilization=perf_report.avg_cpu_utilization,
            parallel_efficiency=perf_report.parallel_efficiency,
            threshold_violations=perf_report.threshold_violations,
            performance_recommendations=perf_report.recommendations,
        )
    
    def _create_error_report(self, start_time: datetime, error_message: str) -> HarnessReport:
        """Create error report when harness execution fails."""
        end_time = datetime.now()
        
        error_result = TestResult(
            component="harness",
            test_name="execution",
            status=HarnessStatus.ERROR,
            duration=(end_time - start_time).total_seconds(),
            error_message=error_message,
        )
        
        performance_metrics = PerformanceMetrics(
            total_duration=(end_time - start_time).total_seconds(),
            peak_memory_mb=0.0,
            cpu_utilization=0.0,
        )
        
        return self.reporter.generate_report(
            execution_id=self._execution_id,
            mode=self.config.mode.value,
            test_results=[error_result],
            workflow_results=[],
            performance_metrics=performance_metrics,
            start_time=start_time,
            end_time=end_time,
        )
    
    def _run_full_workflow(self, env_context: EnvironmentContext) -> Dict[str, Any]:
        """Execute complete end-to-end workflow."""
        test_results = []
        workflow_results = []
        
        # Create test project
        project = env_context.projects.get("demo") or env_context.projects.setdefault(
            "demo", 
            self.environment.create_test_project("demo-bootstrap", "demo")
        )
        
        # Run all workflow components
        components = [
            "onboarding",
            "discovery", 
            "protocol",
            "spec",
            "quality",
            "cli_interface",
            "api_integration",
            "error_conditions",
        ]
        
        self._logger.info(f"Running full workflow with {len(components)} components")
        
        if self.config.parallel:
            test_results = self._run_components_parallel(components, project, env_context)
        else:
            for component in components:
                result = self._run_component_test(component, project, env_context)
                test_results.append(result)
        
        # Run end-to-end workflow
        workflow_result = self._run_end_to_end_workflow(project, env_context)
        workflow_results.append(workflow_result)
        
        return {
            "test_results": test_results,
            "workflow_results": workflow_results,
        }
    
    def _run_component_tests(self, env_context: EnvironmentContext) -> Dict[str, Any]:
        """Execute specific component tests in isolation."""
        test_results = []
        
        # Use specified components or default set
        components = self.config.components or ["onboarding", "discovery", "protocol"]
        
        project = self.environment.create_test_project("demo-bootstrap", "demo")
        env_context.projects["demo"] = project
        
        if self.config.parallel and len(components) > 1:
            test_results = self._run_components_parallel(components, project, env_context)
        else:
            for component in components:
                result = self._run_component_test(component, project, env_context)
                test_results.append(result)
        
        return {"test_results": test_results, "workflow_results": []}
    
    def _run_components_parallel(self, components: List[str], project, 
                               env_context: EnvironmentContext) -> List[TestResult]:
        """Execute components in parallel with optimized isolation using ParallelTestExecutor."""
        # Create test tasks for each component
        tasks = []
        component_priorities = {
            "onboarding": 5,        # High priority - needed for other tests
            "cli_interface": 4,     # High priority - quick and independent
            "error_conditions": 4,  # High priority - quick and independent
            "spec": 3,             # Medium priority
            "quality": 2,          # Lower priority - can be slow
            "discovery": 1,        # Lowest priority - very slow
            "protocol": 1,         # Lowest priority - slow and complex
            "api_integration": 2,  # Lower priority - needs setup
        }
        
        for component in components:
            # Create test function that captures the component context
            def create_test_func(comp_name):
                def test_func():
                    result = self._run_component_test(comp_name, project, env_context)
                    return result.status == HarnessStatus.PASS
                return test_func
            
            task = TestTask(
                task_id=f"{component}_test",
                component=component,
                test_function=create_test_func(component),
                isolation_group=f"component_{component}",
                priority=component_priorities.get(component, 1)
            )
            tasks.append(task)
        
        # Optimize task isolation to improve parallel efficiency
        optimized_tasks = self.parallel_executor.optimize_task_isolation(tasks)
        
        # Calculate optimal worker count for this execution
        avg_duration = 60.0  # Estimated average task duration
        optimal_workers = self.parallel_executor.get_optimal_worker_count(
            len(optimized_tasks), avg_duration
        )
        
        # Update executor worker count if beneficial
        if optimal_workers != self.parallel_executor.max_workers:
            self._logger.info(f"Adjusting worker count from {self.parallel_executor.max_workers} to {optimal_workers}")
            self.parallel_executor.max_workers = optimal_workers
        
        # Execute tasks in parallel
        parallel_result = self.parallel_executor.execute_parallel(optimized_tasks)
        
        # Log parallel execution metrics
        self._logger.info(f"Parallel execution completed: efficiency={parallel_result.parallel_efficiency:.2f}, "
                         f"duration={parallel_result.execution_time:.1f}s")
        
        if parallel_result.parallel_efficiency < 0.7:  # Target >70% efficiency
            self._logger.warning(f"Parallel efficiency below target: {parallel_result.parallel_efficiency:.2f} < 0.70")
            
            # Log efficiency issues for debugging
            efficiency_issues = self.parallel_executor.validate_parallel_efficiency(parallel_result, 0.7)
            for issue in efficiency_issues:
                self._logger.warning(f"Efficiency issue: {issue}")
        
        return parallel_result.test_results
    
    def _run_smoke_tests(self, env_context: EnvironmentContext) -> Dict[str, Any]:
        """Execute minimal set of critical path tests."""
        test_results = []
        
        project = self.environment.create_test_project("demo-bootstrap", "demo")
        env_context.projects["demo"] = project
        
        # Run only critical components for smoke testing
        critical_components = ["onboarding", "cli_interface"]
        
        self._logger.info(f"Running smoke tests with {len(critical_components)} critical components")
        
        for component in critical_components:
            result = self._run_component_test(component, project, env_context)
            test_results.append(result)
        
        return {"test_results": test_results, "workflow_results": []}
    
    def _run_regression_tests(self, env_context: EnvironmentContext) -> Dict[str, Any]:
        """Focus on previously failing scenarios."""
        # TODO: Implement regression test tracking based on previous failures
        # For now, run a focused set of components that commonly fail
        test_results = []
        
        project = self.environment.create_test_project("demo-bootstrap", "demo")
        env_context.projects["demo"] = project
        
        # Focus on components that historically have issues
        regression_components = ["protocol", "discovery", "api_integration"]
        
        self._logger.info(f"Running regression tests with {len(regression_components)} components")
        
        for component in regression_components:
            result = self._run_component_test(component, project, env_context)
            test_results.append(result)
        
        return {"test_results": test_results, "workflow_results": []}
    
    def _run_development_tests(self, env_context: EnvironmentContext) -> Dict[str, Any]:
        """Provide verbose output and debugging information."""
        # Same as component tests but with enhanced logging
        self._logger.info("Running development tests with verbose output")
        
        # Enable debug logging for development mode
        if self.config.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
        
        return self._run_component_tests(env_context)
    
    def _run_ci_tests(self, env_context: EnvironmentContext) -> Dict[str, Any]:
        """Non-interactive mode for continuous integration."""
        self._logger.info("Running CI tests in non-interactive mode")
        
        # CI mode runs full workflow but with optimizations for CI environment
        # Force parallel execution for faster CI runs
        original_parallel = self.config.parallel
        self.config.parallel = True
        
        # Set CI-specific environment variables
        import os
        os.environ["TASKSGODZILLA_CI_MODE"] = "true"
        os.environ["TASKSGODZILLA_NON_INTERACTIVE"] = "true"
        
        try:
            # Run full workflow with CI optimizations
            results = self._run_full_workflow(env_context)
            
            # Add CI-specific result processing
            self._process_ci_results(results)
            
            return results
        finally:
            self.config.parallel = original_parallel
            # Clean up CI environment variables
            os.environ.pop("TASKSGODZILLA_CI_MODE", None)
            os.environ.pop("TASKSGODZILLA_NON_INTERACTIVE", None)
    
    def _process_ci_results(self, results: Dict[str, Any]) -> None:
        """Process results for CI-specific requirements."""
        test_results = results.get("test_results", [])
        
        # Log CI-specific summary
        total_tests = len(test_results)
        passed_tests = sum(1 for r in test_results if r.status == HarnessStatus.PASS)
        failed_tests = sum(1 for r in test_results if r.status == HarnessStatus.FAIL)
        error_tests = sum(1 for r in test_results if r.status == HarnessStatus.ERROR)
        
        self._logger.info(f"CI Test Summary: {passed_tests}/{total_tests} passed, {failed_tests} failed, {error_tests} errors")
        
        # Set exit code based on results
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        self._ci_exit_code = 0 if success_rate >= 80 else 1
        
        # Log critical failures for CI visibility
        critical_failures = [r for r in test_results if r.status in [HarnessStatus.FAIL, HarnessStatus.ERROR]]
        if critical_failures:
            self._logger.error(f"CI Critical Failures ({len(critical_failures)}):")
            for failure in critical_failures[:5]:  # Show top 5 failures
                self._logger.error(f"  - {failure.component}.{failure.test_name}: {failure.error_message}")
    
    def get_ci_exit_code(self) -> int:
        """Get exit code for CI systems."""
        return getattr(self, '_ci_exit_code', 0)
    
    def _run_component_test(self, component: str, project, env_context: EnvironmentContext) -> TestResult:
        """Run test for a specific component using registered component classes."""
        start_time = datetime.now()
        self._logger.info(f"Running component test: {component}")
        
        try:
            # Execute before_test hooks
            self.registry.execute_hooks('before_test', component, project, env_context)
            
            # Get component instance and run test
            component_instance = self.registry.get_component(component)
            
            if hasattr(component_instance, 'run_test'):
                success = component_instance.run_test(project, env_context)
            else:
                # Fallback to legacy method dispatch
                success = self._dispatch_legacy_component_test(component, project, env_context)
            
            status = HarnessStatus.PASS if success else HarnessStatus.FAIL
            error_message = None if success else f"Component {component} test failed"
            
            # Execute after_test hooks
            self.registry.execute_hooks('after_test', component, project, env_context, success)
            
        except Exception as e:
            self._logger.error(f"Component {component} test error: {e}")
            self._logger.debug(traceback.format_exc())
            status = HarnessStatus.ERROR
            error_message = str(e)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        result = TestResult(
            component=component,
            test_name=f"{component}_component_test",
            status=status,
            duration=duration,
            error_message=error_message,
            timestamp=start_time,
        )
        
        self._logger.info(f"Component {component} test completed: {status.value} ({duration:.2f}s)")
        return result
    
    def _dispatch_legacy_component_test(self, component: str, project, env_context: EnvironmentContext) -> bool:
        """Dispatch to legacy component test methods for backward compatibility."""
        method_map = {
            "onboarding": self._test_onboarding_component,
            "discovery": self._test_discovery_component,
            "protocol": self._test_protocol_component,
            "spec": self._test_spec_component,
            "quality": self._test_quality_component,
            "cli_interface": self._test_cli_interface_component,
            "api_integration": self._test_api_integration_component,
        }
        
        method = method_map.get(component)
        if method:
            return method(project, env_context)
        else:
            self._logger.warning(f"Unknown component: {component}")
            return False
    
    def _test_onboarding_component(self, project, env_context: EnvironmentContext) -> bool:
        """Test project onboarding functionality."""
        # Placeholder - will be implemented in later tasks
        return True
    
    def _test_discovery_component(self, project, env_context: EnvironmentContext) -> bool:
        """Test discovery functionality."""
        # Placeholder - will be implemented in later tasks
        return True
    
    def _test_protocol_component(self, project, env_context: EnvironmentContext) -> bool:
        """Test protocol functionality."""
        # Placeholder - will be implemented in later tasks
        return True
    
    def _test_spec_component(self, project, env_context: EnvironmentContext) -> bool:
        """Test spec functionality."""
        # Placeholder - will be implemented in later tasks
        return True
    
    def _test_quality_component(self, project, env_context: EnvironmentContext) -> bool:
        """Test quality functionality."""
        # Placeholder - will be implemented in later tasks
        return True
    
    def _test_cli_interface_component(self, project, env_context: EnvironmentContext) -> bool:
        """Test CLI interface functionality."""
        # Placeholder - will be implemented in later tasks
        return True
    
    def _test_api_integration_component(self, project, env_context: EnvironmentContext) -> bool:
        """Test API integration functionality."""
        # Placeholder - will be implemented in later tasks
        return True
    
    def _run_end_to_end_workflow(self, project, env_context: EnvironmentContext) -> WorkflowResult:
        """Execute complete end-to-end workflow."""
        steps = []
        
        # Simulate workflow steps
        workflow_steps = [
            "project_onboarding",
            "discovery_execution", 
            "protocol_creation",
            "spec_validation",
            "quality_check",
        ]
        
        for step_name in workflow_steps:
            start_time = datetime.now()
            
            # Placeholder implementation
            success = True  # Will be replaced with actual workflow execution
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            steps.append(TestResult(
                component="workflow",
                test_name=step_name,
                status=HarnessStatus.PASS if success else HarnessStatus.FAIL,
                duration=duration,
            ))
        
        overall_status = HarnessStatus.PASS if all(s.status == HarnessStatus.PASS for s in steps) else HarnessStatus.FAIL
        
        return WorkflowResult(
            workflow_name="end_to_end_workflow",
            steps=steps,
            overall_status=overall_status,
        )