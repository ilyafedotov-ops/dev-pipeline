"""
DevGodzilla Quality Service

Service for quality assurance and validation of protocol steps.
Orchestrates QA gates and manages verdicts.
"""

import json
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
    ChecklistGate,
    FormatGate,
    CoverageGate,
    SpecKitChecklistGate,
    ConstitutionalGate,
    PromptQAGate,
)
from devgodzilla.qa.gate_registry import GateRegistry, create_default_registry
from devgodzilla.qa.smart_context import SmartContextManager, ArtifactContext
from devgodzilla.qa.report_generator import ReportGenerator, QAReport
from devgodzilla.services.base import Service, ServiceContext
from devgodzilla.services.constitution import ConstitutionService
from devgodzilla.services.events import get_event_bus, QAStarted, QAPassed, QAFailed
from devgodzilla.services.policy import PolicyService
from devgodzilla.qa.feedback import FeedbackRouter, FeedbackAction
from devgodzilla.engines import EngineNotFoundError, get_registry
from devgodzilla.spec import resolve_spec_path
from devgodzilla.services.agent_config import AgentConfigService
from devgodzilla.services.workspace_paths import resolve_workspace_root

logger = get_logger(__name__)


def _normalize_qa_policy(value: Optional[str]) -> str:
    if not value:
        return "full"
    return str(value).strip().lower()


def _policy_required_checks(policy: Dict[str, Any]) -> List[str]:
    defaults = policy.get("defaults", {})
    ci_config = defaults.get("ci", {})
    if isinstance(ci_config.get("required_checks"), list):
        return [str(c) for c in ci_config["required_checks"]]
    requirements = policy.get("requirements", {})
    if isinstance(requirements.get("required_checks"), list):
        return [str(c) for c in requirements["required_checks"]]
    return []


def _gate_ids_from_required_checks(checks: List[str]) -> List[str]:
    gate_ids = []
    for check in checks:
        text = str(check).lower()
        if "lint" in text:
            gate_ids.append("lint")
        elif "type" in text or "mypy" in text or "pyright" in text:
            gate_ids.append("type")
        elif "test" in text or "pytest" in text or "unit" in text:
            gate_ids.append("test")
        elif "checklist" in text:
            gate_ids.append("checklist")
        elif "format" in text or "fmt" in text or "prettier" in text or "black" in text:
            gate_ids.append("format")
        elif "coverage" in text or "cov" in text:
            gate_ids.append("coverage")
        elif "constitution" in text or "constitutional" in text:
            gate_ids.append("constitutional")
    return list(dict.fromkeys(gate_ids))


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
    - Run composable QA gates via GateRegistry
    - Aggregate gate results into verdicts
    - Update step status based on QA results
    - Support auto-fix for certain error types
    - Handle large files via SmartContextManager
    
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
        registry: Optional[GateRegistry] = None,
        smart_context: Optional[SmartContextManager] = None,
    ) -> None:
        super().__init__(context)
        self.db = db
        self.default_gates = default_gates or []
        
        # Initialize or use provided registry
        self._registry = registry
        self._smart_context = smart_context or SmartContextManager()
        self.report_generator = ReportGenerator(format="markdown")
    
    @property
    def registry(self) -> GateRegistry:
        """Get or create the gate registry."""
        if self._registry is None:
            self._registry = create_default_registry()
            # Register any default gates passed to constructor
            for gate in self.default_gates:
                self._registry.register(gate, category="custom")
        return self._registry
    
    def register_gate(self, gate: Gate, category: str = "custom") -> None:
        """Register a gate with the service.
        
        Args:
            gate: Gate instance to register
            category: Category for the gate
        """
        self.registry.register(gate, category=category)
    
    def unregister_gate(self, gate_id: str) -> Optional[Gate]:
        """Unregister a gate from the service.
        
        Args:
            gate_id: ID of gate to unregister
            
        Returns:
            The removed gate, or None if not found
        """
        return self.registry.unregister(gate_id)
    
    def build_artifact_context(
        self,
        files: List[Path],
        query: str,
    ) -> ArtifactContext:
        """Build artifact context from files for large file handling.
        
        Args:
            files: List of file paths
            query: Query for relevance scoring
            
        Returns:
            ArtifactContext with chunked file contents
        """
        artifact_ctx = ArtifactContext()
        for file_path in files:
            if file_path.exists() and file_path.is_file():
                artifact_ctx.add_file(self._smart_context, file_path)
        return artifact_ctx

    def _qa_prompt_path(self) -> Path:
        repo_root = Path(__file__).resolve().parents[2]
        return repo_root / "prompts" / "quality-validator.prompt.md"

    def _resolve_qa_engine(self, *, project_id: Optional[int] = None):
        registry = get_registry()
        if not registry.list_ids():
            try:
                from devgodzilla.engines.bootstrap import bootstrap_default_engines

                bootstrap_default_engines(replace=False)
            except Exception:
                pass
        if not registry.has("dummy"):
            try:
                from devgodzilla.engines.bootstrap import bootstrap_default_engines

                bootstrap_default_engines(replace=False)
            except Exception:
                pass
        engine_id = None
        model = None
        cfg: Optional["AgentConfigService"] = None
        try:
            from devgodzilla.services.agent_config import AgentConfigService

            cfg = AgentConfigService(self.context, db=self.db)
            engine_id = cfg.get_default_engine_id(
                "qa",
                project_id=project_id,
                fallback=self.context.config.engine_defaults.get("qa"),  # type: ignore[union-attr]
            )
            model = self.context.config.qa_model  # type: ignore[union-attr]
        except Exception:
            engine_id = None
            model = None
            cfg = None
        if not engine_id:
            engine_id = (
                self.context.config.engine_defaults.get("qa")  # type: ignore[union-attr]
                or self.context.config.default_engine_id  # type: ignore[union-attr]
                or "opencode"
            )
        try:
            engine = registry.get(engine_id)
        except EngineNotFoundError:
            if registry.has("dummy"):
                engine = registry.get("dummy")
            else:
                raise RuntimeError(f"QA engine not registered: {engine_id}")
        try:
            available = engine.check_availability()
        except Exception as exc:
            available = False
            availability_error = str(exc)
        else:
            availability_error = None
        if not available:
            if engine.metadata.id != "dummy" and registry.has("dummy"):
                engine = registry.get("dummy")
            else:
                error = f"QA engine unavailable: {engine.metadata.id}"
                if availability_error:
                    error = f"{error} ({availability_error})"
                raise RuntimeError(error)
        if not model:
            resolved_agent_model: Optional[str] = None
            try:
                if cfg is not None:
                    agent_cfg = cfg.get_agent(engine.metadata.id, project_id=project_id)
                    if agent_cfg and isinstance(agent_cfg.default_model, str) and agent_cfg.default_model.strip():
                        resolved_agent_model = agent_cfg.default_model.strip()
            except Exception:
                resolved_agent_model = None
            model = resolved_agent_model or engine.metadata.default_model
        return engine, model

    def _build_prompt_gate(
        self,
        *,
        project_id: Optional[int] = None,
        prompt_path: Optional[Path] = None,
    ) -> PromptQAGate:
        engine, model = self._resolve_qa_engine(project_id=project_id)
        return PromptQAGate(
            engine=engine,
            prompt_path=prompt_path or self._qa_prompt_path(),
            model=model,
        )

    @staticmethod
    def _serialize_findings(findings: List[Finding]) -> List[Dict[str, Any]]:
        return [
            {
                "gate_id": f.gate_id,
                "severity": f.severity,
                "message": f.message,
                "file_path": f.file_path,
                "line_number": f.line_number,
                "rule_id": f.rule_id,
                "suggestion": f.suggestion,
                "metadata": f.metadata,
            }
            for f in findings
        ]

    @classmethod
    def _serialize_gate_results(cls, gate_results: List[GateResult]) -> List[Dict[str, Any]]:
        return [
            {
                "gate_id": r.gate_id,
                "gate_name": r.gate_name,
                "verdict": r.verdict.value if hasattr(r.verdict, "value") else str(r.verdict),
                "duration_seconds": r.duration_seconds,
                "metadata": r.metadata,
                "error": r.error,
                "findings": cls._serialize_findings(r.findings),
            }
            for r in gate_results
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
        if run.protocol_root:
            configured = Path(run.protocol_root)
            protocol_root_path = configured if configured.is_absolute() else (workspace_root / configured)
        else:
            specs = workspace_root / "specs" / run.protocol_name
            protocols = workspace_root / ".protocols" / run.protocol_name
            if specs.exists():
                protocol_root_path = specs
            elif protocols.exists():
                protocol_root_path = protocols
            else:
                protocol_root_path = specs
        protocol_root = str(protocol_root_path)
        
        context = GateContext(
            workspace_root=str(workspace_root),
            protocol_root=protocol_root,
            step_name=step.step_name,
            step_run_id=step_run_id,
            protocol_run_id=run.id,
            project_id=project.id,
            metadata=self._load_task_cycle_context_metadata(
                workspace_root=workspace_root,
                protocol_run_id=run.id,
                step_run_id=step_run_id,
            ),
        )

        policy_service = PolicyService(self.context, self.db)
        qa_policy = "full"
        required_checks: List[str] = []
        try:
            effective = policy_service.resolve_effective_policy(
                project.id,
                repo_root=workspace_root,
                include_repo_local=True,
            )
            defaults = effective.policy.get("defaults", {}) if isinstance(effective.policy, dict) else {}
            qa_defaults = defaults.get("qa", {}) if isinstance(defaults, dict) else {}
            qa_policy = _normalize_qa_policy(qa_defaults.get("policy"))
            required_checks = _policy_required_checks(effective.policy)
        except Exception:
            qa_policy = "full"

        if qa_policy == "skip":
            qa_policy = "full"

        # Run gates
        skip_ids = set(skip_gates or [])
        prompt_gate = None
        prompt_gate_error = None
        if "prompt_qa" not in skip_ids:
            try:
                prompt_path = self._qa_prompt_path()
                assignment = None
                try:
                    cfg = AgentConfigService(self.context, db=self.db)
                    assignment = cfg.resolve_prompt_assignment("qa", project_id=project.id)
                except Exception:
                    assignment = None

                if assignment:
                    prompt_path_value = assignment.get("path")
                    if not isinstance(prompt_path_value, str) or not prompt_path_value.strip():
                        raise ValueError("QA prompt assignment missing path")
                    candidate = resolve_spec_path(
                        str(prompt_path_value),
                        protocol_root_path,
                        workspace_root,
                    )
                    if not candidate.exists():
                        raise FileNotFoundError(f"QA prompt not found: {candidate}")
                    prompt_path = candidate

                prompt_gate = self._build_prompt_gate(project_id=project.id, prompt_path=prompt_path)
            except Exception as exc:
                prompt_gate_error = str(exc)
                self.logger.error(
                    "qa_prompt_gate_failed",
                    extra=self.log_extra(
                        project_id=project.id,
                        step_run_id=step_run_id,
                        error=prompt_gate_error,
                    ),
                )
        gates_to_run: List[Gate] = []
        if prompt_gate is not None:
            gates_to_run.append(prompt_gate)
        if gates is None:
            gate_ids = _gate_ids_from_required_checks(required_checks)
            constitution_gate = None
            if gate_ids:
                gate_map = {
                    "lint": LintGate(),
                    "type": TypeGate(),
                    "test": TestGate(),
                    "checklist": ChecklistGate(),
                    "format": FormatGate(),
                    "coverage": CoverageGate(),
                }
                if "constitutional" in gate_ids:
                    constitution_gate = self._load_constitution_gate(project.id, workspace_root)
                    if constitution_gate:
                        gate_map["constitutional"] = constitution_gate
                gates_to_run.extend([gate_map[g] for g in gate_ids if g in gate_map])
            elif qa_policy == "light":
                gates_to_run.append(LintGate())
            else:
                gates_to_run.extend(self.default_gates)

            # Add SpecKit checklist gate when a checklist exists.
            speckit_gate = SpecKitChecklistGate()
            if speckit_gate.has_checklist(context):
                if not any(g.gate_id == speckit_gate.gate_id for g in gates_to_run):
                    gates_to_run.append(speckit_gate)

            # Add constitutional gate when a constitution exists.
            if constitution_gate is None:
                constitution_gate = self._load_constitution_gate(project.id, workspace_root)
            if constitution_gate and not any(g.gate_id == constitution_gate.gate_id for g in gates_to_run):
                gates_to_run.append(constitution_gate)
        else:
            gates_to_run.extend(gates)

        deduped: Dict[str, Gate] = {}
        for gate in gates_to_run:
            if gate.gate_id not in deduped:
                deduped[gate.gate_id] = gate
        gates_to_run = list(deduped.values())
        try:
            gate_ids = [g.gate_id for g in gates_to_run]
            if prompt_gate_error and "prompt_qa" not in skip_ids:
                gate_ids = ["prompt_qa", *gate_ids]
            get_event_bus().publish(
                QAStarted(
                    step_run_id=step.id,
                    protocol_run_id=run.id,
                    gates=gate_ids,
                )
            )
        except Exception:
            pass
        
        gate_results = []
        if prompt_gate_error and "prompt_qa" not in skip_ids:
            gate_results.append(
                GateResult(
                    gate_id="prompt_qa",
                    gate_name="Prompt QA",
                    verdict=GateVerdict.ERROR,
                    error=prompt_gate_error,
                )
            )
        for gate in gates_to_run:
            if gate.gate_id in skip_ids:
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

        try:
            if qa_result.verdict == QAVerdict.PASS:
                get_event_bus().publish(
                    QAPassed(step_run_id=step.id, protocol_run_id=run.id)
                )
            elif qa_result.verdict == QAVerdict.FAIL:
                failures = [
                    {"gate_id": f.gate_id, "message": f.message, "severity": f.severity}
                    for f in qa_result.blocking_findings
                ]
                get_event_bus().publish(
                    QAFailed(
                        step_run_id=step.id,
                        protocol_run_id=run.id,
                        failures=failures,
                        action="retry",
                    )
                )
        except Exception:
            pass
        
        # Update step status
        self._update_step_status(step, run, qa_result)

        # Feedback routing for failures (clarifications + events).
        if qa_result.verdict == QAVerdict.FAIL:
            try:
                router = FeedbackRouter(max_auto_fix_attempts=self.context.config.qa_max_auto_fix_attempts)
                routed = router.route_all(qa_result.all_findings)
                for item in routed:
                    try:
                        self.db.append_feedback_event(
                            protocol_run_id=run.id,
                            step_run_id=step.id,
                            error_type=item.route.category.value,
                            action_taken=item.route.action.value,
                            attempt_number=item.attempt + 1,
                            context={
                                "gate_id": item.finding.gate_id,
                                "message": item.finding.message,
                            },
                        )
                    except Exception:
                        pass

                    if item.route.action in (FeedbackAction.BLOCK, FeedbackAction.ESCALATE):
                        key = f"qa:{item.finding.gate_id}:{abs(hash(item.finding.message))}"
                        self.db.upsert_clarification(
                            scope=f"step:{step.id}",
                            project_id=project.id,
                            protocol_run_id=run.id,
                            step_run_id=step.id,
                            key=key,
                            question=f"Resolve QA finding: {item.finding.message}",
                            recommended=item.finding.metadata or None,
                            applies_to="qa",
                            blocking=True,
                        )
            except Exception:
                pass

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
        return self.run_qa(step_run_id, gates=inline_gates, skip_gates=["prompt_qa"])

    def _get_workspace(self, run: ProtocolRun, project) -> Path:
        """Get workspace root path."""
        return resolve_workspace_root(run, project)

    def _load_constitution_gate(
        self,
        project_id: int,
        workspace_root: Path,
    ) -> Optional[ConstitutionalGate]:
        try:
            constitution_service = ConstitutionService(self.context, self.db)
            constitution = constitution_service.load_from_repo(
                project_id,
                repo_root=workspace_root,
            )
        except Exception:
            return None
        if not constitution.articles:
            return None
        return ConstitutionalGate(constitution)

    def _load_task_cycle_context_metadata(
        self,
        *,
        workspace_root: Path,
        protocol_run_id: int,
        step_run_id: int,
    ) -> Dict[str, Any]:
        context_pack = (
            workspace_root
            / ".devgodzilla"
            / "task-cycle"
            / "protocols"
            / str(protocol_run_id)
            / "work-items"
            / str(step_run_id)
            / "context_pack.json"
        )
        if not context_pack.exists():
            return {}
        try:
            payload = json.loads(context_pack.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(payload, dict):
            return {}

        metadata: Dict[str, Any] = {}
        metadata["context_pack_path"] = str(context_pack)
        test_commands = payload.get("test_commands")
        if isinstance(test_commands, list):
            metadata["test_commands"] = [str(item) for item in test_commands if str(item).strip()]

        metadata["context_pack"] = payload
        artifact_refs = payload.get("artifact_refs")
        if isinstance(artifact_refs, dict):
            metadata["artifact_refs"] = artifact_refs
            step_artifacts_dir = artifact_refs.get("step_artifacts_dir")
            if isinstance(step_artifacts_dir, str) and step_artifacts_dir.strip():
                step_dir = Path(step_artifacts_dir)
                if not step_dir.is_absolute():
                    step_dir = workspace_root / step_dir
                diff_paths = [step_dir / "changes.diff", step_dir / "changes_cached.diff"]
                existing = [str(path) for path in diff_paths if path.exists()]
                if existing:
                    metadata["diff_paths"] = existing

        raw_specs = payload.get("test_command_specs")
        if isinstance(raw_specs, list):
            specs: List[Dict[str, Any]] = []
            for item in raw_specs:
                if not isinstance(item, dict):
                    continue
                raw_command = item.get("command")
                if not isinstance(raw_command, list) or not raw_command:
                    continue
                command = [str(part) for part in raw_command if str(part).strip()]
                if not command:
                    continue
                spec: Dict[str, Any] = {
                    "cwd": str(item.get("cwd") or "."),
                    "command": command,
                    "display": str(item.get("display") or " ".join(command)),
                }
                specs.append(spec)
            if specs:
                metadata["test_command_specs"] = specs

        return metadata

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
        elif result.verdict == QAVerdict.SKIP:
            self.db.update_step_status(
                step.id,
                StepStatus.COMPLETED,
                summary="QA skipped",
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
            self.db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)

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
        *,
        report_path: Optional[Path] = None,
    ) -> None:
        """
        Persist QA verdict to database.
        
        Args:
            qa_result: QA result to persist
            step_run_id: Step run ID
        """
        if not self.db:
            return
        try:
            gate_results = self._serialize_gate_results(qa_result.gate_results)
            findings = self._serialize_findings(qa_result.all_findings)
            summary = f"{qa_result.verdict.value.upper()}: {len(findings)} findings"

            prompt_meta: Dict[str, Any] = {}
            for gate in qa_result.gate_results:
                if gate.gate_id == "prompt_qa":
                    prompt_meta = gate.metadata or {}
                    break

            step = self.db.get_step_run(step_run_id)
            run = self.db.get_protocol_run(step.protocol_run_id)
            project = self.db.get_project(run.project_id)

            record = self.db.create_qa_result(
                project_id=project.id,
                protocol_run_id=run.id,
                step_run_id=step_run_id,
                verdict=qa_result.verdict.value,
                summary=summary,
                gate_results=gate_results,
                findings=findings,
                prompt_path=prompt_meta.get("prompt_path"),
                prompt_hash=prompt_meta.get("prompt_hash"),
                engine_id=prompt_meta.get("engine_id"),
                model=prompt_meta.get("model"),
                report_path=str(report_path) if report_path else None,
                report_text=prompt_meta.get("report_text"),
                duration_seconds=qa_result.duration_seconds,
            )

            verdict_data = {
                "qa_result_id": record.id,
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
        Generate a quality-report.md file using ReportGenerator.
        
        Args:
            qa_result: QA result to report on
            output_path: Directory to write report to
            step_name: Optional step name for context
            include_findings: Whether to include detailed findings
            
        Returns:
            Path to generated report
        """
        # Create a simple verdict object compatible with ReportGenerator
        class VerdictWrapper:
            def __init__(self, qa_result: QAResult):
                self._qa_result = qa_result
            
            @property
            def passed(self) -> bool:
                return self._qa_result.passed

            @property
            def has_skipped_gates(self) -> bool:
                return any(
                    getattr(g.verdict, "value", str(g.verdict)) == "skip"
                    for g in self._qa_result.gate_results
                )
            
            @property
            def score(self) -> float:
                # Calculate score from gate results
                if not self._qa_result.gate_results:
                    return 1.0
                passed = sum(
                    1
                    for g in self._qa_result.gate_results
                    if getattr(g.verdict, "value", str(g.verdict)) == "pass"
                )
                return passed / len(self._qa_result.gate_results)
        
        # Create a simple step_run wrapper
        class StepRunWrapper:
            def __init__(self, qa_result: QAResult, step_name: Optional[str]):
                self.step_name = step_name or "Unknown Step"
                self.step_id = str(qa_result.step_run_id)
        
        step_run = StepRunWrapper(qa_result, step_name)
        verdict = VerdictWrapper(qa_result)
        
        # Generate report using ReportGenerator
        report = self.report_generator.generate(
            step_run=step_run,
            gate_results=qa_result.gate_results,
            checklist_result=None,
            verdict=verdict,
        )
        
        # Render to markdown
        markdown_content = self.report_generator.render(report)
        
        # Write to file
        output_path.mkdir(parents=True, exist_ok=True)
        report_path = output_path / "quality-report.md"
        report_path.write_text(markdown_content)
        
        self.logger.info(
            "quality_report_generated",
            extra=self.log_extra(path=str(report_path)),
        )
        
        return report_path
