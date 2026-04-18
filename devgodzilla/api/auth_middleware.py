"""
JWT Authentication Middleware for DevGodzilla.

Provides FastAPI dependencies for extracting and validating JWT Bearer tokens.
- ``get_current_user`` — required auth (raises 401 on missing/invalid token)
- ``get_optional_user`` — optional auth (returns None when no token present)

Token blacklist is held in-memory via a module-level set.  For multi-process
deployments, replace with Redis / DB store.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from devgodzilla.config import get_config

_bearer_scheme = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# In-memory refresh-token blacklist (jti set)
# ---------------------------------------------------------------------------
_revoked_jtis: set[str] = set()


def revoke_token(jti: str) -> None:
    """Add a *jti* to the in-memory revocation set."""
    _revoked_jtis.add(jti)


def is_token_revoked(jti: str) -> bool:
    return jti in _revoked_jtis


def _decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT.  Raises ``HTTPException(401)`` on any error."""
    config = get_config()
    secret = config.jwt_secret or os.environ.get("DEVGODZILLA_JWT_SECRET", "")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT auth not configured",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload: Dict[str, Any] = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            issuer=config.jwt_issuer,
            options={
                "require": ["exp", "sub", "iss", "type"],
                "verify_exp": True,
                "verify_iss": True,
            },
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check revocation
    jti = payload.get("jti")
    if jti and is_token_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Only access tokens are accepted for user identification
    token_type = payload.get("type")
    if token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> Dict[str, Any]:
    """
    FastAPI dependency that **requires** a valid JWT Bearer token.

    Returns a dict with at least ``sub``, ``username``, ``role``.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _decode_token(credentials.credentials)


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> Optional[Dict[str, Any]]:
    """
    FastAPI dependency that **optionally** validates a JWT Bearer token.

    Returns ``None`` when no Authorization header is present; raises 401 if a
    token is present but invalid.
    """
    if credentials is None:
        return None
    return _decode_token(credentials.credentials)
