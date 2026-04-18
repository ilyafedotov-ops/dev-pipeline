"""
User profile API Routes — authenticated user operations.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

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


# In-memory profile overrides (placeholder until DB-backed user store)
_profile_overrides: Dict[str, Dict[str, str]] = {}


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
