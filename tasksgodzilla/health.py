from dataclasses import dataclass
from typing import Literal, Optional

from tasksgodzilla.storage import BaseDatabase, Database, PostgresDatabase

Status = Literal["ok", "degraded", "error"]


@dataclass
class DBStatus:
    status: Status
    backend: str
    detail: Optional[str] = None


def check_db(db: BaseDatabase) -> DBStatus:
    backend = "postgres" if isinstance(db, PostgresDatabase) else "sqlite"
    try:
        # minimal probe: list projects count
        _ = db.list_projects()
        return DBStatus(status="ok", backend=backend)
    except Exception as exc:
        return DBStatus(status="error", backend=backend, detail=str(exc))
