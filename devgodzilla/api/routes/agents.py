from typing import List
from fastapi import APIRouter, Depends, HTTPException

from devgodzilla.api import schemas
from devgodzilla.engines.registry import get_registry

router = APIRouter()

@router.get("/agents", response_model=List[schemas.AgentInfo])
def list_agents():
    """List available agents."""
    registry = get_registry()
    agents = []
    
    # Use real registry metadata if populated
    # In a real app, engines are registered at startup.
    # If standard engines are not auto-registered in this context, the list might be empty.
    # For now, we trust list_metadata() returns what's registered.
    
    for meta in registry.list_metadata():
        agents.append(schemas.AgentInfo(
            id=meta.id,
            name=meta.display_name,
            kind=meta.kind.value if hasattr(meta.kind, 'value') else str(meta.kind),
            capabilities=meta.capabilities,
            status="available" # Health check logic can go here
        ))
        
    return agents
