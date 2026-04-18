"""Central registry for QA gates with dynamic registration.

The GateRegistry provides a centralized way to:
- Register and unregister gate instances
- Organize gates by category
- Evaluate gates individually or in batches
- Create registries with default gate configurations
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Type
import time

from devgodzilla.qa.gates.interface import Gate, GateContext, GateResult, GateVerdict
from devgodzilla.logging import get_logger

logger = get_logger(__name__)


@dataclass
class GateRegistry:
    """Central registry for all QA gates.
    
    Provides dynamic registration and lookup of QA gates, organized by
    category for flexible evaluation strategies.
    
    Example:
        registry = GateRegistry()
        registry.register(LintGate(), category="code_quality")
        registry.register(TestGate(), category="testing")
        
        # Evaluate all gates
        results = registry.evaluate_all(context)
        
        # Evaluate specific category
        results = registry.evaluate_category("code_quality", context)
    """
    
    _gates: Dict[str, Gate] = field(default_factory=dict)
    _categories: Dict[str, List[str]] = field(default_factory=dict)
    
    def register(self, gate: Gate, category: str = "general") -> None:
        """Register a gate instance.
        
        Args:
            gate: Gate instance to register
            category: Category for grouping (default: "general")
            
        Raises:
            ValueError: If gate_id is empty or already registered
        """
        if not gate.gate_id:
            raise ValueError("Gate must have a non-empty gate_id")
        
        if gate.gate_id in self._gates:
            logger.warning(
                "gate_registry_overwrite",
                extra={"gate_id": gate.gate_id, "category": category},
            )
            # Remove from old category if exists
            for cat_gates in self._categories.values():
                if gate.gate_id in cat_gates:
                    cat_gates.remove(gate.gate_id)
        
        self._gates[gate.gate_id] = gate
        
        if category not in self._categories:
            self._categories[category] = []
        
        if gate.gate_id not in self._categories[category]:
            self._categories[category].append(gate.gate_id)
        
        logger.debug(
            "gate_registered",
            extra={"gate_id": gate.gate_id, "category": category},
        )
    
    def unregister(self, gate_id: str) -> Optional[Gate]:
        """Remove a gate from registry.
        
        Args:
            gate_id: ID of gate to remove
            
        Returns:
            The removed gate, or None if not found
        """
        gate = self._gates.pop(gate_id, None)
        if gate:
            # Remove from all categories
            for cat_gates in self._categories.values():
                if gate_id in cat_gates:
                    cat_gates.remove(gate_id)
            logger.debug("gate_unregistered", extra={"gate_id": gate_id})
        return gate
    
    def get(self, gate_id: str) -> Optional[Gate]:
        """Get gate by ID.
        
        Args:
            gate_id: Gate identifier
            
        Returns:
            Gate instance or None if not found
        """
        return self._gates.get(gate_id)
    
    def get_by_category(self, category: str) -> List[Gate]:
        """Get all gates in a category.
        
        Args:
            category: Category name
            
        Returns:
            List of gate instances in the category
        """
        gate_ids = self._categories.get(category, [])
        gates = []
        for gid in gate_ids:
            gate = self._gates.get(gid)
            if gate:
                gates.append(gate)
        return gates
    
    def get_categories(self) -> List[str]:
        """Get all category names.
        
        Returns:
            List of category names
        """
        return list(self._categories.keys())
    
    def list_all(self) -> List[Gate]:
        """List all registered gates.
        
        Returns:
            List of all gate instances
        """
        return list(self._gates.values())
    
    def list_ids(self) -> List[str]:
        """List all gate IDs.
        
        Returns:
            List of gate identifiers
        """
        return list(self._gates.keys())
    
    def has(self, gate_id: str) -> bool:
        """Check if a gate is registered.
        
        Args:
            gate_id: Gate identifier
            
        Returns:
            True if gate is registered
        """
        return gate_id in self._gates
    
    def evaluate_all(self, context: GateContext) -> List[GateResult]:
        """Evaluate all registered gates.
        
        Args:
            context: Gate execution context
            
        Returns:
            List of gate results
        """
        return self.evaluate_gates(list(self._gates.keys()), context)
    
    def evaluate_category(self, category: str, context: GateContext) -> List[GateResult]:
        """Evaluate all gates in a category.
        
        Args:
            category: Category name
            context: Gate execution context
            
        Returns:
            List of gate results
        """
        gate_ids = self._categories.get(category, [])
        return self.evaluate_gates(gate_ids, context)
    
    def evaluate_gates(self, gate_ids: List[str], context: GateContext) -> List[GateResult]:
        """Evaluate specific gates by ID.
        
        Args:
            gate_ids: List of gate identifiers to evaluate
            context: Gate execution context
            
        Returns:
            List of gate results
        """
        results: List[GateResult] = []
        
        for gate_id in gate_ids:
            gate = self._gates.get(gate_id)
            if not gate:
                logger.warning(
                    "gate_not_found",
                    extra={"gate_id": gate_id},
                )
                continue
            
            if not gate.enabled:
                results.append(gate.skip("Gate disabled"))
                continue
            
            try:
                start = time.time()
                result = gate.run(context)
                if result.duration_seconds is None:
                    result.duration_seconds = time.time() - start
                results.append(result)
            except Exception as e:
                logger.error(
                    "gate_evaluation_failed",
                    extra={"gate_id": gate_id, "error": str(e)},
                )
                results.append(gate.error(str(e)))
        
        return results
    
    def clear(self) -> None:
        """Remove all registered gates."""
        self._gates.clear()
        self._categories.clear()
        logger.debug("gate_registry_cleared")
    
    def __len__(self) -> int:
        """Return number of registered gates."""
        return len(self._gates)
    
    def __contains__(self, gate_id: str) -> bool:
        """Check if gate is registered."""
        return gate_id in self._gates


def create_default_registry(
    include_gates: Optional[List[str]] = None,
    exclude_gates: Optional[List[str]] = None,
) -> GateRegistry:
    """Create registry with all default gates registered.
    
    Args:
        include_gates: Optional list of gate IDs to include (if None, include all)
        exclude_gates: Optional list of gate IDs to exclude
        
    Returns:
        GateRegistry with default gates registered
    """
    registry = GateRegistry()
    
    include_set = set(include_gates) if include_gates else None
    exclude_set = set(exclude_gates) if exclude_gates else set()
    
    # Import gates lazily to avoid circular imports
    from devgodzilla.qa.gates import (
        TestGate,
        LintGate,
        TypeGate,
        ChecklistGate,
        FormatGate,
        CoverageGate,
        SecurityGate,
        IntegrationTestGate,
    )
    
    # Import ChecklistValidator and wrap it as a gate
    from devgodzilla.qa.checklist_validator import ChecklistValidator
    from devgodzilla.qa.gates.interface import Gate, GateContext, GateResult, GateVerdict, Finding
    
    class ChecklistValidatorGate(Gate):
        """Gate adapter that delegates to ChecklistValidator."""
        
        __test__ = False
        
        def __init__(self, validator: ChecklistValidator) -> None:
            self._validator = validator
        
        @property
        def gate_id(self) -> str:
            return "checklist_validator"
        
        @property
        def gate_name(self) -> str:
            return "Checklist Validator Gate"
        
        def run(self, context: GateContext) -> GateResult:
            import time as _time
            from pathlib import Path as _Path
            
            start = _time.time()
            workspace = _Path(context.workspace_root)
            
            # Collect checklist files from workspace
            checklist_files = list(workspace.glob("**/*checklist*.md")) + \
                              list(workspace.glob("**/*CHECKLIST*"))
            
            if not checklist_files:
                return self.skip("No checklist files found")
            
            # Collect artifact files
            artifacts = [
                p for p in workspace.rglob("*")
                if p.is_file() and p.suffix in (".py", ".js", ".ts", ".md")
                and ".venv" not in str(p) and "node_modules" not in str(p)
            ][:100]
            
            all_findings: list[Finding] = []
            total_items = 0
            passed_items = 0
            
            for checklist_file in checklist_files:
                try:
                    content = checklist_file.read_text()
                    items = self._validator.parse_checklist(content)
                    total_items += len(items)
                    
                    results = self._validator.validate_all(items, artifacts)
                    for r in results:
                        if r.passed:
                            passed_items += 1
                        else:
                            all_findings.append(Finding(
                                gate_id=self.gate_id,
                                severity="warning",
                                message=f"Checklist item not satisfied: {r.item_id}",
                                metadata={
                                    "reasoning": r.reasoning,
                                    "confidence": r.confidence,
                                },
                            ))
                except Exception as e:
                    all_findings.append(Finding(
                        gate_id=self.gate_id,
                        severity="warning",
                        message=f"Failed to process {checklist_file.name}: {e}",
                    ))
            
            duration = _time.time() - start
            
            if total_items == 0:
                return self.skip("No checklist items found")
            
            verdict = GateVerdict.PASS if passed_items == total_items else GateVerdict.WARN
            
            return GateResult(
                gate_id=self.gate_id,
                gate_name=self.gate_name,
                verdict=verdict,
                findings=all_findings,
                duration_seconds=duration,
                metadata={
                    "total_items": total_items,
                    "passed_items": passed_items,
                    "checklist_files": [str(f) for f in checklist_files],
                },
            )
    
    _checklist_validator_gate = ChecklistValidatorGate(ChecklistValidator())
    
    # Standard gates with their categories
    default_gates = [
        (TestGate(), "testing"),
        (LintGate(), "code_quality"),
        (TypeGate(), "type_safety"),
        (ChecklistGate(), "validation"),
        (FormatGate(), "code_quality"),
        (CoverageGate(), "testing"),
        (SecurityGate(), "security"),
        (IntegrationTestGate(), "testing"),
        (_checklist_validator_gate, "validation"),
    ]
    
    for gate, category in default_gates:
        if include_set is not None and gate.gate_id not in include_set:
            continue
        if gate.gate_id in exclude_set:
            continue
        registry.register(gate, category=category)
    
    logger.info(
        "default_registry_created",
        extra={
            "gate_count": len(registry),
            "gates": registry.list_ids(),
        },
    )
    
    return registry


# Module-level singleton for convenience
_default_registry: Optional[GateRegistry] = None


def get_default_registry() -> GateRegistry:
    """Get or create the default gate registry singleton.
    
    Returns:
        The default GateRegistry instance
    """
    global _default_registry
    if _default_registry is None:
        _default_registry = create_default_registry()
    return _default_registry


def reset_default_registry() -> None:
    """Reset the default registry singleton."""
    global _default_registry
    _default_registry = None
