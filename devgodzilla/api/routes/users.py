"""
User profile API Routes — authenticated user operations.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.hash import pbkdf2_sha256
from pydantic import BaseModel, Field

from devgodzilla.api.auth_middleware import get_current_user

router = APIRouter(prefix="/users", tags=["Users"])


class UserProfile(BaseModel):
    sub: str
    username: str
    role: str = "admin"
    name: Optional[str] = None
    email: Optional[str] = None


class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6)


class ChangePasswordResponse(BaseModel):
    success: bool = True
    message: str = "Password updated"


# In-memory profile overrides (placeholder until DB-backed user store)
_profile_overrides: Dict[str, Dict[str, str]] = {}


def _verify_current_password(plain: str, hashed_or_plain: str) -> bool:
    """Verify a password against a hash, or fall back to plaintext comparison."""
    if not hashed_or_plain:
        return False
    if hashed_or_plain.startswith(("$pbkdf2", "$bcrypt", "$argon")):
        try:
            return pbkdf2_sha256.verify(plain, hashed_or_plain)
        except Exception:
            return False
    import secrets
    return secrets.compare_digest(plain, hashed_or_plain)


@router.get("/me", response_model=UserProfile)
def get_user_profile(user: Dict[str, Any] = Depends(get_current_user)):
    """Return the current authenticated user's profile."""
    sub = user.get("sub", "")
    overrides = _profile_overrides.get(sub, {})
    return UserProfile(
        sub=sub,
        username=user.get("username", ""),
        role=user.get("role", "admin"),
        name=overrides.get("name"),
        email=overrides.get("email"),
    )


@router.put("/me", response_model=UserProfile)
def update_user_profile(
    body: UserProfileUpdate,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Update the current authenticated user's profile (name, email)."""
    sub = user.get("sub", "")
    overrides = _profile_overrides.setdefault(sub, {})
    if body.name is not None:
        overrides["name"] = body.name
    if body.email is not None:
        overrides["email"] = body.email
    return UserProfile(
        sub=sub,
        username=user.get("username", ""),
        role=user.get("role", "admin"),
        name=overrides.get("name"),
        email=overrides.get("email"),
    )


@router.post("/me/password", response_model=ChangePasswordResponse)
def change_password(
    body: ChangePasswordRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Change the current authenticated user's password."""
    from devgodzilla.config import get_config

    config = get_config()
    password_hash = (
        config.admin_password_hash
        or config.admin_password
        or os.environ.get("DEVGODZILLA_ADMIN_PASSWORD", "")
    )

    if not password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password management not configured",
        )

    if not _verify_current_password(body.current_password, password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    new_hash = pbkdf2_sha256.hash(body.new_password)

    # Update in-memory config / env — until a persistent user store exists
    # we update the runtime config object so subsequent logins use the new hash.
    config.admin_password_hash = new_hash
    # Clear the plaintext fallback so the hash is always preferred
    config.admin_password = None

    return ChangePasswordResponse()
