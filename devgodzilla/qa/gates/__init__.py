"""
DevGodzilla QA Gates Package

Composable QA gates for quality assurance.
"""

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
        FormatGate,
        CoverageGate,
    )
    from devgodzilla.qa.gates.constitutional import (
        ConstitutionalGate,
        ConstitutionalSummaryGate,
    )
    from devgodzilla.qa.gates.speckit import SpecKitChecklistGate
    from devgodzilla.qa.gates.prompt import PromptQAGate
    from devgodzilla.qa.gates.library_first import (
        LibraryFirstGate,
        LibraryFirstSummaryGate,
    )
    from devgodzilla.qa.gates.simplicity import (
        SimplicityGate,
        SimplicitySummaryGate,
    )
    from devgodzilla.qa.gates.anti_abstraction import (
        AntiAbstractionGate,
        AntiAbstractionSummaryGate,
    )
    from devgodzilla.qa.gates.test_first import TestFirstGate
    from devgodzilla.qa.gates.security import SecurityGate
    from devgodzilla.qa.gates.integration_test import IntegrationTestGate

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
    "SpecKitChecklistGate",
    "PromptQAGate",
    "FormatGate",
    "CoverageGate",
    # Constitutional gates
    "ConstitutionalGate",
    "ConstitutionalSummaryGate",
    # Article-specific constitutional gates
    "LibraryFirstGate",
    "LibraryFirstSummaryGate",
    "SimplicityGate",
    "SimplicitySummaryGate",
    "AntiAbstractionGate",
    "AntiAbstractionSummaryGate",
    # Test-first gate
    "TestFirstGate",
    # Security gate
    "SecurityGate",
    # Integration test gate
    "IntegrationTestGate",
]

_EXPORTS = {
    "Gate": "devgodzilla.qa.gates.interface",
    "GateContext": "devgodzilla.qa.gates.interface",
    "GateResult": "devgodzilla.qa.gates.interface",
    "GateVerdict": "devgodzilla.qa.gates.interface",
    "Finding": "devgodzilla.qa.gates.interface",
    "TestGate": "devgodzilla.qa.gates.common",
    "LintGate": "devgodzilla.qa.gates.common",
    "TypeGate": "devgodzilla.qa.gates.common",
    "ChecklistGate": "devgodzilla.qa.gates.common",
    "FormatGate": "devgodzilla.qa.gates.common",
    "CoverageGate": "devgodzilla.qa.gates.common",
    "ConstitutionalGate": "devgodzilla.qa.gates.constitutional",
    "ConstitutionalSummaryGate": "devgodzilla.qa.gates.constitutional",
    "SpecKitChecklistGate": "devgodzilla.qa.gates.speckit",
    "PromptQAGate": "devgodzilla.qa.gates.prompt",
    "LibraryFirstGate": "devgodzilla.qa.gates.library_first",
    "LibraryFirstSummaryGate": "devgodzilla.qa.gates.library_first",
    "SimplicityGate": "devgodzilla.qa.gates.simplicity",
    "SimplicitySummaryGate": "devgodzilla.qa.gates.simplicity",
    "AntiAbstractionGate": "devgodzilla.qa.gates.anti_abstraction",
    "AntiAbstractionSummaryGate": "devgodzilla.qa.gates.anti_abstraction",
    "TestFirstGate": "devgodzilla.qa.gates.test_first",
    "SecurityGate": "devgodzilla.qa.gates.security",
    "IntegrationTestGate": "devgodzilla.qa.gates.integration_test",
}


def __getattr__(name: str):
    module_path = _EXPORTS.get(name)
    if not module_path:
        raise AttributeError(f"module {__name__} has no attribute {name}")
    module = import_module(module_path)
    return getattr(module, name)


def __dir__() -> list[str]:
    return sorted(__all__)
