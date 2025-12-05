import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .domain import Event, Project, ProtocolRun, StepRun

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    git_url TEXT NOT NULL,
    base_branch TEXT NOT NULL,
    ci_provider TEXT,
    secrets TEXT,
    default_models TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS protocol_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    protocol_name TEXT NOT NULL,
    status TEXT NOT NULL,
    base_branch TEXT NOT NULL,
    worktree_path TEXT,
    protocol_root TEXT,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS step_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    protocol_run_id INTEGER NOT NULL REFERENCES protocol_runs(id),
    step_index INTEGER NOT NULL,
    step_name TEXT NOT NULL,
    step_type TEXT NOT NULL,
    status TEXT NOT NULL,
    retries INTEGER DEFAULT 0,
    model TEXT,
    summary TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    protocol_run_id INTEGER NOT NULL REFERENCES protocol_runs(id),
    step_run_id INTEGER REFERENCES step_runs(id),
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    """
    Lightweight SQLite-backed persistence for orchestrator state.
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    def _fetchone(self, query: str, params: Iterable[Any]) -> Optional[sqlite3.Row]:
        with self._connect() as conn:
            cur = conn.execute(query, params)
            row = cur.fetchone()
        return row

    def _fetchall(self, query: str, params: Iterable[Any] = ()) -> List[sqlite3.Row]:
        with self._connect() as conn:
            cur = conn.execute(query, params)
            rows = cur.fetchall()
        return rows

    def create_project(
        self,
        name: str,
        git_url: str,
        base_branch: str,
        ci_provider: Optional[str],
        default_models: Optional[dict],
        secrets: Optional[dict] = None,
    ) -> Project:
        default_models_json = json.dumps(default_models) if default_models else None
        secrets_json = json.dumps(secrets) if secrets else None
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO projects (name, git_url, base_branch, ci_provider, default_models, secrets)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name, git_url, base_branch, ci_provider, default_models_json, secrets_json),
            )
            project_id = cur.lastrowid
            conn.commit()
        return self.get_project(project_id)

    def get_project(self, project_id: int) -> Project:
        row = self._fetchone("SELECT * FROM projects WHERE id = ?", (project_id,))
        if row is None:
            raise KeyError(f"Project {project_id} not found")
        return self._row_to_project(row)

    def list_projects(self) -> List[Project]:
        rows = self._fetchall("SELECT * FROM projects ORDER BY created_at DESC")
        return [self._row_to_project(row) for row in rows]

    def create_protocol_run(
        self,
        project_id: int,
        protocol_name: str,
        status: str,
        base_branch: str,
        worktree_path: Optional[str],
        protocol_root: Optional[str],
        description: Optional[str],
    ) -> ProtocolRun:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO protocol_runs (project_id, protocol_name, status, base_branch, worktree_path, protocol_root, description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    protocol_name,
                    status,
                    base_branch,
                    worktree_path,
                    protocol_root,
                    description,
                ),
            )
            run_id = cur.lastrowid
            conn.commit()
        return self.get_protocol_run(run_id)

    def get_protocol_run(self, run_id: int) -> ProtocolRun:
        row = self._fetchone("SELECT * FROM protocol_runs WHERE id = ?", (run_id,))
        if row is None:
            raise KeyError(f"ProtocolRun {run_id} not found")
        return self._row_to_protocol(row)

    def find_protocol_run_by_name(self, protocol_name: str) -> Optional[ProtocolRun]:
        row = self._fetchone("SELECT * FROM protocol_runs WHERE protocol_name = ?", (protocol_name,))
        return self._row_to_protocol(row) if row else None

    def find_protocol_run_by_branch(self, branch: str) -> Optional[ProtocolRun]:
        """
        Attempt to locate a protocol run based on branch/ref naming (NNNN-<task>).
        """
        ref = branch.replace("refs/heads/", "").replace("refs/tags/", "")
        ref = ref.split("/")[-1]
        row = self._fetchone(
            "SELECT * FROM protocol_runs WHERE protocol_name = ? OR base_branch = ?",
            (ref, ref),
        )
        if row:
            return self._row_to_protocol(row)
        return self.find_protocol_run_by_name(ref)

    def list_protocol_runs(self, project_id: int) -> List[ProtocolRun]:
        rows = self._fetchall(
            "SELECT * FROM protocol_runs WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        )
        return [self._row_to_protocol(row) for row in rows]

    def update_protocol_status(self, run_id: int, status: str) -> ProtocolRun:
        with self._connect() as conn:
            conn.execute(
                "UPDATE protocol_runs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, run_id),
            )
            conn.commit()
        return self.get_protocol_run(run_id)

    def create_step_run(
        self,
        protocol_run_id: int,
        step_index: int,
        step_name: str,
        step_type: str,
        status: str,
        model: Optional[str],
        summary: Optional[str] = None,
    ) -> StepRun:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO step_runs (protocol_run_id, step_index, step_name, step_type, status, model, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    protocol_run_id,
                    step_index,
                    step_name,
                    step_type,
                    status,
                    model,
                    summary,
                ),
            )
            step_id = cur.lastrowid
            conn.commit()
        return self.get_step_run(step_id)

    def get_step_run(self, step_id: int) -> StepRun:
        row = self._fetchone("SELECT * FROM step_runs WHERE id = ?", (step_id,))
        if row is None:
            raise KeyError(f"StepRun {step_id} not found")
        return self._row_to_step(row)

    def list_step_runs(self, protocol_run_id: int) -> List[StepRun]:
        rows = self._fetchall(
            "SELECT * FROM step_runs WHERE protocol_run_id = ? ORDER BY step_index ASC",
            (protocol_run_id,),
        )
        return [self._row_to_step(row) for row in rows]

    def latest_step_run(self, protocol_run_id: int) -> Optional[StepRun]:
        row = self._fetchone(
            "SELECT * FROM step_runs WHERE protocol_run_id = ? ORDER BY updated_at DESC, created_at DESC LIMIT 1",
            (protocol_run_id,),
        )
        return self._row_to_step(row) if row else None

    def update_step_status(self, step_id: int, status: str, summary: Optional[str] = None) -> StepRun:
        with self._connect() as conn:
            conn.execute(
                "UPDATE step_runs SET status = ?, summary = COALESCE(?, summary), updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, summary, step_id),
            )
            conn.commit()
        return self.get_step_run(step_id)

    def append_event(
        self,
        protocol_run_id: int,
        event_type: str,
        message: str,
        step_run_id: Optional[int] = None,
    ) -> Event:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO events (protocol_run_id, step_run_id, event_type, message)
                VALUES (?, ?, ?, ?)
                """,
                (protocol_run_id, step_run_id, event_type, message),
            )
            event_id = cur.lastrowid
            conn.commit()
        row = self._fetchone("SELECT * FROM events WHERE id = ?", (event_id,))
        return self._row_to_event(row)  # type: ignore[arg-type]

    def list_events(self, protocol_run_id: int) -> List[Event]:
        rows = self._fetchall(
            "SELECT * FROM events WHERE protocol_run_id = ? ORDER BY created_at DESC",
            (protocol_run_id,),
        )
        return [self._row_to_event(row) for row in rows]

    @staticmethod
    def _row_to_project(row: sqlite3.Row) -> Project:
        default_models = json.loads(row["default_models"]) if row["default_models"] else None
        secrets = json.loads(row["secrets"]) if row["secrets"] else None
        return Project(
            id=row["id"],
            name=row["name"],
            git_url=row["git_url"],
            base_branch=row["base_branch"],
            ci_provider=row["ci_provider"],
            secrets=secrets,
            default_models=default_models,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_protocol(row: sqlite3.Row) -> ProtocolRun:
        return ProtocolRun(
            id=row["id"],
            project_id=row["project_id"],
            protocol_name=row["protocol_name"],
            status=row["status"],
            base_branch=row["base_branch"],
            worktree_path=row["worktree_path"],
            protocol_root=row["protocol_root"],
            description=row["description"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_step(row: sqlite3.Row) -> StepRun:
        return StepRun(
            id=row["id"],
            protocol_run_id=row["protocol_run_id"],
            step_index=row["step_index"],
            step_name=row["step_name"],
            step_type=row["step_type"],
            status=row["status"],
            retries=row["retries"],
            model=row["model"],
            summary=row["summary"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> Event:
        return Event(
            id=row["id"],
            protocol_run_id=row["protocol_run_id"],
            step_run_id=row["step_run_id"],
            event_type=row["event_type"],
            message=row["message"],
            created_at=row["created_at"],
        )
