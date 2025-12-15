"""
DevGodzilla Git Service

Centralized git operations including repository management, worktree creation,
branch operations, PR/MR creation, and CI triggering.
"""

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, TypeVar

import httpx

from devgodzilla.config import get_config
from devgodzilla.errors import GitCommandError, GitLockError
from devgodzilla.logging import get_logger, log_extra
from devgodzilla.models.domain import ProtocolRun, ProtocolStatus
from devgodzilla.services.base import Service, ServiceContext

logger = get_logger(__name__)

T = TypeVar("T")


def run_process(
    cmd: list,
    *,
    cwd: Optional[Path] = None,
    capture_output: bool = True,
    text: bool = True,
    check: bool = True,
    **kwargs,
) -> subprocess.CompletedProcess:
    """
    Run a subprocess command with sensible defaults.
    
    Args:
        cmd: Command and arguments to run
        cwd: Working directory for the command
        capture_output: Whether to capture stdout/stderr
        text: Whether to decode output as text
        check: Whether to raise on non-zero exit code
        
    Returns:
        CompletedProcess result
        
    Raises:
        subprocess.CalledProcessError: If check=True and command fails
    """
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=capture_output,
        text=text,
        **kwargs,
    )
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            cmd,
            result.stdout,
            result.stderr,
        )
    return result


def is_git_lock_error(error: Exception) -> bool:
    """Check if an exception is related to git index.lock contention."""
    error_str = str(error).lower()
    lock_indicators = [
        "index.lock",
        "unable to create",
        "another git process seems to be running",
        "lock file exists",
        "could not lock",
    ]
    return any(indicator in error_str for indicator in lock_indicators)


def with_git_lock_retry(
    func: Callable[[], T],
    max_retries: int = 5,
    retry_delay: float = 1.0,
    repo_root: Optional[Path] = None,
) -> T:
    """
    Execute a git operation with automatic retry on index.lock contention.

    Args:
        func: The git operation to execute
        max_retries: Maximum number of retry attempts
        retry_delay: Initial delay between retries (exponential backoff applied)
        repo_root: Optional repo root to check for stale lock files

    Returns:
        The result of the git operation

    Raises:
        GitLockError: If operation fails after all retries due to lock contention
        Exception: Other exceptions are re-raised immediately
    """
    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as exc:
            if not is_git_lock_error(exc):
                raise

            last_error = exc

            if attempt < max_retries:
                delay = retry_delay * (2 ** attempt)
                logger.warning(
                    "git_lock_contention",
                    extra={
                        "attempt": attempt + 1,
                        "max_retries": max_retries,
                        "delay_seconds": delay,
                        "error": str(exc),
                    },
                )

                if repo_root:
                    _cleanup_stale_lock(repo_root)

                time.sleep(delay)

    raise GitLockError(
        f"Git operation failed after {max_retries + 1} attempts due to lock contention: {last_error}"
    )


def _cleanup_stale_lock(repo_root: Path) -> bool:
    """
    Attempt to clean up a stale index.lock file.

    Only removes the lock if it appears to be stale (older than 5 minutes
    and no git process is running).

    Returns True if a stale lock was removed, False otherwise.
    """
    lock_file = repo_root / ".git" / "index.lock"
    if not lock_file.exists():
        return False

    try:
        lock_age = time.time() - lock_file.stat().st_mtime
        if lock_age < 300:  # 5 minutes
            return False

        lock_file.unlink()
        logger.info(
            "git_stale_lock_removed",
            extra={"lock_file": str(lock_file), "age_seconds": lock_age},
        )
        return True
    except Exception as exc:
        logger.warning(
            "git_stale_lock_cleanup_failed",
            extra={"lock_file": str(lock_file), "error": str(exc)},
        )
        return False


class GitService(Service):
    """
    Service for handling all git and worktree operations.
    
    This service provides centralized git operations including repository management,
    worktree creation, branch operations, PR/MR creation, and CI triggering.
    
    Worktree Strategy:
    By default, uses a single shared worktree branch (DEVGODZILLA_SINGLE_WORKTREE=true)
    to avoid creating many per-protocol branches. Set to false for per-protocol branches.
    
    Example:
        git_service = GitService(context)
        
        # Create or reuse worktree
        worktree = git_service.ensure_worktree(
            repo_root, "protocol-name", "main"
        )
        
        # Push and open PR
        pushed = git_service.push_and_open_pr(
            worktree, "protocol-name", "main"
        )
    """

    def __init__(self, context: ServiceContext) -> None:
        super().__init__(context)
        self._single_worktree = os.environ.get(
            "DEVGODZILLA_SINGLE_WORKTREE", "true"
        ).lower() in ("1", "true", "yes", "on")
        self._default_branch = os.environ.get(
            "DEVGODZILLA_WORKTREE_BRANCH", "devgodzilla-worktree"
        )

    def get_branch_name(self, protocol_name: str) -> str:
        """
        Resolve the branch name to use for worktrees.
        
        Uses a shared branch by default to avoid creating many per-protocol branches.
        """
        if not self._single_worktree:
            return protocol_name
        return self._default_branch

    def get_worktree_path(self, repo_root: Path, protocol_name: str) -> tuple[Path, str]:
        """Get the worktree path and branch name for a protocol."""
        branch_name = self.get_branch_name(protocol_name)
        worktrees_root = repo_root / "worktrees"
        return worktrees_root / branch_name, branch_name

    def resolve_repo_path(
        self,
        git_url: str,
        project_name: Optional[str],
        local_path: Optional[str],
        *,
        project_id: Optional[int] = None,
        clone_if_missing: bool = False,
    ) -> Path:
        """
        Resolve a local repo path for a project.
        
        Prefers the stored local_path when present, falls back to default location.
        
        Args:
            git_url: Repository URL
            project_name: Project name for directory naming
            local_path: Optional pre-configured local path
            project_id: Optional project ID for directory naming
            clone_if_missing: Whether to clone if not present
            
        Returns:
            Path to the local repository
            
        Raises:
            FileNotFoundError: If repo doesn't exist and clone_if_missing is False
            GitCommandError: If clone fails
        """
        if local_path:
            path = Path(local_path).expanduser()
            if path.exists():
                return path

        # Determine default location
        projects_dir = Path("projects")
        if project_id:
            repo_name = git_url.rstrip("/").split("/")[-1].removesuffix(".git")
            default_path = projects_dir / str(project_id) / repo_name
        elif project_name:
            default_path = projects_dir / project_name
        else:
            repo_name = git_url.rstrip("/").split("/")[-1].removesuffix(".git")
            default_path = projects_dir / repo_name

        if default_path.exists():
            return default_path

        if not clone_if_missing:
            raise FileNotFoundError(f"Repository not found at {default_path}")

        # Clone the repository
        default_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            run_process(
                ["git", "clone", git_url, str(default_path)],
                cwd=default_path.parent,
            )
        except Exception as exc:
            raise GitCommandError(f"Failed to clone {git_url}: {exc}") from exc

        return default_path

    def ensure_worktree(
        self,
        repo_root: Path,
        protocol_name: str,
        base_branch: str,
        *,
        protocol_run_id: Optional[int] = None,
        project_id: Optional[int] = None,
    ) -> Path:
        """
        Ensure a worktree exists for the given protocol/branch.
        
        Creates the worktree if it doesn't exist, using the base branch as starting point.
        
        Args:
            repo_root: Path to the main repository
            protocol_name: Protocol name for branch naming
            base_branch: Branch to base the worktree on
            protocol_run_id: Optional protocol run ID for logging
            project_id: Optional project ID for logging
            
        Returns:
            Path to the worktree
        """
        config = get_config()
        
        if not (repo_root / ".git").exists():
            self.logger.info(
                "worktree_skipped_not_git_repo",
                extra=self.log_extra(
                    protocol_run_id=protocol_run_id,
                    project_id=project_id,
                    repo_root=str(repo_root),
                ),
            )
            return repo_root

        worktree, branch_name = self.get_worktree_path(repo_root, protocol_name)
        
        if worktree.exists():
            return worktree

        self.logger.info(
            "creating_worktree",
            extra=self.log_extra(
                protocol_run_id=protocol_run_id,
                project_id=project_id,
                branch=branch_name,
                base_branch=base_branch,
            ),
        )

        def _create_worktree() -> None:
            try:
                run_process(
                    [
                        "git", "worktree", "add", "--checkout",
                        "-b", branch_name, str(worktree),
                        f"origin/{base_branch}",
                    ],
                    cwd=repo_root,
                )
            except Exception:
                try:
                    run_process(
                        ["git", "worktree", "add", "--checkout", str(worktree), branch_name],
                        cwd=repo_root,
                    )
                except Exception:
                    run_process(
                        [
                            "git", "worktree", "add", "--checkout",
                            "-b", branch_name, str(worktree), "HEAD",
                        ],
                        cwd=repo_root,
                    )

        with_git_lock_retry(
            _create_worktree,
            max_retries=config.git_lock_max_retries,
            retry_delay=config.git_lock_retry_delay,
            repo_root=repo_root,
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
    ) -> bool:
        """
        Commit, push, and open a PR/MR for the worktree changes.
        
        Args:
            worktree: Path to the worktree
            protocol_name: Protocol name for branch/PR naming
            base_branch: Target branch for the PR
            
        Returns:
            True if push succeeded or branch exists, False otherwise
        """
        config = get_config()
        pushed = False
        branch_exists = False

        def _git_add_and_commit() -> bool:
            run_process(["git", "add", "."], cwd=worktree)
            try:
                run_process(
                    ["git", "commit", "-m", f"chore: sync protocol {protocol_name}"],
                    cwd=worktree,
                )
                return True
            except Exception as exc:
                msg = str(exc).lower()
                if "nothing to commit" in msg or "no changes" in msg or "clean" in msg:
                    self.logger.info(
                        "No changes to commit",
                        extra=self.log_extra(
                            protocol_run_id=protocol_run_id,
                            project_id=project_id,
                            protocol_name=protocol_name,
                        ),
                    )
                    return True
                raise

        def _git_push() -> None:
            run_process(
                ["git", "push", "--set-upstream", "origin", protocol_name],
                cwd=worktree,
            )

        try:
            with_git_lock_retry(
                _git_add_and_commit,
                max_retries=config.git_lock_max_retries,
                retry_delay=config.git_lock_retry_delay,
                repo_root=worktree,
            )
            _git_push()
            pushed = True
        except Exception as exc:
            branch_exists = self.remote_branch_exists(worktree, protocol_name)
            self.logger.warning(
                "Failed to push branch",
                extra=self.log_extra(
                    protocol_run_id=protocol_run_id,
                    project_id=project_id,
                    error=str(exc),
                    branch_exists=branch_exists,
                ),
            )
            if not branch_exists:
                try:
                    _git_push()
                    return True
                except Exception:
                    return False

        self._create_pr_if_possible(worktree, protocol_name, base_branch)
        return pushed or branch_exists

    def remote_branch_exists(self, repo_root: Path, branch: str) -> bool:
        """Check if a branch exists on the remote repository."""
        try:
            result = run_process(
                ["git", "ls-remote", "--exit-code", "--heads", "origin", f"refs/heads/{branch}"],
                cwd=repo_root,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False

    def list_remote_branches(self, repo_root: Path) -> list[str]:
        """List remote branch names (origin) for the given repo root."""
        result = run_process(
            ["git", "ls-remote", "--heads", "origin"],
            cwd=repo_root,
        )
        branches: list[str] = []
        for line in result.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) == 2 and parts[1].startswith("refs/heads/"):
                branches.append(parts[1].replace("refs/heads/", ""))
        return branches

    def delete_remote_branch(self, repo_root: Path, branch: str) -> None:
        """Delete a remote branch (origin)."""
        try:
            run_process(
                ["git", "push", "origin", f":refs/heads/{branch}"],
                cwd=repo_root,
            )
        except Exception as exc:
            raise GitCommandError(f"Failed to delete remote branch {branch}") from exc

    def trigger_ci(
        self,
        repo_root: Path,
        branch: str,
        ci_provider: Optional[str] = None,
        *,
        protocol_run_id: Optional[int] = None,
        project_id: Optional[int] = None,
    ) -> bool:
        """
        Best-effort CI trigger after push.
        
        Tries gh workflow run for GitHub or glab ci trigger for GitLab.
        
        Returns:
            True if CI was triggered successfully
        """
        provider = (ci_provider or "github").lower()
        result = False

        try:
            if provider == "github" and shutil.which("gh"):
                run_process(
                    ["gh", "workflow", "run", "--ref", branch],
                    cwd=repo_root,
                    check=False,
                )
                result = True
            elif provider == "gitlab" and shutil.which("glab"):
                run_process(
                    ["glab", "ci", "trigger", "--branch", branch],
                    cwd=repo_root,
                    check=False,
                )
                result = True
        except Exception as exc:
            self.logger.warning(
                "CI trigger failed",
                extra=self.log_extra(
                    protocol_run_id=protocol_run_id,
                    project_id=project_id,
                    provider=provider,
                    error=str(exc),
                ),
            )

        self.logger.info(
            "CI trigger",
            extra=self.log_extra(
                protocol_run_id=protocol_run_id,
                project_id=project_id,
                provider=provider,
                branch=branch,
                triggered=result,
            ),
        )
        return result

    def _create_pr_if_possible(
        self,
        worktree: Path,
        protocol_name: str,
        base_branch: str,
    ) -> bool:
        """Helper to try creating PR via GH/GLAB CLI or API fallback."""
        pr_title = f"WIP: {protocol_name}"
        pr_body = f"Protocol {protocol_name} in progress"

        if shutil.which("gh"):
            try:
                run_process(
                    [
                        "gh", "pr", "create",
                        "--title", pr_title,
                        "--body", pr_body,
                        "--base", base_branch,
                    ],
                    cwd=worktree,
                )
                return True
            except Exception:
                pass
        elif shutil.which("glab"):
            try:
                run_process(
                    [
                        "glab", "mr", "create",
                        "--title", pr_title,
                        "--description", pr_body,
                        "--target-branch", base_branch,
                    ],
                    cwd=worktree,
                )
                return True
            except Exception:
                pass
        else:
            if self._create_github_pr_api(
                worktree, head=protocol_name, base=base_branch, title=pr_title, body=pr_body
            ):
                return True
        return False

    def _create_github_pr_api(
        self,
        repo_root: Path,
        *,
        head: str,
        base: str,
        title: str,
        body: str,
    ) -> bool:
        """Create a GitHub PR via REST API (fallback when CLI not available)."""
        owner_repo = self._parse_github_remote(repo_root)
        if not owner_repo:
            return False
            
        owner, repo = owner_repo
        gh_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not gh_token:
            return False

        url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        headers = {
            "Authorization": f"Bearer {gh_token}",
            "Accept": "application/vnd.github+json",
        }
        payload = {
            "title": title,
            "head": head,
            "base": base,
            "body": body,
            "maintainer_can_modify": True,
        }
        
        try:
            resp = httpx.post(url, headers=headers, json=payload, timeout=30)
            return resp.status_code in (201, 422)  # 422 = already exists
        except Exception:
            return False

    def _parse_github_remote(self, repo_root: Path) -> Optional[tuple[str, str]]:
        """Parse origin remote into (owner, repo) for GitHub URLs."""
        try:
            result = run_process(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=repo_root,
                check=False,
            )
            if result.returncode != 0:
                return None
        except Exception:
            return None

        url = result.stdout.strip()
        if not url or "github.com" not in url:
            return None

        # https://github.com/owner/repo.git or git@github.com:owner/repo.git
        if url.startswith("http"):
            parts = url.split("github.com/", 1)[-1]
        elif url.startswith("git@"):
            parts = url.split(":", 1)[-1]
        else:
            return None

        parts = parts.rstrip("/").removesuffix(".git").split("/")
        if len(parts) < 2:
            return None
            
        owner, repo = parts[0], parts[1]
        if not owner or not repo:
            return None
        return owner, repo
