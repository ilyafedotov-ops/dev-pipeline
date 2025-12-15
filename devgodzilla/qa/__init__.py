"""
DevGodzilla Quality Assurance

Constitutional QA with spec-kit checklist integration.
Composable QA gates (TestGate, LintGate, ChecklistGate).
"""

from devgodzilla.qa.gates import (
    Gate,
    GateContext,
    GateResult,
    GateVerdict,
    Finding,
    TestGate,
    LintGate,
    TypeGate,
    ChecklistGate,
    ConstitutionalGate,
    ConstitutionalSummaryGate,
)
from devgodzilla.qa.feedback import (
    FeedbackRouter,
    FeedbackAction,
    FeedbackRoute,
    RoutedFeedback,
    ErrorCategory,
    classify_error,
)

__all__ = [
    # Gates interface
    "Gate",
    "GateContext",
    "GateResult",
    "GateVerdict",
    "Finding",
    # Common gates
    "TestGate",
    "LintGate",
    "TypeGate",
    "ChecklistGate",
    # Constitutional gates
    "ConstitutionalGate",
    "ConstitutionalSummaryGate",
    # Feedback routing
    "FeedbackRouter",
    "FeedbackAction",
    "FeedbackRoute",
    "RoutedFeedback",
    "ErrorCategory",
    "classify_error",
]
