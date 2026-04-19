import os
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from devgodzilla.api import schemas
from devgodzilla.api.dependencies import get_db, get_service_context
from devgodzilla.db.database import Database
from devgodzilla.engines.registry import get_registry
from devgodzilla.logging import get_logger, log_extra
from devgodzilla.services.agent_config import AgentConfigService
from devgodzilla.services.base import ServiceContext

router = APIRouter()
logger = get_logger(__name__)

@router.get("/agents", response_model=List[schemas.AgentInfo])
def list_agents(
    project_id: Optional[int] = Query(default=None),
    enabled_only: bool = Query(default=False),
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """List available agents."""
    # Prefer YAML-configured agents (stable list even when engines are not registered).
    cfg = AgentConfigService(ctx, db=db)
    agents = [
        schemas.AgentInfo(
            id=a.id,
            name=a.name,
            kind=a.kind,
            capabilities=a.capabilities,
            status="configured" if a.enabled else "disabled",
            default_model=a.default_model,
            command_dir=a.command_dir,
            enabled=a.enabled,
            command=a.command,
            endpoint=a.endpoint,
            sandbox=a.sandbox,
            format=a.format,
            timeout_seconds=a.timeout_seconds,
            max_retries=a.max_retries,
        )
        for a in cfg.list_agents(enabled_only=enabled_only, project_id=project_id)
    ]

    # Fallback to registry metadata if config is empty.
    if agents or project_id is not None:
        logger.info(
            "agents_listed",
            extra=log_extra(
                request_id=ctx.request_id,
                project_id=project_id,
                enabled_only=enabled_only,
                source="config",
                result_count=len(agents),
            ),
        )
        return agents

    registry = get_registry()
    items = [
        schemas.AgentInfo(
            id=meta.id,
            name=meta.display_name,
            kind=meta.kind.value if hasattr(meta.kind, "value") else str(meta.kind),
            capabilities=meta.capabilities,
            status="available",
        )
        for meta in registry.list_metadata()
    ]
    logger.info(
        "agents_listed",
        extra=log_extra(
            request_id=ctx.request_id,
            enabled_only=enabled_only,
            source="registry",
            result_count=len(items),
        ),
    )
    return items


@router.get("/agents/health", response_model=List[schemas.AgentHealthOut])
def check_all_agents_health(
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """Check health for all enabled agents."""
    cfg = AgentConfigService(ctx, db=db)
    results = cfg.check_all_health()
    out = []
    for r in results:
        warnings: list[str] = []
        # Check for engine-specific warnings (e.g. missing API keys)
        agent_cfg = cfg.get_agent(r.agent_id)
        if agent_cfg and r.available:
            aid = agent_cfg.id
            if aid == "gemini-cli":
                if not (
                    os.environ.get("GOOGLE_API_KEY")
                    or os.environ.get("GEMINI_API_KEY")
                ):
                    warnings.append("GOOGLE_API_KEY not set")
        out.append(
            schemas.AgentHealthOut(
                agent_id=r.agent_id,
                available=r.available,
                version=r.version,
                error=r.error,
                response_time_ms=r.response_time_ms,
                warnings=warnings,
            )
        )
    logger.info(
        "agents_health_checked",
        extra=log_extra(
            request_id=ctx.request_id,
            result_count=len(out),
            available_count=sum(1 for item in out if item.available),
        ),
    )
    return out


@router.get("/agents/metrics", response_model=List[schemas.AgentMetricsOut])
def list_agent_metrics(
    project_id: Optional[int] = Query(default=None),
    db: Database = Depends(get_db),
):
    """Return step execution metrics grouped by agent."""
    metrics: Dict[str, schemas.AgentMetricsOut] = {}
    if project_id is None:
        runs = db.list_all_protocol_runs(limit=500)
    else:
        runs = db.list_protocol_runs(project_id)

    for run in runs:
        for step in db.list_step_runs(run.id):
            agent_id = step.engine_id or step.assigned_agent
            if not agent_id:
                continue
            entry = metrics.setdefault(agent_id, schemas.AgentMetricsOut(agent_id=agent_id))
            entry.total_steps += 1
            if step.status == "running":
                entry.active_steps += 1
            elif step.status == "completed":
                entry.completed_steps += 1
            elif step.status == "failed":
                entry.failed_steps += 1
            if step.updated_at and (entry.last_activity_at is None or step.updated_at > entry.last_activity_at):
                entry.last_activity_at = step.updated_at

    results = list(metrics.values())
    logger.info("agent_metrics_listed", extra=log_extra(project_id=project_id, result_count=len(results)))
    return results


@router.put("/agents/{agent_id}/config", response_model=schemas.AgentInfo)
def update_agent_config(
    agent_id: str,
    config: schemas.AgentConfigUpdate,
    project_id: Optional[int] = Query(default=None),
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """Update agent configuration."""
    cfg = AgentConfigService(ctx, db=db)
    try:
        updated_agent = cfg.update_config(
            agent_id=agent_id,
            enabled=config.enabled,
            default_model=config.default_model,
            capabilities=config.capabilities,
            command_dir=config.command_dir,
            name=config.name,
            kind=config.kind,
            command=config.command,
            endpoint=config.endpoint,
            sandbox=config.sandbox,
            format=config.format,
            timeout_seconds=config.timeout_seconds,
            max_retries=config.max_retries,
            project_id=project_id,
        )
        response = schemas.AgentInfo(
            id=updated_agent.id,
            name=updated_agent.name,
            kind=updated_agent.kind,
            capabilities=updated_agent.capabilities,
            status="configured" if updated_agent.enabled else "disabled",
            default_model=updated_agent.default_model,
            command_dir=updated_agent.command_dir,
            enabled=updated_agent.enabled,
            command=updated_agent.command,
            endpoint=updated_agent.endpoint,
            sandbox=updated_agent.sandbox,
            format=updated_agent.format,
            timeout_seconds=updated_agent.timeout_seconds,
            max_retries=updated_agent.max_retries,
        )
        logger.info(
            "agent_config_updated",
            extra=log_extra(
                request_id=ctx.request_id,
                project_id=project_id,
                agent_id=agent_id,
                updated_fields=sorted(config.model_dump(exclude_unset=True).keys()),
                enabled=response.enabled,
            ),
        )
        return response
    except ValueError as e:
        logger.warning(
            "agent_config_update_not_found",
            extra=log_extra(request_id=ctx.request_id, project_id=project_id, agent_id=agent_id, error=str(e)),
        )
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(
            "agent_config_update_failed",
            extra=log_extra(request_id=ctx.request_id, project_id=project_id, agent_id=agent_id, error=str(e)),
        )
        raise HTTPException(status_code=500, detail=f"Failed to update agent config: {str(e)}")


@router.put("/agents/projects/{project_id}/agents/{agent_id}", response_model=schemas.AgentInfo)
def update_project_agent_config(
    project_id: int,
    agent_id: str,
    config: schemas.AgentConfigUpdate,
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """Update project-specific agent configuration overrides."""
    return update_agent_config(agent_id, config, project_id=project_id, ctx=ctx, db=db)


@router.get("/agents/defaults", response_model=schemas.AgentDefaults)
def get_agent_defaults(
    project_id: Optional[int] = Query(default=None),
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """Get agent defaults."""
    cfg = AgentConfigService(ctx, db=db)
    defaults = cfg.get_defaults(project_id=project_id)
    logger.info(
        "agent_defaults_loaded",
        extra=log_extra(request_id=ctx.request_id, project_id=project_id, keys=sorted(defaults.keys())),
    )
    return schemas.AgentDefaults(**defaults)


@router.put("/agents/defaults", response_model=schemas.AgentDefaults)
def update_agent_defaults(
    defaults: schemas.AgentDefaults,
    project_id: Optional[int] = Query(default=None),
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """Update agent defaults."""
    cfg = AgentConfigService(ctx, db=db)
    updated = cfg.update_defaults(defaults.model_dump(exclude_unset=True), project_id=project_id)
    logger.info(
        "agent_defaults_updated",
        extra=log_extra(
            request_id=ctx.request_id,
            project_id=project_id,
            updated_fields=sorted(defaults.model_dump(exclude_unset=True).keys()),
        ),
    )
    return schemas.AgentDefaults(**updated)

@router.get("/agents/assignments", response_model=schemas.AgentAssignments)
def list_agent_assignments(
    project_id: Optional[int] = Query(default=None),
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """List agent assignments (global or project-scoped)."""
    cfg = AgentConfigService(ctx, db=db)
    payload = cfg.get_assignments(project_id=project_id)
    logger.info(
        "agent_assignments_listed",
        extra=log_extra(
            request_id=ctx.request_id,
            project_id=project_id,
            assignment_count=len(payload.get("assignments", {}) or {}),
        ),
    )
    return schemas.AgentAssignments(**payload)


@router.put("/agents/assignments", response_model=schemas.AgentAssignments)
def update_agent_assignments(
    assignments: schemas.AgentAssignments,
    project_id: Optional[int] = Query(default=None),
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """Update agent assignments (global or project-scoped)."""
    cfg = AgentConfigService(ctx, db=db)
    if project_id is not None and assignments.inherit_global is not None:
        cfg.update_assignment_settings(project_id, bool(assignments.inherit_global))
    assignment_payload = assignments.model_dump(exclude_unset=True).get("assignments", {})
    if assignment_payload:
        updated = cfg.update_assignments(assignment_payload, project_id=project_id)
    else:
        updated = cfg.get_assignments(project_id=project_id)
    logger.info(
        "agent_assignments_updated",
        extra=log_extra(
            request_id=ctx.request_id,
            project_id=project_id,
            assignment_count=len(updated.get("assignments", {}) or {}),
        ),
    )
    return schemas.AgentAssignments(**updated)


@router.get("/projects/{project_id}/agents/assignments", response_model=schemas.AgentAssignments)
def list_project_assignments(
    project_id: int,
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """List agent assignments for a project."""
    cfg = AgentConfigService(ctx, db=db)
    payload = cfg.get_assignments(project_id=project_id)
    return schemas.AgentAssignments(**payload)


@router.put("/projects/{project_id}/agents/assignments", response_model=schemas.AgentAssignments)
def update_project_assignments(
    project_id: int,
    assignments: schemas.AgentAssignments,
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """Update agent assignments for a project."""
    cfg = AgentConfigService(ctx, db=db)
    if assignments.inherit_global is not None:
        cfg.update_assignment_settings(project_id, bool(assignments.inherit_global))
    assignment_payload = assignments.model_dump(exclude_unset=True).get("assignments", {})
    if assignment_payload:
        updated = cfg.update_assignments(assignment_payload, project_id=project_id)
    else:
        updated = cfg.get_assignments(project_id=project_id)
    return schemas.AgentAssignments(**updated)


@router.get("/projects/{project_id}/agents/overrides", response_model=schemas.AgentOverrides)
def list_project_agent_overrides(
    project_id: int,
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """List per-project agent overrides."""
    cfg = AgentConfigService(ctx, db=db)
    overrides = cfg.get_agent_overrides(project_id)
    return schemas.AgentOverrides(agents=overrides)


@router.put("/projects/{project_id}/agents/overrides", response_model=schemas.AgentOverrides)
def update_project_agent_overrides_v2(
    project_id: int,
    overrides: schemas.AgentOverrides,
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """Update per-project agent overrides."""
    cfg = AgentConfigService(ctx, db=db)
    updated = cfg.update_agent_overrides(project_id, overrides.model_dump(exclude_unset=True).get("agents", {}))
    return schemas.AgentOverrides(agents=updated)


@router.get("/agents/prompts", response_model=List[schemas.AgentPromptTemplate])
def list_agent_prompts(
    project_id: Optional[int] = Query(default=None),
    enabled_only: bool = Query(default=False),
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """List prompt templates."""
    cfg = AgentConfigService(ctx, db=db)
    prompts = cfg.list_prompts(project_id=project_id, enabled_only=enabled_only)
    sources = {}
    if project_id is not None:
        project_prompts = cfg.get_project_overrides(project_id).get("prompts", {}) or {}
        if isinstance(project_prompts, dict):
            sources = {pid: "project" for pid in project_prompts.keys()}
    items = [
        schemas.AgentPromptTemplate(
            id=p.get("id") or "",
            name=p.get("name") or p.get("id") or "",
            path=p.get("path") or "",
            kind=p.get("kind"),
            engine_id=p.get("engine_id"),
            model=p.get("model"),
            tags=p.get("tags"),
            enabled=p.get("enabled"),
            description=p.get("description"),
            source=sources.get(p.get("id"), "global"),
        )
        for p in prompts
    ]
    logger.info(
        "agent_prompts_listed",
        extra=log_extra(
            request_id=ctx.request_id,
            project_id=project_id,
            enabled_only=enabled_only,
            result_count=len(items),
        ),
    )
    return items


@router.put("/agents/prompts/{prompt_id}", response_model=schemas.AgentPromptTemplate)
def update_agent_prompt(
    prompt_id: str,
    prompt: schemas.AgentPromptUpdate,
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """Update a global prompt template."""
    cfg = AgentConfigService(ctx, db=db)
    updated = cfg.update_prompt(prompt_id, prompt.model_dump(exclude_unset=True))
    return schemas.AgentPromptTemplate(
        id=updated.get("id") or prompt_id,
        name=updated.get("name") or prompt_id,
        path=updated.get("path") or "",
        kind=updated.get("kind"),
        engine_id=updated.get("engine_id"),
        model=updated.get("model"),
        tags=updated.get("tags"),
        enabled=updated.get("enabled"),
        description=updated.get("description"),
    )


@router.put("/agents/projects/{project_id}/prompts/{prompt_id}", response_model=schemas.AgentPromptTemplate)
def update_project_prompt(
    project_id: int,
    prompt_id: str,
    prompt: schemas.AgentPromptUpdate,
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """Update a project prompt override."""
    cfg = AgentConfigService(ctx, db=db)
    updated = cfg.update_prompt(prompt_id, prompt.model_dump(exclude_unset=True), project_id=project_id)
    return schemas.AgentPromptTemplate(
        id=updated.get("id") or prompt_id,
        name=updated.get("name") or prompt_id,
        path=updated.get("path") or "",
        kind=updated.get("kind"),
        engine_id=updated.get("engine_id"),
        model=updated.get("model"),
        tags=updated.get("tags"),
        enabled=updated.get("enabled"),
        description=updated.get("description"),
        source="project",
    )


@router.get("/agents/projects/{project_id}", response_model=schemas.AgentProjectOverrides)
def get_project_agent_overrides(
    project_id: int,
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """Get project-level agent overrides."""
    cfg = AgentConfigService(ctx, db=db)
    overrides = cfg.get_project_overrides(project_id)
    logger.info(
        "agent_project_overrides_loaded",
        extra=log_extra(
            request_id=ctx.request_id,
            project_id=project_id,
            keys=sorted(overrides.keys()),
        ),
    )
    return schemas.AgentProjectOverrides(**overrides)


@router.put("/agents/projects/{project_id}", response_model=schemas.AgentProjectOverrides)
def update_project_agent_overrides(
    project_id: int,
    overrides: schemas.AgentProjectOverrides,
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """Update project-level agent overrides."""
    cfg = AgentConfigService(ctx, db=db)
    updated = cfg.update_project_overrides(project_id, overrides.model_dump(exclude_unset=True))
    logger.info(
        "agent_project_overrides_updated",
        extra=log_extra(
            request_id=ctx.request_id,
            project_id=project_id,
            updated_fields=sorted(overrides.model_dump(exclude_unset=True).keys()),
        ),
    )
    return schemas.AgentProjectOverrides(**updated)


@router.get("/agents/{agent_id}", response_model=schemas.AgentInfo)
def get_agent(
    agent_id: str,
    project_id: Optional[int] = Query(default=None),
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """Get agent details by ID."""
    cfg = AgentConfigService(ctx, db=db)
    agent = cfg.get_agent(agent_id, project_id=project_id)
    if agent:
        response = schemas.AgentInfo(
            id=agent.id,
            name=agent.name,
            kind=agent.kind,
            capabilities=agent.capabilities,
            status="available" if agent.enabled else "unavailable",
            default_model=agent.default_model,
            command_dir=agent.command_dir,
            enabled=agent.enabled,
            command=agent.command,
            endpoint=agent.endpoint,
            sandbox=agent.sandbox,
            format=agent.format,
            timeout_seconds=agent.timeout_seconds,
            max_retries=agent.max_retries,
        )
        logger.info(
            "agent_loaded",
            extra=log_extra(
                request_id=ctx.request_id,
                project_id=project_id,
                agent_id=agent_id,
                source="config",
                enabled=response.enabled,
            ),
        )
        return response

    if project_id is None:
        registry = get_registry()
        meta = next((m for m in registry.list_metadata() if m.id == agent_id), None)
        if meta is None:
            logger.warning("agent_not_found", extra=log_extra(request_id=ctx.request_id, agent_id=agent_id))
            raise HTTPException(status_code=404, detail="Agent not found")
        response = schemas.AgentInfo(
            id=meta.id,
            name=meta.display_name,
            kind=meta.kind.value if hasattr(meta.kind, "value") else str(meta.kind),
            capabilities=meta.capabilities,
            status="available",
        )
        logger.info("agent_loaded", extra=log_extra(request_id=ctx.request_id, agent_id=agent_id, source="registry"))
        return response

    logger.warning(
        "agent_not_found",
        extra=log_extra(request_id=ctx.request_id, project_id=project_id, agent_id=agent_id),
    )
    raise HTTPException(status_code=404, detail="Agent not found")


@router.put("/agents/{agent_id}", response_model=schemas.AgentInfo)
def update_agent(
    agent_id: str,
    config: schemas.AgentConfigUpdate,
    project_id: Optional[int] = Query(default=None),
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """Update agent configuration by ID.

    Accepts JSON body with config overrides (model, temperature, max_tokens, etc).
    Delegates to the same AgentConfigService.update_config used by /config.
    """
    cfg = AgentConfigService(ctx, db=db)
    try:
        updated_agent = cfg.update_config(
            agent_id=agent_id,
            enabled=config.enabled,
            default_model=config.default_model,
            capabilities=config.capabilities,
            command_dir=config.command_dir,
            name=config.name,
            kind=config.kind,
            command=config.command,
            endpoint=config.endpoint,
            sandbox=config.sandbox,
            format=config.format,
            timeout_seconds=config.timeout_seconds,
            max_retries=config.max_retries,
            project_id=project_id,
        )
        return schemas.AgentInfo(
            id=updated_agent.id,
            name=updated_agent.name,
            kind=updated_agent.kind,
            capabilities=updated_agent.capabilities,
            status="configured" if updated_agent.enabled else "disabled",
            default_model=updated_agent.default_model,
            command_dir=updated_agent.command_dir,
            enabled=updated_agent.enabled,
            command=updated_agent.command,
            endpoint=updated_agent.endpoint,
            sandbox=updated_agent.sandbox,
            format=updated_agent.format,
            timeout_seconds=updated_agent.timeout_seconds,
            max_retries=updated_agent.max_retries,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update agent: {str(e)}")


@router.get("/agents/{agent_id}/health")
def check_agent_health(
    agent_id: str,
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """Check agent health (availability)."""
    cfg = AgentConfigService(ctx, db=db)
    res = cfg.check_health(agent_id)
    if res.error == "Agent not found":
        logger.warning("agent_health_not_found", extra=log_extra(request_id=ctx.request_id, agent_id=agent_id))
        raise HTTPException(status_code=404, detail="Agent not found")

    warnings: list[str] = []

    # Check if agent is a CLI engine that reports available only via assume_auth
    agent_cfg = cfg.get_agent(agent_id)
    if agent_cfg and agent_cfg.is_cli:
        assume_auth = os.environ.get("DEVGODZILLA_ASSUME_AGENT_AUTH", "").lower() in (
            "1", "true", "yes", "on",
        )
        if assume_auth:
            # Check whether the real API key is present for known engines
            has_real_key = False
            aid = agent_cfg.id
            if aid == "gemini-cli":
                has_real_key = bool(
                    os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
                )
            if not has_real_key:
                warnings.append(
                    "API key not set — agent available via assume_auth only"
                )

    logger.info(
        "agent_health_checked",
        extra=log_extra(
            request_id=ctx.request_id,
            agent_id=agent_id,
            available=res.available,
            warning_count=len(warnings),
        ),
    )
    return {
        "status": "available" if res.available else "unavailable",
        "warnings": warnings,
    }


@router.post("/agents/{agent_id}/test", response_model=schemas.AgentTestOut)
def test_agent_setup(
    agent_id: str,
    req: schemas.AgentTestRequest,
    project_id: Optional[int] = Query(default=None),
    ctx: ServiceContext = Depends(get_service_context),
    db: Database = Depends(get_db),
):
    """Run a lightweight setup test for a single agent (auth/provider checks where possible)."""
    cfg = AgentConfigService(ctx, db=db)
    overrides = req.overrides.model_dump(exclude_unset=True) if req.overrides is not None else None
    res = cfg.test_setup(agent_id, project_id=project_id, overrides=overrides)
    if any((c.name == "agent" and not c.ok and c.error == "Agent not found") for c in (res.checks or [])):
        logger.warning(
            "agent_setup_test_not_found",
            extra=log_extra(request_id=ctx.request_id, project_id=project_id, agent_id=agent_id),
        )
        raise HTTPException(status_code=404, detail="Agent not found")
    logger.info(
        "agent_setup_tested",
        extra=log_extra(
            request_id=ctx.request_id,
            project_id=project_id,
            agent_id=agent_id,
            ok=res.ok,
            check_count=len(res.checks or []),
        ),
    )
    return schemas.AgentTestOut(
        agent_id=res.agent_id,
        ok=res.ok,
        duration_ms=res.duration_ms,
        checks=[
            schemas.AgentTestCheckOut(
                name=c.name,
                ok=c.ok,
                error=c.error,
                details=c.details,
            )
            for c in (res.checks or [])
        ],
    )
