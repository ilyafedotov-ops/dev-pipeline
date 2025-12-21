"""
DevGodzilla Prometheus Metrics Endpoint

Provides Prometheus-compatible metrics for observability.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from devgodzilla.api.dependencies import get_db
from devgodzilla.db.database import Database

# Try to import prometheus_client, provide stub if not available
try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        generate_latest,
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Stubs
    class Counter:
        def __init__(self, *args, **kwargs): pass
        def inc(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    class Histogram:
        def __init__(self, *args, **kwargs): pass
        def observe(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    class Gauge:
        def __init__(self, *args, **kwargs): pass
        def set(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self

router = APIRouter(tags=["Metrics"])


# ==================== JSON Summary Models ====================

class JobTypeMetric(BaseModel):
    job_type: str
    count: int
    avg_duration_seconds: Optional[float] = None


class EndpointMetric(BaseModel):
    path: str
    calls: int
    avg_ms: Optional[float] = None


class MetricsSummary(BaseModel):
    total_events: int
    total_protocol_runs: int
    total_step_runs: int
    total_job_runs: int
    active_projects: int
    success_rate: float
    job_type_metrics: list[JobTypeMetric]
    recent_events_count: int


@router.get("/metrics/summary", response_model=MetricsSummary)
def metrics_summary(
    hours: int = 24,
    db: Database = Depends(get_db),
):
    """
    JSON metrics summary for the frontend dashboard.
    
    Returns aggregated stats from the database.
    """
    # Get basic counts
    projects = db.list_projects()
    active_projects = len([p for p in projects if p.status != "archived"])
    
    # Get protocol runs across all projects
    all_protocol_runs = []
    for project in projects:
        try:
            runs = db.list_protocol_runs(project.id)
            all_protocol_runs.extend(runs)
        except Exception:
            pass
    total_protocol_runs = len(all_protocol_runs)
    
    # Calculate success rate
    completed = [r for r in all_protocol_runs if r.status in ("completed", "passed")]
    failed = [r for r in all_protocol_runs if r.status in ("failed", "error")]
    total_finished = len(completed) + len(failed)
    success_rate = (len(completed) / total_finished * 100) if total_finished > 0 else 100.0
    
    # Get step runs across all protocol runs
    total_step_runs = 0
    for pr in all_protocol_runs:
        try:
            steps = db.list_step_runs(pr.id)
            total_step_runs += len(steps)
        except Exception:
            pass
    
    # Get job runs (this method supports limit directly)
    job_runs = db.list_job_runs(limit=1000)
    total_job_runs = len(job_runs)
    
    # Aggregate job runs by type
    job_type_counts: dict[str, list] = {}
    def _parse_ts(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None

    for jr in job_runs:
        jt = jr.job_type or "unknown"
        if jt not in job_type_counts:
            job_type_counts[jt] = []
        # Calculate duration if we have start/end times
        duration = None
        started_at = _parse_ts(jr.started_at)
        finished_at = _parse_ts(jr.finished_at)
        if started_at and finished_at:
            duration = (finished_at - started_at).total_seconds()
        job_type_counts[jt].append(duration)
    
    job_type_metrics = []
    for jt, durations in job_type_counts.items():
        valid_durations = [d for d in durations if d is not None]
        avg_dur = sum(valid_durations) / len(valid_durations) if valid_durations else None
        job_type_metrics.append(JobTypeMetric(
            job_type=jt,
            count=len(durations),
            avg_duration_seconds=avg_dur,
        ))
    
    # Sort by count descending
    job_type_metrics.sort(key=lambda x: x.count, reverse=True)
    
    # Get recent events count
    recent_events = db.list_recent_events(limit=500)
    recent_events_count = len(recent_events)
    total_events = recent_events_count  # This is approximate
    
    return MetricsSummary(
        total_events=total_events,
        total_protocol_runs=total_protocol_runs,
        total_step_runs=total_step_runs,
        total_job_runs=total_job_runs,
        active_projects=active_projects,
        success_rate=round(success_rate, 1),
        job_type_metrics=job_type_metrics,
        recent_events_count=recent_events_count,
    )



# ==================== Metrics Definitions ====================

# Protocol metrics
PROTOCOL_RUNS_TOTAL = Counter(
    "devgodzilla_protocol_runs_total",
    "Total number of protocol runs",
    ["status"],
)

PROTOCOL_DURATION_SECONDS = Histogram(
    "devgodzilla_protocol_duration_seconds",
    "Protocol run duration in seconds",
    buckets=[10, 30, 60, 120, 300, 600, 1800, 3600],
)

# Step metrics
STEP_RUNS_TOTAL = Counter(
    "devgodzilla_step_runs_total",
    "Total number of step runs",
    ["step_type", "status"],
)

STEP_DURATION_SECONDS = Histogram(
    "devgodzilla_step_duration_seconds",
    "Step run duration in seconds",
    ["step_type"],
    buckets=[5, 15, 30, 60, 120, 300],
)

# QA metrics
QA_EVALUATIONS_TOTAL = Counter(
    "devgodzilla_qa_evaluations_total",
    "Total number of QA evaluations",
    ["verdict"],
)

QA_FINDINGS_TOTAL = Counter(
    "devgodzilla_qa_findings_total",
    "Total number of QA findings",
    ["severity"],
)

# Agent metrics
AGENT_EXECUTIONS_TOTAL = Counter(
    "devgodzilla_agent_executions_total",
    "Total number of agent executions",
    ["agent_id", "status"],
)

AGENT_TOKENS_TOTAL = Counter(
    "devgodzilla_agent_tokens_total",
    "Total tokens used by agents",
    ["agent_id"],
)

# Active gauges
ACTIVE_PROTOCOL_RUNS = Gauge(
    "devgodzilla_active_protocol_runs",
    "Number of currently running protocols",
)

ACTIVE_STEP_RUNS = Gauge(
    "devgodzilla_active_step_runs",
    "Number of currently running steps",
)

# ==================== Endpoints ====================

@router.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.
    
    Returns metrics in Prometheus text format.
    """
    if not PROMETHEUS_AVAILABLE:
        return Response(
            content="# prometheus_client not installed\n",
            media_type="text/plain",
        )
    
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


# ==================== Helper Functions ====================

def record_protocol_started():
    """Record a protocol run started."""
    PROTOCOL_RUNS_TOTAL.labels(status="started").inc()
    ACTIVE_PROTOCOL_RUNS.set(ACTIVE_PROTOCOL_RUNS._value.get() + 1 if hasattr(ACTIVE_PROTOCOL_RUNS, '_value') else 1)


def record_protocol_completed(status: str, duration_seconds: float):
    """Record a protocol run completed."""
    PROTOCOL_RUNS_TOTAL.labels(status=status).inc()
    PROTOCOL_DURATION_SECONDS.observe(duration_seconds)
    ACTIVE_PROTOCOL_RUNS.set(max(0, ACTIVE_PROTOCOL_RUNS._value.get() - 1 if hasattr(ACTIVE_PROTOCOL_RUNS, '_value') else 0))


def record_step_started(step_type: str):
    """Record a step run started."""
    STEP_RUNS_TOTAL.labels(step_type=step_type, status="started").inc()
    ACTIVE_STEP_RUNS.set(ACTIVE_STEP_RUNS._value.get() + 1 if hasattr(ACTIVE_STEP_RUNS, '_value') else 1)


def record_step_completed(step_type: str, status: str, duration_seconds: float):
    """Record a step run completed."""
    STEP_RUNS_TOTAL.labels(step_type=step_type, status=status).inc()
    STEP_DURATION_SECONDS.labels(step_type=step_type).observe(duration_seconds)
    ACTIVE_STEP_RUNS.set(max(0, ACTIVE_STEP_RUNS._value.get() - 1 if hasattr(ACTIVE_STEP_RUNS, '_value') else 0))


def record_qa_evaluation(verdict: str, findings_by_severity: dict):
    """Record a QA evaluation."""
    QA_EVALUATIONS_TOTAL.labels(verdict=verdict).inc()
    for severity, count in findings_by_severity.items():
        for _ in range(count):
            QA_FINDINGS_TOTAL.labels(severity=severity).inc()


def record_agent_execution(agent_id: str, status: str, tokens: int = 0):
    """Record an agent execution."""
    AGENT_EXECUTIONS_TOTAL.labels(agent_id=agent_id, status=status).inc()
    if tokens > 0:
        AGENT_TOKENS_TOTAL.labels(agent_id=agent_id).inc(tokens)
