"""
DevGodzilla QA Gate Interface

Defines the abstract interface for QA gates.
Gates are composable validation units for quality assurance.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from devgodzilla.logging import get_logger

logger = get_logger(__name__)


class GateVerdict(str, Enum):
    """Verdict from a QA gate."""
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"
    ERROR = "error"


@dataclass
class Finding:
    """A finding from a QA gate."""
    gate_id: str
    severity: str  # "info", "warning", "error", "critical"
    message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    rule_id: Optional[str] = None
    suggestion: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GateResult:
    """Result from running a QA gate."""
    gate_id: str
    gate_name: str
    verdict: GateVerdict
    findings: List[Finding] = field(default_factory=list)
    duration_seconds: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    
    @property
    def passed(self) -> bool:
        return self.verdict in (GateVerdict.PASS, GateVerdict.WARN, GateVerdict.SKIP)
    
    @property
    def blocking(self) -> bool:
        return self.verdict in (GateVerdict.FAIL, GateVerdict.ERROR)


@dataclass
class GateContext:
    """Context for running QA gates."""
    workspace_root: str
    protocol_root: Optional[str] = None
    step_name: Optional[str] = None
    step_run_id: Optional[int] = None
    protocol_run_id: Optional[int] = None
    project_id: Optional[int] = None
    
    # Artifacts from execution
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    
    # Additional context
    metadata: Dict[str, Any] = field(default_factory=dict)


class Gate(ABC):
    """
    Abstract base class for QA gates.
    
    Gates are composable validation units that check specific aspects
    of code quality:
    - TestGate: Runs tests
    - LintGate: Runs linters
    - TypeGate: Runs type checkers
    - ChecklistGate: Validates against checklists
    - ConstitutionalGate: Validates against constitution articles
    
    Example:
        class MyGate(Gate):
            @property
            def gate_id(self) -> str:
                return "my-gate"
            
            @property
            def gate_name(self) -> str:
                return "My Custom Gate"
            
            def run(self, context: GateContext) -> GateResult:
                # Validation logic
                return GateResult(
                    gate_id=self.gate_id,
                    gate_name=self.gate_name,
                    verdict=GateVerdict.PASS,
                )
    """

    @property
    @abstractmethod
    def gate_id(self) -> str:
        """Unique identifier for this gate."""
        ...

    @property
    @abstractmethod
    def gate_name(self) -> str:
        """Human-readable name."""
        ...

    @property
    def blocking(self) -> bool:
        """Whether this gate blocks on failure."""
        return True

    @property
    def enabled(self) -> bool:
        """Whether this gate is enabled."""
        return True

    @abstractmethod
    def run(self, context: GateContext) -> GateResult:
        """
        Run the gate validation.
        
        Args:
            context: Gate execution context
            
        Returns:
            GateResult with verdict and findings
        """
        ...

    def skip(self, reason: str = "Skipped") -> GateResult:
        """Return a skip result."""
        return GateResult(
            gate_id=self.gate_id,
            gate_name=self.gate_name,
            verdict=GateVerdict.SKIP,
            metadata={"skip_reason": reason},
        )

    def error(self, error_msg: str) -> GateResult:
        """Return an error result."""
        return GateResult(
            gate_id=self.gate_id,
            gate_name=self.gate_name,
            verdict=GateVerdict.ERROR,
            error=error_msg,
        )
