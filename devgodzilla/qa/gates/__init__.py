"""
DevGodzilla QA Gates Package

Composable QA gates for quality assurance.
"""

from devgodzilla.qa.gates.interface import (
    Gate,
    GateContext,
    GateResult,
    GateVerdict,
    Finding,
)
from devgodzilla.qa.gates.common import (
    TestGate,
    LintGate,
    TypeGate,
    ChecklistGate,
)
from devgodzilla.qa.gates.constitutional import (
    ConstitutionalGate,
    ConstitutionalSummaryGate,
)

__all__ = [
    # Interface
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
]
