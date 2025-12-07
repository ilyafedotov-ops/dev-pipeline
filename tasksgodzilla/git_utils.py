from pathlib import Path
from typing import List, Optional

from tasksgodzilla.codex import run_process
from tasksgodzilla.errors import GitCommandError
from tasksgodzilla.project_setup import ensure_local_repo


def resolve_project_repo_path(git_url: str, project_name: Optional[str], local_path: Optional[str]) -> Path:
    """
    Resolve a local repo path for a project, preferring the stored local_path when present.
    Falls back to ensure_local_repo which may clone when permitted.
    """
    if local_path:
        path = Path(local_path).expanduser()
        if path.exists():
            return path
    return ensure_local_repo(git_url, project_name)


def list_remote_branches(repo_root: Path) -> List[str]:
    """
    List remote branch names (origin) for the given repo root.
    """
    result = run_process(
        ["git", "ls-remote", "--heads", "origin"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    branches: List[str] = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) == 2 and parts[1].startswith("refs/heads/"):
            branches.append(parts[1].replace("refs/heads/", ""))
    return branches


def delete_remote_branch(repo_root: Path, branch: str) -> None:
    """
    Delete a remote branch (origin). Raises GitCommandError on failure.
    """
    try:
        run_process(
            ["git", "push", "origin", f":refs/heads/{branch}"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        raise GitCommandError(f"Failed to delete remote branch {branch}") from exc
