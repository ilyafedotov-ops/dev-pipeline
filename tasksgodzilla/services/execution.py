from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tasksgodzilla.config import load_config
from tasksgodzilla.codemachine.runtime_adapter import (
    build_prompt_text,
    find_agent_for_step,
    is_codemachine_run,
    output_paths,
)
from tasksgodzilla.domain import ProtocolStatus, StepStatus
from tasksgodzilla.engine_resolver import resolve_prompt_and_outputs
from tasksgodzilla.engines import registry
from tasksgodzilla.errors import CodexCommandError
from tasksgodzilla.logging import get_logger, log_extra
from tasksgodzilla.pipeline import execute_step_prompt
from tasksgodzilla.project_setup import auto_clone_enabled
from tasksgodzilla.prompt_utils import prompt_version
from tasksgodzilla.spec import (
    PROTOCOL_SPEC_KEY,
    get_step_spec,
    protocol_spec_hash,
    validate_step_spec_paths,
)
from tasksgodzilla.storage import BaseDatabase
from tasksgodzilla.workers.unified_runner import execute_step_unified

log = get_logger(__name__)


@dataclass
class ExecutionService:
    """Service for executing protocol steps.
    
    This service orchestrates the complete step execution workflow, from repository
    setup through execution to QA triggering.
    
    Responsibilities:
    - Set up repository and worktree for step execution
    - Resolve prompts and select appropriate models/engines
    - Validate step specs before execution
    - Execute steps via Codex or CodeMachine engines
    - Handle execution errors and update step status
    - Push changes and create PRs/MRs
    - Trigger CI pipelines
    - Enqueue or run QA based on policy
    - Apply trigger policies after execution
    - Handle inline (light) QA for fast feedback
    
    Execution Modes:
    - Codex: Traditional protocol-based execution with .protocols/ directory
    - CodeMachine: Agent-based execution with .codemachine/ directory
    
    QA Policies:
    - skip: Mark step as completed without QA
    - light: Run inline QA immediately after execution
    - (default): Mark step as NEEDS_QA and enqueue separate QA job
    
    Stub Execution:
    When repository or Codex CLI is unavailable, executes in "stub mode" to
    allow development and testing without full infrastructure.
    
    Usage:
        execution_service = ExecutionService(db)
        
        # Execute a step
        execution_service.execute_step(
            step_run_id=456,
            job_id="job-123"
        )
    """

    db: BaseDatabase

    def execute_step(self, step_run_id: int, job_id: Optional[str] = None) -> None:
        """Execute the given StepRun."""
        from tasksgodzilla.services.budget import BudgetService
        from tasksgodzilla.services.git import GitService
        from tasksgodzilla.services.orchestrator import OrchestratorService
        from tasksgodzilla.services.prompts import PromptService
        from tasksgodzilla.services.quality import QualityService
        from tasksgodzilla.services.spec import SpecService

        step = self.db.get_step_run(step_run_id)
        run = self.db.get_protocol_run(step.protocol_run_id)
        project = self.db.get_project(run.project_id)
        config = load_config()
        git_service = GitService(self.db)
        budget_service = BudgetService()
        orchestrator = OrchestratorService(self.db)
        spec_service = SpecService(self.db)
        branch_name = git_service.get_branch_name(run.protocol_name)
        auto_clone = auto_clone_enabled()
        budget_limit = config.max_tokens_per_step or config.max_tokens_per_protocol
        step_spec = get_step_spec(run.template_config, step.step_name)
        qa_cfg = (step_spec.get("qa") if step_spec else {}) or {}
        qa_policy = qa_cfg.get("policy")
        template_cfg = run.template_config or {}
        protocol_spec = template_cfg.get(PROTOCOL_SPEC_KEY) if isinstance(template_cfg, dict) else None
        spec_hash_val = protocol_spec_hash(protocol_spec) if protocol_spec else None
        
        log.info(
            "Executing step",
            extra={
                **self._log_context(run=run, step=step, job_id=job_id),
                "protocol_name": run.protocol_name,
                "branch": branch_name,
                "step_name": step.step_name,
            },
        )
        self.db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
        codemachine = is_codemachine_run(run)
        step_path: Optional[Path] = None
        repo_root: Optional[Path] = None

        def _stub_execute(reason: str) -> None:
            summary = f"Executed via stub ({reason})"
            if qa_policy == "skip":
                self.db.update_step_status(step.id, StepStatus.COMPLETED, summary=summary)
                self.db.append_event(
                    step.protocol_run_id,
                    "step_completed",
                    f"Step executed (stub; {reason}). QA skipped by policy.",
                    step_run_id=step.id,
                    metadata={"spec_hash": spec_hash_val},
                )
                self.db.append_event(
                    step.protocol_run_id,
                    "qa_skipped_policy",
                    "QA skipped by policy during stub execution.",
                    step_run_id=step.id,
                    metadata={"policy": qa_policy, "spec_hash": spec_hash_val},
                )
                orchestrator.handle_step_completion(step.id, qa_verdict="PASS")
                return
            self.db.update_step_status(step.id, StepStatus.NEEDS_QA, summary=summary)
            self.db.append_event(
                step.protocol_run_id,
                "step_completed",
                f"Step executed (stub; {reason}). QA required.",
                step_run_id=step.id,
                metadata={"spec_hash": spec_hash_val},
            )
            orchestrator.apply_trigger_policy(step, reason="exec_stub")
            if getattr(config, "auto_qa_after_exec", False):
                self.db.append_event(
                    step.protocol_run_id,
                    "qa_enqueued",
                    "Auto QA after execution.",
                    step_run_id=step.id,
                    metadata={"source": "auto_after_exec"},
                )
                quality_service = QualityService(db=self.db)
                quality_service.run_for_step_run(step.id, job_id=job_id)

        if codemachine:
            repo_root = git_service.ensure_repo_or_block(project, run, job_id=job_id)
            if repo_root is None:
                self.db.update_step_status(step.id, StepStatus.BLOCKED, summary="Repository unavailable")
                return
        else:
            repo_root = git_service.ensure_repo_or_block(
                project,
                run,
                job_id=job_id,
                block_on_missing=False,
                clone_if_missing=auto_clone,
            )
            if repo_root is None:
                _stub_execute("repository unavailable")
                return

        if codemachine:
            workspace_root = Path(run.worktree_path).expanduser() if run.worktree_path else repo_root
            protocol_root = Path(run.protocol_root).resolve() if run.protocol_root else (workspace_root / ".codemachine")
        else:
            if shutil.which("codex") is None:
                _stub_execute("codex unavailable")
                return
            worktree = git_service.ensure_worktree(
                repo_root,
                run.protocol_name,
                run.base_branch,
                protocol_run_id=run.id,
                project_id=project.id,
                job_id=job_id,
            )
            workspace_root = worktree
            protocol_root = worktree / ".protocols" / run.protocol_name

        spec_errors = validate_step_spec_paths(protocol_root, step_spec or {}, workspace=workspace_root)
        if spec_errors:
            for err in spec_errors:
                self.db.append_event(
                    run.id,
                    "spec_validation_error",
                    err,
                    step_run_id=step.id,
                    metadata={"step": step.step_name, "spec_hash": spec_hash_val},
                )
            self.db.update_step_status(step.id, StepStatus.FAILED, summary="Spec validation failed")
            self.db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
            return

        resolution = resolve_prompt_and_outputs(
            step_spec or {},
            protocol_root=protocol_root,
            workspace_root=workspace_root,
            protocol_spec=protocol_spec,
            default_engine_id=step.engine_id or registry.get_default().metadata.id,
        )
        kind = "codemachine" if codemachine else "codex"
        engine_id = resolution.engine_id or registry.get_default().metadata.id
        exec_model: Optional[str] = resolution.model

        if codemachine:
            agent = find_agent_for_step(step, template_cfg)
            if not agent:
                self.db.update_step_status(step.id, StepStatus.FAILED, summary="CodeMachine agent not found")
                self.db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
                self.db.append_event(
                    run.id,
                    "codemachine_step_failed",
                    "CodeMachine agent not found.",
                    step_run_id=step.id,
                    metadata={"step_name": step.step_name, "template": template_cfg.get("template")},
                )
                return
            placeholders = template_cfg.get("placeholders") or {}
            prompt_text, prompt_path = build_prompt_text(agent, protocol_root, placeholders, step_spec=step_spec, workspace=workspace_root)
            engine_defaults = (template_cfg.get("template") or {}).get("engineDefaults") or {}
            agent_id = str(agent.get("id") or agent.get("agent_id") or step.step_name)
            engine_id = (
                step_spec.get("engine_id")
                or step.engine_id
                or agent.get("engine_id")
                or engine_defaults.get("execute")
                or registry.get_default().metadata.id
            )
            exec_model = (
                exec_model
                or step_spec.get("model")
                or step.model
                or agent.get("model")
                or engine_defaults.get("executeModel")
                or (project.default_models.get("exec") if project.default_models else None)
                or getattr(config, "exec_model", None)
                or registry.get(engine_id).metadata.default_model
                or "codex-5.1-max-xhigh"
            )
            resolution.prompt_path = prompt_path
            resolution.prompt_text = prompt_text
            resolution.prompt_version = prompt_version(prompt_path)
            resolution.engine_id = engine_id
            resolution.model = exec_model
            resolution.agent_id = agent_id
            resolution.step_name = step.step_name
            default_protocol, default_codemachine = output_paths(workspace_root, protocol_root, run, step, agent_id)
            if not resolution.outputs.protocol:
                resolution.outputs.protocol = default_protocol
                resolution.outputs.raw["protocol"] = str(default_protocol)
            if "codemachine" not in resolution.outputs.aux:
                resolution.outputs.aux["codemachine"] = default_codemachine
            resolution.workdir = workspace_root
            step_path = resolution.prompt_path
        else:
            step_path = resolution.prompt_path
            if not step_path.exists():
                fallback = (protocol_root / step.step_name).resolve()
                if fallback.exists():
                    step_path = fallback
            step_content = step_path.read_text(encoding="utf-8") if step_path.exists() else ""
            plan_md = (protocol_root / "plan.md").read_text(encoding="utf-8")
            exec_prompt = execute_step_prompt(run.protocol_name, run.protocol_name.split("-")[0], plan_md, step_path.name, step_content)
            engine_id = step_spec.get("engine_id") or step.engine_id or engine_id
            exec_model = (
                exec_model
                or step_spec.get("model")
                or step.model
                or (project.default_models.get("exec") if project.default_models else None)
                or config.exec_model
                or "codex-5.1-max-xhigh"
            )
            resolution.prompt_path = step_path
            resolution.prompt_text = exec_prompt
            resolution.prompt_version = prompt_version(step_path)
            resolution.engine_id = engine_id
            resolution.model = exec_model
            resolution.workdir = workspace_root
            if not resolution.outputs.protocol:
                default_protocol_out = step_path if step_path else (protocol_root / step.step_name).resolve()
                resolution.outputs.protocol = default_protocol_out
                resolution.outputs.raw["protocol"] = str(default_protocol_out)

        try:
            engine = registry.get(engine_id)
        except KeyError as exc:  # pragma: no cover - defensive guard
            self.db.update_step_status(step.id, StepStatus.FAILED, summary=str(exc))
            self.db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
            self.db.append_event(
                run.id,
                "step_execution_failed",
                f"Execution failed: {exc}",
                step_run_id=step.id,
                metadata={"engine_id": engine_id, "spec_hash": spec_hash_val},
            )
            return

        if engine.metadata.id == "codex" and shutil.which("codex") is None:
            _stub_execute("codex unavailable")
            return

        exec_tokens = budget_service.check_and_track(
            resolution.prompt_text, exec_model, "exec", config.token_budget_mode, budget_limit
        )
        self.db.append_event(
            step.protocol_run_id,
            "step_started",
            f"Executing step via {kind.title()}.",
            step_run_id=step.id,
            metadata={
                "engine_id": engine_id,
                "model": exec_model,
                "prompt_path": str(resolution.prompt_path),
                "prompt_versions": {"exec": resolution.prompt_version},
                "spec_hash": spec_hash_val,
                "agent_id": resolution.agent_id,
            },
        )
        try:
            exec_result = execute_step_unified(
                resolution,
                project_id=project.id,
                protocol_run_id=run.id,
                step_run_id=step.id,
            )
        except CodexCommandError as exc:
            self.db.update_step_status(step.id, StepStatus.FAILED, summary=f"Execution error: {exc}")
            self.db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
            self.db.append_event(
                step.protocol_run_id,
                "step_execution_failed",
                f"Execution failed: {exc}",
                step_run_id=step.id,
                metadata={"error": str(exc), "error_type": exc.__class__.__name__, "engine_id": engine_id, "spec_hash": spec_hash_val},
            )
            log.warning(
                "step_execution_codex_failed",
                extra={**self._log_context(run=run, step=step, job_id=job_id), "error": str(exc), "error_type": exc.__class__.__name__},
            )
            raise
        except Exception as exc:  # pragma: no cover - best effort
            self.db.update_step_status(step.id, StepStatus.FAILED, summary=f"Execution error: {exc}")
            self.db.append_event(
                step.protocol_run_id,
                "step_execution_failed",
                f"Execution failed: {exc}",
                step_run_id=step.id,
                metadata={"protocol_run_id": run.id, "step_run_id": step.id, "model": exec_model},
            )
            orchestrator.handle_step_completion(step.id, qa_verdict="FAIL")
            return

        if kind == "codex":
            pushed = git_service.push_and_open_pr(
                workspace_root,
                run.protocol_name,
                run.base_branch,
                protocol_run_id=run.id,
                project_id=project.id,
                job_id=job_id,
            )
            if pushed:
                triggered = git_service.trigger_ci(
                    workspace_root,
                    run.protocol_name,
                    project.ci_provider,
                    protocol_run_id=run.id,
                    project_id=project.id,
                    job_id=job_id,
                )
                if triggered:
                    self.db.append_event(step.protocol_run_id, "ci_triggered", "CI triggered after push.", step_run_id=step.id, metadata={"branch": run.protocol_name})
                self.db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
            else:
                if git_service.remote_branch_exists(workspace_root, run.protocol_name):
                    self.db.append_event(
                        step.protocol_run_id,
                        "open_pr_branch_exists",
                        "Branch already exists remotely; skipping push/PR.",
                        step_run_id=step.id,
                        metadata={"branch": run.protocol_name},
                    )
                    self.db.update_protocol_status(run.id, ProtocolStatus.RUNNING)
                else:
                    self.db.append_event(
                        step.protocol_run_id,
                        "open_pr_failed",
                        "Failed to push branch or open PR/MR.",
                        step_run_id=step.id,
                        metadata={"branch": run.protocol_name},
                    )
                    self.db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)

        outputs_meta = exec_result.metadata.get("outputs") if exec_result else {}
        base_meta = {
            "protocol_run_id": run.id,
            "step_run_id": step.id,
            "estimated_tokens": {"exec": exec_tokens},
            "outputs": outputs_meta,
            "prompt_versions": {"exec": resolution.prompt_version},
            "prompt_path": str(resolution.prompt_path),
            "engine_id": engine_id,
            "model": exec_model,
            "spec_hash": spec_hash_val,
            "spec_validated": True,
            "agent_id": resolution.agent_id,
        }
        if kind == "codemachine":
            self.db.append_event(
                step.protocol_run_id,
                "codemachine_step_completed",
                f"CodeMachine agent {resolution.agent_id} executed.",
                step_run_id=step.id,
                metadata=base_meta,
            )
        self.db.append_event(
            step.protocol_run_id,
            "step_completed",
            f"Step executed via {kind.title()}. {'Inline QA running.' if qa_policy == 'light' else 'QA required.'}",
            step_run_id=step.id,
            metadata=base_meta,
        )
        spec_service.append_protocol_log(protocol_root, f"{step.step_name} executed via {kind.title()} ({exec_model or engine_id}); QA {'inline' if qa_policy == 'light' else 'pending'}.")

        orchestrator.apply_trigger_policy(step, reason="exec_completed")

        if qa_policy == "light":
            prompt_service = PromptService(workspace_root=workspace_root)
            qa_prompt_path, qa_prompt_version = prompt_service.resolve_qa_prompt(qa_cfg, protocol_root, workspace_root)
            step_path_for_qa = prompt_service.resolve_step_path_for_qa(protocol_root, step.step_name, workspace_root)
            qa_context = prompt_service.build_qa_context(protocol_root, step_path_for_qa, workspace_root)
            
            quality_service = QualityService(db=self.db)
            quality_service.run_inline_qa(
                step=step,
                run=run,
                project=project,
                resolution=resolution,
                qa_cfg=qa_cfg,
                qa_context=qa_context,
                protocol_root=protocol_root,
                workspace_root=workspace_root,
                qa_prompt_path=qa_prompt_path,
                qa_prompt_version=qa_prompt_version,
                spec_hash_val=spec_hash_val,
                exec_model=exec_model,
                engine_id=engine_id,
                exec_tokens=exec_tokens,
                base_meta=base_meta,
            )
            return

        self.db.update_step_status(step.id, StepStatus.NEEDS_QA, summary=f"Executed via {kind.title()}; pending QA", model=exec_model, engine_id=engine_id)
        if getattr(config, "auto_qa_after_exec", False):
            self.db.append_event(
                step.protocol_run_id,
                "qa_enqueued",
                "Auto QA after execution.",
                step_run_id=step.id,
                metadata={"source": "auto_after_exec"},
            )
            quality_service = QualityService(db=self.db)
            quality_service.run_for_step_run(step.id, job_id=job_id)

    def _log_context(self, run=None, step=None, job_id=None, project_id=None, protocol_run_id=None):
        """Build a standard extra payload so job/protocol/step IDs are always populated."""
        return log_extra(
            job_id=job_id,
            project_id=project_id or (run.project_id if run else None),
            protocol_run_id=protocol_run_id or (run.id if run else None),
            step_run_id=step.id if step else None,
        )

