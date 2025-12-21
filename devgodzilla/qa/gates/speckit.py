"""
SpecKit Checklist Gate

Evaluates SpecKit checklist markdown and reports unchecked items.
"""

import re
import time
from pathlib import Path
from typing import List, Optional

from devgodzilla.qa.gates.interface import Gate, GateContext, GateResult, GateVerdict, Finding


class SpecKitChecklistGate(Gate):
    def __init__(self, *, checklist_path: Optional[Path] = None) -> None:
        self.checklist_path = checklist_path

    @property
    def gate_id(self) -> str:
        return "speckit_checklist"

    @property
    def gate_name(self) -> str:
        return "SpecKit Checklist"

    def has_checklist(self, context: GateContext) -> bool:
        return self._resolve_checklist_path(context).exists()

    def run(self, context: GateContext) -> GateResult:
        start = time.time()
        checklist_path = self._resolve_checklist_path(context)
        if not checklist_path.exists():
            return self.skip("Checklist not found")

        content = checklist_path.read_text(encoding="utf-8")
        findings: List[Finding] = []
        total_items = 0
        unchecked_items = 0

        for line in content.splitlines():
            match = re.match(r"^\s*-\s*\[([ xX])\]\s*(.+)$", line)
            if not match:
                continue
            total_items += 1
            status = match.group(1).strip().lower()
            text = match.group(2).strip()
            if status != "x":
                unchecked_items += 1
                findings.append(
                    Finding(
                        gate_id=self.gate_id,
                        severity="warning",
                        message=f"Unchecked checklist item: {text}",
                        file_path=str(checklist_path),
                    )
                )

        duration = time.time() - start
        if total_items == 0:
            return self.skip("Checklist has no items")

        verdict = GateVerdict.PASS if unchecked_items == 0 else GateVerdict.WARN
        return GateResult(
            gate_id=self.gate_id,
            gate_name=self.gate_name,
            verdict=verdict,
            findings=findings,
            duration_seconds=duration,
            metadata={
                "checklist_path": str(checklist_path),
                "total_items": total_items,
                "unchecked_items": unchecked_items,
            },
        )

    def _resolve_checklist_path(self, context: GateContext) -> Path:
        protocol_root = Path(context.protocol_root)
        candidates = [protocol_root / "checklist.md"]
        if protocol_root.name == "_runtime":
            candidates.append(protocol_root.parent / "checklist.md")
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]
