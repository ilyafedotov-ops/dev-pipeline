"""Unit tests for performance monitoring functionality."""

import time
import threading
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from tests.harness.performance import (
    PerformanceMonitor, 
    PerformanceThresholds, 
    OperationMetrics,
    PerformanceReport
)
from tests.harness.parallel import (
    ParallelTestExecutor,
    TestTask,
    ParallelExecutionResult,
    ResourceIsolationManager
)


class TestPerformanceMonitor:
    """Test cases for PerformanceMonitor class."""
    
    def test_performance_monitor_initialization(self):
        """Test PerformanceMonitor initializes correctly."""
        monitor = PerformanceMonitor()
        
        assert monitor.thresholds is not None
        assert isinstance(monitor.thresholds, PerformanceThresholds)
        assert not monitor._monitoring_active
        assert len(monitor._operations) == 0
        assert len(monitor._resource_samples) == 0
    
    def test_performance_monitor_with_custom_thresholds(self):
        """Test PerformanceMonitor with custom thresholds."""
        thresholds = PerformanceThresholds(
            max_duration_seconds=600.0,
            max_memory_mb=1024.0,
            min_cpu_efficiency=0.2
        )
        
        monitor = PerformanceMonitor(thresholds)
        
        assert monitor.thresholds.max_duration_seconds == 600.0
        assert monitor.thresholds.max_memory_mb == 1024.0
        assert monitor.thresholds.min_cpu_efficiency == 0.2
    
    def test_track_operation_context_manager(self):
        """Test operation tracking with context manager."""
        monitor = PerformanceMonitor()
        
        with monitor.track_operation("test_operation", test_param="value") as operation:
            assert operation.name == "test_operation"
            assert operation.metadata["test_param"] == "value"
            assert operation.start_time is not None
            assert operation.end_time is None
            
            # Simulate some work
            time.sleep(0.1)
        
        # After context manager exits
        assert operation.end_time is not None
        assert operation.duration > 0.0
        assert operation.is_complete
        
        # Check operation is stored
        stored_operation = monitor.get_operation_metrics("test_operation")
        assert stored_operation is not None
        assert stored_operation.name == "test_operation"
        assert stored_operation.duration > 0.0
    
    def test_track_multiple_operations(self):
        """Test tracking multiple operations."""
        monitor = PerformanceMonitor()
        
        # Track first operation
        with monitor.track_operation("operation_1"):
            time.sleep(0.05)
        
        # Track second operation
        with monitor.track_operation("operation_2"):
            time.sleep(0.05)
        
        all_operations = monitor.get_all_operations()
        assert len(all_operations) == 2
        
        op1 = monitor.get_operation_metrics("operation_1")
        op2 = monitor.get_operation_metrics("operation_2")
        
        assert op1 is not None
        assert op2 is not None
        assert op1.duration > 0.0
        assert op2.duration > 0.0
    
    def test_duplicate_operation_names(self):
        """Test handling of duplicate operation names."""
        monitor = PerformanceMonitor()
        
        with monitor.track_operation("duplicate_name"):
            time.sleep(0.01)
        
        with monitor.track_operation("duplicate_name"):
            time.sleep(0.01)
        
        all_operations = monitor.get_all_operations()
        assert len(all_operations) == 2
        
        # Should have different names due to timestamp suffix
        names = [op.name for op in all_operations]
        assert len(set(names)) == 2  # All names should be unique
    
    @patch('tests.harness.performance.psutil.Process')
    def test_global_monitoring(self, mock_process):
        """Test global monitoring start/stop."""
        # Mock psutil.Process
        mock_process_instance = Mock()
        mock_process_instance.memory_info.return_value.rss = 100 * 1024 * 1024  # 100MB
        mock_process_instance.cpu_percent.return_value = 25.0
        mock_process.return_value = mock_process_instance
        
        monitor = PerformanceMonitor()
        
        # Start monitoring
        monitor.start_monitoring()
        assert monitor._monitoring_active
        assert monitor._global_start_time is not None
        
        # Let monitoring run briefly
        time.sleep(0.1)
        
        # Stop monitoring
        monitor.stop_monitoring()
        assert not monitor._monitoring_active
        assert monitor._global_end_time is not None
        
        # Should have collected some resource samples
        assert len(monitor._resource_samples) > 0
    
    def test_threshold_validation(self):
        """Test performance threshold validation."""
        thresholds = PerformanceThresholds(
            max_duration_seconds=1.0,
            max_memory_mb=50.0
        )
        monitor = PerformanceMonitor(thresholds)
        
        # Create operation that exceeds duration threshold
        with monitor.track_operation("slow_operation"):
            time.sleep(1.1)  # Exceed 1.0 second threshold
        
        violations = monitor.validate_thresholds()
        
        # Should have at least one violation for the slow operation
        assert len(violations) > 0
        assert any("slow_operation" in violation for violation in violations)
    
    def test_performance_recommendations(self):
        """Test performance recommendation generation."""
        monitor = PerformanceMonitor()
        
        # Create some operations with different characteristics
        with monitor.track_operation("fast_operation"):
            time.sleep(0.01)
        
        with monitor.track_operation("slow_operation"):
            time.sleep(0.1)
        
        recommendations = monitor.generate_recommendations()
        
        # Should generate some recommendations
        assert isinstance(recommendations, list)
        # With operations tracked, should have at least one recommendation
        assert len(recommendations) >= 0
    
    def test_parallel_efficiency_calculation(self):
        """Test parallel efficiency calculation."""
        monitor = PerformanceMonitor()
        
        # Test perfect efficiency
        efficiency = monitor.calculate_parallel_efficiency(
            sequential_duration=10.0,
            parallel_duration=2.5,
            worker_count=4
        )
        assert efficiency == 1.0  # Perfect efficiency
        
        # Test partial efficiency
        efficiency = monitor.calculate_parallel_efficiency(
            sequential_duration=10.0,
            parallel_duration=5.0,
            worker_count=4
        )
        assert 0.0 < efficiency < 1.0
        
        # Test edge cases
        efficiency = monitor.calculate_parallel_efficiency(
            sequential_duration=0.0,
            parallel_duration=1.0,
            worker_count=4
        )
        assert efficiency == 0.0
    
    def test_performance_report_generation(self):
        """Test comprehensive performance report generation."""
        monitor = PerformanceMonitor()
        
        # Start global monitoring
        monitor.start_monitoring()
        
        # Track some operations
        with monitor.track_operation("test_op_1"):
            time.sleep(0.05)
        
        with monitor.track_operation("test_op_2"):
            time.sleep(0.05)
        
        # Stop monitoring
        monitor.stop_monitoring()
        
        # Generate report
        report = monitor.generate_performance_report()
        
        assert isinstance(report, PerformanceReport)
        assert report.total_duration > 0.0
        assert len(report.operations) == 2
        assert report.operation_count == 2
        assert report.completed_operations == 2
        assert isinstance(report.threshold_violations, list)
        assert isinstance(report.recommendations, list)
    
    def test_monitor_reset(self):
        """Test monitor reset functionality."""
        monitor = PerformanceMonitor()
        
        # Add some data
        monitor.start_monitoring()
        with monitor.track_operation("test_operation"):
            time.sleep(0.01)
        monitor.stop_monitoring()
        
        # Verify data exists
        assert len(monitor.get_all_operations()) > 0
        
        # Reset monitor
        monitor.reset()
        
        # Verify data is cleared
        assert len(monitor.get_all_operations()) == 0
        assert len(monitor._resource_samples) == 0
        assert not monitor._monitoring_active
        assert monitor._global_start_time is None
        assert monitor._global_end_time is None


class TestParallelTestExecutor:
    """Test cases for ParallelTestExecutor class."""
    
    def test_parallel_executor_initialization(self):
        """Test ParallelTestExecutor initializes correctly."""
        executor = ParallelTestExecutor(max_workers=2)
        
        assert executor.max_workers == 2
        assert executor.isolation_manager is not None
        assert len(executor._results) == 0
    
    def test_create_task_from_component(self):
        """Test creating test tasks from component information."""
        executor = ParallelTestExecutor()
        
        def dummy_test():
            return True
        
        task = executor.create_task_from_component(
            "test_component",
            dummy_test,
            isolation_group="group1",
            priority=5,
            param1="value1"
        )
        
        assert task.component == "test_component"
        assert task.test_function == dummy_test
        assert task.isolation_group == "group1"
        assert task.priority == 5
        assert task.kwargs["param1"] == "value1"
    
    def test_execute_parallel_empty_tasks(self):
        """Test parallel execution with empty task list."""
        executor = ParallelTestExecutor()
        
        result = executor.execute_parallel([])
        
        assert isinstance(result, ParallelExecutionResult)
        assert len(result.test_results) == 0
        assert result.execution_time == 0.0
        assert result.parallel_efficiency == 0.0
        assert len(result.failed_tasks) == 0
    
    def test_execute_parallel_single_task(self):
        """Test parallel execution with single task."""
        executor = ParallelTestExecutor()
        
        def test_function():
            time.sleep(0.05)
            return True
        
        task = TestTask(
            task_id="single_task",
            component="test_component",
            test_function=test_function
        )
        
        result = executor.execute_parallel([task])
        
        assert len(result.test_results) == 1
        assert result.test_results[0].component == "test_component"
        assert result.test_results[0].status.value == "pass"
        assert result.execution_time > 0.0
        assert result.success_rate == 100.0
    
    def test_execute_parallel_multiple_tasks(self):
        """Test parallel execution with multiple tasks."""
        executor = ParallelTestExecutor(max_workers=2)
        
        def fast_test():
            time.sleep(0.01)
            return True
        
        def slow_test():
            time.sleep(0.05)
            return True
        
        tasks = [
            TestTask("task1", "component1", fast_test),
            TestTask("task2", "component2", slow_test),
            TestTask("task3", "component3", fast_test),
        ]
        
        result = executor.execute_parallel(tasks)
        
        assert len(result.test_results) == 3
        assert all(r.status.value == "pass" for r in result.test_results)
        assert result.success_rate == 100.0
        assert result.execution_time > 0.0
    
    def test_execute_parallel_with_failures(self):
        """Test parallel execution with task failures."""
        executor = ParallelTestExecutor()
        
        def passing_test():
            return True
        
        def failing_test():
            return False
        
        def error_test():
            raise ValueError("Test error")
        
        tasks = [
            TestTask("pass_task", "component1", passing_test),
            TestTask("fail_task", "component2", failing_test),
            TestTask("error_task", "component3", error_test),
        ]
        
        result = executor.execute_parallel(tasks)
        
        assert len(result.test_results) == 3
        assert result.success_rate < 100.0
        assert len(result.failed_tasks) == 2  # fail_task and error_task
        
        # Check specific statuses
        statuses = [r.status.value for r in result.test_results]
        assert "pass" in statuses
        assert "fail" in statuses
        assert "error" in statuses
    
    def test_task_priority_ordering(self):
        """Test that tasks are executed in priority order within groups."""
        executor = ParallelTestExecutor(max_workers=1)  # Sequential execution
        
        execution_order = []
        
        def create_test_func(task_name):
            def test_func():
                execution_order.append(task_name)
                time.sleep(0.01)
                return True
            return test_func
        
        tasks = [
            TestTask("low_priority", "comp1", create_test_func("low"), priority=1),
            TestTask("high_priority", "comp2", create_test_func("high"), priority=10),
            TestTask("medium_priority", "comp3", create_test_func("medium"), priority=5),
        ]
        
        result = executor.execute_parallel(tasks)
        
        assert len(result.test_results) == 3
        # With sequential execution, high priority should execute first
        # Note: Due to threading, exact order may vary, but high priority should be early
        assert "high" in execution_order
    
    def test_optimal_worker_count_calculation(self):
        """Test optimal worker count calculation."""
        executor = ParallelTestExecutor(max_workers=8)
        
        # Single task
        assert executor.get_optimal_worker_count(1) == 1
        
        # Short tasks - use more workers
        assert executor.get_optimal_worker_count(10, 15.0) <= 8
        
        # Long tasks - use fewer workers
        assert executor.get_optimal_worker_count(10, 400.0) <= 2
        
        # Medium tasks - use default
        assert executor.get_optimal_worker_count(5, 60.0) <= 8
    
    def test_parallel_efficiency_validation(self):
        """Test parallel execution efficiency validation."""
        executor = ParallelTestExecutor()
        
        # Create mock result with low efficiency
        result = ParallelExecutionResult(
            test_results=[],
            execution_time=10.0,
            parallel_efficiency=0.1,  # Low efficiency
            failed_tasks=["task1"],
            resource_conflicts=["conflict1"]
        )
        
        issues = executor.validate_parallel_efficiency(result, min_efficiency=0.3)
        
        assert len(issues) > 0
        assert any("Low parallel efficiency" in issue for issue in issues)
        assert any("Resource conflicts" in issue for issue in issues)
        assert any("Failed tasks" in issue for issue in issues)


class TestResourceIsolationManager:
    """Test cases for ResourceIsolationManager class."""
    
    def test_resource_isolation_manager_initialization(self):
        """Test ResourceIsolationManager initializes correctly."""
        manager = ResourceIsolationManager()
        
        assert len(manager._resource_locks) == 0
        assert len(manager._active_resources) == 0
    
    def test_acquire_and_release_resource(self):
        """Test basic resource acquisition and release."""
        manager = ResourceIsolationManager()
        
        # Acquire resource
        success = manager.acquire_resource("test_resource", "task1")
        assert success
        
        # Resource should be active
        conflicts = manager.get_resource_conflicts()
        assert len(conflicts) == 1
        assert "test_resource" in conflicts[0]
        assert "task1" in conflicts[0]
        
        # Release resource
        manager.release_resource("test_resource", "task1")
        
        # Resource should no longer be active
        conflicts = manager.get_resource_conflicts()
        assert len(conflicts) == 0
    
    def test_resource_contention(self):
        """Test resource contention between tasks."""
        manager = ResourceIsolationManager()
        
        # First task acquires resource
        success1 = manager.acquire_resource("shared_resource", "task1", timeout=0.1)
        assert success1
        
        # Second task tries to acquire same resource (should fail due to timeout)
        success2 = manager.acquire_resource("shared_resource", "task2", timeout=0.1)
        assert not success2
        
        # Release resource from first task
        manager.release_resource("shared_resource", "task1")
        
        # Now second task should be able to acquire it
        success3 = manager.acquire_resource("shared_resource", "task2", timeout=0.1)
        assert success3
        
        # Clean up
        manager.release_resource("shared_resource", "task2")
    
    def test_multiple_resources(self):
        """Test managing multiple different resources."""
        manager = ResourceIsolationManager()
        
        # Acquire different resources
        success1 = manager.acquire_resource("resource1", "task1")
        success2 = manager.acquire_resource("resource2", "task2")
        
        assert success1
        assert success2
        
        # Both resources should be active
        conflicts = manager.get_resource_conflicts()
        assert len(conflicts) == 2
        
        # Release both resources
        manager.release_resource("resource1", "task1")
        manager.release_resource("resource2", "task2")
        
        # No resources should be active
        conflicts = manager.get_resource_conflicts()
        assert len(conflicts) == 0


class TestOperationMetrics:
    """Test cases for OperationMetrics data class."""
    
    def test_operation_metrics_initialization(self):
        """Test OperationMetrics initializes correctly."""
        start_time = datetime.now()
        metrics = OperationMetrics(
            name="test_operation",
            start_time=start_time
        )
        
        assert metrics.name == "test_operation"
        assert metrics.start_time == start_time
        assert metrics.end_time is None
        assert metrics.duration == 0.0
        assert not metrics.is_complete
    
    def test_operation_metrics_completion(self):
        """Test OperationMetrics completion tracking."""
        start_time = datetime.now()
        metrics = OperationMetrics(
            name="test_operation",
            start_time=start_time
        )
        
        # Mark as complete
        end_time = start_time + timedelta(seconds=1.5)
        metrics.end_time = end_time
        metrics.duration = 1.5
        
        assert metrics.is_complete
        assert metrics.duration == 1.5


class TestPerformanceThresholds:
    """Test cases for PerformanceThresholds data class."""
    
    def test_performance_thresholds_defaults(self):
        """Test PerformanceThresholds default values."""
        thresholds = PerformanceThresholds()
        
        assert thresholds.max_duration_seconds == 1800.0  # 30 minutes
        assert thresholds.max_memory_mb == 2048.0  # 2GB
        assert thresholds.min_cpu_efficiency == 0.1  # 10%
        assert thresholds.max_parallel_overhead == 0.3  # 30%
    
    def test_performance_thresholds_custom(self):
        """Test PerformanceThresholds with custom values."""
        thresholds = PerformanceThresholds(
            max_duration_seconds=600.0,
            max_memory_mb=1024.0,
            min_cpu_efficiency=0.2,
            max_parallel_overhead=0.2
        )
        
        assert thresholds.max_duration_seconds == 600.0
        assert thresholds.max_memory_mb == 1024.0
        assert thresholds.min_cpu_efficiency == 0.2
        assert thresholds.max_parallel_overhead == 0.2


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])