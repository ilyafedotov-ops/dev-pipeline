from fastapi import HTTPException

from devgodzilla.db.database import Database
from devgodzilla.logging import get_logger

logger = get_logger(__name__)


def get_project_or_404(db: Database, project_id: int):
    try:
        return db.get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


def get_local_project_or_400(db: Database, project_id: int):
    project = get_project_or_404(db, project_id)
    if not project.local_path:
        raise HTTPException(status_code=400, detail="Project has no local path")
    return project
