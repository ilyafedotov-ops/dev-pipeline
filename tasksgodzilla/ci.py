import shutil
from pathlib import Path

from .codex import run_process
from .errors import CITriggerError
from .logging import get_logger

log = get_logger(__name__)


def trigger_github(repo_root: Path, branch: str) -> bool:
    if shutil.which("gh") is None:
        log.warning("gh not available; cannot trigger GitHub Actions manually.", extra={"branch": branch})
        return False
    try:
        run_process(["gh", "workflow", "run", "--ref", branch], cwd=repo_root, capture_output=True, text=True)
        log.info("Triggered GitHub workflow", extra={"branch": branch})
        return True
    except Exception as exc:
        log.error("Failed to trigger GitHub workflow", extra={"error": str(exc), "branch": branch})
        return False


def trigger_gitlab(repo_root: Path, branch: str) -> bool:
    if shutil.which("glab") is None:
        log.warning("glab not available; cannot trigger GitLab pipeline manually.", extra={"branch": branch})
        return False
    try:
        run_process(["glab", "pipeline", "run", "--ref", branch], cwd=repo_root, capture_output=True, text=True)
        log.info("Triggered GitLab pipeline", extra={"branch": branch})
        return True
    except Exception as exc:
        log.error("Failed to trigger GitLab pipeline", extra={"error": str(exc), "branch": branch})
        return False


def trigger_ci(platform: str, repo_root: Path, branch: str) -> bool:
    if platform == "github":
        return trigger_github(repo_root, branch)
    if platform == "gitlab":
        return trigger_gitlab(repo_root, branch)
    raise CITriggerError(f"Unsupported platform: {platform}", metadata={"platform": platform})
