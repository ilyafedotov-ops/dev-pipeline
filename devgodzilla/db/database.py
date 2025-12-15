"""
DevGodzilla Database Service

Provides dual SQLite + PostgreSQL support with a unified interface.
Uses the Protocol pattern to define the database contract.
"""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Protocol, Union

from devgodzilla.logging import get_logger
from devgodzilla.models.domain import (
    Clarification,
    Event,
    FeedbackEvent,
    JobRun,
    PolicyPack,
    Project,
    ProtocolRun,
    RunArtifact,
    StepRun,
)

logger = get_logger(__name__)

# Try to import psycopg for PostgreSQL support
try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool
except ImportError:
    psycopg = None  # type: ignore
    dict_row = None  # type: ignore
    ConnectionPool = None  # type: ignore


# Sentinel for unset optional parameters
_UNSET = object()


class DatabaseProtocol(Protocol):
    """Protocol defining the database interface."""
    
    def init_schema(self) -> None: ...
    
    # Projects
    def create_project(
        self,
        name: str,
        git_url: str,
        base_branch: str,
        ci_provider: Optional[str] = None,
        default_models: Optional[dict] = None,
        secrets: Optional[dict] = None,
        local_path: Optional[str] = None,
        project_classification: Optional[str] = None,
        policy_pack_key: Optional[str] = None,
        policy_pack_version: Optional[str] = None,
    ) -> Project: ...
    
    def get_project(self, project_id: int) -> Project: ...
    def list_projects(self) -> List[Project]: ...
    def update_project_local_path(self, project_id: int, local_path: str) -> Project: ...
    
    # Protocol runs
    def create_protocol_run(
        self,
        project_id: int,
        protocol_name: str,
        status: str,
        base_branch: str,
        worktree_path: Optional[str] = None,
        protocol_root: Optional[str] = None,
        description: Optional[str] = None,
    ) -> ProtocolRun: ...
    
    def get_protocol_run(self, run_id: int) -> ProtocolRun: ...
    def list_protocol_runs(self, project_id: int) -> List[ProtocolRun]: ...
    def update_protocol_status(self, run_id: int, status: str) -> ProtocolRun: ...
    
    # Step runs
    def create_step_run(
        self,
        protocol_run_id: int,
        step_index: int,
        step_name: str,
        step_type: str,
        status: str,
        depends_on: Optional[List[int]] = None,
        parallel_group: Optional[str] = None,
        assigned_agent: Optional[str] = None,
    ) -> StepRun: ...
    
    def get_step_run(self, step_run_id: int) -> StepRun: ...
    def list_step_runs(self, protocol_run_id: int) -> List[StepRun]: ...
    def update_step_status(self, step_run_id: int, status: str, **kwargs) -> StepRun: ...
    
    # Events
    def append_event(
        self,
        protocol_run_id: int,
        event_type: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        step_run_id: Optional[int] = None,
    ) -> Event: ...
    
    def list_events(self, protocol_run_id: int) -> List[Event]: ...


class SQLiteDatabase:
    """
    SQLite-backed persistence for DevGodzilla state.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _transaction(self):
        """Context manager for database transactions."""
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _fetchone(self, query: str, params: Iterable[Any] = ()) -> Optional[sqlite3.Row]:
        with self._connect() as conn:
            cur = conn.execute(query, tuple(params))
            return cur.fetchone()

    def _fetchall(self, query: str, params: Iterable[Any] = ()) -> List[sqlite3.Row]:
        with self._connect() as conn:
            cur = conn.execute(query, tuple(params))
            return cur.fetchall()

    def init_schema(self) -> None:
        """Initialize database schema."""
        from devgodzilla.db.schema import SCHEMA_SQLITE
        
        with self._transaction() as conn:
            conn.executescript(SCHEMA_SQLITE)
            conn.commit()

    # Helper methods for JSON and timestamp parsing
    @staticmethod
    def _parse_json(value: Any) -> Optional[Union[dict, list]]:
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except Exception:
            return None

    @staticmethod
    def _coerce_ts(value: Any) -> str:
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                return str(value)
        return str(value) if value else ""

    # Row to model converters
    def _row_to_project(self, row: sqlite3.Row) -> Project:
        keys = set(row.keys())
        return Project(
            id=row["id"],
            name=row["name"],
            git_url=row["git_url"],
            base_branch=row["base_branch"],
            local_path=row["local_path"] if "local_path" in keys else None,
            ci_provider=row["ci_provider"],
            secrets=self._parse_json(row["secrets"]),
            default_models=self._parse_json(row["default_models"]),
            project_classification=row["project_classification"] if "project_classification" in keys else None,
            policy_pack_key=row["policy_pack_key"] if "policy_pack_key" in keys else None,
            policy_pack_version=row["policy_pack_version"] if "policy_pack_version" in keys else None,
            policy_overrides=self._parse_json(row["policy_overrides"] if "policy_overrides" in keys else None),
            policy_repo_local_enabled=bool(row["policy_repo_local_enabled"]) if "policy_repo_local_enabled" in keys and row["policy_repo_local_enabled"] is not None else None,
            policy_effective_hash=row["policy_effective_hash"] if "policy_effective_hash" in keys else None,
            policy_enforcement_mode=row["policy_enforcement_mode"] if "policy_enforcement_mode" in keys else None,
            constitution_version=row["constitution_version"] if "constitution_version" in keys else None,
            constitution_hash=row["constitution_hash"] if "constitution_hash" in keys else None,
            created_at=self._coerce_ts(row["created_at"]),
            updated_at=self._coerce_ts(row["updated_at"]),
        )

    def _row_to_protocol_run(self, row: sqlite3.Row) -> ProtocolRun:
        keys = set(row.keys())
        return ProtocolRun(
            id=row["id"],
            project_id=row["project_id"],
            protocol_name=row["protocol_name"],
            status=row["status"],
            base_branch=row["base_branch"],
            worktree_path=row["worktree_path"],
            protocol_root=row["protocol_root"],
            description=row["description"],
            template_config=self._parse_json(row["template_config"] if "template_config" in keys else None),
            template_source=self._parse_json(row["template_source"] if "template_source" in keys else None),
            policy_pack_key=row["policy_pack_key"] if "policy_pack_key" in keys else None,
            policy_pack_version=row["policy_pack_version"] if "policy_pack_version" in keys else None,
            policy_effective_hash=row["policy_effective_hash"] if "policy_effective_hash" in keys else None,
            policy_effective_json=self._parse_json(row["policy_effective_json"] if "policy_effective_json" in keys else None),
            windmill_flow_id=row["windmill_flow_id"] if "windmill_flow_id" in keys else None,
            speckit_metadata=self._parse_json(row["speckit_metadata"] if "speckit_metadata" in keys else None),
            created_at=self._coerce_ts(row["created_at"]),
            updated_at=self._coerce_ts(row["updated_at"]),
        )

    def _row_to_step_run(self, row: sqlite3.Row) -> StepRun:
        keys = set(row.keys())
        depends_on = self._parse_json(row["depends_on"] if "depends_on" in keys else "[]") or []
        return StepRun(
            id=row["id"],
            protocol_run_id=row["protocol_run_id"],
            step_index=row["step_index"],
            step_name=row["step_name"],
            step_type=row["step_type"],
            status=row["status"],
            retries=row["retries"] or 0,
            model=row["model"],
            engine_id=row["engine_id"],
            policy=self._parse_json(row["policy"] if "policy" in keys else None),
            runtime_state=self._parse_json(row["runtime_state"] if "runtime_state" in keys else None),
            summary=row["summary"],
            depends_on=depends_on if isinstance(depends_on, list) else [],
            parallel_group=row["parallel_group"] if "parallel_group" in keys else None,
            assigned_agent=row["assigned_agent"] if "assigned_agent" in keys else None,
            created_at=self._coerce_ts(row["created_at"]),
            updated_at=self._coerce_ts(row["updated_at"]),
        )

    def _row_to_event(self, row: sqlite3.Row) -> Event:
        keys = set(row.keys())
        return Event(
            id=row["id"],
            protocol_run_id=row["protocol_run_id"],
            step_run_id=row["step_run_id"],
            event_type=row["event_type"],
            message=row["message"],
            metadata=self._parse_json(row["metadata"] if "metadata" in keys else None),
            created_at=self._coerce_ts(row["created_at"]),
        )

    def _row_to_job_run(self, row: sqlite3.Row) -> JobRun:
        keys = set(row.keys())
        return JobRun(
            run_id=row["run_id"],
            job_type=row["job_type"],
            status=row["status"],
            run_kind=row["run_kind"] if "run_kind" in keys else None,
            project_id=row["project_id"] if "project_id" in keys else None,
            protocol_run_id=row["protocol_run_id"] if "protocol_run_id" in keys else None,
            step_run_id=row["step_run_id"] if "step_run_id" in keys else None,
            queue=row["queue"] if "queue" in keys else None,
            attempt=row["attempt"] if "attempt" in keys else None,
            worker_id=row["worker_id"] if "worker_id" in keys else None,
            started_at=self._coerce_ts(row["started_at"]) if row.get("started_at") else None,
            finished_at=self._coerce_ts(row["finished_at"]) if row.get("finished_at") else None,
            prompt_version=row["prompt_version"] if "prompt_version" in keys else None,
            params=self._parse_json(row["params"] if "params" in keys else None),
            result=self._parse_json(row["result"] if "result" in keys else None),
            error=row["error"] if "error" in keys else None,
            log_path=row["log_path"] if "log_path" in keys else None,
            cost_tokens=row["cost_tokens"] if "cost_tokens" in keys else None,
            cost_cents=row["cost_cents"] if "cost_cents" in keys else None,
            windmill_job_id=row["windmill_job_id"] if "windmill_job_id" in keys else None,
            created_at=self._coerce_ts(row["created_at"]),
            updated_at=self._coerce_ts(row["updated_at"]),
        )

    # Project operations
    def create_project(
        self,
        name: str,
        git_url: str,
        base_branch: str,
        ci_provider: Optional[str] = None,
        default_models: Optional[dict] = None,
        secrets: Optional[dict] = None,
        local_path: Optional[str] = None,
        project_classification: Optional[str] = None,
        policy_pack_key: Optional[str] = None,
        policy_pack_version: Optional[str] = None,
    ) -> Project:
        with self._transaction() as conn:
            cur = conn.execute(
                """
                INSERT INTO projects (
                    name, git_url, base_branch, ci_provider,
                    default_models, secrets, local_path,
                    project_classification, policy_pack_key, policy_pack_version,
                    policy_enforcement_mode
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'warn')
                """,
                (
                    name, git_url, base_branch, ci_provider,
                    json.dumps(default_models) if default_models else None,
                    json.dumps(secrets) if secrets else None,
                    local_path, project_classification,
                    policy_pack_key or "default",
                    policy_pack_version or "1.0",
                ),
            )
            project_id = cur.lastrowid
        return self.get_project(project_id)

    def get_project(self, project_id: int) -> Project:
        row = self._fetchone("SELECT * FROM projects WHERE id = ?", (project_id,))
        if row is None:
            raise KeyError(f"Project {project_id} not found")
        return self._row_to_project(row)

    def list_projects(self) -> List[Project]:
        rows = self._fetchall("SELECT * FROM projects ORDER BY created_at DESC")
        return [self._row_to_project(row) for row in rows]

    def update_project_local_path(self, project_id: int, local_path: str) -> Project:
        with self._transaction() as conn:
            conn.execute(
                "UPDATE projects SET local_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (local_path, project_id),
            )
        return self.get_project(project_id)

    def update_project(
        self,
        project_id: int,
        *,
        name: Optional[str] = None,
        local_path: Optional[str] = None,
        constitution_version: Optional[str] = None,
        constitution_hash: Optional[str] = None,
    ) -> Project:
        """Update project fields."""
        updates = ["updated_at = CURRENT_TIMESTAMP"]
        params: List[Any] = []
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if local_path is not None:
            updates.append("local_path = ?")
            params.append(local_path)
        if constitution_version is not None:
            updates.append("constitution_version = ?")
            params.append(constitution_version)
        if constitution_hash is not None:
            updates.append("constitution_hash = ?")
            params.append(constitution_hash)
        params.append(project_id)
        
        with self._transaction() as conn:
            conn.execute(
                f"UPDATE projects SET {', '.join(updates)} WHERE id = ?",
                tuple(params),
            )
        return self.get_project(project_id)

    # Protocol run operations
    def create_protocol_run(
        self,
        project_id: int,
        protocol_name: str,
        status: str,
        base_branch: str,
        worktree_path: Optional[str] = None,
        protocol_root: Optional[str] = None,
        description: Optional[str] = None,
    ) -> ProtocolRun:
        with self._transaction() as conn:
            cur = conn.execute(
                """
                INSERT INTO protocol_runs (
                    project_id, protocol_name, status, base_branch,
                    worktree_path, protocol_root, description
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (project_id, protocol_name, status, base_branch, worktree_path, protocol_root, description),
            )
            run_id = cur.lastrowid
        return self.get_protocol_run(run_id)

    def get_protocol_run(self, run_id: int) -> ProtocolRun:
        row = self._fetchone("SELECT * FROM protocol_runs WHERE id = ?", (run_id,))
        if row is None:
            raise KeyError(f"ProtocolRun {run_id} not found")
        return self._row_to_protocol_run(row)

    def list_protocol_runs(self, project_id: int) -> List[ProtocolRun]:
        rows = self._fetchall(
            "SELECT * FROM protocol_runs WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        )
        return [self._row_to_protocol_run(row) for row in rows]

    def update_protocol_status(self, run_id: int, status: str) -> ProtocolRun:
        with self._transaction() as conn:
            conn.execute(
                "UPDATE protocol_runs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, run_id),
            )
        return self.get_protocol_run(run_id)

    def update_protocol_windmill(
        self,
        run_id: int,
        windmill_flow_id: Optional[str] = None,
        speckit_metadata: Optional[dict] = None,
    ) -> ProtocolRun:
        """Update Windmill-specific fields on a protocol run."""
        updates = ["updated_at = CURRENT_TIMESTAMP"]
        params: List[Any] = []
        if windmill_flow_id is not None:
            updates.append("windmill_flow_id = ?")
            params.append(windmill_flow_id)
        if speckit_metadata is not None:
            updates.append("speckit_metadata = ?")
            params.append(json.dumps(speckit_metadata))
        params.append(run_id)
        
        with self._transaction() as conn:
            conn.execute(
                f"UPDATE protocol_runs SET {', '.join(updates)} WHERE id = ?",
                tuple(params),
            )
        return self.get_protocol_run(run_id)

    # Step run operations
    def create_step_run(
        self,
        protocol_run_id: int,
        step_index: int,
        step_name: str,
        step_type: str,
        status: str,
        depends_on: Optional[List[int]] = None,
        parallel_group: Optional[str] = None,
        assigned_agent: Optional[str] = None,
    ) -> StepRun:
        with self._transaction() as conn:
            cur = conn.execute(
                """
                INSERT INTO step_runs (
                    protocol_run_id, step_index, step_name, step_type, status,
                    depends_on, parallel_group, assigned_agent
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    protocol_run_id, step_index, step_name, step_type, status,
                    json.dumps(depends_on or []), parallel_group, assigned_agent,
                ),
            )
            step_id = cur.lastrowid
        return self.get_step_run(step_id)

    def get_step_run(self, step_run_id: int) -> StepRun:
        row = self._fetchone("SELECT * FROM step_runs WHERE id = ?", (step_run_id,))
        if row is None:
            raise KeyError(f"StepRun {step_run_id} not found")
        return self._row_to_step_run(row)

    def list_step_runs(self, protocol_run_id: int) -> List[StepRun]:
        rows = self._fetchall(
            "SELECT * FROM step_runs WHERE protocol_run_id = ? ORDER BY step_index ASC",
            (protocol_run_id,),
        )
        return [self._row_to_step_run(row) for row in rows]

    def update_step_status(
        self,
        step_run_id: int,
        status: str,
        retries: Optional[int] = None,
        summary: Optional[str] = None,
        model: Optional[str] = None,
        engine_id: Optional[str] = None,
        runtime_state: Optional[dict] = None,
    ) -> StepRun:
        updates = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
        params: List[Any] = [status]
        
        if retries is not None:
            updates.append("retries = ?")
            params.append(retries)
        if summary is not None:
            updates.append("summary = ?")
            params.append(summary)
        if model is not None:
            updates.append("model = ?")
            params.append(model)
        if engine_id is not None:
            updates.append("engine_id = ?")
            params.append(engine_id)
        if runtime_state is not None:
            updates.append("runtime_state = ?")
            params.append(json.dumps(runtime_state))
        
        params.append(step_run_id)
        
        with self._transaction() as conn:
            conn.execute(
                f"UPDATE step_runs SET {', '.join(updates)} WHERE id = ?",
                tuple(params),
            )
        return self.get_step_run(step_run_id)

    # Event operations
    def append_event(
        self,
        protocol_run_id: int,
        event_type: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        step_run_id: Optional[int] = None,
    ) -> Event:
        with self._transaction() as conn:
            cur = conn.execute(
                """
                INSERT INTO events (
                    protocol_run_id, step_run_id, event_type, message, metadata
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (protocol_run_id, step_run_id, event_type, message, json.dumps(metadata) if metadata else None),
            )
            event_id = cur.lastrowid
        row = self._fetchone("SELECT * FROM events WHERE id = ?", (event_id,))
        return self._row_to_event(row)

    def list_events(self, protocol_run_id: int) -> List[Event]:
        rows = self._fetchall(
            "SELECT * FROM events WHERE protocol_run_id = ? ORDER BY created_at ASC",
            (protocol_run_id,),
        )
        return [self._row_to_event(row) for row in rows]

    # Feedback event operations (new for DevGodzilla)
    def append_feedback_event(
        self,
        protocol_run_id: int,
        error_type: str,
        action_taken: str,
        attempt_number: int,
        step_run_id: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> FeedbackEvent:
        with self._transaction() as conn:
            cur = conn.execute(
                """
                INSERT INTO feedback_events (
                    protocol_run_id, step_run_id, error_type,
                    action_taken, attempt_number, context
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    protocol_run_id, step_run_id, error_type,
                    action_taken, attempt_number,
                    json.dumps(context) if context else None,
                ),
            )
            event_id = cur.lastrowid
        row = self._fetchone("SELECT * FROM feedback_events WHERE id = ?", (event_id,))
        return FeedbackEvent(
            id=row["id"],
            protocol_run_id=row["protocol_run_id"],
            step_run_id=row["step_run_id"],
            error_type=row["error_type"],
            action_taken=row["action_taken"],
            attempt_number=row["attempt_number"],
            context=self._parse_json(row["context"]),
            created_at=self._coerce_ts(row["created_at"]),
        )

    # Clarification operations
    def upsert_clarification(
        self,
        *,
        scope: str,
        project_id: int,
        key: str,
        question: str,
        recommended: Optional[dict] = None,
        options: Optional[list] = None,
        applies_to: Optional[str] = None,
        blocking: bool = False,
        protocol_run_id: Optional[int] = None,
        step_run_id: Optional[int] = None,
    ) -> Clarification:
        """Insert or update a clarification."""
        with self._transaction() as conn:
            conn.execute(
                """
                INSERT INTO clarifications (
                    scope, project_id, protocol_run_id, step_run_id,
                    key, question, recommended, options, applies_to, blocking,
                    status, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', CURRENT_TIMESTAMP)
                ON CONFLICT(scope, key) DO UPDATE SET
                    project_id=excluded.project_id,
                    protocol_run_id=excluded.protocol_run_id,
                    step_run_id=excluded.step_run_id,
                    question=excluded.question,
                    recommended=excluded.recommended,
                    options=excluded.options,
                    applies_to=excluded.applies_to,
                    blocking=excluded.blocking,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    scope,
                    project_id,
                    protocol_run_id,
                    step_run_id,
                    key,
                    question,
                    json.dumps(recommended) if recommended is not None else None,
                    json.dumps(options) if options is not None else None,
                    applies_to,
                    1 if blocking else 0,
                ),
            )
        row = self._fetchone("SELECT * FROM clarifications WHERE scope = ? AND key = ? LIMIT 1", (scope, key))
        if row is None:
            raise KeyError("Clarification not found after upsert")
        return self._row_to_clarification(row)

    def _row_to_clarification(self, row) -> Clarification:
        """Convert row to Clarification."""
        keys = set(row.keys()) if hasattr(row, "keys") else set()
        return Clarification(
            id=row["id"],
            scope=row["scope"],
            project_id=row["project_id"],
            protocol_run_id=row["protocol_run_id"],
            step_run_id=row["step_run_id"],
            key=row["key"],
            question=row["question"],
            recommended=self._parse_json(row["recommended"] if "recommended" in keys else None),
            options=self._parse_json(row["options"] if "options" in keys else None),
            applies_to=row["applies_to"] if "applies_to" in keys else None,
            blocking=bool(row["blocking"]) if row.get("blocking") is not None else False,
            answer=self._parse_json(row["answer"] if "answer" in keys else None),
            status=row["status"],
            answered_at=self._coerce_ts(row["answered_at"]) if row.get("answered_at") else None,
            answered_by=row["answered_by"] if "answered_by" in keys else None,
            created_at=self._coerce_ts(row["created_at"]),
            updated_at=self._coerce_ts(row["updated_at"]),
        )

    def list_clarifications(
        self,
        *,
        project_id: Optional[int] = None,
        protocol_run_id: Optional[int] = None,
        step_run_id: Optional[int] = None,
        status: Optional[str] = None,
        applies_to: Optional[str] = None,
        limit: int = 200,
    ) -> List[Clarification]:
        """List clarifications with filters."""
        limit = max(1, min(int(limit), 500))
        query = "SELECT * FROM clarifications"
        where: List[str] = []
        params: List[Any] = []
        if project_id is not None:
            where.append("project_id = ?")
            params.append(project_id)
        if protocol_run_id is not None:
            where.append("protocol_run_id = ?")
            params.append(protocol_run_id)
        if step_run_id is not None:
            where.append("step_run_id = ?")
            params.append(step_run_id)
        if status:
            where.append("status = ?")
            params.append(status)
        if applies_to:
            where.append("applies_to = ?")
            params.append(applies_to)
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY updated_at DESC, created_at DESC, id DESC LIMIT ?"
        params.append(limit)
        rows = self._fetchall(query, tuple(params))
        return [self._row_to_clarification(r) for r in rows]

    def answer_clarification(
        self,
        *,
        scope: str,
        key: str,
        answer: Optional[dict],
        answered_by: Optional[str] = None,
        status: str = "answered",
    ) -> Clarification:
        """Set the answer for a clarification."""
        with self._transaction() as conn:
            cur = conn.execute(
                """
                UPDATE clarifications
                SET answer = ?,
                    status = ?,
                    answered_at = CURRENT_TIMESTAMP,
                    answered_by = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE scope = ? AND key = ?
                """,
                (json.dumps(answer) if answer is not None else None, status, answered_by, scope, key),
            )
            if cur.rowcount == 0:
                raise KeyError(f"Clarification {scope}:{key} not found")
        row = self._fetchone("SELECT * FROM clarifications WHERE scope = ? AND key = ? LIMIT 1", (scope, key))
        if row is None:
            raise KeyError("Clarification not found after answer")
        return self._row_to_clarification(row)

    # Policy pack operations
    def _row_to_policy_pack(self, row) -> PolicyPack:
        """Convert row to PolicyPack."""
        keys = set(row.keys()) if hasattr(row, "keys") else set()
        pack_val = self._parse_json(row["pack"] if "pack" in keys else None)
        return PolicyPack(
            id=row["id"],
            key=row["key"],
            version=row["version"],
            name=row["name"],
            description=row["description"] if "description" in keys else None,
            status=row["status"] if "status" in keys else "active",
            pack=pack_val or {},
            created_at=self._coerce_ts(row["created_at"]),
            updated_at=self._coerce_ts(row["updated_at"]),
        )

    def get_policy_pack(self, *, key: str, version: str) -> PolicyPack:
        """Get a policy pack by key and version."""
        row = self._fetchone(
            "SELECT * FROM policy_packs WHERE key = ? AND version = ?",
            (key, version),
        )
        if row is None:
            raise KeyError(f"PolicyPack {key}:{version} not found")
        return self._row_to_policy_pack(row)

    def upsert_policy_pack(
        self,
        *,
        key: str,
        version: str,
        name: str,
        description: Optional[str] = None,
        status: str = "active",
        pack: dict,
    ) -> PolicyPack:
        """Insert or update a policy pack."""
        with self._transaction() as conn:
            conn.execute(
                """
                INSERT INTO policy_packs (key, version, name, description, status, pack, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key, version) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    status=excluded.status,
                    pack=excluded.pack,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (key, version, name, description, status, json.dumps(pack)),
            )
        return self.get_policy_pack(key=key, version=version)

    # Project policy operations
    def update_project_policy(
        self,
        project_id: int,
        *,
        policy_pack_key: Optional[str] = None,
        policy_pack_version: Optional[str] = None,
        policy_overrides: Optional[dict] = None,
        policy_repo_local_enabled: Optional[bool] = None,
        policy_effective_hash: Optional[str] = None,
        policy_enforcement_mode: Optional[str] = None,
    ) -> Project:
        """Update policy-related fields on a project."""
        updates = ["updated_at = CURRENT_TIMESTAMP"]
        params: List[Any] = []
        if policy_pack_key is not None:
            updates.append("policy_pack_key = ?")
            params.append(policy_pack_key)
        if policy_pack_version is not None:
            updates.append("policy_pack_version = ?")
            params.append(policy_pack_version)
        if policy_overrides is not None:
            updates.append("policy_overrides = ?")
            params.append(json.dumps(policy_overrides))
        if policy_repo_local_enabled is not None:
            updates.append("policy_repo_local_enabled = ?")
            params.append(1 if policy_repo_local_enabled else 0)
        if policy_effective_hash is not None:
            updates.append("policy_effective_hash = ?")
            params.append(policy_effective_hash)
        if policy_enforcement_mode is not None:
            updates.append("policy_enforcement_mode = ?")
            params.append(policy_enforcement_mode)
        params.append(project_id)
        
        with self._transaction() as conn:
            conn.execute(
                f"UPDATE projects SET {', '.join(updates)} WHERE id = ?",
                tuple(params),
            )
        return self.get_project(project_id)

    # Protocol template operations
    def update_protocol_template(
        self,
        protocol_run_id: int,
        *,
        template_config: Optional[dict] = None,
        template_source: Optional[dict] = None,
    ) -> ProtocolRun:
        """Update template config and source on a protocol run."""
        updates = ["updated_at = CURRENT_TIMESTAMP"]
        params: List[Any] = []
        if template_config is not None:
            updates.append("template_config = ?")
            params.append(json.dumps(template_config))
        if template_source is not None:
            updates.append("template_source = ?")
            params.append(json.dumps(template_source))
        params.append(protocol_run_id)
        
        with self._transaction() as conn:
            conn.execute(
                f"UPDATE protocol_runs SET {', '.join(updates)} WHERE id = ?",
                tuple(params),
            )
        return self.get_protocol_run(protocol_run_id)

    def update_protocol_policy_audit(
        self,
        protocol_run_id: int,
        *,
        policy_pack_key: str,
        policy_pack_version: str,
        policy_effective_hash: str,
        policy_effective_json: Optional[dict] = None,
    ) -> ProtocolRun:
        """Record the effective policy used for a protocol run (audit trail)."""
        with self._transaction() as conn:
            conn.execute(
                """
                UPDATE protocol_runs
                SET policy_pack_key = ?,
                    policy_pack_version = ?,
                    policy_effective_hash = ?,
                    policy_effective_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    policy_pack_key,
                    policy_pack_version,
                    policy_effective_hash,
                    json.dumps(policy_effective_json) if policy_effective_json else None,
                    protocol_run_id,
                ),
            )
        return self.get_protocol_run(protocol_run_id)


class PostgresDatabase:
    """
    PostgreSQL-backed persistence for DevGodzilla state.
    Requires psycopg>=3. Follows the same contract as the SQLite Database class.
    """

    def __init__(self, db_url: str, pool_size: int = 5) -> None:
        if psycopg is None:
            raise ImportError("psycopg is required for Postgres support. Install psycopg[binary].")
        
        self.db_url = db_url
        self.row_factory = dict_row
        self.pool = None
        
        if ConnectionPool:
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
        if self.row_factory is not None:
            conn.row_factory = self.row_factory
        return conn

    @contextmanager
    def _transaction(self):
        """Context manager for database transactions."""
        with self._connect() as conn:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def _fetchone(self, query: str, params: Iterable[Any] = ()) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, tuple(params))
                return cur.fetchone()

    def _fetchall(self, query: str, params: Iterable[Any] = ()) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, tuple(params))
                return cur.fetchall() or []

    def init_schema(self) -> None:
        """Initialize database schema."""
        from devgodzilla.db.schema import SCHEMA_POSTGRES
        
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA_POSTGRES)

    # Helper methods for JSON and timestamp parsing (reuse SQLite implementations)
    @staticmethod
    def _parse_json(value):
        return SQLiteDatabase._parse_json(value)
    
    @staticmethod
    def _coerce_ts(value):
        return SQLiteDatabase._coerce_ts(value)

    # Row converters (same as SQLite but work with dict rows)
    def _row_to_project(self, row: Dict[str, Any]) -> Project:
        return Project(
            id=row["id"],
            name=row["name"],
            git_url=row["git_url"],
            base_branch=row["base_branch"],
            local_path=row.get("local_path"),
            ci_provider=row.get("ci_provider"),
            secrets=row.get("secrets"),
            default_models=row.get("default_models"),
            project_classification=row.get("project_classification"),
            policy_pack_key=row.get("policy_pack_key"),
            policy_pack_version=row.get("policy_pack_version"),
            policy_overrides=row.get("policy_overrides"),
            policy_repo_local_enabled=row.get("policy_repo_local_enabled"),
            policy_effective_hash=row.get("policy_effective_hash"),
            policy_enforcement_mode=row.get("policy_enforcement_mode"),
            constitution_version=row.get("constitution_version"),
            constitution_hash=row.get("constitution_hash"),
            created_at=self._coerce_ts(row["created_at"]),
            updated_at=self._coerce_ts(row["updated_at"]),
        )

    def _row_to_protocol_run(self, row: Dict[str, Any]) -> ProtocolRun:
        return ProtocolRun(
            id=row["id"],
            project_id=row["project_id"],
            protocol_name=row["protocol_name"],
            status=row["status"],
            base_branch=row["base_branch"],
            worktree_path=row.get("worktree_path"),
            protocol_root=row.get("protocol_root"),
            description=row.get("description"),
            template_config=row.get("template_config"),
            template_source=row.get("template_source"),
            policy_pack_key=row.get("policy_pack_key"),
            policy_pack_version=row.get("policy_pack_version"),
            policy_effective_hash=row.get("policy_effective_hash"),
            policy_effective_json=row.get("policy_effective_json"),
            windmill_flow_id=row.get("windmill_flow_id"),
            speckit_metadata=row.get("speckit_metadata"),
            created_at=self._coerce_ts(row["created_at"]),
            updated_at=self._coerce_ts(row["updated_at"]),
        )

    def _row_to_step_run(self, row: Dict[str, Any]) -> StepRun:
        depends_on = row.get("depends_on", []) or []
        return StepRun(
            id=row["id"],
            protocol_run_id=row["protocol_run_id"],
            step_index=row["step_index"],
            step_name=row["step_name"],
            step_type=row["step_type"],
            status=row["status"],
            retries=row.get("retries", 0) or 0,
            model=row.get("model"),
            engine_id=row.get("engine_id"),
            policy=row.get("policy"),
            runtime_state=row.get("runtime_state"),
            summary=row.get("summary"),
            depends_on=depends_on if isinstance(depends_on, list) else [],
            parallel_group=row.get("parallel_group"),
            assigned_agent=row.get("assigned_agent"),
            created_at=self._coerce_ts(row["created_at"]),
            updated_at=self._coerce_ts(row["updated_at"]),
        )

    def _row_to_event(self, row: Dict[str, Any]) -> Event:
        return Event(
            id=row["id"],
            protocol_run_id=row["protocol_run_id"],
            step_run_id=row.get("step_run_id"),
            event_type=row["event_type"],
            message=row["message"],
            metadata=row.get("metadata"),
            created_at=self._coerce_ts(row["created_at"]),
        )

    # Project operations (PostgreSQL uses %s instead of ?)
    def create_project(
        self,
        name: str,
        git_url: str,
        base_branch: str,
        ci_provider: Optional[str] = None,
        default_models: Optional[dict] = None,
        secrets: Optional[dict] = None,
        local_path: Optional[str] = None,
        project_classification: Optional[str] = None,
        policy_pack_key: Optional[str] = None,
        policy_pack_version: Optional[str] = None,
    ) -> Project:
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO projects (
                        name, git_url, base_branch, ci_provider,
                        default_models, secrets, local_path,
                        project_classification, policy_pack_key, policy_pack_version,
                        policy_enforcement_mode
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'warn')
                    RETURNING id
                    """,
                    (
                        name, git_url, base_branch, ci_provider,
                        json.dumps(default_models) if default_models else None,
                        json.dumps(secrets) if secrets else None,
                        local_path, project_classification,
                        policy_pack_key or "default",
                        policy_pack_version or "1.0",
                    ),
                )
                project_id = cur.fetchone()["id"]
        return self.get_project(project_id)

    def get_project(self, project_id: int) -> Project:
        row = self._fetchone("SELECT * FROM projects WHERE id = %s", (project_id,))
        if row is None:
            raise KeyError(f"Project {project_id} not found")
        return self._row_to_project(row)

    def list_projects(self) -> List[Project]:
        rows = self._fetchall("SELECT * FROM projects ORDER BY created_at DESC")
        return [self._row_to_project(row) for row in rows]

    def update_project_local_path(self, project_id: int, local_path: str) -> Project:
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE projects SET local_path = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (local_path, project_id),
                )
        return self.get_project(project_id)

    # Protocol run operations
    def create_protocol_run(
        self,
        project_id: int,
        protocol_name: str,
        status: str,
        base_branch: str,
        worktree_path: Optional[str] = None,
        protocol_root: Optional[str] = None,
        description: Optional[str] = None,
    ) -> ProtocolRun:
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO protocol_runs (
                        project_id, protocol_name, status, base_branch,
                        worktree_path, protocol_root, description
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (project_id, protocol_name, status, base_branch, worktree_path, protocol_root, description),
                )
                run_id = cur.fetchone()["id"]
        return self.get_protocol_run(run_id)

    def get_protocol_run(self, run_id: int) -> ProtocolRun:
        row = self._fetchone("SELECT * FROM protocol_runs WHERE id = %s", (run_id,))
        if row is None:
            raise KeyError(f"ProtocolRun {run_id} not found")
        return self._row_to_protocol_run(row)

    def list_protocol_runs(self, project_id: int) -> List[ProtocolRun]:
        rows = self._fetchall(
            "SELECT * FROM protocol_runs WHERE project_id = %s ORDER BY created_at DESC",
            (project_id,),
        )
        return [self._row_to_protocol_run(row) for row in rows]

    def update_protocol_status(self, run_id: int, status: str) -> ProtocolRun:
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE protocol_runs SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (status, run_id),
                )
        return self.get_protocol_run(run_id)

    # Step run operations
    def create_step_run(
        self,
        protocol_run_id: int,
        step_index: int,
        step_name: str,
        step_type: str,
        status: str,
        depends_on: Optional[List[int]] = None,
        parallel_group: Optional[str] = None,
        assigned_agent: Optional[str] = None,
    ) -> StepRun:
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO step_runs (
                        protocol_run_id, step_index, step_name, step_type, status,
                        depends_on, parallel_group, assigned_agent
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        protocol_run_id, step_index, step_name, step_type, status,
                        json.dumps(depends_on or []), parallel_group, assigned_agent,
                    ),
                )
                step_id = cur.fetchone()["id"]
        return self.get_step_run(step_id)

    def get_step_run(self, step_run_id: int) -> StepRun:
        row = self._fetchone("SELECT * FROM step_runs WHERE id = %s", (step_run_id,))
        if row is None:
            raise KeyError(f"StepRun {step_run_id} not found")
        return self._row_to_step_run(row)

    def list_step_runs(self, protocol_run_id: int) -> List[StepRun]:
        rows = self._fetchall(
            "SELECT * FROM step_runs WHERE protocol_run_id = %s ORDER BY step_index ASC",
            (protocol_run_id,),
        )
        return [self._row_to_step_run(row) for row in rows]

    def update_step_status(
        self,
        step_run_id: int,
        status: str,
        retries: Optional[int] = None,
        summary: Optional[str] = None,
        model: Optional[str] = None,
        engine_id: Optional[str] = None,
        runtime_state: Optional[dict] = None,
    ) -> StepRun:
        updates = ["status = %s", "updated_at = CURRENT_TIMESTAMP"]
        params: List[Any] = [status]
        
        if retries is not None:
            updates.append("retries = %s")
            params.append(retries)
        if summary is not None:
            updates.append("summary = %s")
            params.append(summary)
        if model is not None:
            updates.append("model = %s")
            params.append(model)
        if engine_id is not None:
            updates.append("engine_id = %s")
            params.append(engine_id)
        if runtime_state is not None:
            updates.append("runtime_state = %s")
            params.append(json.dumps(runtime_state))
        
        params.append(step_run_id)
        
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE step_runs SET {', '.join(updates)} WHERE id = %s",
                    tuple(params),
                )
        return self.get_step_run(step_run_id)

    # Event operations
    def append_event(
        self,
        protocol_run_id: int,
        event_type: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        step_run_id: Optional[int] = None,
    ) -> Event:
        with self._transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO events (
                        protocol_run_id, step_run_id, event_type, message, metadata
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (protocol_run_id, step_run_id, event_type, message, json.dumps(metadata) if metadata else None),
                )
                event_id = cur.fetchone()["id"]
        row = self._fetchone("SELECT * FROM events WHERE id = %s", (event_id,))
        return self._row_to_event(row)

    def list_events(self, protocol_run_id: int) -> List[Event]:
        rows = self._fetchall(
            "SELECT * FROM events WHERE protocol_run_id = %s ORDER BY created_at ASC",
            (protocol_run_id,),
        )
        return [self._row_to_event(row) for row in rows]


# Type alias for the unified database interface
Database = Union[SQLiteDatabase, PostgresDatabase]


def get_database(db_url: Optional[str] = None, db_path: Optional[Path] = None, pool_size: int = 5) -> Database:
    """
    Factory function to create the appropriate database instance.
    
    Args:
        db_url: PostgreSQL connection URL (postgresql://...)
        db_path: SQLite database file path
        pool_size: Connection pool size for PostgreSQL
        
    Returns:
        Either SQLiteDatabase or PostgresDatabase instance
    """
    if db_url and db_url.startswith("postgres"):
        return PostgresDatabase(db_url, pool_size=pool_size)
    
    if db_path:
        return SQLiteDatabase(db_path)
    
    # Default to SQLite with default path
    return SQLiteDatabase(Path(".devgodzilla.sqlite"))
