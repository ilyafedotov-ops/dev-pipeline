"""Performance monitoring for CLI workflow harness."""

import time
import psutil
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta


@dataclass
class OperationMetrics:
    """Metrics for a single operation."""
    name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: float = 0.0
    peak_memory_mb: float = 0.0
    avg_cpu_percent: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_complete(self) -> bool:
        """Check if operation is complete."""
        return self.end_time is not None


@dataclass
class PerformanceThresholds:
    """Performance thresholds for validation."""
    max_duration_seconds: float = 1800.0  # 30 minutes
    max_memory_mb: float = 2048.0  # 2GB
    min_cpu_efficiency: float = 0.1  # 10% minimum CPU usage
    max_parallel_overhead: float = 0.3  # 30% maximum parallel overhead
    
    
@dataclass
class PerformanceReport:
    """Comprehensive performance report."""
    total_duration: float
    peak_memory_mb: float
    avg_cpu_utilization: float
    parallel_efficiency: float
    operations: List[OperationMetrics]
    threshold_violations: List[str]
    recommendations: List[str]
    
    @property
    def operation_count(self) -> int:
        """Total number of operations tracked."""
        return len(self.operations)
    
    @property
    def completed_operations(self) -> int:
        """Number of completed operations."""
        return sum(1 for op in self.operations if op.is_complete)


class PerformanceMonitor:
    """Tracks performance metrics and validates against thresholds."""
    
    def __init__(self, thresholds: Optional[PerformanceThresholds] = None):
        self.thresholds = thresholds or PerformanceThresholds()
        self._operations: Dict[str, OperationMetrics] = {}
        self._global_start_time: Optional[datetime] = None
        self._global_end_time: Optional[datetime] = None
        self._monitoring_active = False
        self._resource_samples: List[Dict[str, float]] = []
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
        
    def start_monitoring(self) -> None:
        """Start global performance monitoring."""
        if self._monitoring_active:
            return
            
        self._global_start_time = datetime.now()
        self._monitoring_active = True
        self._stop_monitoring.clear()
        
        # Start resource monitoring thread
        self._monitor_thread = threading.Thread(target=self._monitor_resources, daemon=True)
        self._monitor_thread.start()
        
    def stop_monitoring(self) -> None:
        """Stop global performance monitoring."""
        if not self._monitoring_active:
            return
            
        self._global_end_time = datetime.now()
        self._monitoring_active = False
        self._stop_monitoring.set()
        
        # Wait for monitoring thread to finish
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=1.0)
    
    def _monitor_resources(self) -> None:
        """Monitor system resources in background thread."""
        process = psutil.Process()
        
        while not self._stop_monitoring.is_set():
            try:
                # Sample current resource usage
                memory_mb = process.memory_info().rss / (1024 * 1024)
                cpu_percent = process.cpu_percent()
                
                sample = {
                    'timestamp': time.time(),
                    'memory_mb': memory_mb,
                    'cpu_percent': cpu_percent,
                }
                
                self._resource_samples.append(sample)
                
                # Sleep for sampling interval
                self._stop_monitoring.wait(0.5)  # Sample every 500ms
                
            except Exception:
                # Ignore monitoring errors to avoid disrupting tests
                pass
    
    @contextmanager
    def track_operation(self, operation_name: str, **metadata):
        """Context manager to track timing and resource usage for operations."""
        if operation_name in self._operations:
            # Handle duplicate operation names by appending timestamp
            operation_name = f"{operation_name}_{int(time.time())}"
        
        # Create operation metrics
        operation = OperationMetrics(
            name=operation_name,
            start_time=datetime.now(),
            metadata=metadata
        )
        
        self._operations[operation_name] = operation
        
        # Get initial resource state
        try:
            process = psutil.Process()
            initial_memory = process.memory_info().rss / (1024 * 1024)
        except Exception:
            initial_memory = 0.0
        
        start_time = time.time()
        
        try:
            yield operation
        finally:
            # Complete operation tracking
            end_time = time.time()
            operation.end_time = datetime.now()
            operation.duration = end_time - start_time
            
            # Calculate resource usage for this operation
            try:
                process = psutil.Process()
                final_memory = process.memory_info().rss / (1024 * 1024)
                operation.peak_memory_mb = max(initial_memory, final_memory)
                
                # Calculate average CPU usage during operation
                operation_samples = [
                    s for s in self._resource_samples 
                    if start_time <= s['timestamp'] <= end_time
                ]
                
                if operation_samples:
                    operation.avg_cpu_percent = sum(s['cpu_percent'] for s in operation_samples) / len(operation_samples)
                
            except Exception:
                # Set defaults if resource tracking fails
                operation.peak_memory_mb = initial_memory
                operation.avg_cpu_percent = 0.0
    
    def get_operation_metrics(self, operation_name: str) -> Optional[OperationMetrics]:
        """Get metrics for a specific operation."""
        return self._operations.get(operation_name)
    
    def get_all_operations(self) -> List[OperationMetrics]:
        """Get metrics for all tracked operations."""
        return list(self._operations.values())
    
    def validate_thresholds(self) -> List[str]:
        """Validate performance against configured thresholds."""
        violations = []
        
        # Check global duration
        if self._global_start_time and self._global_end_time:
            total_duration = (self._global_end_time - self._global_start_time).total_seconds()
            if total_duration > self.thresholds.max_duration_seconds:
                violations.append(
                    f"Total execution time {total_duration:.1f}s exceeds threshold {self.thresholds.max_duration_seconds:.1f}s"
                )
        
        # Check peak memory usage
        if self._resource_samples:
            peak_memory = max(s['memory_mb'] for s in self._resource_samples)
            if peak_memory > self.thresholds.max_memory_mb:
                violations.append(
                    f"Peak memory usage {peak_memory:.1f}MB exceeds threshold {self.thresholds.max_memory_mb:.1f}MB"
                )
        
        # Check individual operation thresholds
        for operation in self._operations.values():
            if operation.duration > self.thresholds.max_duration_seconds:
                violations.append(
                    f"Operation '{operation.name}' duration {operation.duration:.1f}s exceeds threshold"
                )
            
            if operation.peak_memory_mb > self.thresholds.max_memory_mb:
                violations.append(
                    f"Operation '{operation.name}' memory usage {operation.peak_memory_mb:.1f}MB exceeds threshold"
                )
        
        return violations
    
    def generate_recommendations(self) -> List[str]:
        """Generate performance improvement recommendations."""
        recommendations = []
        
        if not self._operations:
            return ["No operations tracked - enable performance monitoring"]
        
        # Analyze operation durations
        completed_ops = [op for op in self._operations.values() if op.is_complete]
        if completed_ops:
            avg_duration = sum(op.duration for op in completed_ops) / len(completed_ops)
            slow_ops = [op for op in completed_ops if op.duration > avg_duration * 2]
            
            if slow_ops:
                recommendations.append(
                    f"Consider optimizing slow operations: {', '.join(op.name for op in slow_ops[:3])}"
                )
        
        # Analyze memory usage
        if self._resource_samples:
            peak_memory = max(s['memory_mb'] for s in self._resource_samples)
            if peak_memory > 1000:  # > 1GB
                recommendations.append(
                    "High memory usage detected - consider implementing memory optimization"
                )
        
        # Analyze CPU utilization
        if self._resource_samples:
            avg_cpu = sum(s['cpu_percent'] for s in self._resource_samples) / len(self._resource_samples)
            if avg_cpu < 20:  # Low CPU utilization
                recommendations.append(
                    "Low CPU utilization - consider enabling parallel execution"
                )
            elif avg_cpu > 90:  # High CPU utilization
                recommendations.append(
                    "High CPU utilization - consider reducing parallel workers"
                )
        
        return recommendations
    
    def calculate_parallel_efficiency(self, sequential_duration: float, parallel_duration: float, 
                                    worker_count: int) -> float:
        """Calculate parallel execution efficiency."""
        if parallel_duration <= 0 or worker_count <= 1:
            return 0.0
        
        # Theoretical speedup with perfect parallelization
        theoretical_duration = sequential_duration / worker_count
        
        # Actual efficiency (0.0 to 1.0)
        efficiency = theoretical_duration / parallel_duration
        
        # Cap at 1.0 (100% efficiency)
        return min(1.0, efficiency)
    
    def generate_performance_report(self) -> PerformanceReport:
        """Generate comprehensive performance report."""
        # Calculate global metrics
        total_duration = 0.0
        if self._global_start_time and self._global_end_time:
            total_duration = (self._global_end_time - self._global_start_time).total_seconds()
        
        peak_memory_mb = 0.0
        avg_cpu_utilization = 0.0
        if self._resource_samples:
            peak_memory_mb = max(s['memory_mb'] for s in self._resource_samples)
            avg_cpu_utilization = sum(s['cpu_percent'] for s in self._resource_samples) / len(self._resource_samples)
        
        # Calculate parallel efficiency (simplified)
        parallel_efficiency = 0.0
        completed_ops = [op for op in self._operations.values() if op.is_complete]
        if len(completed_ops) > 1:
            sequential_duration = sum(op.duration for op in completed_ops)
            if total_duration > 0:
                parallel_efficiency = min(1.0, sequential_duration / total_duration)
        
        # Get threshold violations and recommendations
        threshold_violations = self.validate_thresholds()
        recommendations = self.generate_recommendations()
        
        return PerformanceReport(
            total_duration=total_duration,
            peak_memory_mb=peak_memory_mb,
            avg_cpu_utilization=avg_cpu_utilization,
            parallel_efficiency=parallel_efficiency,
            operations=list(self._operations.values()),
            threshold_violations=threshold_violations,
            recommendations=recommendations,
        )
    
    def reset(self) -> None:
        """Reset all performance tracking data."""
        self.stop_monitoring()
        self._operations.clear()
        self._resource_samples.clear()
        self._global_start_time = None
        self._global_end_time = None
        self._monitoring_active = False