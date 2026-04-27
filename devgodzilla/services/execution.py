"""
DevGodzilla Execution Service

Service for executing protocol steps via AI coding engines.
Coordinates repository setup, engine invocation, and QA triggering.
"""

import os
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from devgodzilla.logging import get_logger
from devgodzilla.models.domain import (
    ProtocolRun,
    ProtocolStatus,
    StepRun,
    StepStatus,
)
from devgodzilla.engines import (
    Engine,
    EngineNotFoundError,
    EngineRequest,
    EngineResult,
    SandboxMode,
    get_registry,
)
from devgodzilla.engines.artifacts import ArtifactWriter
from devgodzilla.engines.sandbox import (
    SandboxRunner,
    SandboxConfig,
    SandboxType,
    create_sandbox_runner,
    get_default_sandbox_type,
)
from devgodzilla.engines.block_detector import BlockDetector, BlockInfo, BlockReason
from devgodzilla.spec import get_step_spec as get_step_spec_from_template, resolve_spec_path
from devgodzilla.services.base import Service, ServiceContext
from devgodzilla.services.agent_config import AgentConfigService
from devgodzilla.services.events import get_event_bus, StepStarted, StepCompleted, StepFailed
from devgodzilla.services.clarifier import ClarifierService
from devgodzilla.services.policy import PolicyService
from devgodzilla.services.quality import QualityService
from devgodzilla.services.workflow_context import build_workflow_prompt_context
from devgodzilla.services.workspace_paths import resolve_protocol_root, resolve_workspace_root

logger = get_logger(__name__)

def _normalize_policy_enforcement_mode(mode: Optional[str]) -> str:
    if mode is None:
        return "warn"
    value = str(mode).strip().lower()
    mapping = {
        "advisory": "warn",
        "mandatory": "block",
        "enforce": "block",
        "blocking": "block",
    }
    return mapping.get(value, value)


@dataclass
class ExecutionResult:
    """Result from step execution."""
    success: bool
    step_run_id: int
    engine_id: str
    model: Optional[str] = None
    
    # Cost tracking
    tokens_used: Optional[int] = None
    cost_cents: Optional[int] = None
    duration_seconds: Optional[float] = None
    
    # Outputs
    stdout: str = ""
    stderr: str = ""
    outputs_written: Dict[str, Path] = field(default_factory=dict)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class StepResolution:
    """Resolved step execution context."""
    engine_id: str
    model: Optional[str]
    prompt_text: str
    prompt_path: Optional[Path]
    prompt_version: Optional[str]
    
    # Working directories
    workdir: Path
    protocol_root: Path
    workspace_root: Path
    
    # Sandbox mode
    sandbox: SandboxMode = SandboxMode.WORKSPACE_WRITE
    
    # Timeout
    timeout: Optional[int] = None
    
    # Outputs configuration
    outputs: Dict[str, Any] = field(default_factory=dict)
    
    # Additional context
    agent_id: Optional[str] = None
    step_name: Optional[str] = None
    spec_hash: Optional[str] = None


class ExecutionService(Service):
    """
    Service for executing protocol steps.
    
    Responsibilities:
    - Resolve step prompts and select engines/models
    - Execute steps via configured AI engines
    - Track execution costs and tokens
    - Handle errors and update step status
    - Trigger QA after successful execution
    - Detect execution blocks requiring human intervention
    
    Example:
        execution = ExecutionService(context, db)
        result = execution.execute_step(step_run_id=123)
        
        if result.success:
            print(f"Step completed with {result.tokens_used} tokens")
    """

    def __init__(
        self,
        context: ServiceContext,
        db,
        *,
        git_service=None,
        quality_service=None,
        default_timeout: int = 600,  # Increased for real agent operations
        sandbox_type: Optional[SandboxType] = None,
    ) -> None:
        super().__init__(context)
        self.db = db
        self.git_service = git_service
        self.quality_service = quality_service
        self.default_timeout = default_timeout
        self._sandbox_type = sandbox_type
        self._block_detector = BlockDetector()

    def _create_sandbox_runner(
        self,
        workspace_dir: Path,
        *,
        allow_network: bool = False,
    ) -> SandboxRunner:
        """Create a sandbox runner for the workspace.
        
        Args:
            workspace_dir: Working directory to allow writes
            allow_network: Whether to allow network access
            
        Returns:
            Configured SandboxRunner instance
        """
        sandbox_type = self._sandbox_type or get_default_sandbox_type()
        return create_sandbox_runner(
            workspace_dir,
            sandbox_type=sandbox_type,
            allow_network=allow_network,
        )

    def detect_block(self, output: str) -> Optional[BlockInfo]:
        """Detect if output indicates blocked execution.
        
        Args:
            output: Agent output to analyze
            
        Returns:
            BlockInfo if a block is detected, None otherwise
        """
        return self._block_detector.detect(output)

    def execute_step(
        self,
        step_run_id: int,
        *,
        job_id: Optional[str] = None,
        engine_id: Optional[str] = None,
        model: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Execute a step.
        
        Args:
            step_run_id: Step run ID
            job_id: Optional job ID for tracking
            engine_id: Override engine ID
            model: Override model
            
        Returns:
            ExecutionResult with execution details
        """
        step = self.db.get_step_run(step_run_id)
        run = self.db.get_protocol_run(step.protocol_run_id)
        project = self.db.get_project(run.project_id)
        
        self.logger.info(
            "execute_step_started",
            extra=self.log_extra(
                step_run_id=step_run_id,
                step_name=step.step_name,
                protocol_run_id=run.id,
            ),
        )

        enforcement_mode = _normalize_policy_enforcement_mode(project.policy_enforcement_mode)
        if enforcement_mode == "block":
            clarifier = ClarifierService(self.context, self.db)
            policy_service = PolicyService(self.context, self.db)
            try:
                workspace_root = resolve_workspace_root(run, project)
            except Exception as exc:
                return self._fail_step_pre_execution(
                    step,
                    run,
                    error=str(exc),
                    engine_id=engine_id or step.engine_id or "unknown",
                )
            workflow_context = build_workflow_prompt_context(
                self.context,
                self.db,
                project_id=project.id,
                repo_root=workspace_root,
                stage="execution",
            )
            if clarifier.has_blocking_open_for_stage(project_id=project.id, stage="execution"):
                self.db.update_step_status(step_run_id, StepStatus.BLOCKED, summary="Blocked on clarifications")
                self.db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
                return ExecutionResult(
                    success=False,
                    step_run_id=step_run_id,
                    engine_id=engine_id or step.engine_id or "unknown",
                    error="Blocked on clarifications",
                )

            effective = workflow_context.effective_policy
            findings = policy_service.evaluate_step(step_run_id, repo_root=workspace_root)
            enforced = PolicyService.apply_enforcement_mode(findings, enforcement_mode, policy=effective.policy)
            if PolicyService.has_blocking_findings(enforced):
                for finding in enforced:
                    self.db.append_event(
                        protocol_run_id=run.id,
                        event_type="policy_finding",
                        message=f"{finding.code}: {finding.message}",
                        metadata=finding.asdict(),
                        step_run_id=step_run_id,
                    )
                self.db.update_step_status(step_run_id, StepStatus.BLOCKED, summary="Blocked by policy findings")
                self.db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
                return ExecutionResult(
                    success=False,
                    step_run_id=step_run_id,
                    engine_id=engine_id or step.engine_id or "unknown",
                    error="Blocked by policy findings",
                )

        # Mark as running
        self.db.update_step_status(step_run_id, StepStatus.RUNNING)
        self.db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
        
        # Emit event
        event_bus = get_event_bus()
        event_bus.publish(
            StepStarted(
                step_run_id=step_run_id,
                protocol_run_id=run.id,
                step_name=step.step_name,
            )
        )
        
        try:
            # Resolve execution context
            resolution = self._resolve_step(step, run, project, engine_id, model)
            
            # Get engine
            registry = get_registry()
            try:
                engine = registry.get(resolution.engine_id)
            except EngineNotFoundError:
                error = f"Engine not registered: {resolution.engine_id}"
                self.logger.error(
                    "engine_not_registered",
                    extra=self.log_extra(
                        step_run_id=step_run_id,
                        requested_engine_id=resolution.engine_id,
                    ),
                )
                return self._fail_step_pre_execution(step, run, error=error, engine_id=resolution.engine_id)

            availability_error = None
            try:
                available = engine.check_availability()
            except Exception as exc:
                available = False
                availability_error = str(exc)

            if not available:
                error = f"Engine unavailable: {engine.metadata.id}"
                if availability_error:
                    error = f"{error} ({availability_error})"
                self.logger.error(
                    "engine_unavailable",
                    extra=self.log_extra(
                        step_run_id=step_run_id,
                        requested_engine_id=engine.metadata.id,
                    ),
                )
                return self._fail_step_pre_execution(step, run, error=error, engine_id=engine.metadata.id)

            # Persist the model choice deterministically: if the step didn't specify a model,
            # prefer agent-configured default model so UI overrides apply, and finally fall back
            # to the engine default so downstream audits/tests can validate engine+model.
            if resolution.model is None:
                env_model: Optional[str] = None
                if resolution.engine_id == "opencode":
                    candidate = os.environ.get("DEVGODZILLA_OPENCODE_MODEL")
                    if isinstance(candidate, str) and candidate.strip():
                        env_model = candidate.strip()

                resolved_agent_model: Optional[str] = None
                try:
                    from devgodzilla.services.agent_config import AgentConfigService

                    cfg = AgentConfigService(self.context, db=self.db)
                    agent_cfg = cfg.get_agent(resolution.engine_id, project_id=project.id)
                    if agent_cfg and isinstance(agent_cfg.default_model, str) and agent_cfg.default_model.strip():
                        resolved_agent_model = agent_cfg.default_model.strip()
                except Exception:
                    resolved_agent_model = None

                resolution.model = env_model or resolved_agent_model or engine.metadata.default_model
            
            # Build request
            request = EngineRequest(
                project_id=project.id,
                protocol_run_id=run.id,
                step_run_id=step_run_id,
                model=resolution.model,
                prompt_text=resolution.prompt_text,
                prompt_files=[str(resolution.prompt_path)] if resolution.prompt_path else [],
                working_dir=str(resolution.workdir),
                sandbox=resolution.sandbox,
                timeout=resolution.timeout or self.default_timeout,
                extra={"job_id": job_id},
            )
            try:
                from devgodzilla.services.agent_config import AgentConfigService

                cfg = AgentConfigService(self.context, db=self.db)
                agent_cfg = cfg.get_agent(resolution.engine_id, project_id=project.id)
                if agent_cfg and isinstance(agent_cfg.reasoning_effort, str) and agent_cfg.reasoning_effort.strip():
                    request.extra["reasoning_effort"] = agent_cfg.reasoning_effort.strip()
            except Exception:
                pass
            
            # Execute
            engine_result = engine.execute(request)
            
            # Handle result
            result = self._handle_result(
                step,
                run,
                engine,
                engine_result,
                resolution,
            )
            
            # Register with CLI execution tracker
            from devgodzilla.services.cli_execution_tracker import get_execution_tracker
            tracker = get_execution_tracker()
            execution = tracker.start_execution(
                execution_type="step",
                engine_id=engine.metadata.id,
                project_id=project.id,
                command=f"execute_step:{step.step_name}",
            )
            tracker.complete(
                execution.execution_id,
                success=result.success,
                error=result.error,
            )
            
            return result
            
        except Exception as e:
            self.logger.error(
                "execute_step_failed",
                extra=self.log_extra(
                    step_run_id=step_run_id,
                    error=str(e),
                ),
            )
            
            # Register failure with CLI execution tracker
            try:
                from devgodzilla.services.cli_execution_tracker import get_execution_tracker
                tracker = get_execution_tracker()
                execution = tracker.start_execution(
                    execution_type="step",
                    engine_id=engine_id or step.engine_id or "unknown",
                    project_id=project.id if 'project' in dir() else None,
                    command=f"execute_step:{step.step_name}",
                )
                tracker.complete(execution.execution_id, success=False, error=str(e))
            except Exception:
                pass
            
            # Mark as failed
            self.db.update_step_status(
                step_run_id,
                StepStatus.FAILED,
                summary=f"Execution error: {e}",
            )
            
            return ExecutionResult(
                success=False,
                step_run_id=step_run_id,
                engine_id=engine_id or "unknown",
                error=str(e),
            )

    def _resolve_step(
        self,
        step: StepRun,
        run: ProtocolRun,
        project,
        engine_id: Optional[str],
        model: Optional[str],
    ) -> StepResolution:
        """Resolve step execution context."""
        # Determine workspace and protocol roots
        workspace_root = resolve_workspace_root(run, project)
        protocol_root = resolve_protocol_root(run, workspace_root)
        
        # Get step spec from template config
        step_spec = get_step_spec_from_template(run.template_config, step.step_name)
        
        # Resolve engine and model
        default_engine = None
        try:
            cfg = AgentConfigService(self.context, db=self.db)
            default_engine = cfg.get_default_engine_id(
                "exec",
                project_id=project.id,
                fallback=self.context.config.engine_defaults.get("exec"),
            )
        except Exception:
            default_engine = self.context.config.engine_defaults.get("exec")

        resolved_engine = (
            engine_id
            or step.assigned_agent
            or (step_spec.get("engine_id") if step_spec else None)
            or default_engine
            or "codex"
        )
        
        resolved_model = (
            model
            or (step_spec.get("model") if step_spec else None)
            or step.model
            or None
        )
        
        prompt_template_path = None
        prompt_assignment = None
        try:
            cfg = AgentConfigService(self.context, db=self.db)
            prompt_assignment = cfg.resolve_prompt_assignment("exec", project_id=project.id)
        except Exception:
            prompt_assignment = None

        if prompt_assignment:
            prompt_path_value = prompt_assignment.get("path")
            if not isinstance(prompt_path_value, str) or not prompt_path_value.strip():
                raise ValueError("Exec prompt assignment missing path")
            prompt_template_path = resolve_spec_path(
                str(prompt_path_value),
                protocol_root,
                workspace_root,
            )
            if not prompt_template_path.exists():
                raise FileNotFoundError(f"Exec prompt not found: {prompt_template_path}")

        step_prompt_path = None
        if step_spec and step_spec.get("prompt_ref"):
            step_prompt_path = resolve_spec_path(
                str(step_spec["prompt_ref"]),
                protocol_root,
                workspace_root,
            )
        else:
            step_prompt_path = protocol_root / f"{step.step_name}.md"

        workflow_context = ""
        try:
            workflow_context = build_workflow_prompt_context(
                self.context,
                self.db,
                project_id=project.id,
                repo_root=workspace_root,
                stage="execution",
            ).rendered
        except Exception:
            workflow_context = ""

        # Build prompt
        prompt_text = self._build_prompt(
            step,
            protocol_root,
            workspace_root,
            step_prompt_path=step_prompt_path,
            prompt_template_path=prompt_template_path,
            workflow_context=workflow_context,
        )
        prompt_path = step_prompt_path
        
        # Determine timeout
        timeout = None
        if step_spec:
            timeout = step_spec.get("timeout_seconds")
        
        return StepResolution(
            engine_id=resolved_engine,
            model=resolved_model,
            prompt_text=prompt_text,
            prompt_path=prompt_path if prompt_path.exists() else None,
            prompt_version=None,
            workdir=workspace_root,
            protocol_root=protocol_root,
            workspace_root=workspace_root,
            sandbox=SandboxMode.WORKSPACE_WRITE,
            timeout=timeout,
            step_name=step.step_name,
        )

    def _get_step_spec(
        self,
        template_config: Dict[str, Any],
        step_name: str,
    ) -> Optional[Dict[str, Any]]:
        """Get step spec from template configuration."""
        steps = template_config.get("steps", [])
        for s in steps:
            if s.get("name") == step_name or s.get("id") == step_name:
                return s
        return None

    def _build_prompt(
        self,
        step: StepRun,
        protocol_root: Path,
        workspace_root: Path,
        *,
        step_prompt_path: Optional[Path] = None,
        prompt_template_path: Optional[Path] = None,
        workflow_context: str = "",
    ) -> str:
        """Build execution prompt for step."""
        parts = []
        
        # Include prompt template if assigned
        if prompt_template_path and prompt_template_path.exists():
            parts.append(prompt_template_path.read_text(encoding="utf-8"))

        # Include plan if available
        plan_path = protocol_root / "plan.md"
        if plan_path.exists():
            parts.append(f"# Plan\n\n{plan_path.read_text(encoding='utf-8')}")
        
        # Include step file if available
        step_path = step_prompt_path or (protocol_root / f"{step.step_name}.md")
        if step_path.exists():
            parts.append(f"# Task\n\n{step_path.read_text(encoding='utf-8')}")
        elif step.summary:
            parts.append(f"# Task\n\n{step.summary}")

        context_pack = self._load_task_cycle_context_pack(
            workspace_root=workspace_root,
            protocol_run_id=step.protocol_run_id,
            step_run_id=step.id,
        )
        if context_pack:
            parts.append("# ContextPack (machine-readable handoff)\n\n```json\n" + json.dumps(context_pack, indent=2) + "\n```")
            test_commands = context_pack.get("test_commands")
            if isinstance(test_commands, list) and test_commands:
                rendered = "\n".join(f"- `{str(command)}`" for command in test_commands if str(command).strip())
                if rendered:
                    parts.append(f"# Exact Test Commands\n\n{rendered}")
        helper_summary = self._load_task_cycle_helper_summary(
            workspace_root=workspace_root,
            protocol_run_id=step.protocol_run_id,
            step_run_id=step.id,
        )
        if helper_summary:
            helpers = helper_summary.get("helpers")
            if isinstance(helpers, list) and helpers:
                parts.append("# Helper Subtask Findings\n\n```json\n" + json.dumps(helper_summary, indent=2) + "\n```")

        if workflow_context.strip():
            parts.append(workflow_context.strip())
        
        return "\n\n---\n\n".join(parts) if parts else f"Execute step: {step.step_name}"

    def _load_task_cycle_context_pack(
        self,
        *,
        workspace_root: Path,
        protocol_run_id: int,
        step_run_id: int,
    ) -> Optional[Dict[str, Any]]:
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
            return None
        try:
            payload = json.loads(context_pack.read_text(encoding="utf-8"))
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    def _load_task_cycle_helper_summary(
        self,
        *,
        workspace_root: Path,
        protocol_run_id: int,
        step_run_id: int,
    ) -> Optional[Dict[str, Any]]:
        helper_summary = (
            workspace_root
            / ".devgodzilla"
            / "task-cycle"
            / "protocols"
            / str(protocol_run_id)
            / "work-items"
            / str(step_run_id)
            / "helpers"
            / "helper_summary.json"
        )
        if not helper_summary.exists():
            return None
        try:
            payload = json.loads(helper_summary.read_text(encoding="utf-8"))
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    def _fail_step_pre_execution(
        self,
        step: StepRun,
        run: ProtocolRun,
        *,
        error: str,
        engine_id: str,
    ) -> ExecutionResult:
        self.db.update_step_status(step.id, StepStatus.FAILED, summary=error)
        self.db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
        try:
            get_event_bus().publish(
                StepFailed(
                    step_run_id=step.id,
                    protocol_run_id=run.id,
                    step_name=step.step_name,
                    error=error,
                )
            )
        except Exception:
            pass
        return ExecutionResult(
            success=False,
            step_run_id=step.id,
            engine_id=engine_id or "unknown",
            error=error,
        )

    def _handle_result(
        self,
        step: StepRun,
        run: ProtocolRun,
        engine: Engine,
        engine_result: EngineResult,
        resolution: StepResolution,
    ) -> ExecutionResult:
        """Handle engine execution result."""
        outputs_written: Dict[str, Path] = {}

        # Always write artifacts so the API and E2E checks can validate real outputs.
        try:
            outputs_written = self._write_execution_artifacts(
                step=step,
                run=run,
                engine=engine,
                engine_result=engine_result,
                resolution=resolution,
            )
        except Exception as e:
            # Best-effort; do not fail the step solely because artifact capture failed.
            self.logger.warning(
                "execution_artifacts_write_failed",
                extra=self.log_extra(step_run_id=step.id, protocol_run_id=run.id, error=str(e)),
            )

        fatal_error = self._detect_fatal_engine_error(engine.metadata.id, engine_result)
        if fatal_error:
            self.db.update_step_status(
                step.id,
                StepStatus.FAILED,
                summary=fatal_error,
            )
            self.db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
            get_event_bus().publish(
                StepFailed(
                    step_run_id=step.id,
                    protocol_run_id=run.id,
                    step_name=step.step_name,
                    error=fatal_error,
                )
            )
            return ExecutionResult(
                success=False,
                step_run_id=step.id,
                engine_id=resolution.engine_id,
                model=resolution.model,
                tokens_used=engine_result.tokens_used,
                cost_cents=engine_result.cost_cents,
                duration_seconds=engine_result.duration_seconds,
                stdout=engine_result.stdout,
                stderr=engine_result.stderr,
                outputs_written=outputs_written,
                metadata=engine_result.metadata,
                error=fatal_error,
            )

        if engine_result.success:
            # Check for execution blocks in the output
            combined_output = f"{engine_result.stdout}\n{engine_result.stderr}"
            block_info = self.detect_block(combined_output)
            
            if block_info:
                self.logger.warning(
                    "execution_blocked_detected",
                    extra=self.log_extra(
                        step_run_id=step.id,
                        block_reason=block_info.reason.value,
                        confidence=block_info.confidence,
                    ),
                )
                
                # Mark as blocked and record block info
                block_message = block_info.message
                if block_info.suggested_question:
                    block_message = f"{block_message}. {block_info.suggested_question}"
                
                self.db.update_step_status(
                    step.id,
                    StepStatus.BLOCKED,
                    summary=block_message,
                    model=resolution.model,
                    engine_id=resolution.engine_id,
                )
                self.db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
                
                # Store block info in metadata for retrieval
                block_metadata = {
                    "block_reason": block_info.reason.value,
                    "block_message": block_info.message,
                    "suggested_question": block_info.suggested_question,
                    "confidence": block_info.confidence,
                    "context": block_info.context,
                }
                
                return ExecutionResult(
                    success=False,
                    step_run_id=step.id,
                    engine_id=resolution.engine_id,
                    model=resolution.model,
                    tokens_used=engine_result.tokens_used,
                    cost_cents=engine_result.cost_cents,
                    duration_seconds=engine_result.duration_seconds,
                    stdout=engine_result.stdout,
                    stderr=engine_result.stderr,
                    outputs_written=outputs_written,
                    metadata={**engine_result.metadata, "block_info": block_metadata},
                    error=block_info.message,
                )
            
            # Mark as needs QA (or completed if QA skipped)
            self.db.update_step_status(
                step.id,
                StepStatus.NEEDS_QA,
                summary=f"Executed via {engine.metadata.id}; pending QA",
                model=resolution.model,
                engine_id=resolution.engine_id,
            )
            
            # Emit completion event
            event_bus = get_event_bus()
            event_bus.publish(
                StepCompleted(
                    step_run_id=step.id,
                    protocol_run_id=run.id,
                    step_name=step.step_name,
                    summary=f"Executed via {engine.metadata.id}",
                )
            )
            
            self.logger.info(
                "execute_step_completed",
                extra=self.log_extra(
                    step_run_id=step.id,
                    engine_id=resolution.engine_id,
                    tokens_used=engine_result.tokens_used,
                ),
            )

            # Auto-run QA after execution (prompt-driven).
            qa_service = self.quality_service or QualityService(self.context, self.db)
            qa_report_path = None
            try:
                qa_result = qa_service.run_qa(step.id)
                try:
                    qa_report_path = qa_service.generate_quality_report(
                        qa_result,
                        resolution.protocol_root / ".devgodzilla" / "steps" / str(step.id) / "artifacts",
                        step_name=step.step_name,
                    )
                except Exception:
                    qa_report_path = None
                qa_service.persist_verdict(qa_result, step.id, report_path=qa_report_path)
                try:
                    from devgodzilla.services.orchestrator import OrchestratorService

                    orchestrator = OrchestratorService(context=self.context, db=self.db)
                    orchestrator.check_and_complete_protocol(step.protocol_run_id)
                except Exception:
                    pass
            except Exception as exc:
                self.logger.error(
                    "auto_qa_failed",
                    extra=self.log_extra(step_run_id=step.id, error=str(exc)),
                )
        else:
            # Determine if this was a timeout
            is_timeout = (
                engine_result.metadata.get("timeout") is True
                or (engine_result.error and "timed out" in engine_result.error.lower())
            )
            
            if is_timeout:
                self.db.update_step_status(
                    step.id,
                    StepStatus.TIMEOUT,
                    summary=engine_result.error or "Step execution timed out",
                )
            else:
                # Mark as failed
                self.db.update_step_status(
                    step.id,
                    StepStatus.FAILED,
                    summary=engine_result.error or "Execution failed",
                )
            self.db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
            get_event_bus().publish(
                StepFailed(
                    step_run_id=step.id,
                    protocol_run_id=run.id,
                    step_name=step.step_name,
                    error=engine_result.error or "Execution failed",
                )
            )
        
        return ExecutionResult(
            success=engine_result.success,
            step_run_id=step.id,
            engine_id=resolution.engine_id,
            model=resolution.model,
            tokens_used=engine_result.tokens_used,
            cost_cents=engine_result.cost_cents,
            duration_seconds=engine_result.duration_seconds,
            stdout=engine_result.stdout,
            stderr=engine_result.stderr,
            outputs_written=outputs_written,
            metadata=engine_result.metadata,
            error=engine_result.error,
        )

    def _detect_fatal_engine_error(self, engine_id: str, engine_result: EngineResult) -> Optional[str]:
        """Promote known fatal CLI stderr patterns to execution failures."""
        if not engine_result.success:
            return None

        combined = "\n".join(
            part for part in (engine_result.stdout, engine_result.stderr, engine_result.error) if part
        )
        if not combined.strip():
            return None

        fatal_patterns = []
        if engine_id == "opencode":
            fatal_patterns = [
                "ProviderModelNotFoundError",
                "Model not found:",
                "AuthenticationError",
                "Invalid API key",
            ]

        for marker in fatal_patterns:
            if marker.lower() in combined.lower():
                return f"{engine_id} execution failed: {marker}"

        return None

    def check_availability(self, engine_id: Optional[str] = None) -> bool:
        """Check if an engine is available."""
        registry = get_registry()
        engine = registry.get_or_default(engine_id)
        return engine.check_availability()

    def _write_execution_artifacts(
        self,
        *,
        step: StepRun,
        run: ProtocolRun,
        engine: Engine,
        engine_result: EngineResult,
        resolution: StepResolution,
    ) -> Dict[str, Path]:
        protocol_root = resolution.protocol_root
        artifacts_dir = protocol_root / ".devgodzilla" / "steps" / str(step.id) / "artifacts"
        writer = ArtifactWriter(artifacts_dir=artifacts_dir, step_run_id=step.id)

        outputs: Dict[str, Path] = {}

        meta = {
            "engine_id": engine.metadata.id,
            "model": resolution.model,
            "protocol_run_id": run.id,
            "step_run_id": step.id,
            "step_name": step.step_name,
            "workspace_root": str(resolution.workspace_root),
            "protocol_root": str(protocol_root),
        }
        outputs["execution_meta"] = writer.write_json("execution", meta, kind="meta").path

        if engine_result.stdout:
            outputs["stdout"] = writer.write_text("stdout", engine_result.stdout, kind="log", extension=".log").path
        if engine_result.stderr:
            outputs["stderr"] = writer.write_text("stderr", engine_result.stderr, kind="log", extension=".log").path
        if engine_result.error:
            outputs["error"] = writer.write_text("error", engine_result.error, kind="log", extension=".txt").path

        # Capture best-effort git status/diff if the workspace is a git repo.
        # Use sandbox runner for safer git operations
        repo_root = resolution.workspace_root
        if (repo_root / ".git").exists():
            import subprocess
            
            # Try sandboxed execution first, fall back to direct execution
            sandbox_runner = None
            try:
                sandbox_runner = self._create_sandbox_runner(repo_root)
            except Exception as sandbox_err:
                self.logger.warning(
                    "sandbox_runner_creation_failed",
                    extra=self.log_extra(
                        step_run_id=step.id,
                        error=str(sandbox_err),
                    ),
                )
            
            def run_git_command(cmd: List[str]) -> str:
                """Run a git command, using sandbox if available."""
                try:
                    if sandbox_runner:
                        result = sandbox_runner.run(
                            cmd,
                            cwd=repo_root,
                            capture_output=True,
                            timeout=30,
                        )
                        return result.stdout or ""
                except Exception as sandbox_error:
                    self.logger.warning(
                        "sandbox_git_command_failed",
                        extra=self.log_extra(
                            step_run_id=step.id,
                            command=" ".join(cmd),
                            error=str(sandbox_error),
                        ),
                    )
                # Fallback to direct execution
                try:
                    result = subprocess.run(  # noqa: S603
                        cmd,
                        cwd=repo_root,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    return result.stdout or ""
                except Exception as e:
                    self.logger.warning(
                        "git_command_failed",
                        extra=self.log_extra(
                            step_run_id=step.id,
                            command=" ".join(cmd),
                            error=str(e),
                        ),
                    )
                    return ""

            status_output = run_git_command(["git", "status", "--porcelain=v1"])
            outputs["git_status"] = writer.write_text(
                "git-status",
                status_output.strip() + ("\n" if status_output.strip() else ""),
                kind="diff",
                extension=".txt",
            ).path

            diff_output = run_git_command(["git", "diff"])
            outputs["git_diff"] = writer.write_text(
                "changes",
                diff_output,
                kind="diff",
                extension=".diff",
            ).path

            diff_cached_output = run_git_command(["git", "diff", "--cached"])
            outputs["git_diff_cached"] = writer.write_text(
                "changes_cached",
                diff_cached_output,
                kind="diff",
                extension=".diff",
            ).path

        return outputs
