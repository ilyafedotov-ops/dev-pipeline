"""Data models for CLI workflow harness."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime


class HarnessStatus(Enum):
    """Test execution status."""
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    ERROR = "error"


@dataclass
class TestResult:
    """Result of a single test execution."""
    component: str
    test_name: str
    status: HarnessStatus
    duration: float
    error_message: Optional[str] = None
    artifacts: List[Path] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class WorkflowResult:
    """Result of a complete workflow execution."""
    workflow_name: str
    steps: List[TestResult]
    overall_status: HarnessStatus
    data_artifacts: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> float:
        """Total duration of all steps."""
        return sum(step.duration for step in self.steps)
    
    @property
    def passed_steps(self) -> int:
        """Number of passed steps."""
        return sum(1 for step in self.steps if step.status == HarnessStatus.PASS)
    
    @property
    def failed_steps(self) -> int:
        """Number of failed steps."""
        return sum(1 for step in self.steps if step.status == HarnessStatus.FAIL)


@dataclass
class MissingFeature:
    """Identified missing feature or functionality."""
    feature_name: str
    component: str
    description: str
    impact: str  # "critical", "major", "minor"
    related_tests: List[str] = field(default_factory=list)


@dataclass
class Recommendation:
    """Actionable recommendation for improvement."""
    priority: int
    category: str  # "fix", "implement", "improve"
    description: str
    estimated_effort: str
    related_components: List[str] = field(default_factory=list)


@dataclass
class PerformanceMetrics:
    """Performance metrics for test execution."""
    total_duration: float
    peak_memory_mb: float
    cpu_utilization: float
    parallel_efficiency: float = 0.0
    threshold_violations: List[str] = field(default_factory=list)
    performance_recommendations: List[str] = field(default_factory=list)
    
    
@dataclass
class HarnessReport:
    """Comprehensive report of harness execution."""
    execution_id: str
    mode: str
    start_time: datetime
    end_time: datetime
    test_results: List[TestResult]
    workflow_results: List[WorkflowResult]
    missing_features: List[MissingFeature]
    recommendations: List[Recommendation]
    performance_metrics: PerformanceMetrics
    environment_info: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def total_tests(self) -> int:
        """Total number of tests executed."""
        return len(self.test_results)
    
    @property
    def passed_tests(self) -> int:
        """Number of passed tests."""
        return sum(1 for result in self.test_results if result.status == HarnessStatus.PASS)
    
    @property
    def failed_tests(self) -> int:
        """Number of failed tests."""
        return sum(1 for result in self.test_results if result.status == HarnessStatus.FAIL)
    
    @property
    def success_rate(self) -> float:
        """Test success rate as percentage."""
        if self.total_tests == 0:
            return 0.0
        return (self.passed_tests / self.total_tests) * 100.0