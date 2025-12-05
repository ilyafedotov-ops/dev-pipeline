import shutil
from pathlib import Path

from .codex import run_process


def trigger_github(repo_root: Path, branch: str) -> bool:
    if shutil.which("gh") is None:
        print("gh not available; cannot trigger GitHub Actions manually.")
        return False
    try:
        run_process(["gh", "workflow", "run", "--ref", branch], cwd=repo_root, capture_output=True, text=True)
        print(f"Triggered GitHub workflow for branch {branch}")
        return True
    except Exception as exc:
        print(f"Failed to trigger GitHub workflow: {exc}")
        return False


def trigger_gitlab(repo_root: Path, branch: str) -> bool:
    if shutil.which("glab") is None:
        print("glab not available; cannot trigger GitLab pipeline manually.")
        return False
    try:
        run_process(["glab", "pipeline", "run", "--ref", branch], cwd=repo_root, capture_output=True, text=True)
        print(f"Triggered GitLab pipeline for branch {branch}")
        return True
    except Exception as exc:
        print(f"Failed to trigger GitLab pipeline: {exc}")
        return False


def trigger_ci(platform: str, repo_root: Path, branch: str) -> bool:
    if platform == "github":
        return trigger_github(repo_root, branch)
    if platform == "gitlab":
        return trigger_gitlab(repo_root, branch)
    raise ValueError(f"Unsupported platform: {platform}")
