"""
DevGodzilla Prometheus Metrics Endpoint

Provides Prometheus-compatible metrics for observability.
"""

from fastapi import APIRouter, Response

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
