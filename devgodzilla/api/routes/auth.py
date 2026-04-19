"""
Auth API Routes — JWT-based authentication for DevGodzilla.

Endpoints:
- POST /auth/login     — username/password → {access_token, refresh_token}
- POST /auth/refresh   — refresh_token → new access_token
- GET  /auth/me        — current user info (requires Bearer token)
- POST /auth/logout    — revoke refresh token
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from passlib.hash import pbkdf2_sha256
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field

from devgodzilla.api.auth_middleware import get_current_user, revoke_token
from devgodzilla.config import get_config
from devgodzilla.logging import get_logger

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserInfo(BaseModel):
    sub: str
    username: str
    role: str = "admin"


class LogoutResponse(BaseModel):
    message: str = "Logged out"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_secret() -> str:
    config = get_config()
    secret = config.jwt_secret or os.environ.get("DEVGODZILLA_JWT_SECRET", "")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT secret not configured",
        )
    return secret


def _verify_password(plain: str, hashed_or_plain: str) -> bool:
    """Verify a password against a hash, or fall back to plaintext comparison."""
    if not hashed_or_plain:
        return False
    # If it looks like a passlib hash, verify against it
    if hashed_or_plain.startswith(("$pbkdf2", "$bcrypt", "$argon")):
        try:
            return pbkdf2_sha256.verify(plain, hashed_or_plain)
        except Exception:
            return False
    # Fallback: plaintext comparison (dev mode)
    return secrets.compare_digest(plain, hashed_or_plain)


def _create_access_token(sub: str, username: str, role: str = "admin") -> str:
    config = get_config()
    secret = _get_secret()
    now = datetime.now(timezone.utc)
    ttl = timedelta(seconds=config.jwt_access_ttl_seconds)
    payload = {
        "iss": config.jwt_issuer,
        "sub": sub,
        "username": username,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _create_refresh_token(sub: str, username: str, role: str = "admin") -> str:
    config = get_config()
    secret = _get_secret()
    now = datetime.now(timezone.utc)
    ttl = timedelta(seconds=config.jwt_refresh_ttl_seconds)
    jti = secrets.token_urlsafe(32)
    payload = {
        "iss": config.jwt_issuer,
        "sub": sub,
        "username": username,
        "role": role,
        "type": "refresh",
        "jti": jti,
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    """
    Authenticate with username/password and receive JWT tokens.
    """
    config = get_config()
    expected_username = config.admin_username or os.environ.get("DEVGODZILLA_ADMIN_USERNAME", "")
    password_hash = config.admin_password_hash or config.admin_password or os.environ.get("DEVGODZILLA_ADMIN_PASSWORD", "")

    if not expected_username or not password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication not configured",
        )

    if not secrets.compare_digest(body.username, expected_username):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not _verify_password(body.password, password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    sub = f"user:{body.username}"
    access_token = _create_access_token(sub=sub, username=body.username)
    refresh_token = _create_refresh_token(sub=sub, username=body.username)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=RefreshResponse)
def refresh_token(body: RefreshRequest):
    """
    Exchange a valid refresh token for a new access token.
    """
    config = get_config()
    secret = _get_secret()

    try:
        payload = jwt.decode(
            body.refresh_token,
            secret,
            algorithms=["HS256"],
            issuer=config.jwt_issuer,
            options={
                "require": ["exp", "sub", "iss", "type", "jti"],
                "verify_exp": True,
                "verify_iss": True,
            },
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid refresh token: {exc}",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    from devgodzilla.api.auth_middleware import is_token_revoked
    jti = payload.get("jti", "")
    if is_token_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revoked",
        )

    access_token = _create_access_token(
        sub=payload["sub"],
        username=payload.get("username", ""),
        role=payload.get("role", "admin"),
    )

    return RefreshResponse(access_token=access_token)


@router.get("/me", response_model=UserInfo)
def get_me(user: Dict[str, Any] = Depends(get_current_user)):
    """
    Return current user info from the JWT.
    """
    return UserInfo(
        sub=user.get("sub", ""),
        username=user.get("username", ""),
        role=user.get("role", "admin"),
    )


@router.post("/logout", response_model=LogoutResponse)
def logout(body: RefreshRequest):
    """
    Revoke a refresh token so it can no longer be used.
    """
    config = get_config()
    secret = _get_secret()

    try:
        payload = jwt.decode(
            body.refresh_token,
            secret,
            algorithms=["HS256"],
            issuer=config.jwt_issuer,
            options={
                "require": ["exp", "sub", "iss", "type"],
                "verify_exp": False,  # allow expired tokens to be revoked
                "verify_iss": True,
            },
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid refresh token: {exc}",
        )

    jti = payload.get("jti")
    if jti:
        revoke_token(jti)

    return LogoutResponse()
