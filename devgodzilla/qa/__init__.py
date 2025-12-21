"""
DevGodzilla Quality Assurance

Constitutional QA with spec-kit checklist integration.
Composable QA gates (TestGate, LintGate, ChecklistGate).
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
        FormatGate,
        CoverageGate,
        ConstitutionalGate,
        ConstitutionalSummaryGate,
        PromptQAGate,
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
    "FormatGate",
    "CoverageGate",
    # Constitutional gates
    "ConstitutionalGate",
    "ConstitutionalSummaryGate",
    "PromptQAGate",
    # Feedback routing
    "FeedbackRouter",
    "FeedbackAction",
    "FeedbackRoute",
    "RoutedFeedback",
    "ErrorCategory",
    "classify_error",
]

_GATE_EXPORTS = {
    "Gate",
    "GateContext",
    "GateResult",
    "GateVerdict",
    "Finding",
    "TestGate",
    "LintGate",
    "TypeGate",
    "ChecklistGate",
    "FormatGate",
    "CoverageGate",
    "ConstitutionalGate",
    "ConstitutionalSummaryGate",
    "PromptQAGate",
}
_FEEDBACK_EXPORTS = {
    "FeedbackRouter",
    "FeedbackAction",
    "FeedbackRoute",
    "RoutedFeedback",
    "ErrorCategory",
    "classify_error",
}


def __getattr__(name: str):
    if name in _GATE_EXPORTS:
        from devgodzilla.qa import gates as gates_module
        return getattr(gates_module, name)
    if name in _FEEDBACK_EXPORTS:
        from devgodzilla.qa import feedback as feedback_module
        return getattr(feedback_module, name)
    raise AttributeError(f"module {__name__} has no attribute {name}")


def __dir__() -> list[str]:
    return sorted(__all__)
