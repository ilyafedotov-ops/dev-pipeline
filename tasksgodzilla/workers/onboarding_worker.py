from pathlib import Path
from typing import Optional

import os
import shutil

from tasksgodzilla.domain import ProtocolStatus
from tasksgodzilla.logging import get_logger, log_extra
from tasksgodzilla.project_setup import (
    DEFAULT_PROJECTS_ROOT,
    configure_git_identity,
    configure_git_remote,
    ensure_assets,
    run_codex_discovery,
    local_repo_dir,
    prefer_github_ssh,
)
from tasksgodzilla.storage import BaseDatabase
from tasksgodzilla.git_utils import resolve_project_repo_path

log = get_logger(__name__)


def handle_project_setup(project_id: int, db: BaseDatabase, protocol_run_id: Optional[int] = None) -> None:
    """
    Lightweight onboarding job that prepares a project using the existing starter assets.
    It intentionally avoids mutating git state; the goal is to surface progress to the console.
    """
    project = db.get_project(project_id)
    if protocol_run_id is None:
        run = db.create_protocol_run(
            project_id=project.id,
            protocol_name=f"setup-{project.id}",
            status=ProtocolStatus.PENDING,
            base_branch=project.base_branch,
            worktree_path=None,
            protocol_root=None,
            description="Project setup and bootstrap",
        )
        protocol_run_id = run.id

    db.update_protocol_status(protocol_run_id, ProtocolStatus.RUNNING)
    db.append_event(
        protocol_run_id,
        "setup_started",
        f"Onboarding {project.name}",
        metadata={"git_url": project.git_url, "local_path": project.local_path},
    )

    try:
        default_repo_path = local_repo_dir(project.git_url, project.name, project_id=project.id)
        repo_hint = project.local_path or str(default_repo_path)
        candidate_paths = [default_repo_path]
        if project.local_path:
            candidate_paths.append(Path(project.local_path).expanduser())
        repo_preexisting = any(path.exists() for path in candidate_paths)
        try:
            repo_path = resolve_project_repo_path(
                project.git_url,
                project.name,
                project.local_path,
                project_id=project.id,
            )
        except FileNotFoundError:
            db.append_event(
                protocol_run_id,
                "setup_pending_clone",
                f"Repo path {repo_hint} not present locally. "
                "Set TASKSGODZILLA_AUTO_CLONE=true or clone manually before running setup.",
                metadata={"git_url": project.git_url, "local_path": project.local_path, "projects_root": str(DEFAULT_PROJECTS_ROOT)},
            )
            db.update_protocol_status(protocol_run_id, ProtocolStatus.BLOCKED)
            db.append_event(protocol_run_id, "setup_blocked", "Setup blocked until repository is present.")
            return
        except Exception as exc:  # pragma: no cover - defensive
            db.append_event(
                protocol_run_id,
                "setup_clone_failed",
                f"Repo clone failed: {exc}",
                metadata={"git_url": project.git_url, "projects_root": str(DEFAULT_PROJECTS_ROOT)},
            )
            db.update_protocol_status(protocol_run_id, ProtocolStatus.BLOCKED)
            return

        if repo_path.exists() and not repo_preexisting:
            db.append_event(
                protocol_run_id,
                "setup_cloned",
                "Repository cloned for project setup.",
                metadata={"path": str(repo_path), "git_url": project.git_url},
            )
        if not project.local_path or Path(project.local_path).expanduser() != repo_path:
            try:
                db.update_project_local_path(project.id, str(repo_path))
                db.append_event(
                    protocol_run_id,
                    "setup_local_path_recorded",
                    "Recorded project local_path for future runs.",
                    metadata={"local_path": str(repo_path)},
                )
            except Exception:
                pass

        _run_discovery(repo_path, protocol_run_id, db)

        try:
            ensure_assets(repo_path)
            db.append_event(
                protocol_run_id,
                "setup_assets",
                "Ensured starter assets (docs/prompts/CI scripts).",
                metadata={"path": str(repo_path)},
            )
        except Exception as exc:  # pragma: no cover - best effort
            db.append_event(
                protocol_run_id,
                "setup_warning",
                f"Skipped asset provisioning: {exc}",
                metadata={"path": str(repo_path)},
            )
        try:
            prefer_ssh = prefer_github_ssh()
            origin = configure_git_remote(repo_path, project.git_url, prefer_ssh_remote=prefer_ssh)
            if origin:
                db.append_event(
                    protocol_run_id,
                    "setup_git_remote",
                    f"Configured git origin (ssh={prefer_ssh}).",
                    metadata={"origin": origin},
                )
        except Exception as exc:  # pragma: no cover - best effort
            db.append_event(
                protocol_run_id,
                "setup_warning",
                f"Git remote configuration skipped: {exc}",
                metadata={"path": str(repo_path)},
            )
        try:
            user = os.environ.get("TASKSGODZILLA_GIT_USER")
            email = os.environ.get("TASKSGODZILLA_GIT_EMAIL")
            if configure_git_identity(repo_path, user, email):
                db.append_event(
                    protocol_run_id,
                    "setup_git_identity",
                    "Configured git user.name/user.email.",
                    metadata={"user": user, "email": email},
                )
        except Exception as exc:  # pragma: no cover - best effort
            db.append_event(
                protocol_run_id,
                "setup_warning",
                f"Git identity configuration skipped: {exc}",
                metadata={"path": str(repo_path)},
            )
        questions = _build_clarifications(project, repo_path)
        blocking = require_onboarding_clarifications()
        db.append_event(
            protocol_run_id,
            "setup_clarifications",
            "Review onboarding clarifications and confirm settings.",
            metadata={"questions": questions, "blocking": blocking},
        )
        if blocking:
            db.update_protocol_status(protocol_run_id, ProtocolStatus.BLOCKED)
            db.append_event(
                protocol_run_id,
                "setup_blocked",
                "Awaiting onboarding clarification responses.",
                metadata={"questions": [q.get('key') for q in questions]},
            )
        else:
            db.update_protocol_status(protocol_run_id, ProtocolStatus.COMPLETED)
            db.append_event(protocol_run_id, "setup_completed", "Project setup job finished.")
    except Exception as exc:  # pragma: no cover - defensive
        log.exception(
            "Project setup failed",
            extra={
                **log_extra(project_id=project_id, protocol_run_id=protocol_run_id),
                "error": str(exc),
                "error_type": exc.__class__.__name__,
            },
        )
        db.update_protocol_status(protocol_run_id, ProtocolStatus.FAILED)
        db.append_event(protocol_run_id, "setup_failed", f"Setup failed: {exc}")


def _run_discovery(repo_path: Path, protocol_run_id: int, db: BaseDatabase) -> None:
    """
    Trigger Codex discovery automatically during onboarding. Emits events so
    console/TUI/CLI can show progress regardless of success/failure/skip.
    """
    model = os.environ.get("PROTOCOL_DISCOVERY_MODEL", "gpt-5.1-codex-max")
    timeout_env = os.environ.get("TASKSGODZILLA_DISCOVERY_TIMEOUT", "15")
    try:
        timeout_seconds = int(timeout_env)
    except Exception:
        timeout_seconds = 15
    prompt_path = repo_path / "prompts" / "repo-discovery.prompt.md"
    fallback_prompt = Path(__file__).resolve().parents[2] / "prompts" / "repo-discovery.prompt.md"

    if shutil.which("codex") is None:
        db.append_event(
            protocol_run_id,
            "setup_discovery_skipped",
            "Discovery skipped: codex CLI not available.",
            metadata={"path": str(repo_path), "model": model},
        )
        return

    if not prompt_path.exists() and fallback_prompt.exists():
        prompt_path = fallback_prompt

    if not prompt_path.exists():
        db.append_event(
            protocol_run_id,
            "setup_discovery_skipped",
            "Discovery skipped: repo-discovery prompt missing.",
            metadata={"path": str(repo_path)},
        )
        return

    db.append_event(
        protocol_run_id,
        "setup_discovery_started",
        "Running Codex repository discovery.",
        metadata={"path": str(repo_path), "model": model, "prompt": str(prompt_path), "timeout_seconds": timeout_seconds},
    )
    try:
        run_codex_discovery(repo_path, model, prompt_file=prompt_path, timeout_seconds=timeout_seconds)
        db.append_event(
            protocol_run_id,
            "setup_discovery_completed",
            "Discovery finished.",
            metadata={"path": str(repo_path), "model": model},
        )
    except Exception as exc:  # pragma: no cover - best effort
        db.append_event(
            protocol_run_id,
            "setup_discovery_warning",
            f"Discovery failed or was skipped: {exc}",
            metadata={"path": str(repo_path), "model": model},
        )


def require_onboarding_clarifications() -> bool:
    return os.environ.get("TASKSGODZILLA_REQUIRE_ONBOARDING_CLARIFICATIONS", "false").lower() in ("1", "true", "yes", "on")


def _build_clarifications(project, repo_path):
    """
    Produce a list of clarification questions with recommended values to surface in UI/CLI/TUI.
    """
    recommended_ci = project.ci_provider or "github"
    recommended_models = project.default_models or {"planning": "gpt-5.1-high", "exec": "codex-5.1-max-xhigh"}
    prefer_ssh = prefer_github_ssh()
    git_user = os.environ.get("TASKSGODZILLA_GIT_USER") or ""
    git_email = os.environ.get("TASKSGODZILLA_GIT_EMAIL") or ""
    base_branch = project.base_branch or "main"
    required_checks = ["scripts/ci/test.sh", "scripts/ci/lint.sh", "scripts/ci/typecheck.sh", "scripts/ci/build.sh"]
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
            "recommended": {"user": git_user or "Demo Bot", "email": git_email or "demo-bot@example.com"},
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
