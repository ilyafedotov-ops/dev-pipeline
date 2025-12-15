"""
DevGodzilla Execution Service

Service for executing protocol steps via AI coding engines.
Coordinates repository setup, engine invocation, and QA triggering.
"""

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
    EngineRequest,
    EngineResult,
    SandboxMode,
    get_registry,
)
from devgodzilla.services.base import Service, ServiceContext
from devgodzilla.services.events import get_event_bus, StepStarted, StepCompleted

logger = get_logger(__name__)


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
        default_timeout: int = 300,
    ) -> None:
        super().__init__(context)
        self.db = db
        self.git_service = git_service
        self.quality_service = quality_service
        self.default_timeout = default_timeout

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
        
        # Mark as running
        self.db.update_step_status(step_run_id, StepStatus.RUNNING)
        self.db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
        
        # Emit event
        event_bus = get_event_bus()
        event_bus.publish(StepStarted(
            step_run_id=step_run_id,
            step_name=step.step_name,
        ))
        
        try:
            # Resolve execution context
            resolution = self._resolve_step(step, run, project, engine_id, model)
            
            # Get engine
            registry = get_registry()
            engine = registry.get_or_default(resolution.engine_id)
            
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
            
            return result
            
        except Exception as e:
            self.logger.error(
                "execute_step_failed",
                extra=self.log_extra(
                    step_run_id=step_run_id,
                    error=str(e),
                ),
            )
            
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
        if run.worktree_path:
            workspace_root = Path(run.worktree_path).expanduser()
        else:
            workspace_root = Path(project.local_path).expanduser() if project.local_path else Path.cwd()
        
        if run.protocol_root:
            protocol_root = Path(run.protocol_root)
        else:
            protocol_root = workspace_root / ".specify" / "specs" / run.protocol_name
        
        # Get step spec from template config
        template_config = run.template_config or {}
        step_spec = self._get_step_spec(template_config, step.step_name)
        
        # Resolve engine and model
        resolved_engine = (
            engine_id
            or (step_spec.get("engine_id") if step_spec else None)
            or step.assigned_agent
            or self.context.config.engine_defaults.get("exec")
            or "codex"
        )
        
        resolved_model = (
            model
            or (step_spec.get("model") if step_spec else None)
            or step.model
            or None
        )
        
        # Build prompt
        prompt_text = self._build_prompt(step, protocol_root, workspace_root)
        prompt_path = protocol_root / f"{step.step_name}.md"
        
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
    ) -> str:
        """Build execution prompt for step."""
        parts = []
        
        # Include plan if available
        plan_path = protocol_root / "plan.md"
        if plan_path.exists():
            parts.append(f"# Plan\n\n{plan_path.read_text(encoding='utf-8')}")
        
        # Include step file if available
        step_path = protocol_root / f"{step.step_name}.md"
        if step_path.exists():
            parts.append(f"# Task\n\n{step_path.read_text(encoding='utf-8')}")
        elif step.description:
            parts.append(f"# Task\n\n{step.description}")
        
        return "\n\n---\n\n".join(parts) if parts else f"Execute step: {step.step_name}"

    def _handle_result(
        self,
        step: StepRun,
        run: ProtocolRun,
        engine: Engine,
        engine_result: EngineResult,
        resolution: StepResolution,
    ) -> ExecutionResult:
        """Handle engine execution result."""
        if engine_result.success:
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
            event_bus.publish(StepCompleted(
                step_run_id=step.id,
                success=True,
            ))
            
            self.logger.info(
                "execute_step_completed",
                extra=self.log_extra(
                    step_run_id=step.id,
                    engine_id=resolution.engine_id,
                    tokens_used=engine_result.tokens_used,
                ),
            )
        else:
            # Mark as failed
            self.db.update_step_status(
                step.id,
                StepStatus.FAILED,
                summary=engine_result.error or "Execution failed",
            )
            self.db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
        
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
            metadata=engine_result.metadata,
            error=engine_result.error,
        )

    def check_availability(self, engine_id: Optional[str] = None) -> bool:
        """Check if an engine is available."""
        registry = get_registry()
        engine = registry.get_or_default(engine_id)
        return engine.check_availability()
