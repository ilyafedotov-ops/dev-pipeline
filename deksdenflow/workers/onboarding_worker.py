from pathlib import Path
from typing import Optional

from deksdenflow.domain import ProtocolStatus
from deksdenflow.logging import get_logger, log_extra
from deksdenflow.project_setup import ensure_assets
from deksdenflow.storage import BaseDatabase

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
    db.append_event(protocol_run_id, "setup_started", f"Onboarding {project.name}")

    try:
        repo_path = Path(project.git_url)
        if repo_path.exists():
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
        else:
            db.append_event(
                protocol_run_id,
                "setup_pending_clone",
                f"Repo path {project.git_url} not present locally. Clone before running setup.",
            )
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
