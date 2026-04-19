"""
Policy Packs API Routes

Endpoints for managing policy packs.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException

from devgodzilla.api import schemas
from devgodzilla.api.dependencies import get_db, Database
from devgodzilla.logging import get_logger, log_extra

router = APIRouter(tags=["policy_packs"])
logger = get_logger(__name__)


@router.get("/policy_packs", response_model=List[schemas.PolicyPackOut])
def list_policy_packs(
    status: Optional[str] = None,
    limit: int = 100,
    db: Database = Depends(get_db),
):
    """List all policy packs."""
    packs = db.list_policy_packs(status=status, limit=limit)
    logger.info("policy_packs_listed", extra=log_extra(status=status, limit=limit, result_count=len(packs)))
    return packs


@router.get("/policy_packs/{key}", response_model=schemas.PolicyPackOut)
def get_policy_pack_latest(
    key: str,
    db: Database = Depends(get_db),
):
    """Get the latest active version of a policy pack by key."""
    try:
        pack = db.get_policy_pack(key=key, version=None)
    except KeyError:
        logger.warning("policy_pack_not_found", extra=log_extra(policy_pack_key=key))
        raise HTTPException(status_code=404, detail=f"Policy pack {key} not found")
    logger.info("policy_pack_loaded", extra=log_extra(policy_pack_key=key, version=pack.version))
    return pack


@router.get("/policy_packs/{key}/{version}", response_model=schemas.PolicyPackOut)
def get_policy_pack(
    key: str,
    version: str,
    db: Database = Depends(get_db),
):
    """Get a specific policy pack by key and version."""
    try:
        pack = db.get_policy_pack(key=key, version=version)
    except KeyError:
        logger.warning("policy_pack_version_not_found", extra=log_extra(policy_pack_key=key, version=version))
        raise HTTPException(status_code=404, detail=f"Policy pack {key}:{version} not found")
    logger.info("policy_pack_loaded", extra=log_extra(policy_pack_key=key, version=version))
    return pack


@router.post("/policy_packs", response_model=schemas.PolicyPackOut)
def create_or_update_policy_pack(
    data: schemas.PolicyPackCreate,
    db: Database = Depends(get_db),
):
    """Create or update a policy pack."""
    pack = db.upsert_policy_pack(
        key=data.key,
        version=data.version,
        name=data.name,
        description=data.description,
        status=data.status,
        pack=data.pack,
    )
    logger.info(
        "policy_pack_upserted",
        extra=log_extra(policy_pack_key=data.key, version=data.version, status=data.status),
    )
    return pack
