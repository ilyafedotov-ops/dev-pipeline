"""
Prompt-driven QA Gate

Runs the quality-validator prompt through the configured QA engine.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import time
from pathlib import Path
from typing import Optional

from devgodzilla.engines.interface import Engine, EngineRequest, EngineResult, SandboxMode
from devgodzilla.qa.gates.interface import Gate, GateContext, GateResult, GateVerdict, Finding


class PromptQAGate(Gate):
    def __init__(
        self,
        *,
        engine: Engine,
        prompt_path: Path,
        model: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ) -> None:
        self._engine = engine
        self._prompt_path = prompt_path
        self._model = model
        self._timeout_seconds = timeout_seconds

    @property
    def gate_id(self) -> str:
        return "prompt_qa"

    @property
    def gate_name(self) -> str:
        return "Prompt QA"

    def run(self, context: GateContext) -> GateResult:
        start = time.time()
        if not self._prompt_path.exists():
            return self.error(f"QA prompt not found: {self._prompt_path}")

        if not self._engine.check_availability():
            return self.error(f"QA engine unavailable: {self._engine.metadata.id}")

        prompt_text = self._build_prompt(context)
        prompt_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:16]

        req = EngineRequest(
            project_id=context.project_id or 0,
            protocol_run_id=context.protocol_run_id or 0,
            step_run_id=context.step_run_id or 0,
            model=self._model,
            prompt_text=prompt_text,
            working_dir=context.workspace_root,
            sandbox=SandboxMode.READ_ONLY,
            timeout=self._timeout_seconds,
            extra={},
        )

        result = self._engine.qa(req)
        duration = time.time() - start
        gate_result = self._parse_result(result, duration_seconds=duration)
        gate_result.metadata.update(
            {
                "prompt_path": str(self._prompt_path),
                "prompt_hash": prompt_hash,
                "engine_id": self._engine.metadata.id,
                "model": req.model or self._engine.metadata.default_model,
                "report_text": result.stdout.strip(),
            }
        )
        return gate_result

    def _build_prompt(self, context: GateContext) -> str:
        prompt_header = self._prompt_path.read_text(encoding="utf-8")
        protocol_root = Path(context.protocol_root) if context.protocol_root else None
        step_name = context.step_name or ""

        plan_text = self._read_file(protocol_root / "plan.md") if protocol_root else ""
        context_text = self._read_file(protocol_root / "context.md") if protocol_root else ""
        log_text = self._read_file(protocol_root / "log.md") if protocol_root else ""
        step_text = ""
        if protocol_root and step_name:
            step_text = self._read_file(protocol_root / f"{step_name}.md")

        git_status = self._git_cmd(["git", "status", "--porcelain"], context.workspace_root)
        last_commit = self._git_cmd(["git", "log", "-1", "--pretty=%B"], context.workspace_root)

        sections = [
            prompt_header,
            "",
            "## plan.md",
            plan_text or "MISSING",
            "",
            "## context.md",
            context_text or "MISSING",
            "",
            "## log.md",
            log_text or "MISSING",
            "",
            f"## {step_name or 'step'}.md",
            step_text or "MISSING",
            "",
            "## git status",
            git_status or "MISSING",
            "",
            "## last commit",
            last_commit or "MISSING",
        ]
        return "\n".join(sections).strip()

    @staticmethod
    def _read_file(path: Path) -> str:
        try:
            if path.exists():
                return path.read_text(encoding="utf-8")
        except Exception:
            pass
        return ""

    @staticmethod
    def _git_cmd(cmd: list[str], cwd: str) -> str:
        try:
            proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=10)
            if proc.returncode == 0:
                return proc.stdout.strip()
            return (proc.stdout or proc.stderr or "").strip()
        except Exception:
            return ""

    def _parse_result(self, result: EngineResult, *, duration_seconds: float) -> GateResult:
        output = (result.stdout or "").strip()
        verdict = self._extract_verdict(output)
        findings = []
        if verdict == GateVerdict.FAIL:
            findings.append(
                Finding(
                    gate_id=self.gate_id,
                    severity="error",
                    message="Prompt QA reported FAIL",
                )
            )
        elif verdict == GateVerdict.ERROR:
            findings.append(
                Finding(
                    gate_id=self.gate_id,
                    severity="error",
                    message=result.error or "Prompt QA failed to return a verdict",
                )
            )

        return GateResult(
            gate_id=self.gate_id,
            gate_name=self.gate_name,
            verdict=verdict,
            findings=findings,
            duration_seconds=duration_seconds,
        )

    @staticmethod
    def _extract_verdict(text: str) -> GateVerdict:
        match = re.search(
            r"\bVerdict\s*:\s*(PASS|FAIL|WARN|WARNING|SKIP|SKIPPED|ERROR)\b",
            text,
            re.IGNORECASE,
        )
        if not match:
            return GateVerdict.SKIP
        verdict = match.group(1).upper()
        if verdict in ("WARN", "WARNING"):
            return GateVerdict.WARN
        if verdict in ("SKIP", "SKIPPED"):
            return GateVerdict.SKIP
        if verdict == "ERROR":
            return GateVerdict.ERROR
        return GateVerdict.PASS if verdict == "PASS" else GateVerdict.FAIL
