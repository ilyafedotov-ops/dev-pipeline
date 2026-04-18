"""
DevGodzilla SQLite Tracing Wrapper

Wraps sqlite3.Connection with OpenTelemetry spans for database query tracing.
Records query text, duration, row counts, and error information as span attributes.
Falls back to plain sqlite3 when OpenTelemetry is not available.
"""

import sqlite3
import time
from typing import Any, Iterable, List, Optional

from devgodzilla.logging import get_logger

logger = get_logger(__name__)

# Try to import OpenTelemetry components
try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    trace = None  # type: ignore
    Status = None  # type: ignore
    StatusCode = None  # type: ignore

TRACER_NAME = "devgodzilla.db.sqlite"


def _get_tracer() -> Optional[Any]:
    """Get the OTel tracer for database operations, or None if unavailable."""
    if not OTEL_AVAILABLE:
        return None
    try:
        return trace.get_tracer(TRACER_NAME)
    except Exception:
        return None


def _extract_operation(query: str) -> str:
    """Extract the SQL operation keyword from a query string."""
    if not query:
        return "UNKNOWN"
    first_word = query.strip().split()[0].upper() if query.strip() else "UNKNOWN"
    return first_word if first_word else "UNKNOWN"


class TracedCursor:
    """
    Wrapper around sqlite3.Cursor that creates OTel spans for fetch operations.
    """

    def __init__(self, cursor: sqlite3.Cursor, query: str, tracer: Optional[Any]):
        self._cursor = cursor
        self._query = query
        self._tracer = tracer

    def fetchone(self) -> Optional[sqlite3.Row]:
        if not self._tracer:
            return self._cursor.fetchone()

        start = time.monotonic()
        try:
            result = self._cursor.fetchone()
            duration_ms = (time.monotonic() - start) * 1000
            self._record_fetch_span("sqlite.fetchone", duration_ms, row_count=1 if result else 0)
            return result
        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            self._record_fetch_span("sqlite.fetchone", duration_ms, error=exc)
            raise

    def fetchall(self) -> List[sqlite3.Row]:
        if not self._tracer:
            return self._cursor.fetchall()

        start = time.monotonic()
        try:
            result = self._cursor.fetchall()
            duration_ms = (time.monotonic() - start) * 1000
            self._record_fetch_span("sqlite.fetchall", duration_ms, row_count=len(result))
            return result
        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            self._record_fetch_span("sqlite.fetchall", duration_ms, error=exc)
            raise

    def fetchmany(self, size: Optional[int] = None) -> List[sqlite3.Row]:
        if not self._tracer:
            if size is not None:
                return self._cursor.fetchmany(size)
            return self._cursor.fetchmany()

        start = time.monotonic()
        try:
            result = (
                self._cursor.fetchmany(size) if size is not None
                else self._cursor.fetchmany()
            )
            duration_ms = (time.monotonic() - start) * 1000
            self._record_fetch_span("sqlite.fetchmany", duration_ms, row_count=len(result))
            return result
        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            self._record_fetch_span("sqlite.fetchmany", duration_ms, error=exc)
            raise

    def _record_fetch_span(
        self,
        operation: str,
        duration_ms: float,
        row_count: Optional[int] = None,
        error: Optional[Exception] = None,
    ) -> None:
        """Record a short span for a fetch operation."""
        if not self._tracer:
            return
        try:
            with self._tracer.start_as_current_span(operation) as span:
                if span and span.is_recording():
                    span.set_attribute("db.system", "sqlite")
                    span.set_attribute("db.statement", self._query)
                    span.set_attribute("db.operation", _extract_operation(self._query))
                    span.set_attribute("db.sqlite.duration_ms", round(duration_ms, 3))
                    if row_count is not None:
                        span.set_attribute("db.result.row_count", row_count)
                    if error is not None:
                        span.record_exception(error)
                        span.set_status(Status(StatusCode.ERROR, str(error)))
        except Exception:
            pass  # Never let tracing break the application

    # Proxy all other cursor attributes to the underlying cursor
    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)

    @property
    def lastrowid(self) -> Optional[int]:
        return self._cursor.lastrowid

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    @property
    def description(self) -> Optional[Any]:
        return self._cursor.description

    def close(self) -> None:
        self._cursor.close()

    def execute(self, sql: str, parameters: Iterable[Any] = ()) -> "TracedCursor":
        # Nested execute - trace it
        return TracedCursor(self._cursor.execute(sql, parameters), sql, self._tracer)

    def executemany(self, sql: str, seq_of_parameters: Iterable[Iterable[Any]]) -> "TracedCursor":
        return TracedCursor(
            self._cursor.executemany(sql, seq_of_parameters), sql, self._tracer
        )

    def executescript(self, sql_script: str) -> "TracedCursor":
        return TracedCursor(self._cursor.executescript(sql_script), sql_script, self._tracer)

    def __iter__(self):
        return iter(self._cursor)

    def __next__(self):
        return next(self._cursor)


class TracedConnection:
    """
    Wrapper around sqlite3.Connection that creates OTel spans for database operations.

    Wraps execute, fetchone, fetchall, and other database operations with spans that
    record query text, duration, row counts, and error information as span attributes.

    Falls back to no-op behavior when OpenTelemetry is not available, adding negligible
    overhead (just a single tracer availability check per call).
    """

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._tracer = _get_tracer()

    def execute(
        self, sql: str, parameters: Iterable[Any] = ()
    ) -> TracedCursor:
        """Execute a SQL statement, wrapped in an OTel span."""
        if not self._tracer:
            return TracedCursor(
                self._conn.execute(sql, parameters), sql, None
            )

        operation = _extract_operation(sql)
        span_name = f"sqlite {operation}"
        start = time.monotonic()

        try:
            cursor = self._conn.execute(sql, parameters)
            duration_ms = (time.monotonic() - start) * 1000

            with self._tracer.start_as_current_span(span_name) as span:
                if span and span.is_recording():
                    span.set_attribute("db.system", "sqlite")
                    span.set_attribute("db.statement", sql)
                    span.set_attribute("db.operation", operation)
                    span.set_attribute("db.sqlite.duration_ms", round(duration_ms, 3))
                    if cursor.rowcount >= 0:
                        span.set_attribute("db.result.row_count", cursor.rowcount)
                    if cursor.lastrowid is not None:
                        span.set_attribute("db.result.last_insert_rowid", cursor.lastrowid)

            return TracedCursor(cursor, sql, self._tracer)

        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000

            try:
                with self._tracer.start_as_current_span(span_name) as span:
                    if span and span.is_recording():
                        span.set_attribute("db.system", "sqlite")
                        span.set_attribute("db.statement", sql)
                        span.set_attribute("db.operation", operation)
                        span.set_attribute("db.sqlite.duration_ms", round(duration_ms, 3))
                        span.record_exception(exc)
                        span.set_status(Status(StatusCode.ERROR, str(exc)))
            except Exception:
                pass  # Never let tracing break the application

            raise

    def executemany(
        self, sql: str, seq_of_parameters: Iterable[Iterable[Any]]
    ) -> TracedCursor:
        """Execute a SQL statement with multiple parameter sets, wrapped in an OTel span."""
        if not self._tracer:
            return TracedCursor(
                self._conn.executemany(sql, seq_of_parameters), sql, None
            )

        operation = _extract_operation(sql)
        span_name = f"sqlite {operation}.many"
        start = time.monotonic()

        try:
            cursor = self._conn.executemany(sql, seq_of_parameters)
            duration_ms = (time.monotonic() - start) * 1000

            with self._tracer.start_as_current_span(span_name) as span:
                if span and span.is_recording():
                    span.set_attribute("db.system", "sqlite")
                    span.set_attribute("db.statement", sql)
                    span.set_attribute("db.operation", operation)
                    span.set_attribute("db.sqlite.duration_ms", round(duration_ms, 3))
                    if cursor.rowcount >= 0:
                        span.set_attribute("db.result.row_count", cursor.rowcount)

            return TracedCursor(cursor, sql, self._tracer)

        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000

            try:
                with self._tracer.start_as_current_span(span_name) as span:
                    if span and span.is_recording():
                        span.set_attribute("db.system", "sqlite")
                        span.set_attribute("db.statement", sql)
                        span.set_attribute("db.operation", operation)
                        span.set_attribute("db.sqlite.duration_ms", round(duration_ms, 3))
                        span.record_exception(exc)
                        span.set_status(Status(StatusCode.ERROR, str(exc)))
            except Exception:
                pass

            raise

    def executescript(self, sql_script: str) -> TracedCursor:
        """Execute a SQL script, wrapped in an OTel span."""
        if not self._tracer:
            return TracedCursor(self._conn.executescript(sql_script), sql_script, None)

        span_name = "sqlite SCRIPT"
        start = time.monotonic()

        try:
            cursor = self._conn.executescript(sql_script)
            duration_ms = (time.monotonic() - start) * 1000

            with self._tracer.start_as_current_span(span_name) as span:
                if span and span.is_recording():
                    span.set_attribute("db.system", "sqlite")
                    span.set_attribute("db.operation", "SCRIPT")
                    span.set_attribute("db.sqlite.duration_ms", round(duration_ms, 3))

            return TracedCursor(cursor, sql_script, self._tracer)

        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000

            try:
                with self._tracer.start_as_current_span(span_name) as span:
                    if span and span.is_recording():
                        span.set_attribute("db.system", "sqlite")
                        span.set_attribute("db.operation", "SCRIPT")
                        span.set_attribute("db.sqlite.duration_ms", round(duration_ms, 3))
                        span.record_exception(exc)
                        span.set_status(Status(StatusCode.ERROR, str(exc)))
            except Exception:
                pass

            raise

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()

    @property
    def row_factory(self) -> Optional[Any]:
        return self._conn.row_factory

    @row_factory.setter
    def row_factory(self, value: Optional[Any]) -> None:
        self._conn.row_factory = value

    @property
    def total_changes(self) -> int:
        return self._conn.total_changes

    @property
    def in_transaction(self) -> bool:
        return self._conn.in_transaction

    def cursor(self) -> TracedCursor:
        """Return a traced cursor."""
        return TracedCursor(self._conn.cursor(), "", self._tracer)

    # Context manager support
    def __enter__(self) -> "TracedConnection":
        self._conn.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._conn.__exit__(exc_type, exc_val, exc_tb)

    # Proxy any other attributes to the underlying connection
    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)


def wrap_connection(conn: sqlite3.Connection) -> TracedConnection:
    """
    Wrap a sqlite3.Connection with tracing.

    If OpenTelemetry is not available, the returned TracedConnection still functions
    correctly — it simply won't create spans.

    Args:
        conn: A raw sqlite3.Connection instance

    Returns:
        TracedConnection wrapping the original connection
    """
    return TracedConnection(conn)
