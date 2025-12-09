import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tasksgodzilla.ci import trigger_ci
from tasksgodzilla.codex import run_process
from tasksgodzilla.domain import ProtocolRun, ProtocolStatus
from tasksgodzilla.git_utils import create_github_pr, resolve_project_repo_path
from tasksgodzilla.logging import get_logger, log_extra
from tasksgodzilla.project_setup import local_repo_dir
from tasksgodzilla.storage import BaseDatabase

log = get_logger(__name__)

SINGLE_WORKTREE = os.environ.get("TASKSGODZILLA_SINGLE_WORKTREE", "true").lower() in ("1", "true", "yes", "on")
DEFAULT_WORKTREE_BRANCH = os.environ.get("TASKSGODZILLA_WORKTREE_BRANCH", "tasksgodzilla-worktree")


@dataclass
class GitService:
    """Service for handling all git and worktree operations.
    
    This service provides centralized git operations including repository management,
    worktree creation, branch operations, PR/MR creation, and CI triggering.
    
    Responsibilities:
    - Resolve and validate repository paths
    - Create and manage git worktrees for protocol isolation
    - Push branches and create PRs/MRs via gh/glab CLI or API
    - Trigger CI pipelines for GitHub Actions and GitLab CI
    - Check remote branch existence
    - Handle git failures gracefully with appropriate status updates
    
    Worktree Strategy:
    By default, uses a single shared worktree branch (TASKSGODZILLA_SINGLE_WORKTREE=true)
    to avoid creating many per-protocol branches. Set to false for per-protocol branches.
    
    Usage:
        git_service = GitService(db)
        
        # Ensure repository exists
        repo_root = git_service.ensure_repo_or_block(
            project, run, job_id="job-123"
        )
        
        # Create or reuse worktree
        worktree = git_service.ensure_worktree(
            repo_root, "protocol-name", "main"
        )
        
        # Push and open PR
        pushed = git_service.push_and_open_pr(
            worktree, "protocol-name", "main"
        )
        
        # Trigger CI
        triggered = git_service.trigger_ci(
            repo_root, "protocol-name", "github"
        )
    """

    db: BaseDatabase

    def get_branch_name(self, protocol_name: str) -> str:
        """
        Resolve the branch name to use for worktrees. Defaults to a shared branch to
        avoid creating many per-protocol branches unless overridden.
        """
        if not SINGLE_WORKTREE:
            return protocol_name
        return DEFAULT_WORKTREE_BRANCH

    def get_worktree_path(self, repo_root: Path, protocol_name: str) -> tuple[Path, str]:
        branch_name = self.get_branch_name(protocol_name)
        worktrees_root = repo_root.parent / "worktrees"
        return worktrees_root / branch_name, branch_name

    def ensure_repo_or_block(
        self,
        project,
        run: ProtocolRun,
        *,
        job_id: Optional[str] = None,
        clone_if_missing: Optional[bool] = None,
        block_on_missing: bool = True,
    ) -> Optional[Path]:
        """
        Resolve (and optionally clone) the project repository. Marks the protocol as blocked and
        emits an event when the repo is unavailable.
        """
        try:
            repo_root = resolve_project_repo_path(
                project.git_url,
                project.name,
                project.local_path,
                project_id=project.id,
                clone_if_missing=clone_if_missing,
            )
        except FileNotFoundError as exc:
            self.db.append_event(
                run.id,
                "repo_missing",
                f"Repository not present locally: {exc}",
                metadata={"git_url": project.git_url},
            )
            if block_on_missing:
                self.db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
            return None
        except Exception as exc:  # pragma: no cover - defensive
            log.warning(
                "Repo unavailable",
                extra={
                    **self._log_context(run=run, job_id=job_id, project_id=project.id),
                    "error": str(exc),
                    "error_type": exc.__class__.__name__,
                },
            )
            self.db.append_event(
                run.id,
                "repo_clone_failed",
                f"Repository clone failed: {exc}",
                metadata={"git_url": project.git_url},
            )
            if block_on_missing:
                self.db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
            return None
        if not repo_root.exists():
            self.db.append_event(
                run.id,
                "repo_missing",
                "Repository path not available locally.",
                metadata={"git_url": project.git_url, "resolved_path": str(repo_root)},
            )
            if block_on_missing:
                self.db.update_protocol_status(run.id, ProtocolStatus.BLOCKED)
            return None
        return repo_root

    def ensure_worktree(
        self,
        repo_root: Path,
        protocol_name: str,
        base_branch: str,
        *,
        protocol_run_id: Optional[int] = None,
        project_id: Optional[int] = None,
        job_id: Optional[str] = None,
    ) -> Path:
        """Ensure a worktree exists for the given protocol/branch."""
        worktree, branch_name = self.get_worktree_path(repo_root, protocol_name)
        if not worktree.exists():
            log.info(
                "creating_worktree",
                extra={
                    **self._log_context(protocol_run_id=protocol_run_id, project_id=project_id, job_id=job_id),
                    "protocol_name": protocol_name,
                    "branch": branch_name,
                    "base_branch": base_branch,
                },
            )
            run_process(
                [
                    "git",
                    "worktree",
                    "add",
                    "--checkout",
                    "-b",
                    branch_name,
                    str(worktree),
                    f"origin/{base_branch}",
                ],
                cwd=repo_root,
            )
        return worktree

    def push_and_open_pr(
        self,
        worktree: Path,
        protocol_name: str,
        base_branch: str,
        *,
        protocol_run_id: Optional[int] = None,
        project_id: Optional[int] = None,
        job_id: Optional[str] = None,
    ) -> bool:
        """Commit, push, and open a PR/MR for the worktree changes."""
        pushed = False
        branch_exists = False
        commit_attempted = False
        try:
            run_process(["git", "add", "."], cwd=worktree, capture_output=True, text=True)
            try:
                commit_attempted = True
                run_process(
                    ["git", "commit", "-m", f"chore: sync protocol {protocol_name}"],
                    cwd=worktree,
                    capture_output=True,
                    text=True,
                )
            except Exception as exc:
                msg = str(exc).lower()
                if "nothing to commit" in msg or "no changes added to commit" in msg or "clean" in msg:
                    log.info(
                        "No changes to commit; pushing existing branch state",
                        extra={
                            **self._log_context(protocol_run_id=protocol_run_id, project_id=project_id, job_id=job_id),
                            "protocol_name": protocol_name,
                            "base_branch": base_branch,
                        },
                    )
                else:
                    raise
            run_process(
                ["git", "push", "--set-upstream", "origin", protocol_name],
                cwd=worktree,
                capture_output=True,
                text=True,
            )
            pushed = True
        except Exception as exc:
            branch_exists = self.remote_branch_exists(worktree, protocol_name)
            log.warning(
                "Failed to push branch",
                extra={
                    **self._log_context(protocol_run_id=protocol_run_id, project_id=project_id, job_id=job_id),
                    "protocol_name": protocol_name,
                    "base_branch": base_branch,
                    "error": str(exc),
                    "error_type": exc.__class__.__name__,
                    "branch_exists": branch_exists,
                    "commit_attempted": commit_attempted,
                },
            )
            if not branch_exists:
                try:
                    run_process(
                        ["git", "push", "--set-upstream", "origin", protocol_name],
                        cwd=worktree,
                        capture_output=True,
                        text=True,
                    )
                    return True
                except Exception:
                    return False
        
        # Attempt PR/MR creation if CLI is available
        self._create_pr_if_possible(worktree, protocol_name, base_branch)
        
        return pushed or branch_exists

    def trigger_ci(
        self,
        repo_root: Path,
        branch: str,
        ci_provider: Optional[str],
        *,
        protocol_run_id: Optional[int] = None,
        project_id: Optional[int] = None,
        job_id: Optional[str] = None,
    ) -> bool:
        """Best-effort CI trigger after push (gh/glab)."""
        provider = (ci_provider or "github").lower()
        result = trigger_ci(provider, repo_root, branch)
        log.info(
            "CI trigger",
            extra={
                **self._log_context(protocol_run_id=protocol_run_id, project_id=project_id, job_id=job_id),
                "provider": provider,
                "branch": branch,
                "triggered": result,
            },
        )
        return result

    def remote_branch_exists(self, repo_root: Path, branch: str) -> bool:
        """Check if a branch exists on the remote repository."""
        try:
            result = run_process(
                ["git", "ls-remote", "--exit-code", "--heads", "origin", f"refs/heads/{branch}"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def _remote_branch_exists(self, repo_root: Path, branch: str) -> bool:
        """Deprecated: Use remote_branch_exists instead."""
        return self.remote_branch_exists(repo_root, branch)

    def _create_pr_if_possible(self, worktree: Path, protocol_name: str, base_branch: str) -> bool:
        """Helper to try creating PR via GH/GLAB CLI or API fallback."""
        pr_title = f"WIP: {protocol_name}"
        pr_body = f"Protocol {protocol_name} in progress"
        
        if shutil.which("gh"):
            try:
                run_process(
                    [
                        "gh",
                        "pr",
                        "create",
                        "--title",
                        pr_title,
                        "--body",
                        pr_body,
                        "--base",
                        base_branch,
                    ],
                    cwd=worktree,
                    capture_output=True,
                    text=True,
                )
                return True
            except Exception:
                pass
        elif shutil.which("glab"):
            try:
                run_process(
                    [
                        "glab",
                        "mr",
                        "create",
                        "--title",
                        pr_title,
                        "--description",
                        pr_body,
                        "--target-branch",
                        base_branch,
                    ],
                    cwd=worktree,
                    capture_output=True,
                    text=True,
                )
                return True
            except Exception:
                pass
        else:
            if create_github_pr(worktree, head=protocol_name, base=base_branch, title=pr_title, body=pr_body):
                return True
        return False

    def _log_context(
        self,
        run: Optional[ProtocolRun] = None,
        job_id: Optional[str] = None,
        project_id: Optional[int] = None,
        protocol_run_id: Optional[int] = None,
    ) -> dict:
        return log_extra(
            job_id=job_id,
            project_id=project_id or (run.project_id if run else None),
            protocol_run_id=protocol_run_id or (run.id if run else None),
        )
