"""
CLI Execution Tracking Service

Provides persistent tracking of CLI executions (discovery, code generation, etc.)
with real-time log streaming and status updates.

Execution state is persisted to PostgreSQL so data survives container restarts.
In-memory cache is used only for RUNNING executions (for fast access and log streaming).
"""

from __future__ import annotations

import json
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from devgodzilla.logging import get_logger

logger = get_logger(__name__)


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class LogEntry:
    timestamp: datetime
    level: str  # info, debug, warn, error
    message: str
    source: Optional[str] = None  # e.g., "opencode", "discovery", "stdout", "stderr"
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class CLIExecution:
    """Represents an in-progress or completed CLI execution."""
    execution_id: str
    execution_type: str  # discovery, code_gen, qa, etc.
    engine_id: str
    project_id: Optional[int] = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    command: Optional[str] = None
    working_dir: Optional[str] = None
    pid: Optional[int] = None
    exit_code: Optional[int] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    logs: deque = field(default_factory=lambda: deque(maxlen=10000))  # Keep last 10k log entries
    
    def add_log(self, level: str, message: str, source: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            level=level,
            message=message,
            source=source,
            metadata=metadata,
        )
        self.logs.append(entry)
        
    def to_dict(self, include_logs: bool = False, log_limit: int = 100) -> Dict[str, Any]:
        result = {
            "execution_id": self.execution_id,
            "execution_type": self.execution_type,
            "engine_id": self.engine_id,
            "project_id": self.project_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_seconds": (
                (self.finished_at or datetime.now(timezone.utc)) - self.started_at
            ).total_seconds() if self.started_at else None,
            "command": self.command,
            "working_dir": self.working_dir,
            "pid": self.pid,
            "exit_code": self.exit_code,
            "error": self.error,
            "metadata": self.metadata,
            "log_count": len(self.logs),
        }
        if include_logs:
            # Return last N logs
            logs_list = list(self.logs)[-log_limit:]
            result["logs"] = [
                {
                    "timestamp": log.timestamp.isoformat(),
                    "level": log.level,
                    "message": log.message,
                    "source": log.source,
                    "metadata": log.metadata,
                }
                for log in logs_list
            ]
        return result


def _parse_ts(value: Any) -> Optional[datetime]:
    """Parse a timestamp from DB (datetime or ISO string) into a timezone-aware datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except Exception:
            return None
    return None


def _parse_metadata(value: Any) -> Dict[str, Any]:
    """Parse metadata from DB (dict or JSON string)."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            result = json.loads(value)
            return result if isinstance(result, dict) else {}
        except Exception:
            return {}
    return {}


def _row_to_execution(row: Dict[str, Any]) -> CLIExecution:
    """Build a CLIExecution from a database row dict."""
    return CLIExecution(
        execution_id=row["execution_id"],
        execution_type=row["execution_type"],
        engine_id=row["engine_id"],
        project_id=row.get("project_id"),
        status=ExecutionStatus(row.get("status", "running")),
        started_at=_parse_ts(row.get("started_at")),
        finished_at=_parse_ts(row.get("finished_at")),
        command=row.get("command"),
        working_dir=row.get("working_dir"),
        pid=row.get("pid"),
        exit_code=row.get("exit_code"),
        error=row.get("error"),
        metadata=_parse_metadata(row.get("metadata")),
        logs=deque(maxlen=10000),
    )


class CLIExecutionTracker:
    """
    Singleton tracker for CLI executions.
    
    Persists execution state to PostgreSQL. Keeps only RUNNING executions
    in-memory for fast access and log streaming.
    """
    _instance: Optional["CLIExecutionTracker"] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        # In-memory cache: only RUNNING executions (for fast access + log streaming)
        self._executions: Dict[str, CLIExecution] = {}
        self._execution_lock = threading.Lock()
        self._subscribers: Dict[str, List[Callable[[LogEntry], None]]] = {}
        self._initialized = True
        logger.info("cli_execution_tracker_initialized")
    
    def _get_db(self):
        """Lazy accessor for the database instance.

        Uses the same cached database connection as the rest of the API
        (via devgodzilla.cli.main.get_db) so that env-based config and
        connection pooling are reused.
        """
        from devgodzilla.cli.main import get_db as _api_get_db
        return _api_get_db()
    
    def start_execution(
        self,
        execution_type: str,
        engine_id: str,
        project_id: Optional[int] = None,
        command: Optional[str] = None,
        working_dir: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CLIExecution:
        """Start tracking a new CLI execution."""
        execution_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        meta = metadata or {}
        
        execution = CLIExecution(
            execution_id=execution_id,
            execution_type=execution_type,
            engine_id=engine_id,
            project_id=project_id,
            status=ExecutionStatus.RUNNING,
            started_at=now,
            command=command,
            working_dir=working_dir,
            metadata=meta,
        )
        
        # Persist to database
        try:
            db = self._get_db()
            with db._transaction() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO cli_executions
                            (execution_id, execution_type, engine_id, project_id,
                             status, started_at, command, working_dir, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            execution_id,
                            execution_type,
                            engine_id,
                            project_id,
                            ExecutionStatus.RUNNING.value,
                            now,
                            command,
                            working_dir,
                            json.dumps(meta),
                        ),
                    )
        except Exception as exc:
            logger.warning(
                "cli_execution_db_insert_failed",
                extra={"error": str(exc)},
            )
        
        # Add to in-memory cache
        with self._execution_lock:
            self._executions[execution_id] = execution
            
        execution.add_log("info", f"Started {execution_type} with engine {engine_id}", source="tracker")
        logger.info(
            "cli_execution_started",
            extra={
                "execution_id": execution_id,
                "execution_type": execution_type,
                "engine_id": engine_id,
                "project_id": project_id,
            },
        )
        return execution
    
    def log(
        self,
        execution_id: str,
        level: str,
        message: str,
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Add a log entry to an execution (in-memory only, for streaming)."""
        with self._execution_lock:
            execution = self._executions.get(execution_id)
            if not execution:
                return
            execution.add_log(level, message, source, metadata)
            
        # Notify subscribers
        subscribers = self._subscribers.get(execution_id, [])
        entry = execution.logs[-1] if execution.logs else None
        if entry:
            for callback in subscribers:
                try:
                    callback(entry)
                except Exception as e:
                    logger.warning("subscriber_callback_failed", extra={"error": str(e)})
    
    def set_pid(self, execution_id: str, pid: int):
        """Set the process ID for an execution."""
        with self._execution_lock:
            execution = self._executions.get(execution_id)
            if execution:
                execution.pid = pid
                execution.add_log("debug", f"Process started with PID {pid}", source="tracker")
        
        # Persist pid update
        try:
            db = self._get_db()
            with db._transaction() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE cli_executions SET pid = %s WHERE execution_id = %s",
                        (pid, execution_id),
                    )
        except Exception as exc:
            logger.warning(
                "cli_execution_db_update_pid_failed",
                extra={"error": str(exc)},
            )
    
    def complete(
        self,
        execution_id: str,
        success: bool,
        exit_code: Optional[int] = None,
        error: Optional[str] = None,
    ):
        """Mark an execution as completed."""
        now = datetime.now(timezone.utc)
        
        with self._execution_lock:
            execution = self._executions.get(execution_id)
            if not execution:
                # Execution not in memory; just update DB
                self._complete_in_db(execution_id, success, exit_code, error, now)
                return
            if execution.status == ExecutionStatus.CANCELLED:
                # Preserve user-initiated cancellation if the process exits later.
                execution.exit_code = exit_code
                if error:
                    execution.error = error
                if execution.finished_at is None:
                    execution.finished_at = now
                execution.add_log(
                    "debug",
                    "Execution completion received after cancellation; preserving cancelled status",
                    source="tracker",
                )
                # Still update DB with final details
                self._complete_in_db(execution_id, False, exit_code, error, now, override_status=ExecutionStatus.CANCELLED.value)
                return
            execution.status = ExecutionStatus.SUCCEEDED if success else ExecutionStatus.FAILED
            execution.finished_at = now
            execution.exit_code = exit_code
            execution.error = error
            
            status_msg = "completed successfully" if success else f"failed: {error or 'unknown error'}"
            execution.add_log("info", f"Execution {status_msg}", source="tracker")
        
        # Update DB
        self._complete_in_db(execution_id, success, exit_code, error, now)
        
        # Remove from in-memory cache (completed executions live in DB)
        with self._execution_lock:
            self._executions.pop(execution_id, None)
            # Clean up subscribers
            self._subscribers.pop(execution_id, None)
        
        logger.info(
            "cli_execution_completed",
            extra={
                "execution_id": execution_id,
                "success": success,
                "exit_code": exit_code,
                "duration": (
                    (now - execution.started_at).total_seconds()
                    if execution.started_at
                    else None
                ),
            },
        )
    
    def _complete_in_db(
        self,
        execution_id: str,
        success: bool,
        exit_code: Optional[int],
        error: Optional[str],
        finished_at: datetime,
        override_status: Optional[str] = None,
    ):
        """Update the DB row for a completed execution."""
        status = override_status or (ExecutionStatus.SUCCEEDED.value if success else ExecutionStatus.FAILED.value)
        try:
            db = self._get_db()
            with db._transaction() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE cli_executions
                        SET status = %s, finished_at = %s, exit_code = %s, error = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE execution_id = %s
                        """,
                        (status, finished_at, exit_code, error, execution_id),
                    )
        except Exception as exc:
            logger.warning(
                "cli_execution_db_complete_failed",
                extra={"error": str(exc)},
            )
    
    def cancel(self, execution_id: str):
        """Mark an execution as cancelled."""
        now = datetime.now(timezone.utc)
        
        with self._execution_lock:
            execution = self._executions.get(execution_id)
            if execution:
                execution.status = ExecutionStatus.CANCELLED
                execution.finished_at = now
                execution.add_log("warn", "Execution cancelled", source="tracker")
        
        # Update DB
        try:
            db = self._get_db()
            with db._transaction() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE cli_executions
                        SET status = %s, finished_at = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE execution_id = %s
                        """,
                        (ExecutionStatus.CANCELLED.value, now, execution_id),
                    )
        except Exception as exc:
            logger.warning(
                "cli_execution_db_cancel_failed",
                extra={"error": str(exc)},
            )
        
        # Remove from in-memory cache
        with self._execution_lock:
            self._executions.pop(execution_id, None)
            self._subscribers.pop(execution_id, None)
    
    def get_execution(self, execution_id: str) -> Optional[CLIExecution]:
        """Get an execution by ID. Checks in-memory (running) first, then DB."""
        with self._execution_lock:
            execution = self._executions.get(execution_id)
            if execution:
                return execution
        
        # Not in memory — query DB
        try:
            db = self._get_db()
            row = db._fetchone(
                "SELECT * FROM cli_executions WHERE execution_id = %s",
                (execution_id,),
            )
            if row:
                return _row_to_execution(row)
        except Exception as exc:
            logger.warning(
                "cli_execution_db_get_failed",
                extra={"error": str(exc)},
            )
        return None
    
    def list_executions(
        self,
        execution_type: Optional[str] = None,
        project_id: Optional[int] = None,
        status: Optional[ExecutionStatus] = None,
        limit: int = 50,
    ) -> List[CLIExecution]:
        """List executions with optional filters. Reads from DB."""
        conditions = []
        params: list = []
        
        if execution_type:
            conditions.append("execution_type = %s")
            params.append(execution_type)
        if project_id is not None:
            conditions.append("project_id = %s")
            params.append(project_id)
        if status:
            conditions.append("status = %s")
            params.append(status.value)
        
        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)
        
        query = f"""
            SELECT * FROM cli_executions
            {where}
            ORDER BY started_at DESC
            LIMIT %s
        """
        params.append(limit)
        
        try:
            db = self._get_db()
            rows = db._fetchall(query, params)
            return [_row_to_execution(row) for row in rows]
        except Exception as exc:
            logger.warning(
                "cli_execution_db_list_failed",
                extra={"error": str(exc)},
            )
            return []
    
    def list_active(self, limit: int = 50) -> List[CLIExecution]:
        """List currently running executions."""
        return self.list_executions(status=ExecutionStatus.RUNNING, limit=limit)
    
    def subscribe(self, execution_id: str, callback: Callable[[LogEntry], None]):
        """Subscribe to log updates for an execution."""
        with self._execution_lock:
            if execution_id not in self._subscribers:
                self._subscribers[execution_id] = []
            self._subscribers[execution_id].append(callback)
    
    def unsubscribe(self, execution_id: str, callback: Callable[[LogEntry], None]):
        """Unsubscribe from log updates."""
        with self._execution_lock:
            if execution_id in self._subscribers:
                try:
                    self._subscribers[execution_id].remove(callback)
                except ValueError:
                    pass


# Global singleton accessor
def get_execution_tracker() -> CLIExecutionTracker:
    return CLIExecutionTracker()
