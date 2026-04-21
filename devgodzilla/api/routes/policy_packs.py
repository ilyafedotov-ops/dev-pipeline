"""
Policy Packs API Routes

Endpoints for managing policy packs.
"""
from copy import deepcopy
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException

from devgodzilla.api import schemas
from devgodzilla.api.dependencies import get_db, Database
from devgodzilla.logging import get_logger, log_extra
from devgodzilla.policy_catalog import is_builtin_policy_pack_key

router = APIRouter(tags=["policy_packs"])
logger = get_logger(__name__)


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


@router.get("/policy_packs", response_model=List[schemas.PolicyPackOut])
def list_policy_packs(
    status: Optional[str] = None,
    key: Optional[str] = None,
    limit: int = 100,
    db: Database = Depends(get_db),
):
    """List all policy packs."""
    packs = db.list_policy_packs(status=status, key=key, limit=limit)
    logger.info(
        "policy_packs_listed",
        extra=log_extra(status=status, key=key, limit=limit, result_count=len(packs)),
    )
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
    if is_builtin_policy_pack_key(data.key):
        raise HTTPException(
            status_code=409,
            detail=f"Policy pack key {data.key} is reserved for built-in presets. Clone it into a new key instead.",
        )

    pack = db.upsert_policy_pack(
        key=data.key,
        version=data.version,
        name=data.name,
        description=data.description,
        status=data.status,
        is_builtin=False,
        pack=data.pack,
    )
    logger.info(
        "policy_pack_upserted",
        extra=log_extra(policy_pack_key=data.key, version=data.version, status=data.status),
    )
    return pack


@router.post("/policy_packs/{key}/{version}/clone", response_model=schemas.PolicyPackOut)
def clone_policy_pack(
    key: str,
    version: str,
    data: schemas.PolicyPackCloneRequest,
    db: Database = Depends(get_db),
):
    """Clone an existing policy pack into a new custom key/version."""
    if is_builtin_policy_pack_key(data.key):
        raise HTTPException(
            status_code=409,
            detail=f"Policy pack key {data.key} is reserved for built-in presets. Choose a new custom key.",
        )

    try:
        source = db.get_policy_pack(key=key, version=version)
    except KeyError:
        logger.warning("policy_pack_clone_source_missing", extra=log_extra(policy_pack_key=key, version=version))
        raise HTTPException(status_code=404, detail=f"Policy pack {key}:{version} not found")

    cloned_pack = deepcopy(source.pack)
    if data.pack_overrides:
        cloned_pack = _deep_merge(cloned_pack, data.pack_overrides)

    meta = cloned_pack.get("meta")
    if not isinstance(meta, dict):
        meta = {}
    meta["key"] = data.key
    meta["version"] = data.version
    if source.is_builtin:
        meta.pop("classification", None)
    cloned_pack["meta"] = meta

    cloned = db.upsert_policy_pack(
        key=data.key,
        version=data.version,
        name=data.name,
        description=data.description,
        status=data.status,
        is_builtin=False,
        pack=cloned_pack,
    )
    logger.info(
        "policy_pack_cloned",
        extra=log_extra(
            source_key=key,
            source_version=version,
            policy_pack_key=data.key,
            target_version=data.version,
        ),
    )
    return cloned
