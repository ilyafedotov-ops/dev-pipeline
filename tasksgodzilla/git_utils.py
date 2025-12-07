import os
from pathlib import Path
from typing import List, Optional, Tuple

import httpx

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


def _parse_github_remote(repo_root: Path) -> Optional[Tuple[str, str]]:
    """
    Parse origin remote into (owner, repo) for GitHub URLs (https or ssh).
    Returns None when the remote is missing or not GitHub.
    """
    try:
        result = run_process(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    url = result.stdout.strip()
    if not url or "github.com" not in url:
        return None
    # https://github.com/owner/repo.git
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


def create_github_pr(
    repo_root: Path,
    *,
    head: str,
    base: str,
    title: str,
    body: str,
    token: Optional[str] = None,
) -> bool:
    """
    Best-effort GitHub PR creation via REST API.
    Returns True on success or when a matching PR already exists.
    """
    owner_repo = _parse_github_remote(repo_root)
    if not owner_repo:
        return False
    owner, repo = owner_repo
    gh_token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not gh_token:
        return False
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json",
    }
    payload = {"title": title, "head": head, "base": base, "body": body, "maintainer_can_modify": True}
    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=30)
    except Exception:
        return False
    if resp.status_code == 201:
        return True
    if resp.status_code == 422:
        # Likely already exists
        return True
    return False
