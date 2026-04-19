"""
DevGodzilla Dummy Engine

No-op engine used for UI/integration testing when no real agent CLI is installed.
"""

from __future__ import annotations

import time
from typing import Optional

from devgodzilla.logging import get_logger
from devgodzilla.engines.interface import (
    Engine,
    EngineKind,
    EngineMetadata,
    EngineRequest,
    EngineResult,
)

logger = get_logger(__name__)


class DummyEngine(Engine):
    @property
    def metadata(self) -> EngineMetadata:
        return EngineMetadata(
            id="dummy",
            display_name="Dummy (no-op)",
            kind=EngineKind.CLI,
            default_model=None,
            description="No-op engine for integration testing; does not modify the repo.",
            capabilities=["plan", "execute", "qa"],
        )

    def plan(self, req: EngineRequest) -> EngineResult:
        return self._ok(req, stage="plan")

    def execute(self, req: EngineRequest) -> EngineResult:
        return self._ok(req, stage="execute")

    def qa(self, req: EngineRequest) -> EngineResult:
        return self._ok(req, stage="qa")

    def check_availability(self) -> bool:
        return True

    def _ok(self, req: EngineRequest, *, stage: str) -> EngineResult:
        start = time.time()
        prompt = (req.prompt_text or "").strip()
        preview = (prompt[:300] + "…") if len(prompt) > 300 else prompt
        verdict_line = "\nVerdict: PASS\n" if stage == "qa" else "\n"
        return EngineResult(
            success=True,
            stdout=f"dummy:{stage}: step_run_id={req.step_run_id}{verdict_line}{preview}\n",
            stderr="",
            duration_seconds=max(0.0, time.time() - start),
            metadata={
                "engine_id": self.metadata.id,
                "stage": stage,
                "note": "No-op execution (testing mode)",
            },
        )
