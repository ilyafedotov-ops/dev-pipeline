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
from devgodzilla.api.dependencies import get_db, get_service_context, require_api_token, require_webhook_token
from devgodzilla.config import get_config
from devgodzilla.engines.bootstrap import bootstrap_default_engines
from devgodzilla.db.database import Database
from devgodzilla.logging import get_logger, get_log_buffer
from devgodzilla.services.orchestrator import OrchestratorMode, OrchestratorService
from devgodzilla.services.path_contract import validate_path_contract
from devgodzilla.windmill.client import WindmillClient, WindmillConfig

logger = get_logger(__name__)

get_log_buffer()

# Resolve config at module level so routes / lifespan can use it.
config = get_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---

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

# Routes
auth_deps = [Depends(require_api_token)]
app.include_router(projects.router, tags=["Projects"], dependencies=auth_deps)
app.include_router(brownfield.router, dependencies=auth_deps)
app.include_router(protocols.router, tags=["Protocols"], dependencies=auth_deps)
app.include_router(steps.router, tags=["Steps"], dependencies=auth_deps)
app.include_router(agents.router, tags=["Agents"], dependencies=auth_deps)
app.include_router(clarifications.router, tags=["Clarifications"], dependencies=auth_deps)
app.include_router(speckit.router, tags=["SpecKit"], dependencies=auth_deps)
app.include_router(metrics.router)  # /metrics (optionally unauthenticated)
app.include_router(webhooks.router, dependencies=[Depends(require_webhook_token)])  # /webhooks/*
app.include_router(events.router, dependencies=auth_deps)  # /events
app.include_router(logs.router, dependencies=auth_deps)  # /logs
app.include_router(windmill_routes.router, dependencies=auth_deps)  # /flows, /jobs (Windmill)
app.include_router(runs_routes.router, dependencies=auth_deps)  # /runs (Job runs)
app.include_router(project_speckit_routes.router, dependencies=auth_deps)  # /projects/{id}/speckit/*
app.include_router(sprints.router, tags=["Sprints"], dependencies=auth_deps)
app.include_router(tasks.router, tags=["Tasks"], dependencies=auth_deps)
app.include_router(queues.router, dependencies=auth_deps)  # /queues
app.include_router(reconciliation_routes.router, dependencies=auth_deps)  # /reconciliation
app.include_router(policy_packs.router, dependencies=auth_deps)  # /policy_packs
app.include_router(specifications.router, dependencies=auth_deps)  # /specifications
app.include_router(quality.router, dependencies=auth_deps)  # /quality
app.include_router(profile.router, dependencies=auth_deps)  # /profile
app.include_router(templates.router, dependencies=auth_deps)  # /templates
app.include_router(cli_executions.router, tags=["CLI Executions"], dependencies=auth_deps)  # /cli-executions
app.include_router(ws_routes.router)  # /ws/events (WebSocket, no auth)


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
