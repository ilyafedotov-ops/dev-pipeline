import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Protocol

from tasksgodzilla.logging import get_logger

try:  # Optional Postgres support
    import psycopg
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool
except ImportError:  # pragma: no cover - Postgres optional
    psycopg = None  # type: ignore
    dict_row = None  # type: ignore
    ConnectionPool = None  # type: ignore

from .domain import Event, Project, ProtocolRun, StepRun

SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    git_url TEXT NOT NULL,
    base_branch TEXT NOT NULL,
    local_path TEXT,
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
    template_config TEXT,
    template_source TEXT,
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
    engine_id TEXT,
    policy TEXT,
    runtime_state TEXT,
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
    metadata TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

SCHEMA_POSTGRES = """
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    git_url TEXT NOT NULL,
    local_path TEXT,
    base_branch TEXT NOT NULL,
    ci_provider TEXT,
    secrets JSONB,
    default_models JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS protocol_runs (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    protocol_name TEXT NOT NULL,
    status TEXT NOT NULL,
    base_branch TEXT NOT NULL,
    worktree_path TEXT,
    protocol_root TEXT,
    description TEXT,
    template_config JSONB,
    template_source JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS step_runs (
    id SERIAL PRIMARY KEY,
    protocol_run_id INTEGER NOT NULL REFERENCES protocol_runs(id),
    step_index INTEGER NOT NULL,
    step_name TEXT NOT NULL,
    step_type TEXT NOT NULL,
    status TEXT NOT NULL,
    retries INTEGER DEFAULT 0,
    model TEXT,
    engine_id TEXT,
    policy JSONB,
    runtime_state JSONB,
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    protocol_run_id INTEGER NOT NULL REFERENCES protocol_runs(id),
    step_run_id INTEGER REFERENCES step_runs(id),
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class BaseDatabase(Protocol):
    def init_schema(self) -> None: ...
    def create_project(self, name: str, git_url: str, base_branch: str, ci_provider: Optional[str], default_models: Optional[dict], secrets: Optional[dict] = None, local_path: Optional[str] = None) -> Project: ...
    def update_project_local_path(self, project_id: int, local_path: str) -> Project: ...
    def get_project(self, project_id: int) -> Project: ...
    def list_projects(self) -> List[Project]: ...
    def create_protocol_run(self, project_id: int, protocol_name: str, status: str, base_branch: str, worktree_path: Optional[str], protocol_root: Optional[str], description: Optional[str], template_config: Optional[dict] = None, template_source: Optional[dict] = None) -> ProtocolRun: ...
    def update_protocol_paths(self, run_id: int, worktree_path: Optional[str], protocol_root: Optional[str]) -> ProtocolRun: ...
    def update_protocol_template(self, run_id: int, template_config: Optional[dict], template_source: Optional[dict]) -> ProtocolRun: ...
    def get_protocol_run(self, run_id: int) -> ProtocolRun: ...
    def find_protocol_run_by_name(self, protocol_name: str) -> Optional[ProtocolRun]: ...
    def find_protocol_run_by_branch(self, branch: str) -> Optional[ProtocolRun]: ...
    def list_protocol_runs(self, project_id: int) -> List[ProtocolRun]: ...
    def update_protocol_status(self, run_id: int, status: str, expected_status: Optional[str] = None) -> ProtocolRun: ...
    def create_step_run(self, protocol_run_id: int, step_index: int, step_name: str, step_type: str, status: str, model: Optional[str] = None, engine_id: Optional[str] = None, retries: int = 0, summary: Optional[str] = None, policy: Optional[dict] = None) -> StepRun: ...
    def get_step_run(self, step_run_id: int) -> StepRun: ...
    def list_step_runs(self, protocol_run_id: int) -> List[StepRun]: ...
    def latest_step_run(self, protocol_run_id: int) -> Optional[StepRun]: ...
    def update_step_status(self, step_run_id: int, status: str, retries: Optional[int] = None, summary: Optional[str] = None, model: Optional[str] = None, engine_id: Optional[str] = None, runtime_state: Optional[dict] = None, expected_status: Optional[str] = None) -> StepRun: ...
    def append_event(self, protocol_run_id: int, event_type: str, message: str, metadata: Optional[Dict[str, Any]] = None, step_run_id: Optional[int] = None, request_id: Optional[str] = None, job_id: Optional[str] = None) -> Event: ...
    def list_events(self, protocol_run_id: int) -> List[Event]: ...
    def list_recent_events(self, limit: int = 50, project_id: Optional[int] = None) -> List[Event]: ...


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
            conn.executescript(SCHEMA_SQLITE)
            # Backward-compatible migration: add local_path column if missing
            cur = conn.execute("PRAGMA table_info(projects)")
            cols = [r[1] for r in cur.fetchall()]
            if "local_path" not in cols:
                conn.execute("ALTER TABLE projects ADD COLUMN local_path TEXT")
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
        local_path: Optional[str] = None,
    ) -> Project:
        default_models_json = json.dumps(default_models) if default_models else None
        secrets_json = json.dumps(secrets) if secrets else None
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO projects (name, git_url, base_branch, ci_provider, default_models, secrets, local_path)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (name, git_url, base_branch, ci_provider, default_models_json, secrets_json, local_path),
            )
            project_id = cur.lastrowid
            conn.commit()
        return self.get_project(project_id)

    def get_project(self, project_id: int) -> Project:
        row = self._fetchone("SELECT * FROM projects WHERE id = ?", (project_id,))
        if row is None:
            raise KeyError(f"Project {project_id} not found")
        return self._row_to_project(row)

    def update_project_local_path(self, project_id: int, local_path: str) -> Project:
        with self._connect() as conn:
            conn.execute(
                "UPDATE projects SET local_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (local_path, project_id),
            )
            conn.commit()
        return self.get_project(project_id)

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
        template_config: Optional[dict] = None,
        template_source: Optional[dict] = None,
    ) -> ProtocolRun:
        template_config_json = json.dumps(template_config) if template_config is not None else None
        template_source_json = json.dumps(template_source) if template_source is not None else None
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO protocol_runs (project_id, protocol_name, status, base_branch, worktree_path, protocol_root, description, template_config, template_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    protocol_name,
                    status,
                    base_branch,
                    worktree_path,
                    protocol_root,
                    description,
                    template_config_json,
                    template_source_json,
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

    def update_protocol_paths(self, run_id: int, worktree_path: Optional[str], protocol_root: Optional[str]) -> ProtocolRun:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE protocol_runs
                SET worktree_path = ?, protocol_root = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (worktree_path, protocol_root, run_id),
            )
        conn.commit()
        return self.get_protocol_run(run_id)

    def update_protocol_template(self, run_id: int, template_config: Optional[dict], template_source: Optional[dict]) -> ProtocolRun:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE protocol_runs
                SET template_config = ?, template_source = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    json.dumps(template_config) if template_config is not None else None,
                    json.dumps(template_source) if template_source is not None else None,
                    run_id,
                ),
            )
            conn.commit()
        return self.get_protocol_run(run_id)

    def find_protocol_run_by_name(self, protocol_name: str) -> Optional[ProtocolRun]:
        row = self._fetchone("SELECT * FROM protocol_runs WHERE protocol_name = ?", (protocol_name,))
        return self._row_to_protocol(row) if row else None

    def find_protocol_run_by_branch(self, branch: str) -> Optional[ProtocolRun]:
        """
        Attempt to locate a protocol run based on branch/ref naming (NNNN-<task>).
        """
        ref = branch.replace("refs/heads/", "").replace("refs/tags/", "")
        parts = ref.split("/")
        # Prefer last segment; also try full ref
        candidates = [ref, parts[-1]]
        for cand in candidates:
            row = self._fetchone("SELECT * FROM protocol_runs WHERE protocol_name = ?", (cand,))
            if row:
                return self._row_to_protocol(row)
        return None

    def list_protocol_runs(self, project_id: int) -> List[ProtocolRun]:
        rows = self._fetchall(
            "SELECT * FROM protocol_runs WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        )
        return [self._row_to_protocol(row) for row in rows]

    def update_protocol_status(self, run_id: int, status: str, expected_status: Optional[str] = None) -> ProtocolRun:
        with self._connect() as conn:
            if expected_status:
                cur = conn.execute(
                    "UPDATE protocol_runs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = ?",
                    (status, run_id, expected_status),
                )
                if cur.rowcount == 0:
                    raise ValueError(f"ProtocolRun {run_id} status conflict")
            else:
                conn.execute(
                    "UPDATE protocol_runs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (status, run_id),
                )
            conn.commit()
        run = self.get_protocol_run(run_id)
        log = get_logger(__name__)
        log.info("protocol_status_updated", extra={"protocol_run_id": run_id, "status": status})
        return run

    def create_step_run(
        self,
        protocol_run_id: int,
        step_index: int,
        step_name: str,
        step_type: str,
        status: str,
        model: Optional[str],
        engine_id: Optional[str] = None,
        retries: int = 0,
        summary: Optional[str] = None,
        policy: Optional[dict] = None,
    ) -> StepRun:
        policy_json = json.dumps(policy) if policy is not None else None
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO step_runs (protocol_run_id, step_index, step_name, step_type, status, model, engine_id, policy, runtime_state, summary, retries)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    protocol_run_id,
                    step_index,
                    step_name,
                    step_type,
                    status,
                    model,
                    engine_id,
                    policy_json,
                    None,
                    summary,
                    retries,
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

    def update_step_status(
        self,
        step_id: int,
        status: str,
        retries: Optional[int] = None,
        summary: Optional[str] = None,
        model: Optional[str] = None,
        engine_id: Optional[str] = None,
        runtime_state: Optional[dict] = None,
        expected_status: Optional[str] = None,
    ) -> StepRun:
        runtime_state_json = json.dumps(runtime_state) if runtime_state is not None else None
        with self._connect() as conn:
            if expected_status:
                cur = conn.execute(
                    """
                    UPDATE step_runs
                    SET status = ?,
                        summary = COALESCE(?, summary),
                        model = COALESCE(?, model),
                        engine_id = COALESCE(?, engine_id),
                        runtime_state = COALESCE(?, runtime_state),
                        retries = COALESCE(?, retries),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND status = ?
                    """,
                    (status, summary, model, engine_id, runtime_state_json, retries, step_id, expected_status),
                )
                if cur.rowcount == 0:
                    raise ValueError(f"StepRun {step_id} status conflict")
            else:
                conn.execute(
                    """
                    UPDATE step_runs
                    SET status = ?,
                        summary = COALESCE(?, summary),
                        model = COALESCE(?, model),
                        engine_id = COALESCE(?, engine_id),
                        runtime_state = COALESCE(?, runtime_state),
                        retries = COALESCE(?, retries),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (status, summary, model, engine_id, runtime_state_json, retries, step_id),
                )
            conn.commit()
        step = self.get_step_run(step_id)
        log = get_logger(__name__)
        log.info(
            "step_status_updated",
            extra={"step_run_id": step_id, "protocol_run_id": step.protocol_run_id, "status": status},
        )
        return step

    def append_event(
        self,
        protocol_run_id: int,
        event_type: str,
        message: str,
        step_run_id: Optional[int] = None,
        metadata: Optional[dict] = None,
        request_id: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> Event:
        meta = dict(metadata or {})
        if request_id and "request_id" not in meta:
            meta["request_id"] = request_id
        if job_id and "job_id" not in meta:
            meta["job_id"] = job_id
        metadata_json = json.dumps(meta) if meta else None
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO events (protocol_run_id, step_run_id, event_type, message, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (protocol_run_id, step_run_id, event_type, message, metadata_json),
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

    def list_recent_events(self, limit: int = 50, project_id: Optional[int] = None) -> List[Event]:
        """
        Return recent events across projects, newest first. Includes protocol/project context for console views.
        """
        limit = max(1, min(int(limit), 500))
        base = """
        SELECT e.*, pr.protocol_name, pr.project_id, p.name AS project_name
        FROM events e
        JOIN protocol_runs pr ON e.protocol_run_id = pr.id
        JOIN projects p ON pr.project_id = p.id
        """
        params: list[Any] = []
        if project_id is not None:
            base += " WHERE pr.project_id = ?"
            params.append(project_id)
        base += " ORDER BY e.created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._fetchall(base, tuple(params))
        return [self._row_to_event(row) for row in rows]

    @staticmethod
    def _parse_json(value: Any) -> Optional[dict]:
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value  # already decoded
        try:
            return json.loads(value)
        except Exception:
            return None

    @staticmethod
    def _coerce_ts(value: Any) -> Any:
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                return str(value)
        return value

    @staticmethod
    def _row_to_project(row: Any) -> Project:
        default_models = Database._parse_json(row["default_models"])
        secrets = Database._parse_json(row["secrets"])
        return Project(
            id=row["id"],
            name=row["name"],
            git_url=row["git_url"],
            local_path=row["local_path"] if "local_path" in set(row.keys()) else None,
            base_branch=row["base_branch"],
            ci_provider=row["ci_provider"],
            secrets=secrets,
            default_models=default_models,
            created_at=Database._coerce_ts(row["created_at"]),
            updated_at=Database._coerce_ts(row["updated_at"]),
        )

    @staticmethod
    def _row_to_protocol(row: Any) -> ProtocolRun:
        template_config = Database._parse_json(row["template_config"]) if "template_config" in set(row.keys()) else None  # type: ignore[arg-type]
        template_source = Database._parse_json(row["template_source"]) if "template_source" in set(row.keys()) else None  # type: ignore[arg-type]
        return ProtocolRun(
            id=row["id"],
            project_id=row["project_id"],
            protocol_name=row["protocol_name"],
            status=row["status"],
            base_branch=row["base_branch"],
            worktree_path=row["worktree_path"],
            protocol_root=row["protocol_root"],
            description=row["description"],
            template_config=template_config,
            template_source=template_source,
            created_at=Database._coerce_ts(row["created_at"]),
            updated_at=Database._coerce_ts(row["updated_at"]),
        )

    @staticmethod
    def _row_to_step(row: Any) -> StepRun:
        keys = set(row.keys()) if hasattr(row, "keys") else set()
        policy = Database._parse_json(row["policy"]) if "policy" in keys else None
        runtime_state = Database._parse_json(row["runtime_state"]) if "runtime_state" in keys else None
        return StepRun(
            id=row["id"],
            protocol_run_id=row["protocol_run_id"],
            step_index=row["step_index"],
            step_name=row["step_name"],
            step_type=row["step_type"],
            status=row["status"],
            retries=row["retries"],
            model=row["model"],
            engine_id=row["engine_id"] if "engine_id" in keys else None,
            policy=policy,
            runtime_state=runtime_state,
            summary=row["summary"],
            created_at=Database._coerce_ts(row["created_at"]),
            updated_at=Database._coerce_ts(row["updated_at"]),
        )

    @staticmethod
    def _row_to_event(row: Any) -> Event:
        protocol_name = None
        project_id = None
        project_name = None
        if isinstance(row, dict):
            protocol_name = row.get("protocol_name")
            project_id = row.get("project_id")
            project_name = row.get("project_name")
        elif hasattr(row, "keys"):
            keys = set(row.keys())
            if "protocol_name" in keys:
                protocol_name = row["protocol_name"]
            if "project_id" in keys:
                project_id = row["project_id"]
            if "project_name" in keys:
                project_name = row["project_name"]
        return Event(
            id=row["id"],
            protocol_run_id=row["protocol_run_id"],
            step_run_id=row["step_run_id"],
            event_type=row["event_type"],
            message=row["message"],
            metadata=Database._parse_json(row.get("metadata") if isinstance(row, dict) else row["metadata"]),
            created_at=Database._coerce_ts(row["created_at"]),
            protocol_name=protocol_name,
            project_id=project_id,
            project_name=project_name,
        )


class PostgresDatabase:
    """
    Postgres-backed persistence for orchestrator state.
    Requires psycopg>=3. Follows the same contract as the SQLite Database class.
    """

    def __init__(self, db_url: str, pool_size: int = 5):
        if psycopg is None:  # pragma: no cover - optional dependency
            raise ImportError("psycopg is required for Postgres support. Install psycopg[binary].")
        self.db_url = db_url
        self.row_factory = dict_row
        self.pool = None
        if ConnectionPool:
            # Ensure we always get dicts back from cursors when using pooled connections.
            self.pool = ConnectionPool(
                conninfo=db_url,
                min_size=1,
                max_size=pool_size,
                kwargs={"row_factory": self.row_factory},
            )

    def _connect(self):
        if self.pool:
            conn = self.pool.connection()
        else:
            conn = psycopg.connect(self.db_url, row_factory=self.row_factory)
        # Defensive: pool connections should already have the row factory set via kwargs,
        # but set it here to be sure.
        if self.row_factory is not None:
            conn.row_factory = self.row_factory
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA_POSTGRES)
                try:
                    cur.execute(
                        "SELECT column_name FROM information_schema.columns WHERE table_name='projects' AND column_name='local_path'"
                    )
                    if not cur.fetchone():
                        cur.execute("ALTER TABLE projects ADD COLUMN local_path TEXT")
                except Exception:
                    pass
            conn.commit()

    def _fetchone(self, query: str, params: Iterable[Any]) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                row = cur.fetchone()
        return row

    def _fetchall(self, query: str, params: Iterable[Any] = ()) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
        return rows or []

    def create_project(
        self,
        name: str,
        git_url: str,
        base_branch: str,
        ci_provider: Optional[str],
        default_models: Optional[dict],
        secrets: Optional[dict] = None,
        local_path: Optional[str] = None,
    ) -> Project:
        with self._connect() as conn:
            with conn.cursor() as cur:
                default_models_json = json.dumps(default_models) if default_models is not None else None
                secrets_json = json.dumps(secrets) if secrets is not None else None
                cur.execute(
                    """
                    INSERT INTO projects (name, git_url, base_branch, ci_provider, default_models, secrets, local_path)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (name, git_url, base_branch, ci_provider, default_models_json, secrets_json, local_path),
                )
                project_id = cur.fetchone()["id"]
            conn.commit()
        return self.get_project(project_id)

    def update_project_local_path(self, project_id: int, local_path: str) -> Project:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE projects SET local_path = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (local_path, project_id),
                )
            conn.commit()
        return self.get_project(project_id)

    def get_project(self, project_id: int) -> Project:
        row = self._fetchone("SELECT * FROM projects WHERE id = %s", (project_id,))
        if row is None:
            raise KeyError(f"Project {project_id} not found")
        return Database._row_to_project(row)  # type: ignore[arg-type]

    def list_projects(self) -> List[Project]:
        rows = self._fetchall("SELECT * FROM projects ORDER BY created_at DESC")
        return [Database._row_to_project(row) for row in rows]  # type: ignore[arg-type]

    def create_protocol_run(
        self,
        project_id: int,
        protocol_name: str,
        status: str,
        base_branch: str,
        worktree_path: Optional[str],
        protocol_root: Optional[str],
        description: Optional[str],
        template_config: Optional[dict] = None,
        template_source: Optional[dict] = None,
    ) -> ProtocolRun:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO protocol_runs (project_id, protocol_name, status, base_branch, worktree_path, protocol_root, description, template_config, template_source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        project_id,
                        protocol_name,
                        status,
                        base_branch,
                        worktree_path,
                        protocol_root,
                        description,
                        json.dumps(template_config) if template_config is not None else None,
                        json.dumps(template_source) if template_source is not None else None,
                    ),
                )
                run_id = cur.fetchone()["id"]
            conn.commit()
        return self.get_protocol_run(run_id)

    def get_protocol_run(self, run_id: int) -> ProtocolRun:
        row = self._fetchone("SELECT * FROM protocol_runs WHERE id = %s", (run_id,))
        if row is None:
            raise KeyError(f"ProtocolRun {run_id} not found")
        return Database._row_to_protocol(row)  # type: ignore[arg-type]

    def find_protocol_run_by_name(self, protocol_name: str) -> Optional[ProtocolRun]:
        row = self._fetchone("SELECT * FROM protocol_runs WHERE protocol_name = %s", (protocol_name,))
        return Database._row_to_protocol(row) if row else None  # type: ignore[arg-type]

    def find_protocol_run_by_branch(self, branch: str) -> Optional[ProtocolRun]:
        ref = branch.replace("refs/heads/", "").replace("refs/tags/", "")
        parts = ref.split("/")
        candidates = [ref, parts[-1]]
        for cand in candidates:
            row = self._fetchone("SELECT * FROM protocol_runs WHERE protocol_name = %s", (cand,))
            if row:
                return Database._row_to_protocol(row)  # type: ignore[arg-type]
        return None

    def list_protocol_runs(self, project_id: int) -> List[ProtocolRun]:
        rows = self._fetchall(
            "SELECT * FROM protocol_runs WHERE project_id = %s ORDER BY created_at DESC",
            (project_id,),
        )
        return [Database._row_to_protocol(row) for row in rows]  # type: ignore[arg-type]

    def update_protocol_status(self, run_id: int, status: str, expected_status: Optional[str] = None) -> ProtocolRun:
        with self._connect() as conn:
            with conn.cursor() as cur:
                if expected_status:
                    cur.execute(
                        "UPDATE protocol_runs SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND status = %s",
                        (status, run_id, expected_status),
                    )
                    if cur.rowcount == 0:
                        raise ValueError(f"ProtocolRun {run_id} status conflict")
                else:
                    cur.execute(
                        "UPDATE protocol_runs SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                        (status, run_id),
                    )
        conn.commit()
        return self.get_protocol_run(run_id)

    def update_protocol_template(self, run_id: int, template_config: Optional[dict], template_source: Optional[dict]) -> ProtocolRun:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE protocol_runs
                    SET template_config = %s, template_source = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (
                        json.dumps(template_config) if template_config is not None else None,
                        json.dumps(template_source) if template_source is not None else None,
                        run_id,
                    ),
                )
            conn.commit()
        return self.get_protocol_run(run_id)

    def update_protocol_paths(self, run_id: int, worktree_path: Optional[str], protocol_root: Optional[str]) -> ProtocolRun:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE protocol_runs
                    SET worktree_path = %s, protocol_root = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (worktree_path, protocol_root, run_id),
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
        engine_id: Optional[str] = None,
        retries: int = 0,
        summary: Optional[str] = None,
        policy: Optional[dict] = None,
    ) -> StepRun:
        policy_json = json.dumps(policy) if policy is not None else None
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO step_runs (protocol_run_id, step_index, step_name, step_type, status, model, engine_id, policy, runtime_state, summary, retries)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        protocol_run_id,
                        step_index,
                        step_name,
                        step_type,
                        status,
                        model,
                        engine_id,
                        policy_json,
                        None,
                        summary,
                        retries,
                    ),
                )
                step_id = cur.fetchone()["id"]
            conn.commit()
        return self.get_step_run(step_id)

    def get_step_run(self, step_id: int) -> StepRun:
        row = self._fetchone("SELECT * FROM step_runs WHERE id = %s", (step_id,))
        if row is None:
            raise KeyError(f"StepRun {step_id} not found")
        return Database._row_to_step(row)  # type: ignore[arg-type]

    def list_step_runs(self, protocol_run_id: int) -> List[StepRun]:
        rows = self._fetchall(
            "SELECT * FROM step_runs WHERE protocol_run_id = %s ORDER BY step_index ASC",
            (protocol_run_id,),
        )
        return [Database._row_to_step(row) for row in rows]  # type: ignore[arg-type]

    def latest_step_run(self, protocol_run_id: int) -> Optional[StepRun]:
        row = self._fetchone(
            "SELECT * FROM step_runs WHERE protocol_run_id = %s ORDER BY updated_at DESC, created_at DESC LIMIT 1",
            (protocol_run_id,),
        )
        return Database._row_to_step(row) if row else None  # type: ignore[arg-type]

    def update_step_status(
        self,
        step_id: int,
        status: str,
        retries: Optional[int] = None,
        summary: Optional[str] = None,
        model: Optional[str] = None,
        engine_id: Optional[str] = None,
        runtime_state: Optional[dict] = None,
        expected_status: Optional[str] = None,
    ) -> StepRun:
        runtime_state_json = json.dumps(runtime_state) if runtime_state is not None else None
        with self._connect() as conn:
            with conn.cursor() as cur:
                if expected_status:
                    cur.execute(
                        """
                        UPDATE step_runs
                        SET status = %s,
                            summary = COALESCE(%s, summary),
                            model = COALESCE(%s, model),
                            engine_id = COALESCE(%s, engine_id),
                            runtime_state = COALESCE(%s, runtime_state),
                            retries = COALESCE(%s, retries),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s AND status = %s
                        """,
                        (status, summary, model, engine_id, runtime_state_json, retries, step_id, expected_status),
                    )
                    if cur.rowcount == 0:
                        raise ValueError(f"StepRun {step_id} status conflict")
                else:
                    cur.execute(
                        """
                        UPDATE step_runs
                        SET status = %s,
                            summary = COALESCE(%s, summary),
                            model = COALESCE(%s, model),
                            engine_id = COALESCE(%s, engine_id),
                            runtime_state = COALESCE(%s, runtime_state),
                            retries = COALESCE(%s, retries),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        (status, summary, model, engine_id, runtime_state_json, retries, step_id),
                    )
            conn.commit()
        return self.get_step_run(step_id)

    def append_event(
        self,
        protocol_run_id: int,
        event_type: str,
        message: str,
        step_run_id: Optional[int] = None,
        metadata: Optional[dict] = None,
        request_id: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> Event:
        meta = dict(metadata or {})
        if request_id and "request_id" not in meta:
            meta["request_id"] = request_id
        if job_id and "job_id" not in meta:
            meta["job_id"] = job_id
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO events (protocol_run_id, step_run_id, event_type, message, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (protocol_run_id, step_run_id, event_type, message, json.dumps(meta) if meta else None),
                )
                event_id = cur.fetchone()["id"]
            conn.commit()
        row = self._fetchone("SELECT * FROM events WHERE id = %s", (event_id,))
        return Database._row_to_event(row)  # type: ignore[arg-type]

    def list_events(self, protocol_run_id: int) -> List[Event]:
        rows = self._fetchall(
            "SELECT * FROM events WHERE protocol_run_id = %s ORDER BY created_at DESC",
            (protocol_run_id,),
        )
        return [Database._row_to_event(row) for row in rows]  # type: ignore[arg-type]

    def list_recent_events(self, limit: int = 50, project_id: Optional[int] = None) -> List[Event]:
        limit = max(1, min(int(limit), 500))
        base = """
        SELECT e.*, pr.protocol_name, pr.project_id, p.name AS project_name
        FROM events e
        JOIN protocol_runs pr ON e.protocol_run_id = pr.id
        JOIN projects p ON pr.project_id = p.id
        """
        params: list[Any] = []
        if project_id is not None:
            base += " WHERE pr.project_id = %s"
            params.append(project_id)
        base += " ORDER BY e.created_at DESC LIMIT %s"
        params.append(limit)
        rows = self._fetchall(base, tuple(params))
        return [Database._row_to_event(row) for row in rows]  # type: ignore[arg-type]


def create_database(db_path: Path, db_url: Optional[str] = None, pool_size: int = 5) -> BaseDatabase:
    """
    Factory to select the backing store. Defaults to SQLite; accepts a Postgres URL
    to allow future migrations without changing callers.
    """
    if db_url and db_url.startswith("postgres"):
        return PostgresDatabase(db_url, pool_size=pool_size)
    return Database(db_path)
