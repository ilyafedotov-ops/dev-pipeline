from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import os
import shutil

from tasksgodzilla.logging import get_logger, log_extra
from tasksgodzilla.project_setup import (
    DEFAULT_PROJECTS_ROOT,
    configure_git_identity,
    configure_git_remote,
    ensure_assets,
    ensure_local_repo,
    local_repo_dir,
    prefer_github_ssh,
)
from tasksgodzilla.storage import BaseDatabase
from tasksgodzilla.domain import ProtocolStatus
from tasksgodzilla.git_utils import resolve_project_repo_path
from tasksgodzilla.services.policy import PolicyService
from tasksgodzilla.services.clarifications import ClarificationsService
from tasksgodzilla.services.git import GitService

log = get_logger(__name__)


@dataclass
class OnboardingService:
    """Service for project onboarding and workspace setup.
    
    This service handles the complete project onboarding workflow, from initial
    registration through repository setup to discovery and configuration.
    
    Responsibilities:
    - Register new projects in the database
    - Clone or validate project repositories
    - Ensure starter assets (prompts, CI scripts, docs)
    - Configure git identity and remotes
    - Run Codex or Opencode discovery for automatic workflow generation
    - Generate onboarding clarification questions
    - Handle blocking vs non-blocking onboarding flows
    
    Onboarding Workflow:
    1. Register project with git URL and base branch
    2. Clone repository (if auto-clone enabled) or validate existing path
    3. Ensure starter assets (prompts/, docs/, scripts/ci/)
    4. Configure git identity (user.name, user.email)
    5. Configure git remote (SSH vs HTTPS)
    6. Run Codex or Opencode discovery (optional, generates docs/workflows)
    7. Present clarification questions (CI provider, models, etc.)
    8. Mark setup as complete or blocked pending clarifications
    
    Clarification Questions:
    - CI provider (github/gitlab)
    - Git SSH preference
    - Git identity (user.name/user.email)
    - Branch naming patterns
    - Required checks before merge
    - PR policy (draft vs ready)
    - Default models for planning/exec/QA
    - Project secrets
    
    Usage:
        onboarding_service = OnboardingService(db)
        
        # Register new project
        project = onboarding_service.register_project(
            name="my-project",
            git_url="https://github.com/org/repo",
            base_branch="main",
            ci_provider="github"
        )
        
        # Ensure workspace is ready
        repo_root = onboarding_service.ensure_workspace(
            project_id=project.id,
            clone_if_missing=True,
            run_discovery_pass=True
        )
        
        # Run full setup job
        onboarding_service.run_project_setup_job(
            project_id=project.id
        )
    """

    db: BaseDatabase

    def register_project(
        self,
        name: str,
        git_url: str,
        base_branch: str,
        *,
        ci_provider: Optional[str] = None,
        project_classification: Optional[str] = None,
        default_models: Optional[dict] = None,
        secrets: Optional[dict] = None,
    ):
        """Create a new project row in the database."""
        project = self.db.create_project(
            name=name,
            git_url=git_url,
            base_branch=base_branch,
            ci_provider=ci_provider,
            project_classification=project_classification,
            default_models=default_models,
            secrets=secrets,
        )
        log.info(
            "onboarding_register_project",
            extra={"project_id": project.id, "git_url": project.git_url, "base_branch": project.base_branch},
        )
        return project

    def ensure_workspace(
        self,
        project_id: int,
        *,
        clone_if_missing: Optional[bool] = None,
        run_discovery_pass: bool = False,
        discovery_model: Optional[str] = None,
    ) -> Path:
        """Ensure the project's repository exists locally and starter assets are present."""
        project = self.db.get_project(project_id)

        repo_root = ensure_local_repo(
            project.git_url,
            project_name=project.name,
            project_id=project.id,
            clone_if_missing=clone_if_missing,
        )
        ensure_assets(repo_root)
        self.db.update_project_local_path(project.id, str(repo_root))

        if run_discovery_pass:
            model = discovery_model or "zai-coding-plan/glm-4.6"
            try:
                self._run_discovery_for_workspace(repo_root, model)
            except Exception as exc:  # pragma: no cover - best effort
                log.warning(
                    "onboarding_discovery_failed",
                    extra={"project_id": project.id, "repo_root": str(repo_root), "error": str(exc)},
                )

        log.info(
            "onboarding_workspace_ready",
            extra={"project_id": project.id, "repo_root": str(repo_root)},
        )
        return repo_root

    def _run_discovery_for_workspace(self, repo_root: Path, model: str) -> None:
        """Run discovery using configured engine (used by ensure_workspace)."""
        from tasksgodzilla.config import load_config
        from tasksgodzilla.engines import EngineRequest, registry
        from tasksgodzilla.project_setup import _resolve_prompt

        config = load_config()
        engine_id = config.engine_defaults.get("discovery", config.default_engine_id)

        # Ensure the appropriate engine module is imported
        if engine_id == "opencode":
            import tasksgodzilla.engines_opencode  # noqa: F401
            has_api_key = bool(os.environ.get("TASKSGODZILLA_OPENCODE_API_KEY", "").strip())
            has_cli = shutil.which("opencode") is not None
            if not has_api_key and not has_cli:
                log.warning(
                    "discovery_skipped",
                    extra={"repo_root": str(repo_root), "reason": "opencode API key not set and CLI not available", "engine_id": engine_id},
                )
                return
        else:
            import tasksgodzilla.engines_codex  # noqa: F401
            has_cli = shutil.which("codex") is not None
            if not has_cli:
                log.warning(
                    "discovery_skipped",
                    extra={"repo_root": str(repo_root), "reason": "codex CLI not available", "engine_id": engine_id},
                )
                return

        stage_map = {
            "inventory": "discovery-inventory.prompt.md",
            "architecture": "discovery-architecture.prompt.md",
            "api_reference": "discovery-api-reference.prompt.md",
            "ci_notes": "discovery-ci-notes.prompt.md",
        }

        engine = registry.get(engine_id)
        timeout_seconds = int(os.environ.get("TASKSGODZILLA_DISCOVERY_TIMEOUT", "180"))

        for stage, prompt_name in stage_map.items():
            prompt_path = _resolve_prompt(repo_root, prompt_name)
            if not prompt_path:
                continue
            try:
                prompt_text = prompt_path.read_text(encoding="utf-8")
                req = EngineRequest(
                    project_id=0,
                    protocol_run_id=0,
                    step_run_id=0,
                    model=model,
                    prompt_files=[],
                    working_dir=str(repo_root),
                    extra={
                        "prompt_text": prompt_text,
                        "sandbox": "workspace-write",
                        "timeout_seconds": timeout_seconds,
                    },
                )
                engine.execute(req)
            except Exception as exc:
                log.warning(
                    "discovery_stage_failed",
                    extra={"stage": stage, "error": str(exc), "repo_root": str(repo_root), "engine_id": engine_id},
                )


    def run_project_setup_job(self, project_id: int, protocol_run_id: Optional[int] = None) -> None:
        """Run the full project-setup flow for a project.

        This mirrors `onboarding_worker.handle_project_setup` but lives in the
        services layer so callers can rely on a stable API while the worker is
        gradually simplified.
        """
        project = self.db.get_project(project_id)
        if protocol_run_id is None:
            run = self.db.create_protocol_run(
                project_id=project.id,
                protocol_name=f"setup-{project.id}",
                status=ProtocolStatus.PENDING,
                base_branch=project.base_branch,
                worktree_path=None,
                protocol_root=None,
                description="Project setup and bootstrap",
            )
            protocol_run_id = run.id

        self.db.update_protocol_status(protocol_run_id, ProtocolStatus.RUNNING)
        self.db.append_event(
            protocol_run_id,
            "setup_started",
            f"Onboarding {project.name}",
            metadata={"git_url": project.git_url, "local_path": project.local_path},
        )

        try:
            # Resolve or clone the repository and record local_path.
            default_repo_path = local_repo_dir(project.git_url, project.name, project_id=project.id)
            repo_hint = project.local_path or str(default_repo_path)
            candidate_paths = [default_repo_path]
            if project.local_path:
                candidate_paths.append(Path(project.local_path).expanduser())
            repo_preexisting = any(path.exists() for path in candidate_paths)
            try:
                # Use the shared resolver so auto-clone behaviour remains aligned
                # with the rest of the orchestrator.
                repo_path = resolve_project_repo_path(
                    project.git_url,
                    project.name,
                    project.local_path,
                    project_id=project.id,
                )
            except FileNotFoundError:
                self.db.append_event(
                    protocol_run_id,
                    "setup_pending_clone",
                    f"Repo path {repo_hint} not present locally. "
                    "Set TASKSGODZILLA_AUTO_CLONE=true or clone manually before running setup.",
                    metadata={
                        "git_url": project.git_url,
                        "local_path": project.local_path,
                        "projects_root": str(DEFAULT_PROJECTS_ROOT),
                    },
                )
                self.db.update_protocol_status(protocol_run_id, ProtocolStatus.BLOCKED)
                self.db.append_event(protocol_run_id, "setup_blocked", "Setup blocked until repository is present.")
                return
            except Exception as exc:  # pragma: no cover - defensive
                self.db.append_event(
                    protocol_run_id,
                    "setup_clone_failed",
                    f"Repo clone failed: {exc}",
                    metadata={"git_url": project.git_url, "projects_root": str(DEFAULT_PROJECTS_ROOT)},
                )
                self.db.update_protocol_status(protocol_run_id, ProtocolStatus.BLOCKED)
                return

            if repo_path.exists() and not repo_preexisting:
                self.db.append_event(
                    protocol_run_id,
                    "setup_cloned",
                    "Repository cloned for project setup.",
                    metadata={"path": str(repo_path), "git_url": project.git_url},
                )
            if not project.local_path or Path(project.local_path).expanduser() != repo_path:
                try:
                    self.db.update_project_local_path(project.id, str(repo_path))
                    self.db.append_event(
                        protocol_run_id,
                        "setup_local_path_recorded",
                        "Recorded project local_path for future runs.",
                        metadata={"local_path": str(repo_path)},
                    )
                except Exception:
                    pass

            # Discovery with event tracking.
            self._run_discovery(repo_path, protocol_run_id)

            # Ensure starter assets; warn but continue on failures.
            try:
                ensure_assets(repo_path)
                self.db.append_event(
                    protocol_run_id,
                    "setup_assets",
                    "Ensured starter assets (docs/prompts/CI scripts).",
                    metadata={"path": str(repo_path)},
                )
            except Exception as exc:  # pragma: no cover - best effort
                self.db.append_event(
                    protocol_run_id,
                    "setup_warning",
                    f"Skipped asset provisioning: {exc}",
                    metadata={"path": str(repo_path)},
                )

            # Git remote and identity configuration.
            try:
                prefer_ssh = prefer_github_ssh()
                origin = configure_git_remote(repo_path, project.git_url, prefer_ssh_remote=prefer_ssh)
                if origin:
                    self.db.append_event(
                        protocol_run_id,
                        "setup_git_remote",
                        f"Configured git origin (ssh={prefer_ssh}).",
                        metadata={"path": str(repo_path), "origin": origin},
                    )
                user = os.environ.get("TASKSGODZILLA_GIT_USER")
                email = os.environ.get("TASKSGODZILLA_GIT_EMAIL")
                if configure_git_identity(repo_path, user, email):
                    self.db.append_event(
                        protocol_run_id,
                        "setup_git_identity",
                        "Configured git user.name/user.email.",
                        metadata={"user": user, "email": email},
                    )
            except Exception as exc:  # pragma: no cover - best effort
                self.db.append_event(
                    protocol_run_id,
                    "setup_warning",
                    f"Git identity configuration skipped: {exc}",
                    metadata={"path": str(repo_path)},
                )

            # Clarifications with optional blocking.
            questions = _build_clarifications(project, repo_path)
            # Merge policy-pack clarifications (project classification) so onboarding can
            # adapt to different project types without hard-coding everything here.
            try:
                policy_service = PolicyService(self.db)
                effective = policy_service.resolve_effective_policy(project.id, repo_root=repo_path)
                policy_questions = effective.policy.get("clarifications") if isinstance(effective.policy, dict) else None
                questions = _merge_clarifications(questions, policy_questions)
                # Persist onboarding clarifications (project scope) for UI/API answers.
                ClarificationsService(self.db).ensure_from_policy(
                    project_id=project.id,
                    policy=effective.policy if isinstance(effective.policy, dict) else {},
                    applies_to="onboarding",
                )
            except Exception:
                pass
            blocking = require_onboarding_clarifications()
            # If the project is in strict mode and has blocking onboarding clarifications, block.
            try:
                enforcement = (project.policy_enforcement_mode or "warn").lower()
                if enforcement == "block":
                    if ClarificationsService(self.db).has_blocking_open(project_id=project.id):
                        blocking = True
            except Exception:
                pass
            self.db.append_event(
                protocol_run_id,
                "setup_clarifications",
                "Review onboarding clarifications and confirm settings.",
                metadata={"questions": questions, "blocking": blocking},
            )

            # Warnings-only policy findings (best-effort).
            try:
                policy_service = PolicyService(self.db)
                findings = policy_service.evaluate_project(project.id)
                if findings:
                    self.db.append_event(
                        protocol_run_id,
                        "policy_findings",
                        f"Policy findings detected ({len(findings)}).",
                        metadata={"scope": "project", "findings": [f.asdict() for f in findings[:25]], "truncated": len(findings) > 25},
                    )
                if policy_service.has_blocking_findings(findings):
                    self.db.update_protocol_status(protocol_run_id, ProtocolStatus.BLOCKED)
                    self.db.append_event(
                        protocol_run_id,
                        "policy_blocked",
                        "Onboarding blocked by policy enforcement mode.",
                        metadata={"blocking_findings": [f.asdict() for f in findings if f.severity == "block"][:25]},
                    )
                    return
            except Exception:
                pass

            if blocking:
                self.db.update_protocol_status(protocol_run_id, ProtocolStatus.BLOCKED)
                self.db.append_event(
                    protocol_run_id,
                    "setup_blocked",
                    "Awaiting onboarding clarification responses.",
                    metadata={"questions": [q.get("key") for q in questions]},
                )
            else:
                self.db.update_protocol_status(protocol_run_id, ProtocolStatus.COMPLETED)
                self.db.append_event(protocol_run_id, "setup_completed", "Project setup job finished.")
                self._finalize_setup(
                    project_id=project_id,
                    protocol_run_id=protocol_run_id,
                    repo_path=repo_path,
                    base_branch=project.base_branch,
                )
        except Exception as exc:  # pragma: no cover - defensive
            log.exception(
                "Project setup failed",
                extra={
                    **log_extra(project_id=project_id, protocol_run_id=protocol_run_id),
                    "error": str(exc),
                    "error_type": exc.__class__.__name__,
                },
            )
            self.db.update_protocol_status(protocol_run_id, ProtocolStatus.FAILED)
            self.db.append_event(protocol_run_id, "setup_failed", f"Setup failed: {exc}")

    def _run_discovery(self, repo_path: Path, protocol_run_id: int) -> None:
        """
        Trigger discovery automatically during onboarding using the configured engine.
        Emits events so console/TUI/CLI can show progress regardless of success/failure/skip.
        """
        from tasksgodzilla.config import load_config
        from tasksgodzilla.engines import EngineRequest, registry
        from tasksgodzilla.project_setup import _resolve_prompt

        config = load_config()
        engine_id = config.engine_defaults.get("discovery", config.default_engine_id)

        model = os.environ.get("PROTOCOL_DISCOVERY_MODEL", "zai-coding-plan/glm-4.6")
        timeout_env = os.environ.get("TASKSGODZILLA_DISCOVERY_TIMEOUT", "180")
        try:
            timeout_seconds = int(timeout_env)
        except Exception:
            timeout_seconds = 180

        # Check engine availability based on configured engine
        if engine_id == "opencode":
            import tasksgodzilla.engines_opencode  # noqa: F401
            has_api_key = bool(os.environ.get("TASKSGODZILLA_OPENCODE_API_KEY", "").strip())
            has_cli = shutil.which("opencode") is not None
            if not has_api_key and not has_cli:
                self.db.append_event(
                    protocol_run_id,
                    "setup_discovery_skipped",
                    "Discovery skipped: opencode API key not set and CLI not available.",
                    metadata={"path": str(repo_path), "model": model, "engine_id": engine_id},
                )
                return
        else:
            import tasksgodzilla.engines_codex  # noqa: F401
            has_cli = shutil.which("codex") is not None
            if not has_cli:
                self.db.append_event(
                    protocol_run_id,
                    "setup_discovery_skipped",
                    "Discovery skipped: codex CLI not available.",
                    metadata={"path": str(repo_path), "model": model, "engine_id": engine_id},
                )
                return

        stage_map: dict[str, str] = {
            "inventory": "discovery-inventory.prompt.md",
            "architecture": "discovery-architecture.prompt.md",
            "api_reference": "discovery-api-reference.prompt.md",
            "ci_notes": "discovery-ci-notes.prompt.md",
        }

        self.db.append_event(
            protocol_run_id,
            "setup_discovery_started",
            f"Running repository discovery with {engine_id} engine.",
            metadata={
                "path": str(repo_path),
                "model": model,
                "engine_id": engine_id,
                "timeout_seconds": timeout_seconds,
                "stages": list(stage_map.keys()),
            },
        )

        engine = registry.get(engine_id)
        log_path = repo_path / f"{engine_id}-discovery.log"
        completed_stages: list[str] = []
        failed_stages: list[str] = []

        for stage, prompt_name in stage_map.items():
            prompt_path = _resolve_prompt(repo_path, prompt_name)
            if not prompt_path:
                log.warning(
                    "discovery_prompt_missing",
                    extra={"stage": stage, "prompt_name": prompt_name, "repo_path": str(repo_path), "engine_id": engine_id},
                )
                continue

            try:
                prompt_text = prompt_path.read_text(encoding="utf-8")
                req = EngineRequest(
                    project_id=0,
                    protocol_run_id=protocol_run_id,
                    step_run_id=0,
                    model=model,
                    prompt_files=[],
                    working_dir=str(repo_path),
                    extra={
                        "prompt_text": prompt_text,
                        "sandbox": "workspace-write",
                        "timeout_seconds": timeout_seconds,
                    },
                )
                result = engine.execute(req)
                with log_path.open("a", encoding="utf-8") as f:
                    f.write(f"\n\n===== discovery stage: {stage} ({prompt_name}) =====\n")
                    f.write((result.stdout or "") + "\n")
                completed_stages.append(stage)
            except Exception as exc:
                log.warning(
                    "discovery_stage_failed",
                    extra={"stage": stage, "error": str(exc), "repo_path": str(repo_path), "engine_id": engine_id},
                )
                failed_stages.append(stage)

        if completed_stages:
            self.db.append_event(
                protocol_run_id,
                "setup_discovery_completed",
                f"Discovery finished ({len(completed_stages)} stages).",
                metadata={
                    "path": str(repo_path),
                    "model": model,
                    "engine_id": engine_id,
                    "completed_stages": completed_stages,
                    "failed_stages": failed_stages,
                },
            )
        else:
            self.db.append_event(
                protocol_run_id,
                "setup_discovery_warning",
                "Discovery completed with no successful stages.",
                metadata={
                    "path": str(repo_path),
                    "model": model,
                    "engine_id": engine_id,
                    "failed_stages": failed_stages,
                },
            )

    def _finalize_setup(
        self,
        project_id: int,
        protocol_run_id: int,
        repo_path: Path,
        base_branch: str,
    ) -> None:
        """
        Finalize project setup by creating branch, worktree, and protocols directory.

        This ensures the project is ready for spec-driven workflows after onboarding:
        1. Creates a git worktree for the setup protocol
        2. Creates the .protocols/<protocol_name>/ directory structure
        3. Commits and pushes the starter assets to the branch

        Called automatically after setup_completed when blocking=False.
        """
        run = self.db.get_protocol_run(protocol_run_id)
        protocol_name = run.protocol_name

        git_service = GitService(self.db)

        try:
            worktree_path = git_service.ensure_worktree(
                repo_root=repo_path,
                protocol_name=protocol_name,
                base_branch=base_branch,
                protocol_run_id=protocol_run_id,
                project_id=project_id,
            )

            self.db.append_event(
                protocol_run_id,
                "setup_worktree_created",
                f"Created worktree for {protocol_name}.",
                metadata={
                    "worktree_path": str(worktree_path),
                    "protocol_name": protocol_name,
                    "base_branch": base_branch,
                },
            )

            protocol_root = worktree_path / ".protocols" / protocol_name
            protocol_root.mkdir(parents=True, exist_ok=True)

            plan_file = protocol_root / "plan.md"
            if not plan_file.exists():
                plan_file.write_text(
                    f"# Protocol: {protocol_name}\n\n"
                    f"Setup protocol for project onboarding.\n\n"
                    f"## Status\n\nCompleted.\n",
                    encoding="utf-8",
                )

            self.db.update_protocol_paths(
                protocol_run_id,
                worktree_path=str(worktree_path),
                protocol_root=str(protocol_root),
            )

            self.db.append_event(
                protocol_run_id,
                "setup_protocols_dir_created",
                f"Created protocols directory at {protocol_root}.",
                metadata={
                    "protocol_root": str(protocol_root),
                    "protocol_name": protocol_name,
                },
            )

            pushed = git_service.push_and_open_pr(
                worktree=worktree_path,
                protocol_name=protocol_name,
                base_branch=base_branch,
                protocol_run_id=protocol_run_id,
                project_id=project_id,
            )

            if pushed:
                self.db.append_event(
                    protocol_run_id,
                    "setup_branch_pushed",
                    f"Pushed branch {protocol_name} with starter assets.",
                    metadata={"branch": protocol_name, "pushed": True},
                )
            else:
                self.db.append_event(
                    protocol_run_id,
                    "setup_branch_push_skipped",
                    "No changes to push or push skipped.",
                    metadata={"branch": protocol_name, "pushed": False},
                )

        except Exception as exc:
            log.warning(
                "setup_finalize_failed",
                extra={
                    **log_extra(project_id=project_id, protocol_run_id=protocol_run_id),
                    "error": str(exc),
                    "error_type": exc.__class__.__name__,
                },
            )
            self.db.append_event(
                protocol_run_id,
                "setup_finalize_warning",
                f"Post-setup finalization had issues: {exc}",
                metadata={"error": str(exc)},
            )


def require_onboarding_clarifications() -> bool:
    return os.environ.get("TASKSGODZILLA_REQUIRE_ONBOARDING_CLARIFICATIONS", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _merge_clarifications(base_questions: list[dict], extra: object) -> list[dict]:
    """
    Merge additional clarification questions into the onboarding set.
    De-dupes by `key` while preserving base ordering.
    """
    out: list[dict] = [q for q in (base_questions or []) if isinstance(q, dict)]
    seen = {str(q.get("key")) for q in out if q.get("key")}
    if not extra or not isinstance(extra, list):
        return out
    for q in extra:
        if not isinstance(q, dict):
            continue
        key = q.get("key")
        if not key:
            continue
        key_s = str(key)
        if key_s in seen:
            continue
        out.append(q)
        seen.add(key_s)
        if len(out) >= 200:
            break
    return out


def _build_clarifications(project, repo_path: Path):
    """
    Produce a list of clarification questions with recommended values to surface in UI/CLI/TUI.
    """
    recommended_ci = project.ci_provider or "github"
    recommended_models = project.default_models or {
        "planning": "zai-coding-plan/glm-4.6",
        "exec": "zai-coding-plan/glm-4.6",
    }
    prefer_ssh = prefer_github_ssh()
    git_user = os.environ.get("TASKSGODZILLA_GIT_USER") or ""
    git_email = os.environ.get("TASKSGODZILLA_GIT_EMAIL") or ""
    base_branch = project.base_branch or "main"
    required_checks = [
        "scripts/ci/test.sh",
        "scripts/ci/lint.sh",
        "scripts/ci/typecheck.sh",
        "scripts/ci/build.sh",
    ]
    return [
        {
            "key": "ci_provider",
            "question": "Which CI provider should be used for PR/MR automation?",
            "recommended": recommended_ci,
            "options": ["github", "gitlab"],
        },
        {
            "key": "prefer_ssh",
            "question": "Use SSH for Git operations?",
            "recommended": prefer_ssh,
            "detected": prefer_ssh,
        },
        {
            "key": "git_identity",
            "question": "Set git user.name / user.email for bot pushes?",
            "recommended": {
                "user": git_user or "Demo Bot",
                "email": git_email or "demo-bot@example.com",
            },
            "detected": {"user": git_user or None, "email": git_email or None},
        },
        {
            "key": "branch_naming",
            "question": "Base branch and naming pattern for protocol branches?",
            "recommended": {"base_branch": base_branch, "pattern": "<number>-<task>"},
        },
        {
            "key": "required_checks",
            "question": "Required checks before merge?",
            "recommended": required_checks,
        },
        {
            "key": "pr_policy",
            "question": "PR policy (draft vs ready, auto-assign reviewers)?",
            "recommended": {"mode": "draft", "auto_assign": False},
        },
        {
            "key": "default_models",
            "question": "Default models for planning/exec/QA?",
            "recommended": recommended_models,
        },
        {
            "key": "secrets",
            "question": "Project secrets/tokens to inject?",
            "recommended": ["TASKSGODZILLA_API_TOKEN", "TASKSGODZILLA_WEBHOOK_TOKEN"],
        },
        {
            "key": "codex_discovery",
            "question": "Run Codex discovery to auto-fill workflows?",
            "recommended": True,
        },
    ]
