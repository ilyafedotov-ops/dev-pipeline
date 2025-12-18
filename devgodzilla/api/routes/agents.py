from typing import List
from fastapi import APIRouter, Depends, HTTPException

from devgodzilla.api import schemas
from devgodzilla.api.dependencies import get_service_context
from devgodzilla.engines.registry import get_registry
from devgodzilla.services.agent_config import AgentConfigService
from devgodzilla.services.base import ServiceContext

router = APIRouter()

@router.get("/agents", response_model=List[schemas.AgentInfo])
def list_agents(ctx: ServiceContext = Depends(get_service_context)):
    """List available agents."""
    # Prefer YAML-configured agents (stable list even when engines are not registered).
    cfg = AgentConfigService(ctx)
    agents = [
        schemas.AgentInfo(
            id=a.id,
            name=a.name,
            kind=a.kind,
            capabilities=a.capabilities,
            status="available" if a.enabled else "unavailable",
            default_model=a.default_model,
            command_dir=a.command_dir,
        )
        for a in cfg.list_agents(enabled_only=False)
    ]

    # Fallback to registry metadata if config is empty.
    if agents:
        return agents

    registry = get_registry()
    return [
        schemas.AgentInfo(
            id=meta.id,
            name=meta.display_name,
            kind=meta.kind.value if hasattr(meta.kind, "value") else str(meta.kind),
            capabilities=meta.capabilities,
            status="available",
        )
        for meta in registry.list_metadata()
    ]


@router.get("/agents/{agent_id}", response_model=schemas.AgentInfo)
def get_agent(agent_id: str, ctx: ServiceContext = Depends(get_service_context)):
    """Get agent details by ID."""
    cfg = AgentConfigService(ctx)
    agent = cfg.get_agent(agent_id)
    if agent:
        return schemas.AgentInfo(
            id=agent.id,
            name=agent.name,
            kind=agent.kind,
            capabilities=agent.capabilities,
            status="available" if agent.enabled else "unavailable",
            default_model=agent.default_model,
            command_dir=agent.command_dir,
        )

    registry = get_registry()
    meta = next((m for m in registry.list_metadata() if m.id == agent_id), None)
    if meta is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return schemas.AgentInfo(
        id=meta.id,
        name=meta.display_name,
        kind=meta.kind.value if hasattr(meta.kind, "value") else str(meta.kind),
        capabilities=meta.capabilities,
        status="available",
    )


@router.get("/agents/{agent_id}/health")
def check_agent_health(agent_id: str, ctx: ServiceContext = Depends(get_service_context)):
    """Check agent health (availability)."""
    cfg = AgentConfigService(ctx)
    res = cfg.check_health(agent_id)
    if res.error == "Agent not found":
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "available" if res.available else "unavailable"}


@router.put("/agents/{agent_id}/config", response_model=schemas.AgentInfo)
def update_agent_config(
    agent_id: str,
    config: schemas.AgentConfigUpdate,
    ctx: ServiceContext = Depends(get_service_context)
):
    """Update agent configuration."""
    cfg = AgentConfigService(ctx)
    try:
        updated_agent = cfg.update_config(
            agent_id=agent_id,
            enabled=config.enabled,
            default_model=config.default_model,
            capabilities=config.capabilities,
            command_dir=config.command_dir,
        )
        return schemas.AgentInfo(
            id=updated_agent.id,
            name=updated_agent.name,
            kind=updated_agent.kind,
            capabilities=updated_agent.capabilities,
            status="available" if updated_agent.enabled else "unavailable",
            default_model=updated_agent.default_model,
            command_dir=updated_agent.command_dir,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update agent config: {str(e)}")
