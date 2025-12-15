"""
DevGodzilla Quality Service

Service for quality assurance and validation of protocol steps.
Orchestrates QA gates and manages verdicts.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from devgodzilla.logging import get_logger
from devgodzilla.models.domain import (
    ProtocolRun,
    ProtocolStatus,
    StepRun,
    StepStatus,
)
from devgodzilla.qa.gates import (
    Gate,
    GateContext,
    GateResult,
    GateVerdict,
    Finding,
    TestGate,
    LintGate,
    TypeGate,
)
from devgodzilla.services.base import Service, ServiceContext
from devgodzilla.services.events import get_event_bus

logger = get_logger(__name__)


class QAVerdict(str, Enum):
    """Overall QA verdict."""
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"
    ERROR = "error"


@dataclass
class QAResult:
    """Result from QA execution."""
    step_run_id: int
    verdict: QAVerdict
    gate_results: List[GateResult] = field(default_factory=list)
    duration_seconds: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    
    @property
    def passed(self) -> bool:
        return self.verdict in (QAVerdict.PASS, QAVerdict.WARN, QAVerdict.SKIP)
    
    @property
    def all_findings(self) -> List[Finding]:
        findings = []
        for result in self.gate_results:
            findings.extend(result.findings)
        return findings
    
    @property
    def blocking_findings(self) -> List[Finding]:
        return [f for f in self.all_findings if f.severity == "error"]


class QualityService(Service):
    """
    Service for quality assurance and validation.
    
    Responsibilities:
    - Run composable QA gates
    - Aggregate gate results into verdicts
    - Update step status based on QA results
    - Support auto-fix for certain error types
    
    Example:
        quality = QualityService(context, db)
        
        # Run QA for a step
        result = quality.run_qa(step_run_id=123)
        
        if result.passed:
            print("QA passed!")
        else:
            for finding in result.blocking_findings:
                print(f"Error: {finding.message}")
    """

    def __init__(
        self,
        context: ServiceContext,
        db,
        *,
        default_gates: Optional[List[Gate]] = None,
    ) -> None:
        super().__init__(context)
        self.db = db
        self.default_gates = default_gates or [
            LintGate(),
            TypeGate(),
            TestGate(),
        ]

    def run_qa(
        self,
        step_run_id: int,
        *,
        job_id: Optional[str] = None,
        gates: Optional[List[Gate]] = None,
        skip_gates: Optional[List[str]] = None,
    ) -> QAResult:
        """
        Run QA for a step.
        
        Args:
            step_run_id: Step run ID
            job_id: Optional job ID for tracking
            gates: Override gates to run (defaults to default_gates)
            skip_gates: Gate IDs to skip
            
        Returns:
            QAResult with verdict and findings
        """
        import time
        start = time.time()
        
        step = self.db.get_step_run(step_run_id)
        run = self.db.get_protocol_run(step.protocol_run_id)
        project = self.db.get_project(run.project_id)
        
        self.logger.info(
            "run_qa_started",
            extra=self.log_extra(
                step_run_id=step_run_id,
                step_name=step.step_name,
            ),
        )
        
        # Build gate context
        workspace_root = self._get_workspace(run, project)
        protocol_root = run.protocol_root or str(workspace_root / ".specify" / "specs" / run.protocol_name)
        
        context = GateContext(
            workspace_root=str(workspace_root),
            protocol_root=protocol_root,
            step_name=step.step_name,
            step_run_id=step_run_id,
            protocol_run_id=run.id,
            project_id=project.id,
        )
        
        # Run gates
        gates_to_run = gates or self.default_gates
        skip_ids = set(skip_gates or [])
        
        gate_results = []
        for gate in gates_to_run:
            if gate.gate_id in skip_ids:
                gate_results.append(gate.skip("Skipped by user"))
                continue
            
            if not gate.enabled:
                gate_results.append(gate.skip("Gate disabled"))
                continue
            
            try:
                result = gate.run(context)
                gate_results.append(result)
            except Exception as e:
                gate_results.append(gate.error(str(e)))
        
        # Aggregate verdict
        verdict = self._aggregate_verdict(gate_results)
        duration = time.time() - start
        
        qa_result = QAResult(
            step_run_id=step_run_id,
            verdict=verdict,
            gate_results=gate_results,
            duration_seconds=duration,
        )
        
        # Update step status
        self._update_step_status(step, run, qa_result)
        
        self.logger.info(
            "run_qa_completed",
            extra=self.log_extra(
                step_run_id=step_run_id,
                verdict=verdict.value,
                duration=duration,
                findings_count=len(qa_result.all_findings),
            ),
        )
        
        return qa_result

    def run_inline_qa(
        self,
        step_run_id: int,
        *,
        gates: Optional[List[Gate]] = None,
    ) -> QAResult:
        """
        Run lightweight inline QA after execution.
        
        Uses a smaller set of gates for faster feedback.
        """
        inline_gates = gates or [LintGate()]
        return self.run_qa(step_run_id, gates=inline_gates)

    def _get_workspace(self, run: ProtocolRun, project) -> Path:
        """Get workspace root path."""
        if run.worktree_path:
            return Path(run.worktree_path).expanduser()
        elif project.local_path:
            return Path(project.local_path).expanduser()
        return Path.cwd()

    def _aggregate_verdict(self, gate_results: List[GateResult]) -> QAVerdict:
        """Aggregate gate results into overall verdict."""
        if not gate_results:
            return QAVerdict.SKIP
        
        # Check for blocking failures
        blocking_failures = [
            r for r in gate_results
            if r.verdict == GateVerdict.FAIL or r.verdict == GateVerdict.ERROR
        ]
        
        if blocking_failures:
            return QAVerdict.FAIL
        
        # Check for warnings
        warnings = [r for r in gate_results if r.verdict == GateVerdict.WARN]
        if warnings:
            return QAVerdict.WARN
        
        # All passed or skipped
        return QAVerdict.PASS

    def _update_step_status(
        self,
        step: StepRun,
        run: ProtocolRun,
        result: QAResult,
    ) -> None:
        """Update step status based on QA result."""
        if result.verdict == QAVerdict.PASS:
            self.db.update_step_status(
                step.id,
                StepStatus.COMPLETED,
                summary="QA passed",
            )
        elif result.verdict == QAVerdict.WARN:
            self.db.update_step_status(
                step.id,
                StepStatus.COMPLETED,
                summary=f"QA passed with {len(result.all_findings)} warnings",
            )
        elif result.verdict == QAVerdict.FAIL:
            self.db.update_step_status(
                step.id,
                StepStatus.FAILED,
                summary=f"QA failed: {len(result.blocking_findings)} errors",
            )
            self.db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
        elif result.verdict == QAVerdict.ERROR:
            self.db.update_step_status(
                step.id,
                StepStatus.FAILED,
                summary=f"QA error: {result.error}",
            )

    def evaluate_step(
        self,
        workspace_root: Path,
        step_name: str,
        *,
        gates: Optional[List[Gate]] = None,
    ) -> QAResult:
        """
        Evaluate a step without database context.
        
        Useful for standalone QA evaluation.
        """
        import time
        start = time.time()
        
        context = GateContext(
            workspace_root=str(workspace_root),
            step_name=step_name,
        )
        
        gates_to_run = gates or self.default_gates
        gate_results = []
        
        for gate in gates_to_run:
            try:
                result = gate.run(context)
                gate_results.append(result)
            except Exception as e:
                gate_results.append(gate.error(str(e)))
        
        verdict = self._aggregate_verdict(gate_results)
        
        return QAResult(
            step_run_id=0,
            verdict=verdict,
            gate_results=gate_results,
            duration_seconds=time.time() - start,
        )

    def persist_verdict(
        self,
        qa_result: QAResult,
        step_run_id: int,
    ) -> None:
        """
        Persist QA verdict to database.
        
        Args:
            qa_result: QA result to persist
            step_run_id: Step run ID
        """
        try:
            # Store verdict as JSON in step's runtime_state
            verdict_data = {
                "verdict": qa_result.verdict.value,
                "duration_seconds": qa_result.duration_seconds,
                "gate_count": len(qa_result.gate_results),
                "findings_count": len(qa_result.all_findings),
                "gates": [
                    {
                        "gate_id": r.gate_id,
                        "verdict": r.verdict.value if hasattr(r.verdict, 'value') else str(r.verdict),
                        "findings_count": len(r.findings),
                    }
                    for r in qa_result.gate_results
                ],
            }
            
            step = self.db.get_step_run(step_run_id)
            runtime_state = step.runtime_state or {}
            runtime_state["qa_verdict"] = verdict_data
            
            self.db.update_step_run(step_run_id, runtime_state=runtime_state)
            
            self.logger.info(
                "qa_verdict_persisted",
                extra=self.log_extra(
                    step_run_id=step_run_id,
                    verdict=qa_result.verdict.value,
                ),
            )
        except Exception as e:
            self.logger.error(
                "qa_verdict_persist_failed",
                extra=self.log_extra(step_run_id=step_run_id, error=str(e)),
            )

    def generate_quality_report(
        self,
        qa_result: QAResult,
        output_path: Path,
        *,
        step_name: Optional[str] = None,
        include_findings: bool = True,
    ) -> Path:
        """
        Generate a quality-report.md file.
        
        Args:
            qa_result: QA result to report on
            output_path: Directory to write report to
            step_name: Optional step name for context
            include_findings: Whether to include detailed findings
            
        Returns:
            Path to generated report
        """
        import datetime
        
        report_path = output_path / "quality-report.md"
        
        lines = [
            "# Quality Assurance Report",
            "",
            f"> Generated: {datetime.datetime.now().isoformat()}",
            f"> Step: {step_name or 'N/A'}",
            "",
            "---",
            "",
            f"## Verdict: **{qa_result.verdict.value.upper()}**",
            "",
            f"- Duration: {qa_result.duration_seconds:.2f}s" if qa_result.duration_seconds else "",
            f"- Total findings: {len(qa_result.all_findings)}",
            f"- Blocking findings: {len(qa_result.blocking_findings)}",
            "",
            "---",
            "",
            "## Gate Results",
            "",
        ]
        
        for gate_result in qa_result.gate_results:
            verdict_icon = "✅" if gate_result.verdict == GateVerdict.PASS else \
                          "⚠️" if gate_result.verdict == GateVerdict.WARN else \
                          "❌" if gate_result.verdict == GateVerdict.FAIL else "⏭️"
            lines.append(f"### {verdict_icon} {gate_result.gate_id}")
            lines.append("")
            lines.append(f"**Verdict:** {gate_result.verdict.value if hasattr(gate_result.verdict, 'value') else gate_result.verdict}")
            if gate_result.message:
                lines.append(f"**Message:** {gate_result.message}")
            lines.append(f"**Findings:** {len(gate_result.findings)}")
            lines.append("")
            
            if include_findings and gate_result.findings:
                lines.append("| Severity | Message | File | Line |")
                lines.append("|----------|---------|------|------|")
                for finding in gate_result.findings[:20]:  # Limit to 20 per gate
                    lines.append(
                        f"| {finding.severity} | {finding.message[:50]}... | "
                        f"{finding.file or 'N/A'} | {finding.line or ''} |"
                    )
                lines.append("")
        
        lines.extend([
            "---",
            "",
            "*Generated by DevGodzilla QualityService*",
        ])
        
        output_path.mkdir(parents=True, exist_ok=True)
        report_path.write_text("\n".join(lines))
        
        self.logger.info(
            "quality_report_generated",
            extra=self.log_extra(path=str(report_path)),
        )
        
        return report_path

