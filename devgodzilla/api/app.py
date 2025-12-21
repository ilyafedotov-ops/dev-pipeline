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
from devgodzilla.api.routes import projects, protocols, steps, agents, clarifications, speckit, sprints, tasks, policy_packs, specifications, quality, profile
from devgodzilla.api.routes import metrics, webhooks, events, logs
from devgodzilla.api.routes import windmill as windmill_routes
from devgodzilla.api.routes import runs as runs_routes
from devgodzilla.api.routes import project_speckit as project_speckit_routes
from devgodzilla.api.routes import queues
from devgodzilla.api.dependencies import get_db, get_service_context, require_api_token, require_webhook_token
from devgodzilla.config import get_config
from devgodzilla.engines.bootstrap import bootstrap_default_engines
from devgodzilla.db.database import Database
from devgodzilla.logging import get_logger, get_log_buffer
from devgodzilla.services.orchestrator import OrchestratorMode, OrchestratorService
from devgodzilla.windmill.client import WindmillClient, WindmillConfig

logger = get_logger(__name__)

get_log_buffer()

app = FastAPI(
    title="DevGodzilla API",
    description="REST API for DevGodzilla AI Development Pipeline",
    version="0.1.0",
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
config = get_config()
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
app.include_router(policy_packs.router, dependencies=auth_deps)  # /policy_packs
app.include_router(specifications.router, dependencies=auth_deps)  # /specifications
app.include_router(quality.router, dependencies=auth_deps)  # /quality
app.include_router(profile.router, dependencies=auth_deps)  # /profile


@app.on_event("startup")
def bootstrap_engines() -> None:
    """
    Register engines for API execution.

    The docker dev stack frequently runs without any real agent CLI installed.
    We always register a DummyEngine as the default so UI/flow integration can
    be tested end-to-end.
    """
    bootstrap_default_engines()


@app.on_event("startup")
def bootstrap_database() -> None:
    """
    Ensure DB schema exists.

    This is safe to run multiple times (CREATE TABLE IF NOT EXISTS).
    """
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


@app.on_event("startup")
def recover_protocol_runs() -> None:
    """Recover protocols stuck in RUNNING without active steps."""
    try:
        from devgodzilla.cli.main import get_db as cli_get_db
        from devgodzilla.cli.main import get_service_context as cli_get_service_context

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


@app.on_event("startup")
def bootstrap_sprint_integration() -> None:
    """Register sprint event handlers."""
    try:
        from devgodzilla.services.sprint_event_handlers import register_sprint_event_handlers
        register_sprint_event_handlers()
    except Exception as e:
        logger.error(f"Failed to register sprint event handlers: {e}")


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
    """Readiness probe (dependencies reachable)."""
    components: dict[str, str] = {"database": "ok", "windmill": "skipped"}
    try:
        db.list_projects()
    except Exception:
        components["database"] = "error"

    try:
        config = ctx.config
        if getattr(config, "windmill_enabled", False):
            wm = WindmillClient(
                WindmillConfig(
                    base_url=config.windmill_url or "http://localhost:8000",
                    token=config.windmill_token or "",
                    workspace=getattr(config, "windmill_workspace", "devgodzilla"),
                )
            )
            components["windmill"] = "ok" if wm.health_check() else "error"
        else:
            components["windmill"] = "disabled"
    except Exception:
        components["windmill"] = "error"

    status = "ok" if all(v in ("ok", "disabled", "skipped") for v in components.values()) else "error"
    return {"status": status, "components": components, "version": app.version}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
