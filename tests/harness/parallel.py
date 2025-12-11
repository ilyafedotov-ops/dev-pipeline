"""Parallel test execution for CLI workflow harness."""

import threading
import queue
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from dataclasses import dataclass, field
from typing import List, Dict, Any, Callable, Optional, Tuple
from datetime import datetime

from .models import TestResult, HarnessStatus
from .performance import PerformanceMonitor


@dataclass
class TestTask:
    """Represents a test task for parallel execution."""
    task_id: str
    component: str
    test_function: Callable
    args: Tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0  # Higher priority tasks run first
    isolation_group: Optional[str] = None  # Tasks in same group run sequentially
    
    def __post_init__(self):
        if not self.task_id:
            self.task_id = f"{self.component}_{id(self)}"


@dataclass
class ExecutionGroup:
    """Group of tasks that must be executed with specific constraints."""
    group_id: str
    tasks: List[TestTask]
    max_parallel: int = 1  # Maximum parallel tasks in this group
    requires_isolation: bool = True  # Whether tasks need resource isolation


@dataclass
class ParallelExecutionResult:
    """Result of parallel test execution."""
    test_results: List[TestResult]
    execution_time: float
    parallel_efficiency: float
    failed_tasks: List[str]
    resource_conflicts: List[str]
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate of parallel execution."""
        if not self.test_results:
            return 0.0
        passed = sum(1 for r in self.test_results if r.status == HarnessStatus.PASS)
        return (passed / len(self.test_results)) * 100.0


class ResourceIsolationManager:
    """Manages resource isolation between parallel test tasks."""
    
    def __init__(self):
        self._resource_locks: Dict[str, threading.Lock] = {}
        self._active_resources: Dict[str, str] = {}  # resource -> task_id
        self._lock = threading.Lock()
    
    def acquire_resource(self, resource_name: str, task_id: str, timeout: float = 30.0) -> bool:
        """Acquire exclusive access to a resource."""
        with self._lock:
            if resource_name not in self._resource_locks:
                self._resource_locks[resource_name] = threading.Lock()
        
        resource_lock = self._resource_locks[resource_name]
        
        if resource_lock.acquire(timeout=timeout):
            with self._lock:
                self._active_resources[resource_name] = task_id
            return True
        
        return False
    
    def release_resource(self, resource_name: str, task_id: str) -> None:
        """Release exclusive access to a resource."""
        with self._lock:
            if resource_name in self._active_resources:
                if self._active_resources[resource_name] == task_id:
                    del self._active_resources[resource_name]
        
        if resource_name in self._resource_locks:
            try:
                self._resource_locks[resource_name].release()
            except Exception:
                pass  # Lock may already be released
    
    def get_resource_conflicts(self) -> List[str]:
        """Get list of current resource conflicts."""
        with self._lock:
            conflicts = []
            for resource, task_id in self._active_resources.items():
                # Check if multiple tasks are trying to use the same resource
                # This is a simplified conflict detection
                conflicts.append(f"Resource '{resource}' held by task '{task_id}'")
            return conflicts


class ParallelTestExecutor:
    """Executes tests in parallel with proper isolation and result aggregation."""
    
    def __init__(self, max_workers: int = 4, performance_monitor: Optional[PerformanceMonitor] = None):
        self.max_workers = max_workers
        self.performance_monitor = performance_monitor
        self.isolation_manager = ResourceIsolationManager()
        self._logger = logging.getLogger(__name__)
        self._result_lock = threading.Lock()
        self._results: List[TestResult] = []
        
    def execute_parallel(self, tasks: List[TestTask]) -> ParallelExecutionResult:
        """Execute test tasks in parallel with proper isolation."""
        if not tasks:
            return ParallelExecutionResult(
                test_results=[],
                execution_time=0.0,
                parallel_efficiency=0.0,
                failed_tasks=[],
                resource_conflicts=[]
            )
        
        start_time = datetime.now()
        self._results.clear()
        
        # Group tasks by isolation requirements
        execution_groups = self._group_tasks_by_isolation(tasks)
        
        # Track performance if monitor is available
        if self.performance_monitor:
            self.performance_monitor.start_monitoring()
        
        try:
            # Execute groups with appropriate parallelism
            for group in execution_groups:
                self._execute_group(group)
        
        finally:
            if self.performance_monitor:
                self.performance_monitor.stop_monitoring()
        
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        # Calculate parallel efficiency
        sequential_time = sum(r.duration for r in self._results)
        parallel_efficiency = 0.0
        if execution_time > 0 and sequential_time > 0:
            parallel_efficiency = min(1.0, sequential_time / (execution_time * self.max_workers))
        
        # Identify failed tasks
        failed_tasks = [
            r.component for r in self._results 
            if r.status in (HarnessStatus.FAIL, HarnessStatus.ERROR)
        ]
        
        # Get resource conflicts
        resource_conflicts = self.isolation_manager.get_resource_conflicts()
        
        return ParallelExecutionResult(
            test_results=self._results.copy(),
            execution_time=execution_time,
            parallel_efficiency=parallel_efficiency,
            failed_tasks=failed_tasks,
            resource_conflicts=resource_conflicts
        )
    
    def _group_tasks_by_isolation(self, tasks: List[TestTask]) -> List[ExecutionGroup]:
        """Group tasks based on isolation requirements and optimize for parallel execution."""
        # Analyze task dependencies and isolation requirements
        independent_tasks = []
        isolated_groups: Dict[str, List[TestTask]] = {}
        
        for task in tasks:
            if task.isolation_group:
                # Tasks with isolation groups need careful handling
                if task.isolation_group not in isolated_groups:
                    isolated_groups[task.isolation_group] = []
                isolated_groups[task.isolation_group].append(task)
            else:
                # Independent tasks can run in parallel
                independent_tasks.append(task)
        
        execution_groups = []
        
        # Create group for independent tasks with maximum parallelism
        if independent_tasks:
            # Sort by priority (higher priority first)
            independent_tasks.sort(key=lambda t: t.priority, reverse=True)
            
            execution_groups.append(ExecutionGroup(
                group_id="independent",
                tasks=independent_tasks,
                max_parallel=min(self.max_workers, len(independent_tasks)),
                requires_isolation=False
            ))
        
        # Create groups for isolated tasks with optimized parallelism
        for group_id, group_tasks in isolated_groups.items():
            # Sort tasks by priority
            group_tasks.sort(key=lambda t: t.priority, reverse=True)
            
            # Determine optimal parallelism for this isolation group
            # Some isolation groups can still have limited parallelism
            max_parallel = self._calculate_optimal_parallelism(group_id, group_tasks)
            
            execution_groups.append(ExecutionGroup(
                group_id=group_id,
                tasks=group_tasks,
                max_parallel=max_parallel,
                requires_isolation=True
            ))
        
        # Sort execution groups by priority (independent tasks first for better efficiency)
        execution_groups.sort(key=lambda g: (
            0 if g.group_id == "independent" else 1,  # Independent tasks first
            -len(g.tasks)  # Larger groups first within same category
        ))
        
        return execution_groups
    
    def _calculate_optimal_parallelism(self, group_id: str, tasks: List[TestTask]) -> int:
        """Calculate optimal parallelism for an isolation group."""
        # Component-specific parallelism rules
        component_parallelism = {
            "component_onboarding": 2,  # Onboarding can have limited parallelism
            "component_discovery": 1,   # Discovery needs full isolation
            "component_protocol": 1,    # Protocol needs full isolation
            "component_spec": 2,        # Spec tests can have limited parallelism
            "component_quality": 1,     # Quality tests need full isolation
            "component_cli_interface": 3,  # CLI tests can be more parallel
            "component_api_integration": 1,  # API tests need isolation
            "component_error_conditions": 2,  # Error tests can have limited parallelism
        }
        
        # Get component-specific parallelism or default to 1
        max_parallel = component_parallelism.get(group_id, 1)
        
        # Don't exceed the number of tasks or max workers
        return min(max_parallel, len(tasks), self.max_workers)
    
    def _execute_group(self, group: ExecutionGroup) -> None:
        """Execute a group of tasks with appropriate parallelism and load balancing."""
        if not group.tasks:
            return
        
        self._logger.info(f"Executing group '{group.group_id}' with {len(group.tasks)} tasks, "
                         f"max_parallel={group.max_parallel}")
        
        # For better load balancing, sort tasks by estimated duration (longest first)
        # This helps prevent the situation where short tasks finish early and workers idle
        sorted_tasks = self._sort_tasks_for_load_balancing(group.tasks)
        
        # Use ThreadPoolExecutor for this group
        with ThreadPoolExecutor(max_workers=group.max_parallel) as executor:
            # Submit all tasks in the group
            future_to_task = {}
            for task in sorted_tasks:
                future = executor.submit(self._execute_task_with_isolation, task, group.requires_isolation)
                future_to_task[future] = task
            
            # Collect results as they complete with progress tracking
            completed_count = 0
            total_count = len(sorted_tasks)
            
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                completed_count += 1
                
                try:
                    # Use dynamic timeout based on task type
                    timeout = self._get_task_timeout(task)
                    result = future.result(timeout=timeout)
                    
                    with self._result_lock:
                        self._results.append(result)
                    
                    self._logger.debug(f"Task {task.task_id} completed ({completed_count}/{total_count})")
                    
                except Exception as e:
                    self._logger.error(f"Task {task.task_id} failed with exception: {e}")
                    self._logger.debug(traceback.format_exc())
                    
                    # Create error result
                    error_result = TestResult(
                        component=task.component,
                        test_name=task.task_id,
                        status=HarnessStatus.ERROR,
                        duration=0.0,
                        error_message=str(e),
                        timestamp=datetime.now()
                    )
                    
                    with self._result_lock:
                        self._results.append(error_result)
    
    def _sort_tasks_for_load_balancing(self, tasks: List[TestTask]) -> List[TestTask]:
        """Sort tasks to optimize load balancing in parallel execution."""
        # Estimate task duration based on component type
        def estimate_duration(task: TestTask) -> float:
            duration_estimates = {
                "onboarding": 60.0,      # Onboarding tasks are typically longer
                "discovery": 120.0,      # Discovery can be very long
                "protocol": 90.0,        # Protocol tests are moderately long
                "spec": 30.0,           # Spec tests are typically shorter
                "quality": 45.0,        # Quality tests are moderate
                "cli_interface": 20.0,  # CLI tests are typically quick
                "api_integration": 40.0, # API tests are moderate
                "error_conditions": 15.0, # Error tests are typically quick
            }
            return duration_estimates.get(task.component, 30.0)  # Default 30 seconds
        
        # Sort by estimated duration (longest first) and then by priority
        return sorted(tasks, key=lambda t: (-estimate_duration(t), -t.priority))
    
    def _get_task_timeout(self, task: TestTask) -> float:
        """Get appropriate timeout for a task based on its type."""
        timeout_map = {
            "onboarding": 300.0,      # 5 minutes for onboarding
            "discovery": 600.0,       # 10 minutes for discovery
            "protocol": 450.0,        # 7.5 minutes for protocol
            "spec": 180.0,           # 3 minutes for spec
            "quality": 240.0,        # 4 minutes for quality
            "cli_interface": 120.0,  # 2 minutes for CLI
            "api_integration": 180.0, # 3 minutes for API
            "error_conditions": 90.0, # 1.5 minutes for error tests
        }
        return timeout_map.get(task.component, 300.0)  # Default 5 minutes
    
    def _execute_task_with_isolation(self, task: TestTask, requires_isolation: bool) -> TestResult:
        """Execute a single task with resource isolation if required."""
        start_time = datetime.now()
        
        # Acquire resources if isolation is required
        resources_acquired = []
        if requires_isolation and task.isolation_group:
            resource_name = f"isolation_{task.isolation_group}"
            if self.isolation_manager.acquire_resource(resource_name, task.task_id):
                resources_acquired.append(resource_name)
            else:
                # Failed to acquire resource - return error
                return TestResult(
                    component=task.component,
                    test_name=task.task_id,
                    status=HarnessStatus.ERROR,
                    duration=0.0,
                    error_message=f"Failed to acquire resource isolation for group '{task.isolation_group}'",
                    timestamp=start_time
                )
        
        try:
            # Track performance for this task
            if self.performance_monitor:
                with self.performance_monitor.track_operation(f"task_{task.task_id}", 
                                                            component=task.component):
                    result = self._execute_task_function(task, start_time)
            else:
                result = self._execute_task_function(task, start_time)
            
            return result
            
        finally:
            # Release acquired resources
            for resource_name in resources_acquired:
                self.isolation_manager.release_resource(resource_name, task.task_id)
    
    def _execute_task_function(self, task: TestTask, start_time: datetime) -> TestResult:
        """Execute the actual task function."""
        try:
            self._logger.debug(f"Executing task {task.task_id} for component {task.component}")
            
            # Call the test function
            success = task.test_function(*task.args, **task.kwargs)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            status = HarnessStatus.PASS if success else HarnessStatus.FAIL
            error_message = None if success else f"Task {task.task_id} returned False"
            
            result = TestResult(
                component=task.component,
                test_name=task.task_id,
                status=status,
                duration=duration,
                error_message=error_message,
                timestamp=start_time
            )
            
            self._logger.debug(f"Task {task.task_id} completed: {status.value} ({duration:.2f}s)")
            return result
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            self._logger.error(f"Task {task.task_id} failed with exception: {e}")
            self._logger.debug(traceback.format_exc())
            
            return TestResult(
                component=task.component,
                test_name=task.task_id,
                status=HarnessStatus.ERROR,
                duration=duration,
                error_message=str(e),
                timestamp=start_time
            )
    
    def validate_parallel_efficiency(self, result: ParallelExecutionResult, 
                                   min_efficiency: float = 0.3) -> List[str]:
        """Validate parallel execution efficiency and return issues."""
        issues = []
        
        if result.parallel_efficiency < min_efficiency:
            issues.append(
                f"Low parallel efficiency: {result.parallel_efficiency:.2f} < {min_efficiency:.2f}"
            )
        
        if result.resource_conflicts:
            issues.append(f"Resource conflicts detected: {len(result.resource_conflicts)} conflicts")
        
        if result.failed_tasks:
            issues.append(f"Failed tasks: {len(result.failed_tasks)} out of {len(result.test_results)}")
        
        # Check for load balancing issues
        if result.test_results:
            durations = [r.duration for r in result.test_results]
            max_duration = max(durations)
            min_duration = min(durations)
            
            if max_duration > 0 and (max_duration / min_duration) > 5.0:
                issues.append(
                    f"Poor load balancing: max task duration {max_duration:.1f}s vs min {min_duration:.1f}s"
                )
        
        return issues
    
    def create_task_from_component(self, component_name: str, test_function: Callable,
                                 isolation_group: Optional[str] = None, 
                                 priority: int = 0, **kwargs) -> TestTask:
        """Create a test task from component information."""
        return TestTask(
            task_id=f"{component_name}_test",
            component=component_name,
            test_function=test_function,
            kwargs=kwargs,
            priority=priority,
            isolation_group=isolation_group
        )
    
    def analyze_task_dependencies(self, tasks: List[TestTask]) -> Dict[str, List[str]]:
        """Analyze task dependencies to identify unnecessary isolation requirements."""
        dependencies = {}
        
        for task in tasks:
            task_deps = []
            
            # Analyze what resources this task actually needs
            if task.component == "onboarding":
                task_deps.extend(["database", "filesystem"])
            elif task.component == "discovery":
                task_deps.extend(["filesystem", "external_api"])
            elif task.component == "protocol":
                task_deps.extend(["database", "filesystem", "git"])
            elif task.component == "spec":
                task_deps.extend(["filesystem"])
            elif task.component == "quality":
                task_deps.extend(["filesystem", "external_api"])
            elif task.component == "cli_interface":
                task_deps.extend(["process", "filesystem"])
            elif task.component == "api_integration":
                task_deps.extend(["network", "database"])
            elif task.component == "error_conditions":
                task_deps.extend(["filesystem"])
            
            dependencies[task.task_id] = task_deps
        
        return dependencies
    
    def optimize_task_isolation(self, tasks: List[TestTask]) -> List[TestTask]:
        """Optimize task isolation by removing unnecessary dependencies."""
        dependencies = self.analyze_task_dependencies(tasks)
        optimized_tasks = []
        
        for task in tasks:
            # Create optimized task with potentially reduced isolation
            optimized_task = TestTask(
                task_id=task.task_id,
                component=task.component,
                test_function=task.test_function,
                args=task.args,
                kwargs=task.kwargs,
                priority=task.priority,
                isolation_group=self._optimize_isolation_group(task, dependencies)
            )
            optimized_tasks.append(optimized_task)
        
        return optimized_tasks
    
    def _optimize_isolation_group(self, task: TestTask, dependencies: Dict[str, List[str]]) -> Optional[str]:
        """Optimize isolation group assignment based on actual dependencies."""
        task_deps = dependencies.get(task.task_id, [])
        
        # Tasks that don't conflict can share isolation groups or run independently
        if not task_deps:
            return None  # No isolation needed
        
        # Group tasks by their actual resource requirements
        if "database" in task_deps and "git" in task_deps:
            return f"component_{task.component}"  # Full isolation for complex tasks
        elif "database" in task_deps:
            return "database_users"  # Shared database isolation group
        elif "filesystem" in task_deps and "external_api" not in task_deps:
            return "filesystem_users"  # Shared filesystem isolation group
        elif "process" in task_deps or "network" in task_deps:
            return f"component_{task.component}"  # Process/network tasks need isolation
        else:
            return None  # Can run independently
    
    def get_optimal_worker_count(self, task_count: int, estimated_task_duration: float = 60.0) -> int:
        """Calculate optimal worker count based on task characteristics."""
        # Enhanced heuristic for optimal worker count
        if task_count <= 1:
            return 1
        
        # Consider system resources
        import os
        cpu_count = os.cpu_count() or 4
        
        # For short tasks, use more workers but don't exceed CPU count
        if estimated_task_duration < 30.0:
            return min(self.max_workers, task_count, cpu_count)
        
        # For medium tasks, use moderate parallelism
        if estimated_task_duration < 120.0:
            return min(self.max_workers, task_count, max(2, cpu_count // 2))
        
        # For long tasks, use fewer workers to avoid resource contention
        if estimated_task_duration > 300.0:  # 5 minutes
            return min(2, self.max_workers, max(1, cpu_count // 4))
        
        # Default to configured max workers with CPU consideration
        return min(self.max_workers, task_count, cpu_count)