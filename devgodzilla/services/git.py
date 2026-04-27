"""
DevGodzilla Git Service

Centralized git operations including repository management, worktree creation,
branch operations, PR/MR creation, and CI triggering.
"""

import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

import httpx

from devgodzilla.config import get_config
from devgodzilla.errors import GitCommandError, GitLockError
from devgodzilla.logging import get_logger
from devgodzilla.services.base import Service, ServiceContext

logger = get_logger(__name__)

T = TypeVar("T")


@dataclass
class PRResult:
    """Result of a PR/MR creation operation."""
    
    provider: str  # "github" or "gitlab"
    pr_number: int
    pr_url: str
    status: str  # "open", "draft", "closed"
    title: Optional[str] = None
    body: Optional[str] = None
    source_branch: Optional[str] = None
    target_branch: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "provider": self.provider,
            "pr_number": self.pr_number,
            "pr_url": self.pr_url,
            "status": self.status,
            "title": self.title,
            "source_branch": self.source_branch,
            "target_branch": self.target_branch,
        }


class PRError(Exception):
    """Error during PR/MR creation."""
    pass


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
    Uses a dedicated branch/worktree per protocol run. The legacy single-worktree
    mode (DEVGODZILLA_SINGLE_WORKTREE) is deprecated.
    
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
        self._single_worktree = False
        self._default_branch = os.environ.get(
            "DEVGODZILLA_WORKTREE_BRANCH", "devgodzilla-worktree"
        )
        if os.environ.get("DEVGODZILLA_SINGLE_WORKTREE") is not None:
            self.logger.warning(
                "single_worktree_deprecated",
                extra=self.log_extra(),
            )

    def build_remote_git_env(
        self,
        git_url: Optional[str],
        github_token: Optional[str] = None,
    ) -> Optional[Dict[str, str]]:
        """Build a transient git env that authenticates GitHub HTTPS/SSH remotes."""
        token = (github_token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
        if not token or not git_url or "github.com" not in git_url:
            return None

        env = os.environ.copy()
        env["GITHUB_TOKEN"] = env.get("GITHUB_TOKEN") or token
        env["GH_TOKEN"] = env.get("GH_TOKEN") or token
        env["GIT_CONFIG_COUNT"] = "3"
        env["GIT_CONFIG_KEY_0"] = f"url.https://{token}:x-oauth-basic@github.com/.insteadOf"
        env["GIT_CONFIG_VALUE_0"] = "https://github.com/"
        env["GIT_CONFIG_KEY_1"] = f"url.https://{token}:x-oauth-basic@github.com/.insteadOf"
        env["GIT_CONFIG_VALUE_1"] = "git@github.com:"
        env["GIT_CONFIG_KEY_2"] = f"url.https://{token}:x-oauth-basic@github.com/.insteadOf"
        env["GIT_CONFIG_VALUE_2"] = "ssh://git@github.com/"
        return env

    def build_repo_remote_git_env(
        self,
        repo_root: Path,
        github_token: Optional[str] = None,
    ) -> Optional[Dict[str, str]]:
        """Build transient git env for the current origin remote, if any."""
        try:
            result = run_process(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=repo_root,
                check=False,
            )
        except Exception:
            return None

        remote_url = (result.stdout or "").strip()
        if result.returncode != 0 or not remote_url:
            return None
        return self.build_remote_git_env(remote_url, github_token)

    def get_branch_name(self, protocol_name: str) -> str:
        """
        Resolve the branch name to use for worktrees.
        
        Returns the protocol name for per-run worktrees.
        """
        return protocol_name

    def get_worktree_path(self, repo_root: Path, protocol_name: str) -> tuple[Path, str]:
        """Get the worktree path and branch name for a protocol."""
        branch_name = self.get_branch_name(protocol_name)
        worktrees_root = repo_root / "worktrees"
        return worktrees_root / branch_name, branch_name

    def get_spec_worktree_path(self, repo_root: Path, branch_name: str) -> Path:
        """Get the worktree path for a SpecKit run."""
        return repo_root / "worktrees" / "specs" / branch_name

    def local_branch_exists(self, repo_root: Path, branch: str) -> bool:
        """Check if a local branch exists."""
        result = run_process(
            ["git", "show-ref", "--verify", f"refs/heads/{branch}"],
            cwd=repo_root,
            check=False,
        )
        return result.returncode == 0

    def create_spec_worktree(
        self,
        repo_root: Path,
        branch_name: str,
        base_branch: str,
        *,
        spec_run_id: Optional[int] = None,
        project_id: Optional[int] = None,
    ) -> Path:
        """
        Create a dedicated worktree for a SpecKit run.

        Unlike protocol worktrees, spec runs always create a new branch/worktree.
        """
        config = get_config()

        if not (repo_root / ".git").exists():
            self.logger.info(
                "spec_worktree_skipped_not_git_repo",
                extra=self.log_extra(
                    spec_run_id=spec_run_id,
                    project_id=project_id,
                    repo_root=str(repo_root),
                ),
            )
            return repo_root

        worktree = self.get_spec_worktree_path(repo_root, branch_name)
        if worktree.exists():
            raise GitCommandError(f"Spec worktree already exists at {worktree}")

        worktree.parent.mkdir(parents=True, exist_ok=True)

        self.logger.info(
            "creating_spec_worktree",
            extra=self.log_extra(
                spec_run_id=spec_run_id,
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

    def remove_worktree(
        self,
        repo_root: Path,
        worktree_path: Path,
        *,
        force: bool = True,
        spec_run_id: Optional[int] = None,
        project_id: Optional[int] = None,
    ) -> None:
        """Remove a worktree from a repository."""
        if not worktree_path.exists():
            return
        args = ["git", "worktree", "remove"]
        if force:
            args.append("--force")
        args.append(str(worktree_path))
        run_process(args, cwd=repo_root, check=False)
        self.logger.info(
            "worktree_removed",
            extra=self.log_extra(
                spec_run_id=spec_run_id,
                project_id=project_id,
                worktree_path=str(worktree_path),
            ),
        )

    def delete_local_branch(self, repo_root: Path, branch: str) -> None:
        """Delete a local branch (best-effort)."""
        run_process(["git", "branch", "-D", branch], cwd=repo_root, check=False)

    def resolve_repo_root(self, worktree_path: Path) -> Path:
        """Resolve the main repo root for a worktree path."""
        result = run_process(
            ["git", "-C", str(worktree_path), "rev-parse", "--git-common-dir"],
            cwd=worktree_path,
            check=False,
        )
        if result.returncode != 0:
            return worktree_path
        common_dir = Path(result.stdout.strip())
        if not common_dir.is_absolute():
            common_dir = (worktree_path / common_dir).resolve()
        return common_dir.parent

    def resolve_repo_path(
        self,
        git_url: str,
        project_name: Optional[str],
        local_path: Optional[str],
        *,
        project_id: Optional[int] = None,
        clone_if_missing: bool = False,
        github_token: Optional[str] = None,
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
        repo_name = git_url.rstrip("/").split("/")[-1].removesuffix(".git")
        self.logger.debug(
            "resolve_repo_path_start",
            extra=self.log_extra(
                project_id=project_id,
                project_name=project_name,
                repo_name=repo_name,
                local_path=local_path,
                clone_if_missing=clone_if_missing,
            ),
        )
        if local_path:
            path = Path(local_path).expanduser()
            if path.exists():
                self.logger.debug(
                    "resolve_repo_path_existing",
                    extra=self.log_extra(
                        project_id=project_id,
                        repo_path=str(path),
                        source="local_path",
                    ),
                )
                return path

        # Determine default location
        projects_dir = self.config.projects_root or Path("projects")
        if project_id:
            default_path = projects_dir / str(project_id) / repo_name
        elif project_name:
            default_path = projects_dir / project_name
        else:
            default_path = projects_dir / repo_name
        self.logger.debug(
            "resolve_repo_path_default",
            extra=self.log_extra(
                project_id=project_id,
                projects_root=str(projects_dir),
                repo_path=str(default_path),
            ),
        )

        if default_path.exists():
            self.logger.debug(
                "resolve_repo_path_existing",
                extra=self.log_extra(
                    project_id=project_id,
                    repo_path=str(default_path),
                    source="default_path",
                ),
            )
            return default_path

        if not clone_if_missing:
            self.logger.debug(
                "resolve_repo_path_missing",
                extra=self.log_extra(
                    project_id=project_id,
                    repo_path=str(default_path),
                ),
            )
            raise FileNotFoundError(f"Repository not found at {default_path}")

        # Clone the repository
        default_path.parent.mkdir(parents=True, exist_ok=True)
        clone_start = time.perf_counter()
        self.logger.info(
            "repo_clone_start",
            extra=self.log_extra(
                project_id=project_id,
                repo_path=str(default_path),
                repo_parent=str(default_path.parent),
            ),
        )
        try:
            run_process(
                ["git", "clone", git_url, default_path.name],
                cwd=default_path.parent,
                env=self.build_remote_git_env(git_url, github_token),
            )
        except Exception as exc:
            self.logger.error(
                "repo_clone_failed",
                extra=self.log_extra(
                    project_id=project_id,
                    repo_path=str(default_path),
                    error=str(exc),
                ),
            )
            raise GitCommandError(f"Failed to clone {git_url}: {exc}") from exc
        clone_duration_ms = int((time.perf_counter() - clone_start) * 1000)
        self.logger.info(
            "repo_clone_complete",
            extra=self.log_extra(
                project_id=project_id,
                repo_path=str(default_path),
                duration_ms=clone_duration_ms,
            ),
        )

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
        github_token: Optional[str] = None,
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
        branch_name = self.get_branch_name(protocol_name)

        def _git_add_and_commit() -> bool:
            self._stage_protocol_changes(worktree)
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
                ["git", "push", "--set-upstream", "origin", branch_name],
                cwd=worktree,
                env=self.build_repo_remote_git_env(worktree, github_token),
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
            branch_exists = self.remote_branch_exists(worktree, branch_name, github_token=github_token)
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

        self._create_pr_if_possible(
            worktree,
            protocol_name,
            base_branch,
            head_branch=branch_name,
            github_token=github_token,
        )
        return pushed or branch_exists

    @staticmethod
    def _protocol_commit_excludes() -> list[str]:
        """Generated artifacts/specs should never be staged into feature PRs by default."""
        return [
            ":(glob).specify/**",
            ":(glob)specs/*/spec.md",
            ":(glob)specs/*/plan.md",
            ":(glob)specs/*/tasks.md",
            ":(glob)specs/*/checklist.md",
            ":(glob)specs/*/_runtime/**",
            ":(glob).devgodzilla/**",
            ":(glob)**/.devgodzilla/**",
        ]

    def _stage_protocol_changes(self, worktree: Path) -> None:
        """Stage product code/tests/docs changes while excluding generated protocol artifacts."""
        run_process(["git", "add", "--all", "--", "."], cwd=worktree)
        excluded = self._protocol_commit_excludes()
        if not excluded:
            return
        result = run_process(
            ["git", "reset", "--quiet", "--", *excluded],
            cwd=worktree,
            check=False,
        )
        if result.returncode not in (0, 1):
            raise GitCommandError("Failed to unstage generated protocol artifacts before commit")

    def remote_branch_exists(
        self,
        repo_root: Path,
        branch: str,
        github_token: Optional[str] = None,
    ) -> bool:
        """Check if a branch exists on the remote repository."""
        try:
            result = run_process(
                ["git", "ls-remote", "--exit-code", "--heads", "origin", f"refs/heads/{branch}"],
                cwd=repo_root,
                check=False,
                env=self.build_repo_remote_git_env(repo_root, github_token),
            )
            return result.returncode == 0
        except Exception:
            return False

    def list_remote_branches(self, repo_root: Path, github_token: Optional[str] = None) -> list[str]:
        """List remote branch names (origin) for the given repo root."""
        result = run_process(
            ["git", "ls-remote", "--heads", "origin"],
            cwd=repo_root,
            env=self.build_repo_remote_git_env(repo_root, github_token),
        )
        branches: list[str] = []
        for line in result.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) == 2 and parts[1].startswith("refs/heads/"):
                branches.append(parts[1].replace("refs/heads/", ""))
        return branches

    def delete_remote_branch(
        self,
        repo_root: Path,
        branch: str,
        github_token: Optional[str] = None,
    ) -> None:
        """Delete a remote branch (origin)."""
        try:
            run_process(
                ["git", "push", "origin", f":refs/heads/{branch}"],
                cwd=repo_root,
                env=self.build_repo_remote_git_env(repo_root, github_token),
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

    def open_pr(
        self,
        worktree: Path,
        protocol_name: str,
        base_branch: str,
        *,
        head_branch: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        github_token: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Best-effort PR/MR creation for an existing branch.

        Returns a dict with a best-effort `url` when available.
        """

        def _extract_url(text: str) -> Optional[str]:
            for token in (text or "").split():
                if token.startswith("http://") or token.startswith("https://"):
                    return token.strip()
            return None

        pr_title = title or f"WIP: {protocol_name}"
        pr_body = description or f"Protocol {protocol_name} in progress"
        head = head_branch or self.get_branch_name(protocol_name)

        if shutil.which("gh"):
            try:
                res = run_process(
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
                        "--head",
                        head,
                    ],
                    cwd=worktree,
                    check=False,
                    env=self.build_repo_remote_git_env(worktree, github_token),
                )
                if res.returncode == 0:
                    return {"success": True, "url": _extract_url((res.stdout or "") + "\n" + (res.stderr or "")) or ""}
            except Exception:
                pass
        elif shutil.which("glab"):
            try:
                res = run_process(
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
                        "--source-branch",
                        head,
                    ],
                    cwd=worktree,
                    check=False,
                    env=self.build_repo_remote_git_env(worktree, github_token),
                )
                if res.returncode == 0:
                    return {"success": True, "url": _extract_url((res.stdout or "") + "\n" + (res.stderr or ""))}
            except Exception:
                pass

        if self._create_github_pr_api(
            worktree,
            head=head,
            base=base_branch,
            title=pr_title,
            body=pr_body,
            github_token=github_token,
        ):
            return {"success": True, "url": None}
        return {"success": False, "url": None}

    def _create_pr_if_possible(
        self,
        worktree: Path,
        protocol_name: str,
        base_branch: str,
        *,
        head_branch: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        github_token: Optional[str] = None,
    ) -> bool:
        """Helper to try creating PR via GH/GLAB CLI or API fallback."""
        result = self.open_pr(
            worktree,
            protocol_name,
            base_branch,
            head_branch=head_branch,
            title=title,
            description=description,
            github_token=github_token,
        )
        return bool(result.get("success"))

    def _create_github_pr_api(
        self,
        repo_root: Path,
        *,
        head: str,
        base: str,
        title: str,
        body: str,
        github_token: Optional[str] = None,
    ) -> bool:
        """Create a GitHub PR via REST API (fallback when CLI not available)."""
        owner_repo = self._parse_github_remote(repo_root)
        if not owner_repo:
            return False
            
        owner, repo = owner_repo
        gh_token = github_token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
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

    def _parse_gitlab_url(self, git_url: str) -> Optional[tuple[str, str]]:
        """
        Parse GitLab URL to extract instance URL and project path.
        
        Args:
            git_url: GitLab repository URL
            
        Returns:
            Tuple of (gitlab_instance_url, project_path) or None if not GitLab
            - gitlab_instance_url: Base URL of GitLab instance (e.g., "https://gitlab.com")
            - project_path: URL-encoded project path (e.g., "group%2Fproject")
        """
        if "gitlab" not in git_url:
            return None
        
        # Handle HTTPS URLs: https://gitlab.com/group/project.git
        if git_url.startswith("https://") or git_url.startswith("http://"):
            # Extract protocol and domain
            match = re.match(r'(https?://[^/]+)/(.+?)(?:\.git)?/?$', git_url)
            if match:
                instance_url = match.group(1)
                project_path = match.group(2).rstrip("/")
                # URL-encode the project path for API (group/project -> group%2Fproject)
                encoded_path = project_path.replace("/", "%2F")
                return instance_url, encoded_path
        
        # Handle SSH URLs: git@gitlab.com:group/project.git
        elif git_url.startswith("git@"):
            match = re.match(r'git@([^:]+):(.+?)(?:\.git)?$', git_url)
            if match:
                domain = match.group(1)
                project_path = match.group(2)
                instance_url = f"https://{domain}"
                encoded_path = project_path.replace("/", "%2F")
                return instance_url, encoded_path
        
        return None

    def _parse_gitlab_remote(self, repo_root: Path) -> Optional[tuple[str, str]]:
        """
        Parse origin remote into (instance_url, project_path) for GitLab URLs.
        
        Args:
            repo_root: Path to the repository
            
        Returns:
            Tuple of (gitlab_instance_url, project_path) or None if not GitLab
        """
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
        return self._parse_gitlab_url(url)

    async def _resolve_gitlab_users(
        self,
        client: httpx.AsyncClient,
        gitlab_url: str,
        token: str,
        usernames: Optional[List[str]],
    ) -> List[int]:
        """
        Resolve GitLab usernames to user IDs.
        
        Args:
            client: httpx async client
            gitlab_url: GitLab instance URL
            token: GitLab private token
            usernames: List of usernames to resolve
            
        Returns:
            List of GitLab user IDs
        """
        if not usernames:
            return []
        
        user_ids: List[int] = []
        
        for username in usernames:
            try:
                response = await client.get(
                    f"{gitlab_url}/api/v4/users",
                    headers={"PRIVATE-TOKEN": token},
                    params={"username": username},
                )
                
                if response.status_code == 200:
                    users = response.json()
                    if users:
                        user_ids.append(users[0]["id"])
            except Exception as exc:
                self.logger.warning(
                    "gitlab_user_resolve_failed",
                    extra={
                        "username": username,
                        "error": str(exc),
                    },
                )
        
        return user_ids

    def detect_git_provider(self, repo_root: Path) -> str:
        """
        Detect the Git provider (github, gitlab, or unknown) for a repository.
        
        Args:
            repo_root: Path to the repository
            
        Returns:
            Provider string: "github", "gitlab", or "unknown"
        """
        try:
            result = run_process(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=repo_root,
                check=False,
            )
            if result.returncode != 0:
                return "unknown"
        except Exception:
            return "unknown"

        url = result.stdout.strip().lower()
        
        if "github.com" in url:
            return "github"
        elif "gitlab" in url:
            return "gitlab"
        elif "bitbucket" in url:
            return "bitbucket"
        
        return "unknown"

    async def open_gitlab_mr(
        self,
        repo_root: Path,
        title: str,
        body: str,
        source_branch: str,
        target_branch: str = "main",
        draft: bool = False,
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
        milestone_id: Optional[int] = None,
        remove_source_branch: bool = True,
        squash: bool = False,
        *,
        gitlab_token: Optional[str] = None,
    ) -> PRResult:
        """
        Open a GitLab merge request via API.
        
        Args:
            repo_root: Path to the repository
            title: MR title
            body: MR description
            source_branch: Branch with changes
            target_branch: Target branch for merge (default: main)
            draft: Create as draft MR
            labels: List of labels to apply
            assignees: List of GitLab usernames to assign
            milestone_id: GitLab milestone ID
            remove_source_branch: Remove source branch after merge
            squash: Squash commits on merge
            gitlab_token: Optional GitLab token (falls back to env var)
            
        Returns:
            PRResult with MR details
            
        Raises:
            PRError: If MR creation fails
        """
        parsed = self._parse_gitlab_remote(repo_root)
        if not parsed:
            raise PRError("Not a GitLab repository or could not parse URL")
        
        gitlab_url, project_path = parsed
        
        # Get token from parameter or environment
        token = gitlab_token or os.environ.get("GITLAB_TOKEN")
        if not token:
            raise PRError(
                "No GitLab token found. Set GITLAB_TOKEN environment variable "
                "or pass gitlab_token parameter."
            )
        
        mr_title = f"Draft: {title}" if draft else title
        
        payload: Dict[str, Any] = {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": mr_title,
            "description": body,
            "remove_source_branch": remove_source_branch,
            "squash": squash,
        }
        
        if labels:
            payload["labels"] = ",".join(labels)
        
        if milestone_id:
            payload["milestone_id"] = milestone_id
        
        self.logger.info(
            "creating_gitlab_mr",
            extra={
                "gitlab_url": gitlab_url,
                "project_path": project_path,
                "source_branch": source_branch,
                "target_branch": target_branch,
                "draft": draft,
            },
        )
        
        async with httpx.AsyncClient(timeout=30) as client:
            # Resolve assignees if provided
            if assignees:
                assignee_ids = await self._resolve_gitlab_users(
                    client, gitlab_url, token, assignees
                )
                if assignee_ids:
                    payload["assignee_ids"] = assignee_ids
            
            # Create MR
            response = await client.post(
                f"{gitlab_url}/api/v4/projects/{project_path}/merge_requests",
                headers={"PRIVATE-TOKEN": token},
                json=payload,
            )
            
            if response.status_code in (200, 201):
                data = response.json()
                self.logger.info(
                    "gitlab_mr_created",
                    extra={
                        "mr_iid": data["iid"],
                        "mr_url": data["web_url"],
                    },
                )
                return PRResult(
                    provider="gitlab",
                    pr_number=data["iid"],
                    pr_url=data["web_url"],
                    status="draft" if draft else "open",
                    title=title,
                    body=body,
                    source_branch=source_branch,
                    target_branch=target_branch,
                )
            elif response.status_code == 409:
                # MR already exists - try to find and return it
                self.logger.info(
                    "gitlab_mr_exists",
                    extra={
                        "source_branch": source_branch,
                        "target_branch": target_branch,
                    },
                )
                # Query for existing MR
                list_response = await client.get(
                    f"{gitlab_url}/api/v4/projects/{project_path}/merge_requests",
                    headers={"PRIVATE-TOKEN": token},
                    params={
                        "source_branch": source_branch,
                        "target_branch": target_branch,
                        "state": "opened",
                    },
                )
                if list_response.status_code == 200:
                    mrs = list_response.json()
                    if mrs:
                        existing = mrs[0]
                        return PRResult(
                            provider="gitlab",
                            pr_number=existing["iid"],
                            pr_url=existing["web_url"],
                            status=existing.get("draft", False) and "draft" or "open",
                            title=existing.get("title"),
                            source_branch=source_branch,
                            target_branch=target_branch,
                        )
                
                raise PRError("GitLab MR already exists but could not retrieve it")
            else:
                error_detail = response.text
                self.logger.error(
                    "gitlab_mr_creation_failed",
                    extra={
                        "status_code": response.status_code,
                        "error": error_detail,
                    },
                )
                raise PRError(
                    f"GitLab MR creation failed (status {response.status_code}): {error_detail}"
                )

    async def open_pr_async(
        self,
        repo_root: Path,
        title: str,
        body: str,
        source_branch: str,
        target_branch: str = "main",
        draft: bool = False,
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
    ) -> PRResult:
        """
        Open a PR/MR asynchronously using the appropriate provider API.
        
        Automatically detects whether to use GitHub or GitLab based on the
        repository's remote origin.
        
        Args:
            repo_root: Path to the repository
            title: PR/MR title
            body: PR/MR description
            source_branch: Branch with changes
            target_branch: Target branch (default: main)
            draft: Create as draft PR/MR
            labels: List of labels to apply
            assignees: List of usernames to assign
            
        Returns:
            PRResult with PR/MR details
            
        Raises:
            PRError: If PR/MR creation fails
        """
        provider = self.detect_git_provider(repo_root)
        
        if provider == "gitlab":
            return await self.open_gitlab_mr(
                repo_root=repo_root,
                title=title,
                body=body,
                source_branch=source_branch,
                target_branch=target_branch,
                draft=draft,
                labels=labels,
                assignees=assignees,
            )
        elif provider == "github":
            return await self.open_github_pr_async(
                repo_root=repo_root,
                title=title,
                body=body,
                head=source_branch,
                base=target_branch,
                draft=draft,
                labels=labels,
                assignees=assignees,
            )
        else:
            raise PRError(f"Unsupported Git provider: {provider}")

    async def open_github_pr_async(
        self,
        repo_root: Path,
        title: str,
        body: str,
        head: str,
        base: str = "main",
        draft: bool = False,
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
    ) -> PRResult:
        """
        Open a GitHub Pull Request via API asynchronously.
        
        Args:
            repo_root: Path to the repository
            title: PR title
            body: PR description
            head: Source branch
            base: Target branch (default: main)
            draft: Create as draft PR
            labels: List of labels to apply
            assignees: List of GitHub usernames to assign
            
        Returns:
            PRResult with PR details
            
        Raises:
            PRError: If PR creation fails
        """
        owner_repo = self._parse_github_remote(repo_root)
        if not owner_repo:
            raise PRError("Not a GitHub repository or could not parse URL")
        
        owner, repo = owner_repo
        gh_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not gh_token:
            raise PRError(
                "No GitHub token found. Set GITHUB_TOKEN or GH_TOKEN environment variable."
            )
        
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        headers = {
            "Authorization": f"Bearer {gh_token}",
            "Accept": "application/vnd.github+json",
        }
        payload: Dict[str, Any] = {
            "title": title,
            "head": head,
            "base": base,
            "body": body,
            "draft": draft,
            "maintainer_can_modify": True,
        }
        
        self.logger.info(
            "creating_github_pr",
            extra={
                "owner": owner,
                "repo": repo,
                "head": head,
                "base": base,
                "draft": draft,
            },
        )
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=headers, json=payload)
            
            if response.status_code == 201:
                data = response.json()
                pr_number = data["number"]
                pr_url = data["html_url"]
                
                # Apply labels and assignees if provided
                if labels or assignees:
                    issue_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}"
                    issue_payload = {}
                    if labels:
                        issue_payload["labels"] = labels
                    if assignees:
                        issue_payload["assignees"] = assignees
                    
                    await client.patch(issue_url, headers=headers, json=issue_payload)
                
                self.logger.info(
                    "github_pr_created",
                    extra={
                        "pr_number": pr_number,
                        "pr_url": pr_url,
                    },
                )
                
                return PRResult(
                    provider="github",
                    pr_number=pr_number,
                    pr_url=pr_url,
                    status="draft" if draft else "open",
                    title=title,
                    body=body,
                    source_branch=head,
                    target_branch=base,
                )
            elif response.status_code == 422:
                # PR already exists - try to find and return it
                self.logger.info(
                    "github_pr_exists",
                    extra={"head": head, "base": base},
                )
                list_url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
                list_response = await client.get(
                    list_url,
                    headers=headers,
                    params={"head": f"{owner}:{head}", "state": "open"},
                )
                if list_response.status_code == 200:
                    prs = list_response.json()
                    if prs:
                        existing = prs[0]
                        return PRResult(
                            provider="github",
                            pr_number=existing["number"],
                            pr_url=existing["html_url"],
                            status=existing.get("draft", False) and "draft" or "open",
                            title=existing.get("title"),
                            source_branch=head,
                            target_branch=base,
                        )
                
                raise PRError("GitHub PR already exists but could not retrieve it")
            else:
                error_detail = response.text
                self.logger.error(
                    "github_pr_creation_failed",
                    extra={
                        "status_code": response.status_code,
                        "error": error_detail,
                    },
                )
                raise PRError(
                    f"GitHub PR creation failed (status {response.status_code}): {error_detail}"
                )
