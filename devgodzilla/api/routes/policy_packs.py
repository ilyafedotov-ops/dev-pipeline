"""
Policy Packs API Routes

Endpoints for managing policy packs.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException

from devgodzilla.api import schemas
from devgodzilla.api.dependencies import get_db, Database

router = APIRouter(tags=["policy_packs"])


@router.get("/policy_packs", response_model=List[schemas.PolicyPackOut])
def list_policy_packs(
    status: Optional[str] = None,
    limit: int = 100,
    db: Database = Depends(get_db),
):
    """List all policy packs."""
    return db.list_policy_packs(status=status, limit=limit)


@router.get("/policy_packs/{key}/{version}", response_model=schemas.PolicyPackOut)
def get_policy_pack(
    key: str,
    version: str,
    db: Database = Depends(get_db),
):
    """Get a specific policy pack by key and version."""
    try:
        return db.get_policy_pack(key=key, version=version)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Policy pack {key}:{version} not found")


@router.post("/policy_packs", response_model=schemas.PolicyPackOut)
def create_or_update_policy_pack(
    data: schemas.PolicyPackCreate,
    db: Database = Depends(get_db),
):
    """Create or update a policy pack."""
    return db.upsert_policy_pack(
        key=data.key,
        version=data.version,
        name=data.name,
        description=data.description,
        status=data.status,
        pack=data.pack,
    )
