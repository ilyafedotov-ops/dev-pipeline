from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    SLOWAPI_AVAILABLE = True
except ImportError:
    SLOWAPI_AVAILABLE = False

from devgodzilla.api import schemas
from devgodzilla.api.sentry import init_sentry
from devgodzilla.services.telemetry import (
    TelemetryConfig,
    get_telemetry,
    init_telemetry,
    shutdown_telemetry,
)
from devgodzilla.services.health import HealthChecker, health_status_to_dict
from devgodzilla.api.routes import projects, protocols, steps, agents, clarifications, speckit, sprints, tasks, policy_packs, specifications, quality, profile, templates, brownfield
from devgodzilla.api.routes import metrics, webhooks, events, logs
from devgodzilla.api.routes import windmill as windmill_routes
from devgodzilla.api.routes import runs as runs_routes
from devgodzilla.api.routes import project_speckit as project_speckit_routes
from devgodzilla.api.routes import cli_executions
from devgodzilla.api.routes import queues
from devgodzilla.api.routes import reconciliation as reconciliation_routes
from devgodzilla.api.routes import ws as ws_routes
from devgodzilla.api.routes import auth as auth_routes
from devgodzilla.api.routes import users as users_routes
from devgodzilla.api.dependencies import get_db, get_service_context, require_api_token, require_webhook_token
from devgodzilla.config import get_config
from devgodzilla.engines.bootstrap import bootstrap_default_engines
from devgodzilla.db.database import Database
from devgodzilla.logging import (
    get_log_buffer,
    get_logger,
    install_ring_buffer_handler,
    json_logging_from_env,
    setup_logging,
)
from devgodzilla.services.orchestrator import OrchestratorMode, OrchestratorService
from devgodzilla.services.path_contract import validate_path_contract
from devgodzilla.windmill.client import WindmillClient, WindmillConfig

# Configure logging at module import so uvicorn-launched entrypoints
# (Dockerfile CMD runs `uvicorn devgodzilla.api.app:app` directly, bypassing
# scripts/api_server.py) still get the root handler, level, and ring buffer.
# Without this, the root level stays at WARNING and every logger.info() in the
# request path is silently dropped before reaching stdout.
setup_logging(json_output=json_logging_from_env())

logger = get_logger(__name__)

get_log_buffer()

# Resolve config at module level so routes / lifespan can use it.
config = get_config()

# Initialise Sentry error tracking (no-op when DSN is not configured).
init_sentry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---

    # Re-apply structured logging after uvicorn has configured its own handlers.
    # Uvicorn overwrites root.handlers during startup, so the module-level
    # setup_logging() call is effectively lost.  Calling it again here ensures
    # our StreamHandler + RequestIdFilter + RingBuffer are active for all
    # request-path logging.
    setup_logging(json_output=json_logging_from_env())
    get_log_buffer()
    install_ring_buffer_handler()
    logger.info("structured_logging_initialised", extra={"json_output": json_logging_from_env()})

    # bootstrap_engines
    bootstrap_default_engines()

    # bootstrap_database
    from devgodzilla.cli.main import get_db as cli_get_db
    from devgodzilla.cli.main import get_service_context as cli_get_service_context

    db = cli_get_db()
    db.init_schema()
    try:
        from devgodzilla.services.event_persistence import install_db_event_sink

        install_db_event_sink(db_provider=cli_get_db)
    except Exception:
        pass
    try:
        from devgodzilla.services.agent_config import AgentConfigService

        ctx = cli_get_service_context()
        cfg = AgentConfigService(ctx, db=db)
        cfg.migrate_yaml_defaults_to_db()
    except Exception as exc:
        logger.error(
            "agent_defaults_migration_failed",
            extra={"error": str(exc)},
        )

    # recover_protocol_runs
    try:
        ctx = cli_get_service_context()
        db = cli_get_db()
        windmill_client = None
        mode = OrchestratorMode.LOCAL
        if getattr(ctx.config, "windmill_enabled", False):
            windmill_client = WindmillClient(
                WindmillConfig(
                    base_url=ctx.config.windmill_url or "http://localhost:8000",
                    token=ctx.config.windmill_token or "",
                    workspace=getattr(ctx.config, "windmill_workspace", "devgodzilla"),
                )
            )
            mode = OrchestratorMode.WINDMILL

        orchestrator = OrchestratorService(
            context=ctx,
            db=db,
            windmill_client=windmill_client,
            mode=mode,
        )
        recovered = orchestrator.recover_stuck_protocols()
        if recovered:
            logger.warning(
                "protocol_recovery_actions",
                extra={"recovered_count": len(recovered)},
            )
    except Exception as exc:
        logger.error(
            "protocol_recovery_failed",
            extra={"error": str(exc)},
        )

    # bootstrap_sprint_integration
    try:
        from devgodzilla.services.sprint_event_handlers import register_sprint_event_handlers
        register_sprint_event_handlers()
    except Exception as e:
        logger.error("sprint_event_handlers_registration_failed", extra={"error": str(e)})

    # validate_path_contract_startup
    report = validate_path_contract(config)
    for warning in report.warnings:
        logger.warning("path_contract_warning", extra={"warning": warning})
    if not report.is_valid:
        logger.error("path_contract_invalid", extra={"errors": report.errors})
        joined = "; ".join(report.errors)
        raise RuntimeError(f"Path contract validation failed: {joined}")

    # initialize_telemetry
    import os

    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    sample_rate = float(os.environ.get("OTEL_SAMPLE_RATE", "1.0"))
    enable_console = os.environ.get("OTEL_CONSOLE_EXPORT", "").lower() in ("1", "true", "yes")

    telemetry_config = TelemetryConfig(
        service_name="devgodzilla-api",
        service_version=app.version,
        environment=os.environ.get("DEVGODZILLA_ENV", "development"),
        otlp_endpoint=otlp_endpoint,
        sample_rate=sample_rate,
        enable_console_export=enable_console,
    )

    if init_telemetry(telemetry_config):
        get_telemetry().instrument_fastapi(app)
        logger.info(
            "telemetry_enabled",
            extra={
                "otlp_endpoint": otlp_endpoint or "none",
                "sample_rate": sample_rate,
                "console_export": enable_console,
            },
        )
    else:
        logger.info("telemetry_disabled", extra={"reason": "not available"})

    yield  # App is running

    # --- Shutdown ---
    shutdown_telemetry()


app = FastAPI(
    title="DevGodzilla API",
    description="REST API for DevGodzilla AI Development Pipeline",
    version="0.1.0",
    lifespan=lifespan,
)

# Rate Limiting
if SLOWAPI_AVAILABLE:
    limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    logger.info("rate_limiting_enabled", extra={"default_limit": "100/minute"})
else:
    limiter = None
    logger.warning("rate_limiting_disabled", extra={"reason": "slowapi not installed"})

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_allow_origins or [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Route registration helper
# ---------------------------------------------------------------------------
# All routers are mounted TWICE:
#   1. Under /api/v1  – the versioned, canonical API (used by frontend)
#   2. At root level   – backward-compatible, **deprecated** routes so that
#                        existing clients, CLI tools and tests continue to work.
# ---------------------------------------------------------------------------

auth_deps = [Depends(require_api_token)]

_router_entries = [
    (projects.router, ["Projects"], auth_deps),
    (brownfield.router, [], auth_deps),
    (protocols.router, ["Protocols"], auth_deps),
    (steps.router, ["Steps"], auth_deps),
    (agents.router, ["Agents"], auth_deps),
    (clarifications.router, ["Clarifications"], auth_deps),
    (speckit.router, ["SpecKit"], auth_deps),
    (metrics.router, [], []),                                  # /metrics (optionally unauthenticated)
    (webhooks.router, [], [Depends(require_webhook_token)]),   # /webhooks/*
    (events.router, [], auth_deps),                            # /events
    (logs.router, [], auth_deps),                              # /logs
    (windmill_routes.router, [], auth_deps),                   # /flows, /jobs (Windmill)
    (runs_routes.router, [], auth_deps),                       # /runs (Job runs)
    (project_speckit_routes.router, [], auth_deps),            # /projects/{id}/speckit/*
    (sprints.router, ["Sprints"], auth_deps),
    (tasks.router, ["Tasks"], auth_deps),
    (queues.router, [], auth_deps),                            # /queues
    (reconciliation_routes.router, [], auth_deps),             # /reconciliation
    (policy_packs.router, [], auth_deps),                      # /policy_packs
    (specifications.router, [], auth_deps),                    # /specifications
    (quality.router, [], auth_deps),                           # /quality
    (profile.router, [], auth_deps),                           # /profile
    (templates.router, [], auth_deps),                         # /templates
    (cli_executions.router, ["CLI Executions"], auth_deps),    # /cli-executions
    (ws_routes.router, [], []),                                # /ws/events (WebSocket, no auth)
    (auth_routes.router, [], []),                              # /auth/* (self-authenticated via JWT)
    (users_routes.router, [], []),                             # /users/* (JWT auth via dependency)
]

for _router, _tags, _deps in _router_entries:
    _kw: dict = {"dependencies": _deps}
    if _tags:
        _kw["tags"] = _tags
    # Versioned API (canonical)
    app.include_router(_router, prefix="/api/v1", **_kw)
    # Backward-compatible root routes (deprecated)
    app.include_router(_router, **_kw)


@app.get("/health", response_model=schemas.Health)
def health_check():
    """Health check endpoint."""
    return schemas.Health()


@app.get("/health/live")
def health_live():
    """Liveness probe (process is running)."""
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready(
    db: Database = Depends(get_db),
    ctx=Depends(get_service_context),
):
    """Readiness probe (dependencies reachable) with comprehensive health checking."""
    from devgodzilla.engines.registry import get_registry
    
    # Build windmill client if enabled
    windmill_client = None
    config = ctx.config
    if getattr(config, "windmill_enabled", False):
        try:
            windmill_client = WindmillClient(
                WindmillConfig(
                    base_url=config.windmill_url or "http://localhost:8000",
                    token=config.windmill_token or "",
                    workspace=getattr(config, "windmill_workspace", "devgodzilla"),
                )
            )
        except Exception:
            pass
    
    # Get agent registry
    try:
        agent_registry = get_registry()
    except Exception:
        agent_registry = None
    
    # Create health checker and run checks
    checker = HealthChecker(
        db=db,
        windmill=windmill_client,
        agent_registry=agent_registry,
    )
    status = checker.check_all_sync()
    
    return health_status_to_dict(status)


@app.get("/health/agents")
def health_agents(
    db: Database = Depends(get_db),
    ctx=Depends(get_service_context),
):
    """Detailed agent availability check."""
    from devgodzilla.engines.registry import get_registry
    
    try:
        agent_registry = get_registry()
        availability = agent_registry.check_all_available()
        engines = agent_registry.list_all()
        
        agents = [
            {
                "agent_id": e.metadata.id,
                "name": e.metadata.display_name,
                "kind": e.metadata.kind.value if hasattr(e.metadata.kind, "value") else str(e.metadata.kind),
                "available": availability.get(e.metadata.id, False),
            }
            for e in engines
        ]
        
        return {
            "total": len(agents),
            "available": sum(1 for a in agents if a["available"]),
            "unavailable": sum(1 for a in agents if not a["available"]),
            "agents": agents,
        }
    except Exception as exc:
        return {
            "total": 0,
            "available": 0,
            "unavailable": 0,
            "agents": [],
            "error": str(exc),
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
