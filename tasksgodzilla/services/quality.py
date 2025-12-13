from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, TYPE_CHECKING, Dict, Any

from tasksgodzilla.config import load_config
from tasksgodzilla.logging import get_logger
from tasksgodzilla.qa import QualityResult, run_quality_check, determine_verdict
from tasksgodzilla.storage import BaseDatabase
from tasksgodzilla.domain import StepRun, ProtocolRun, StepStatus
from tasksgodzilla.metrics import metrics
from tasksgodzilla.engines import registry
from tasksgodzilla.workers.unified_runner import run_qa_unified
from tasksgodzilla.engine_resolver import StepResolution
from tasksgodzilla.services.platform.artifacts import register_run_artifact
from tasksgodzilla.services.clarifications import ClarificationsService

if TYPE_CHECKING:
    from tasksgodzilla.workers.codex_worker import handle_quality

log = get_logger(__name__)


@dataclass
class QualityService:
    """Service for quality assurance and validation of protocol steps.
    
    This service handles QA execution for protocol steps, including prompt building,
    verdict determination, and status updates based on QA results.
    
    Responsibilities:
    - Run QA checks for step runs
    - Build QA prompts with protocol context
    - Execute QA via configured engines (Codex, etc.)
    - Determine QA verdicts (PASS/FAIL) from reports
    - Update step status based on QA results
    - Handle inline (light) QA for fast feedback
    - Apply orchestration policies after QA
    - Record QA metrics and events
    
    QA Policies:
    - skip: Skip QA entirely, mark step as completed
    - light: Run inline QA immediately after execution
    - (default): Run full QA as separate job
    
    QA Context:
    QA prompts include:
    - Protocol plan (plan.md)
    - Protocol context (context.md)
    - Protocol log (log.md)
    - Step file content
    - Git status and last commit
    
    Verdict Determination:
    - Parses QA report for explicit PASS/FAIL verdict
    - Defaults to PASS if verdict not found
    - Updates step status and triggers appropriate policies
    
    Usage:
        quality_service = QualityService(db=db)
        
        # Run QA for a step run
        quality_service.run_for_step_run(
            step_run_id=456,
            job_id="job-123"
        )
        
        # Run inline QA after execution
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
            base_meta=base_meta
        )
    """

    db: Optional[BaseDatabase] = None
    default_model: Optional[str] = None

    def run_for_step_run(self, step_run_id: int, job_id: Optional[str] = None) -> None:
        """Run QA for a StepRun."""
        import shutil
        from tasksgodzilla.config import load_config
        from tasksgodzilla.domain import ProtocolStatus
        from tasksgodzilla.engine_resolver import resolve_prompt_and_outputs
        from tasksgodzilla.engines import registry
        from tasksgodzilla.errors import CodexCommandError, TasksGodzillaError
        from tasksgodzilla.logging import get_logger, log_extra
        from tasksgodzilla.spec import PROTOCOL_SPEC_KEY, get_step_spec, protocol_spec_hash
        from tasksgodzilla.services.budget import BudgetService
        from tasksgodzilla.services.git import GitService
        from tasksgodzilla.services.orchestrator import OrchestratorService
        from tasksgodzilla.services.prompts import PromptService
        from tasksgodzilla.services.spec import SpecService
        from tasksgodzilla.workers.unified_runner import run_qa_unified
        
        if self.db is None:
            raise ValueError("QualityService.db is required for step-run QA")
        
        log = get_logger(__name__)
        step = self.db.get_step_run(step_run_id)
        run = self.db.get_protocol_run(step.protocol_run_id)
        project = self.db.get_project(run.project_id)
        config = load_config()
        git_service = GitService(self.db)
        budget_service = BudgetService()
        orchestrator = OrchestratorService(self.db)
        spec_service = SpecService(self.db)
        clarifications_service = ClarificationsService(self.db)

        # Resolve QA policy early so "skip" doesn't require a git repo/worktree.
        step_spec = get_step_spec(run.template_config, step.step_name) or {}
        if not step_spec:
            step_spec = {"id": step.step_name, "name": step.step_name, "prompt_ref": step.step_name}
        template_cfg = run.template_config or {}
        protocol_spec = template_cfg.get(PROTOCOL_SPEC_KEY) if isinstance(template_cfg, dict) else None
        spec_hash_val = protocol_spec_hash(protocol_spec) if protocol_spec else None
        qa_cfg = (step_spec.get("qa") if step_spec else {}) or {}
        qa_policy = qa_cfg.get("policy")

        if qa_policy == "skip":
            self.db.update_step_status(step.id, StepStatus.COMPLETED, summary="QA skipped (policy)")
            self.db.append_event(
                step.protocol_run_id,
                "qa_skipped_policy",
                "QA skipped by policy.",
                step_run_id=step.id,
                metadata={"policy": qa_policy, "spec_hash": spec_hash_val},
            )
            try:
                _workspace_hint, protocol_hint = spec_service.resolve_protocol_paths(run, project)
                spec_service.append_protocol_log(protocol_hint, f"{step.step_name} QA skipped by policy.")
            except Exception:
                pass
            orchestrator.handle_step_completion(step.id, qa_verdict="PASS")
            return

        # Gate QA on blocking clarifications (project/protocol/step).
        try:
            from tasksgodzilla.services.policy import PolicyService

            policy_service = PolicyService(self.db)
            effective = policy_service.resolve_effective_policy(project.id)
            try:
                clarifications_service.ensure_from_policy(
                    project_id=project.id,
                    policy=effective.policy if isinstance(effective.policy, dict) else {},
                    applies_to="qa",
                    protocol_run_id=run.id,
                    step_run_id=step.id,
                )
            except Exception:
                pass
            blocking_project = clarifications_service.list_blocking_open(project_id=project.id, applies_to="onboarding")
            blocking_protocol = clarifications_service.list_blocking_open(protocol_run_id=run.id, applies_to="planning")
            blocking_step = clarifications_service.list_blocking_open(step_run_id=step.id, applies_to="qa")
            if blocking_project or blocking_protocol or blocking_step:
                self.db.update_step_status(step.id, StepStatus.BLOCKED, summary="QA blocked pending required clarifications")
                self.db.append_event(
                    run.id,
                    "qa_blocked_clarifications",
                    f"QA blocked for {step.step_name} pending required clarifications.",
                    step_run_id=step.id,
                    metadata={
                        "project_id": project.id,
                        "protocol_run_id": run.id,
                        "step_run_id": step.id,
                        "blocking": {
                            "project": [c.__dict__ for c in blocking_project][:25],
                            "protocol": [c.__dict__ for c in blocking_protocol][:25],
                            "step": [c.__dict__ for c in blocking_step][:25],
                        },
                        "truncated": (len(blocking_project) > 25) or (len(blocking_protocol) > 25) or (len(blocking_step) > 25),
                    },
                )
                return
        except Exception:
            pass

        repo_root = git_service.ensure_repo_or_block(
            project, run, job_id=job_id, block_on_missing=False
        )
        if not repo_root or not repo_root.exists():
            repo_root = git_service.ensure_repo_or_block(project, run, job_id=job_id)
            if not repo_root:
                try:
                    self.db.update_step_status(step.id, StepStatus.BLOCKED, summary="Repo missing; QA blocked")
                    self.db.append_event(
                        step.protocol_run_id,
                        "qa_blocked_repo",
                        "QA blocked because repo is missing locally.",
                        step_run_id=step.id,
                        metadata={"git_url": project.git_url},
                    )
                except Exception:
                    pass
                return

        worktree = git_service.ensure_worktree(
            repo_root,
            run.protocol_name,
            run.base_branch,
            protocol_run_id=run.id,
            project_id=project.id,
            job_id=job_id,
        )
        budget_limit = config.max_tokens_per_step or config.max_tokens_per_protocol
        workspace_hint, protocol_hint = spec_service.resolve_protocol_paths(run, project)
        
        log.info(
            "Running QA",
            extra={
                **log_extra(
                    job_id=job_id,
                    project_id=run.project_id,
                    protocol_run_id=run.id,
                    step_run_id=step.id,
                ),
                "protocol_name": run.protocol_name,
                "branch": run.protocol_name,
                "step_name": step.step_name,
            },
        )
        
        protocol_root = worktree / ".protocols" / run.protocol_name
        # Best-effort context sync so QA sees the current step.
        try:
            context_path = protocol_root / "context.md"
            if context_path.exists():
                content = context_path.read_text(encoding="utf-8")
                lines = content.splitlines()
                updated = False
                out_lines: list[str] = []
                for line in lines:
                    if line.lower().startswith("current step"):
                        out_lines.append(f"Current Step: {step.step_name}")
                        updated = True
                    else:
                        out_lines.append(line)
                if not updated:
                    out_lines.insert(0, f"Current Step: {step.step_name}")
                context_path.write_text("\n".join(out_lines).rstrip() + "\n", encoding="utf-8")
        except Exception:
            pass
        prompt_service = PromptService(workspace_root=worktree)
        qa_prompt_path, qa_prompt_version = prompt_service.resolve_qa_prompt(qa_cfg, protocol_root, worktree)
        step_path = prompt_service.resolve_step_path_for_qa(protocol_root, step.step_name, worktree)
        qa_context = prompt_service.build_qa_context(protocol_root, step_path, worktree)

        qa_prefix = qa_prompt_path.read_text(encoding="utf-8") if qa_prompt_path.exists() else ""
        qa_body = f"""You are a QA orchestrator. Validate the current protocol step. Follow the checklist and output Markdown only (no fences).

plan.md:
{qa_context['plan']}

context.md:
{qa_context['context']}

log.md (may be empty):
{qa_context['log']}

Step file ({qa_context['step_name']}):
{qa_context['step']}

Git status (porcelain):
{qa_context['git_status']}

Latest commit message:
{qa_context['last_commit']}

Use the format from the quality-validator prompt. If any blocking issue, verdict = FAIL."""
        qa_prompt_full = f"{qa_prefix}\\n\\n{qa_body}"

        qa_engine_id = (
            qa_cfg.get("engine_id")
            or step.engine_id
            or getattr(config, "default_engine_id", None)
            or registry.get_default().metadata.id
        )

        qa_model = (
            qa_cfg.get("model")
            or (project.default_models.get("qa") if project.default_models else None)
            or config.qa_model
            or registry.get(qa_engine_id).metadata.default_model
            or "codex-5.1-max"
        )

        try:
            registry.get(qa_engine_id)
        except KeyError as exc:  # pragma: no cover - defensive guard
            self.db.update_step_status(step.id, StepStatus.BLOCKED, summary=str(exc))
            self.db.append_event(
                step.protocol_run_id,
                "qa_error",
                f"QA failed to run: {exc}",
                step_run_id=step.id,
                metadata={"engine_id": qa_engine_id, "spec_hash": spec_hash_val},
            )
            self.db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
            return

        def _qa_stub(reason: str) -> None:
            self.db.update_step_status(step.id, StepStatus.COMPLETED, summary=f"QA passed (stub; {reason})")
            metrics.inc_qa_verdict("pass")
            self.db.append_event(
                step.protocol_run_id,
                "qa_passed",
                f"QA passed (stub; {reason}).",
                step_run_id=step.id,
                metadata={"prompt_versions": {"qa": qa_prompt_version}, "model": qa_model, "spec_hash": spec_hash_val},
            )
            orchestrator.handle_step_completion(step.id, qa_verdict="PASS")

        if qa_engine_id == "codex" and shutil.which("codex") is None:
            _qa_stub("codex unavailable")
            return

        resolution = resolve_prompt_and_outputs(
            step_spec or {},
            protocol_root=protocol_root,
            workspace_root=worktree,
            protocol_spec=protocol_spec,
            default_engine_id=qa_engine_id,
        )
        qa_tokens = budget_service.check_and_track(
            qa_prompt_full, qa_model, "qa", config.token_budget_mode, budget_limit
        )

        try:
            qa_result = run_qa_unified(
                resolution,
                project_id=project.id,
                protocol_run_id=run.id,
                step_run_id=step.id,
                qa_prompt_path=qa_prompt_path,
                qa_prompt_text=qa_prompt_full,
                qa_engine_id=qa_engine_id,
                qa_model=qa_model,
                sandbox="read-only",
            )
        except (CodexCommandError, TasksGodzillaError) as exc:
            self.db.update_step_status(step.id, StepStatus.FAILED, summary=f"QA error: {exc}")
            self.db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
            self.db.append_event(
                step.protocol_run_id,
                "qa_error",
                f"QA failed to run: {exc}",
                step_run_id=step.id,
                metadata={"error": str(exc), "error_type": exc.__class__.__name__, "engine_id": qa_engine_id, "spec_hash": spec_hash_val},
            )
            log.warning(
                "qa_codex_failed",
                extra={
                    **log_extra(job_id=job_id, project_id=run.project_id, protocol_run_id=run.id, step_run_id=step.id),
                    "error": str(exc),
                    "error_type": exc.__class__.__name__,
                },
            )
            raise
        except Exception as exc:  # pragma: no cover - best effort
            log.warning(
                "QA job failed",
                extra={
                    **log_extra(job_id=job_id, project_id=run.project_id, protocol_run_id=run.id, step_run_id=step.id),
                    "error": str(exc),
                    "error_type": exc.__class__.__name__,
                },
            )
            self.db.update_step_status(step.id, StepStatus.FAILED, summary=f"QA error: {exc}")
            self.db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
            self.db.append_event(
                step.protocol_run_id,
                "qa_error",
                f"QA failed to run: {exc}",
                step_run_id=step.id,
                metadata={"prompt_versions": {"qa": qa_prompt_version}, "model": qa_model},
            )
            metrics.inc_qa_verdict("fail")
            return
            
        if not qa_result or not getattr(qa_result, "result", None):
            _qa_stub("qa engine unavailable")
            return

        report_text = qa_result.result.stdout.strip() if getattr(qa_result.result, "stdout", None) else ""
        report_path = protocol_root / "quality-report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_text, encoding="utf-8")
        verdict = determine_verdict(report_text).upper()

        if verdict == "FAIL":
            try:
                git_status = (qa_context.get("git_status") or "").splitlines()
                non_protocol_dirty = any(line.strip() and ".protocols/" not in line for line in git_status)
            except Exception:
                non_protocol_dirty = True
            if not non_protocol_dirty:
                verdict = "PASS"
                report_text = report_text + (
                    "\n\n[system] QA verdict downgraded to PASS because git status "
                    "shows only `.protocols/**` bookkeeping changes.\n"
                )
                report_path.write_text(report_text, encoding="utf-8")
                self.db.append_event(
                    step.protocol_run_id,
                    "qa_downgraded_protocol_only",
                    "QA FAIL downgraded: only protocol bookkeeping changes detected.",
                    step_run_id=step.id,
                    metadata={"model": qa_model, "spec_hash": spec_hash_val},
                )

        if job_id:
            try:
                existing = self.db.get_codex_run(job_id)
                merged = dict(existing.result or {})
                merged["qa"] = {
                    "engine_id": qa_engine_id,
                    "model": qa_model,
                    "prompt_versions": {"qa": qa_prompt_version},
                    "prompt_path": str(qa_prompt_path),
                    "report_path": str(report_path),
                    "verdict": verdict,
                    "estimated_tokens": {"qa": qa_tokens},
                    "engine_call": {
                        "success": bool(qa_result.result.success) if qa_result and qa_result.result else None,
                        "stderr_len": len(qa_result.result.stderr or "") if qa_result and qa_result.result else None,
                        "metadata": qa_result.result.metadata if qa_result and qa_result.result else None,
                    },
                }
                self.db.update_codex_run(job_id, result=merged)
            except Exception:
                pass
            try:
                register_run_artifact(
                    self.db,
                    run_id=job_id,
                    name="quality-report",
                    kind="qa_report",
                    path=str(report_path),
                )
            except Exception:
                pass

        if verdict == "FAIL":
            self.db.update_step_status(step.id, StepStatus.FAILED, summary="QA verdict: FAIL")
            self.db.append_event(
                step.protocol_run_id,
                "qa_failed",
                "QA failed via engine.",
                step_run_id=step.id,
                metadata={
                    "protocol_run_id": run.id,
                    "step_run_id": step.id,
                    "estimated_tokens": {"qa": qa_tokens},
                    "prompt_versions": {"qa": qa_prompt_version},
                    "model": qa_model,
                    "spec_hash": spec_hash_val,
                },
            )
            spec_service.append_protocol_log(protocol_root, f"{step.step_name} QA FAIL ({qa_model}).")
            orchestrator.handle_step_completion(step.id, qa_verdict="FAIL")
            metrics.inc_qa_verdict("fail")
        else:
            self.db.update_step_status(step.id, StepStatus.COMPLETED, summary="QA verdict: PASS")
            self.db.append_event(
                step.protocol_run_id,
                "qa_passed",
                "QA passed via engine.",
                step_run_id=step.id,
                metadata={
                    "protocol_run_id": run.id,
                    "step_run_id": step.id,
                    "estimated_tokens": {"qa": qa_tokens},
                    "prompt_versions": {"qa": qa_prompt_version},
                    "model": qa_model,
                    "spec_hash": spec_hash_val,
                },
            )
            spec_service.append_protocol_log(protocol_root, f"{step.step_name} QA PASS ({qa_model}).")
            orchestrator.handle_step_completion(step.id, qa_verdict="PASS")
            metrics.inc_qa_verdict("pass")

    def evaluate_step(
        self,
        protocol_root: Path,
        step_filename: str,
        *,
        prompt_file: Optional[Path] = None,
        sandbox: str = "read-only",
        report_file: Optional[Path] = None,
        engine_id: Optional[str] = None,
    ) -> QualityResult:
        """Run QA for a single step file under the given protocol root."""
        config = load_config()

        model = self.default_model or config.qa_model or "codex-5.1-max"

        # Best-effort resolution of the workspace root for prompts.
        if protocol_root.parent.name == ".protocols":
            workspace_root = protocol_root.parent.parent
        else:
            workspace_root = protocol_root.parent

        prompt_path = prompt_file or (workspace_root / "prompts" / "quality-validator.prompt.md")
        step_path = protocol_root / step_filename

        log.info(
            "quality_service_evaluate_step",
            extra={
                "protocol_root": str(protocol_root),
                "step_file": str(step_path),
                "prompt_file": str(prompt_path),
                "model": model,
                "sandbox": sandbox,
            },
        )

        return run_quality_check(
            protocol_root=protocol_root,
            step_file=step_path,
            model=model,
            prompt_file=prompt_path,
            sandbox=sandbox,
            report_file=report_file,
            max_tokens=config.max_tokens_per_step or config.max_tokens_per_protocol,
            token_budget_mode=config.token_budget_mode,
            engine_id=engine_id,
        )

    def run_inline_qa(
        self,
        step: StepRun,
        run: ProtocolRun,
        project: Any,
        resolution: StepResolution,
        qa_cfg: Dict[str, Any],
        qa_context: Dict[str, str],
        protocol_root: Path,
        workspace_root: Path,
        qa_prompt_path: Path,
        qa_prompt_version: str,
        spec_hash_val: Optional[str],
        exec_model: str,
        engine_id: str,
        exec_tokens: int,
        base_meta: Dict[str, Any],
        job_id: Optional[str] = None,
    ) -> None:
        """
        Run inline (light) QA for a step after execution.
        
        This method handles the inline QA workflow, including:
        - Building the QA prompt
        - Running the QA check
        - Determining the verdict
        - Updating step status and events
        - Calling orchestrator for completion handling
        """
        if self.db is None:
            raise ValueError("QualityService.db is required for inline QA")
        
        from tasksgodzilla.services.budget import BudgetService
        from tasksgodzilla.services.orchestrator import OrchestratorService
        from tasksgodzilla.services.spec import SpecService
        
        config = load_config()
        budget_service = BudgetService()
        orchestrator = OrchestratorService(self.db)
        spec_service = SpecService(self.db)
        budget_limit = config.max_tokens_per_step or config.max_tokens_per_protocol
        
        qa_prefix = qa_prompt_path.read_text(encoding="utf-8") if qa_prompt_path.exists() else ""
        qa_body = f"""You are a QA orchestrator. Validate the current protocol step. Follow the checklist and output Markdown only (no fences).

plan.md:
{qa_context['plan']}

context.md:
{qa_context['context']}

log.md (may be empty):
{qa_context['log']}

Step file ({qa_context['step_name']}):
{qa_context['step']}

Git status (porcelain):
{qa_context['git_status']}

Latest commit message:
{qa_context['last_commit']}

Use the format from the quality-validator prompt. If any blocking issue, verdict = FAIL."""
        qa_prompt_full = f"{qa_prefix}\\n\\n{qa_body}\\n\\nKeep this QA brief; focus on must-fix issues only."
        
        qa_engine_id = (
            qa_cfg.get("engine_id")
            or step.engine_id
            or getattr(config, "default_engine_id", None)
            or registry.get_default().metadata.id
        )

        qa_model = (
            qa_cfg.get("model")
            or (project.default_models.get("qa") if project.default_models else None)
            or config.qa_model
            or registry.get(qa_engine_id).metadata.default_model
            or "codex-5.1-max"
        )
        
        try:
            registry.get(qa_engine_id)
        except KeyError as exc:  # pragma: no cover - defensive
            self.db.update_step_status(step.id, StepStatus.NEEDS_QA, summary="Inline QA unavailable; run full QA", model=exec_model, engine_id=engine_id)
            self.db.append_event(
                step.protocol_run_id,
                "qa_inline_error",
                f"Inline QA unavailable: {exc}",
                step_run_id=step.id,
                metadata={"engine_id": qa_engine_id, "spec_hash": spec_hash_val},
            )
            spec_service.append_protocol_log(protocol_root, f"{step.step_name} inline QA unavailable; run full QA.")
            if getattr(config, "auto_qa_after_exec", False):
                self.run_for_step_run(step.id)
            return

        qa_tokens = budget_service.check_and_track(
            qa_prompt_full, qa_model, "qa", config.token_budget_mode, budget_limit
        )
        
        try:
            qa_result = run_qa_unified(
                resolution,
                project_id=project.id,
                protocol_run_id=run.id,
                step_run_id=step.id,
                qa_prompt_path=qa_prompt_path,
                qa_prompt_text=qa_prompt_full,
                qa_engine_id=qa_engine_id,
                qa_model=qa_model,
                sandbox="read-only",
            )
            report_text = (
                qa_result.result.stdout.strip()
                if qa_result and qa_result.result and getattr(qa_result.result, "stdout", None)
                else ""
            )
        except Exception as exc:  # pragma: no cover - best effort
            self.db.update_step_status(step.id, StepStatus.NEEDS_QA, summary="Inline QA error; run full QA", model=exec_model, engine_id=engine_id)
            self.db.append_event(
                step.protocol_run_id,
                "qa_inline_error",
                f"Inline QA failed: {exc}",
                step_run_id=step.id,
                metadata={"engine_id": qa_engine_id, "spec_hash": spec_hash_val},
            )
            spec_service.append_protocol_log(protocol_root, f"{step.step_name} inline QA errored; run full QA.")
            if getattr(config, "auto_qa_after_exec", False):
                self.run_for_step_run(step.id)
            return

        report_path = protocol_root / "quality-report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_text, encoding="utf-8")
        verdict = determine_verdict(report_text).upper()

        if job_id:
            try:
                existing = self.db.get_codex_run(job_id)
                merged = dict(existing.result or {})
                merged["qa_inline"] = {
                    "qa_engine_id": qa_engine_id,
                    "qa_model": qa_model,
                    "prompt_versions": {"qa": qa_prompt_version},
                    "prompt_path": str(qa_prompt_path),
                    "report_path": str(report_path),
                    "verdict": verdict,
                    "estimated_tokens": {"exec": exec_tokens, "qa": qa_tokens},
                    "engine_call": {
                        "success": bool(qa_result.result.success) if qa_result and qa_result.result else None,
                        "stderr_len": len(qa_result.result.stderr or "") if qa_result and qa_result.result else None,
                        "metadata": qa_result.result.metadata if qa_result and qa_result.result else None,
                    },
                }
                self.db.update_codex_run(job_id, result=merged)
            except Exception:
                pass
            try:
                register_run_artifact(
                    self.db,
                    run_id=job_id,
                    name="quality-report-inline",
                    kind="qa_report",
                    path=str(report_path),
                )
            except Exception:
                pass
        
        qa_meta = {
            **base_meta,
            "estimated_tokens": {"exec": exec_tokens, "qa": qa_tokens},
            "prompt_versions": {"exec": resolution.prompt_version, "qa": qa_prompt_version},
            "qa_engine_id": qa_engine_id,
            "qa_model": qa_model,
        }
        
        if verdict == "FAIL":
            self.db.update_step_status(step.id, StepStatus.FAILED, summary="QA verdict: FAIL (inline)", model=exec_model, engine_id=engine_id)
            self.db.append_event(
                step.protocol_run_id,
                "qa_failed_inline",
                "Inline QA failed.",
                step_run_id=step.id,
                metadata=qa_meta,
            )
            spec_service.append_protocol_log(protocol_root, f"{step.step_name} inline QA FAIL ({qa_model}).")
            orchestrator.handle_step_completion(step.id, qa_verdict="FAIL")
            metrics.inc_qa_verdict("fail")
        else:
            self.db.update_step_status(step.id, StepStatus.COMPLETED, summary="QA verdict: PASS (inline)", model=exec_model, engine_id=engine_id)
            self.db.append_event(
                step.protocol_run_id,
                "qa_passed_inline",
                "Inline QA passed.",
                step_run_id=step.id,
                metadata=qa_meta,
            )
            spec_service.append_protocol_log(protocol_root, f"{step.step_name} inline QA PASS ({qa_model}).")
            orchestrator.handle_step_completion(step.id, qa_verdict="PASS")
            metrics.inc_qa_verdict("pass")
