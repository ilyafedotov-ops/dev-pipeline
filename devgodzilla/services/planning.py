"""
DevGodzilla Planning Service

Service for protocol planning and task breakdown.
Handles specification parsing, step decomposition, and DAG generation.
"""

import shutil
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from devgodzilla.config import Config, get_config
from devgodzilla.logging import get_logger
from devgodzilla.models.domain import ProtocolRun, ProtocolStatus, Project
from devgodzilla.services.base import Service, ServiceContext
from devgodzilla.services.events import get_event_bus, ProtocolStarted, ProtocolCompleted
from devgodzilla.spec import (
    PROTOCOL_SPEC_KEY,
    build_spec_from_protocol_files,
    create_steps_from_spec,
    protocol_spec_hash,
    resolve_spec_path,
    validate_protocol_spec,
)

logger = get_logger(__name__)


@dataclass
class PlanningResult:
    """Result of protocol planning."""
    success: bool
    protocol_run_id: int
    steps_created: int = 0
    spec_hash: Optional[str] = None
    policy_hash: Optional[str] = None
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


def _build_repo_snapshot(repo_root: Path, *, max_files: int = 50) -> str:
    """
    Create a concise snapshot of the repository layout.
    
    Injected into planning prompts so the model can reference real paths.
    
    Args:
        repo_root: Repository root path
        max_files: Maximum files to include per directory
        
    Returns:
        Markdown-formatted snapshot string
    """
    lines = ["# Repository Structure", ""]
    
    # Key directories to scan
    dirs_to_scan = ["src", "lib", "app", "tests", "scripts", "."]
    
    for dir_name in dirs_to_scan:
        dir_path = repo_root / dir_name if dir_name != "." else repo_root
        if not dir_path.exists():
            continue
        
        # Get files
        files = []
        for item in sorted(dir_path.iterdir())[:max_files]:
            if item.name.startswith(".") and item.name not in [".devgodzilla"]:
                continue
            if item.is_file():
                files.append(item.name)
            elif item.is_dir() and not item.name.startswith("__"):
                files.append(f"{item.name}/")
        
        if files:
            header = f"## {dir_name}/" if dir_name != "." else "## (root)"
            lines.append(header)
            for f in files:
                lines.append(f"- {f}")
            lines.append("")
    
    # Build commands from common files
    lines.append("## Common Commands")
    if (repo_root / "Makefile").exists():
        lines.append("- `make` targets available")
    if (repo_root / "package.json").exists():
        lines.append("- `npm run` scripts available")
    if (repo_root / "pyproject.toml").exists():
        lines.append("- Python project (pyproject.toml)")
    
    return "\n".join(lines)


class PlanningService(Service):
    """
    Service for protocol planning operations.
    
    Handles the complete protocol planning workflow including:
    - Resolving policy requirements and clarifications
    - Setting up repository and worktree
    - Parsing protocol specifications
    - Creating step runs with DAG dependencies
    - Windmill flow generation (if enabled)
    
    Example:
        planning = PlanningService(context, db)
        result = planning.plan_protocol(protocol_run_id=1)
        
        if result.success:
            print(f"Created {result.steps_created} steps")
    """

    def __init__(
        self,
        context: ServiceContext,
        db,
        *,
        git_service=None,
        policy_service=None,
        clarifier_service=None,
    ) -> None:
        super().__init__(context)
        self.db = db
        self.git_service = git_service
        self.policy_service = policy_service
        self.clarifier_service = clarifier_service

    def plan_protocol(
        self,
        protocol_run_id: int,
        *,
        job_id: Optional[str] = None,
    ) -> PlanningResult:
        """
        Plan a protocol run.
        
        Orchestrates the complete planning workflow:
        1. Load protocol run and project configuration
        2. Resolve effective policy and clarifications
        3. Gate on blocking clarifications
        4. Parse/validate protocol specification
        5. Create step runs with dependencies
        6. Generate Windmill flow (if enabled)
        
        Args:
            protocol_run_id: ID of the protocol run to plan
            job_id: Optional job ID for logging correlation
            
        Returns:
            PlanningResult with success status and details
        """
        log_extra = self.log_extra(protocol_run_id=protocol_run_id, job_id=job_id)
        
        try:
            # Load protocol run and project
            run = self.db.get_protocol_run(protocol_run_id)
            project = self.db.get_project(run.project_id)
        except KeyError as e:
            self.logger.error("planning_load_failed", extra={**log_extra, "error": str(e)})
            return PlanningResult(
                success=False,
                protocol_run_id=protocol_run_id,
                error=f"Load failed: {e}",
            )
        
        log_extra["project_id"] = project.id
        self.logger.info("planning_started", extra=log_extra)
        
        # Emit event
        event_bus = get_event_bus()
        event_bus.publish(ProtocolStarted(
            protocol_run_id=protocol_run_id,
            protocol_name=run.protocol_name,
        ))
        
        # Update status to planning
        self.db.update_protocol_status(protocol_run_id, ProtocolStatus.PLANNING)
        
        # Check for blocking clarifications
        if self.clarifier_service:
            if self.clarifier_service.has_blocking_open(
                project_id=project.id,
                protocol_run_id=protocol_run_id,
            ):
                self.logger.warning("planning_blocked_on_clarifications", extra=log_extra)
                return PlanningResult(
                    success=False,
                    protocol_run_id=protocol_run_id,
                    error="Blocked on open clarifications",
                )
        
        # Resolve workspace path
        workspace = self._resolve_workspace(run, project)
        if not workspace:
            return PlanningResult(
                success=False,
                protocol_run_id=protocol_run_id,
                error="Could not resolve workspace path",
            )

        # Resolve protocol root early (used to decide whether to create a worktree)
        protocol_root = self._resolve_protocol_root(run, workspace)
        has_runtime_steps = protocol_root.exists() and any(protocol_root.glob("step-*.md"))

        # Ensure worktree for reproducible, isolated execution unless runtime steps already exist.
        if not run.worktree_path and not has_runtime_steps:
            git_service = self.git_service
            if git_service is None:
                try:
                    from devgodzilla.services.git import GitService

                    git_service = GitService(self.context)
                except Exception:
                    git_service = None

            if git_service and project.local_path:
                try:
                    repo_root = Path(project.local_path).expanduser()
                    worktree = git_service.ensure_worktree(
                        repo_root,
                        run.protocol_name,
                        run.base_branch,
                        protocol_run_id=protocol_run_id,
                        project_id=project.id,
                    )
                    run = self.db.update_protocol_paths(protocol_run_id, worktree_path=str(worktree))
                    workspace = worktree
                    protocol_root = self._resolve_protocol_root(run, workspace)
                except Exception as e:
                    self.logger.warning(
                        "worktree_setup_failed",
                        extra={**log_extra, "error": str(e), "repo_root": project.local_path},
                    )

        # If protocol files are missing, optionally generate them via agent (headless SWE mode).
        auto_generate = os.environ.get("DEVGODZILLA_AUTO_GENERATE_PROTOCOL", "true").lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        if auto_generate:
            step_files = sorted(protocol_root.glob("step-*.md"))
            if not step_files:
                try:
                    from devgodzilla.services.protocol_generation import ProtocolGenerationService
                    from devgodzilla.services.agent_config import AgentConfigService

                    engine_id = None
                    try:
                        cfg = AgentConfigService(self.context, db=self.db)
                        engine_id = cfg.get_default_engine_id(
                            "planning",
                            project_id=project.id,
                            fallback=self.context.config.engine_defaults.get("planning"),  # type: ignore[union-attr]
                        )
                    except Exception:
                        engine_id = None
                    if not isinstance(engine_id, str) or not engine_id.strip():
                        engine_id = "opencode"

                    model = None
                    try:
                        model = self.context.config.planning_model  # type: ignore[union-attr]
                    except Exception:
                        model = None

                    prompt_path = None
                    try:
                        assignment = cfg.resolve_prompt_assignment("planning", project_id=project.id)
                        if assignment and assignment.get("path"):
                            candidate = resolve_spec_path(
                                str(assignment["path"]),
                                Path(__file__).resolve().parents[2],
                                workspace,
                            )
                            if candidate.exists():
                                prompt_path = candidate
                            else:
                                self.logger.warning(
                                    "planning_prompt_assignment_missing",
                                    extra=self.log_extra(
                                        project_id=project.id,
                                        protocol_run_id=protocol_run_id,
                                        prompt_path=str(candidate),
                                    ),
                                )
                    except Exception:
                        prompt_path = None

                    gen = ProtocolGenerationService(self.context)
                    gen_result = gen.generate(
                        worktree_root=workspace,
                        protocol_name=run.protocol_name,
                        description=run.description or "",
                        step_count=3,
                        engine_id=engine_id,
                        model=model,
                        prompt_path=prompt_path,
                        timeout_seconds=int(os.environ.get("DEVGODZILLA_PROTOCOL_GENERATE_TIMEOUT_SECONDS", "900")),
                        strict_outputs=True,
                    )
                    if not gen_result.success:
                        return PlanningResult(
                            success=False,
                            protocol_run_id=protocol_run_id,
                            error=f"Protocol generation failed: {gen_result.error}",
                        )

                    protocol_root = gen_result.protocol_root
                    run = self.db.update_protocol_paths(protocol_run_id, protocol_root=str(protocol_root))
                except Exception as e:
                    return PlanningResult(
                        success=False,
                        protocol_run_id=protocol_run_id,
                        error=f"Protocol generation failed: {e}",
                    )
        
        # Resolve effective policy
        policy_hash = None
        if self.policy_service:
            try:
                effective = self.policy_service.resolve_effective_policy(
                    project.id,
                    repo_root=workspace,
                )
                policy_hash = effective.effective_hash
                
                # Audit policy on protocol
                self.policy_service.audit_protocol_policy(
                    protocol_run_id,
                    pack_key=effective.pack_key,
                    pack_version=effective.pack_version,
                    effective_hash=effective.effective_hash,
                    policy=effective.policy,
                )
            except Exception as e:
                self.logger.warning("policy_resolution_failed", extra={**log_extra, "error": str(e)})
        
        # Parse protocol specification
        try:
            spec = self._parse_protocol_spec(run, protocol_root, workspace)
        except Exception as e:
            self.logger.error("spec_parse_failed", extra={**log_extra, "error": str(e)})
            return PlanningResult(
                success=False,
                protocol_run_id=protocol_run_id,
                error=f"Spec parse failed: {e}",
            )
        
        spec_hash = protocol_spec_hash(spec)
        
        # Validate spec
        errors = validate_protocol_spec(protocol_root, spec, workspace)
        if errors:
            self.logger.warning("spec_validation_warnings", extra={**log_extra, "errors": errors})
        
        # Create step runs
        try:
            existing_steps = self.db.list_step_runs(protocol_run_id)
            existing_names = {s.step_name for s in existing_steps}
            step_ids = create_steps_from_spec(
                self.db,
                protocol_run_id,
                spec,
                existing_names=existing_names,
            )
        except Exception as e:
            self.logger.error("step_creation_failed", extra={**log_extra, "error": str(e)})
            return PlanningResult(
                success=False,
                protocol_run_id=protocol_run_id,
                error=f"Step creation failed: {e}",
            )
        
        # Update protocol template_config with spec
        template_config = run.template_config or {}
        template_config[PROTOCOL_SPEC_KEY] = spec
        self.db.update_protocol_template(
            protocol_run_id,
            template_config=template_config,
        )
        
        # Update status to planned (ready for execution)
        self.db.update_protocol_status(protocol_run_id, ProtocolStatus.PLANNED)
        
        self.logger.info(
            "planning_completed",
            extra={
                **log_extra,
                "steps_created": len(step_ids),
                "spec_hash": spec_hash,
                "policy_hash": policy_hash,
            },
        )
        
        # Emit completion event (planning phase completed, not full protocol)
        # Note: ProtocolCompleted is for when the entire protocol finishes execution
        # For planning completion, we just log success
        
        return PlanningResult(
            success=True,
            protocol_run_id=protocol_run_id,
            steps_created=len(step_ids),
            spec_hash=spec_hash,
            policy_hash=policy_hash,
            warnings=errors,
        )

    def _resolve_workspace(
        self,
        run: ProtocolRun,
        project: Project,
    ) -> Optional[Path]:
        """Resolve the workspace path for a protocol run."""
        # Try worktree_path first
        if run.worktree_path:
            path = Path(run.worktree_path)
            if path.exists():
                return path
        
        # Try project local_path
        if project.local_path:
            path = Path(project.local_path)
            if path.exists():
                return path
        
        # Use git service to resolve
        if self.git_service:
            try:
                return self.git_service.resolve_repo_path(project.git_url)
            except Exception:
                pass
        
        return None

    def _resolve_protocol_root(
        self,
        run: ProtocolRun,
        workspace: Path,
    ) -> Path:
        """Resolve the protocol root directory."""
        if run.protocol_root:
            root = Path(run.protocol_root)
            if root.is_absolute():
                return root
            return workspace / run.protocol_root
        
        # Default to .protocols/<protocol_name>
        return workspace / ".protocols" / run.protocol_name

    def _parse_protocol_spec(
        self,
        run: ProtocolRun,
        protocol_root: Path,
        workspace: Path,
    ) -> Dict[str, Any]:
        """Parse protocol specification."""
        # Check if spec is already in template_config
        if run.template_config:
            existing_spec = run.template_config.get(PROTOCOL_SPEC_KEY)
            if existing_spec:
                return existing_spec
        
        # Build spec from protocol files
        default_engine_id: Optional[str] = None
        default_qa_prompt: Optional[str] = None
        try:
            candidate = None
            try:
                from devgodzilla.services.agent_config import AgentConfigService

                cfg = AgentConfigService(self.context, db=self.db)
                candidate = cfg.get_default_engine_id(
                    "exec",
                    project_id=run.project_id,
                    fallback=self.context.config.engine_defaults.get("exec"),  # type: ignore[union-attr]
                )
                qa_assignment = cfg.resolve_prompt_assignment(
                    "qa",
                    project_id=run.project_id,
                )
                if qa_assignment and qa_assignment.get("path"):
                    candidate = resolve_spec_path(
                        str(qa_assignment["path"]),
                        protocol_root,
                        workspace,
                    )
                    if candidate.exists():
                        default_qa_prompt = str(qa_assignment["path"])
                    else:
                        self.logger.warning(
                            "qa_prompt_assignment_missing",
                            extra=self.log_extra(
                                project_id=run.project_id,
                                protocol_run_id=run.id,
                                prompt_path=str(candidate),
                            ),
                        )
            except Exception:
                candidate = self.context.config.engine_defaults.get("exec")  # type: ignore[union-attr]
            if isinstance(candidate, str) and candidate.strip():
                default_engine_id = candidate.strip()
        except Exception:
            default_engine_id = None
        return build_spec_from_protocol_files(
            protocol_root,
            default_engine_id=default_engine_id,
            default_qa_prompt=default_qa_prompt or "prompts/quality-validator.prompt.md",
        )

    def build_repo_snapshot(
        self,
        project: Project,
        workspace: Path,
    ) -> str:
        """
        Build a repository snapshot for prompt injection.
        
        Args:
            project: Project object
            workspace: Workspace path
            
        Returns:
            Markdown-formatted snapshot
        """
        return _build_repo_snapshot(workspace)

    def decompose_step(
        self,
        step_run_id: int,
        *,
        max_substeps: int = 5,
        job_id: Optional[str] = None,
    ) -> List[int]:
        """
        Decompose a complex step into smaller substeps.
        
        Used when a step is too large for single-agent execution.
        
        Args:
            step_run_id: Step run ID to decompose
            max_substeps: Maximum substeps to create
            job_id: Optional job ID for logging
            
        Returns:
            List of created substep IDs
        """
        # This would use an AI agent to decompose the step
        # For now, return empty list (not implemented)
        self.logger.info(
            "step_decomposition_requested",
            extra=self.log_extra(step_run_id=step_run_id, job_id=job_id),
        )
        return []
