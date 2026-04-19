"""
Profile API Routes

User profile endpoints (placeholder until full auth integration).
"""
import os
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends
from typing import List

from devgodzilla.api.dependencies import get_db, Database
from devgodzilla.logging import get_logger, log_extra

router = APIRouter(tags=["profile"])
logger = get_logger(__name__)


class ActivityItem(BaseModel):
    id: str
    action: str
    target: str
    time: str
    icon: str = "activity"


class UserProfile(BaseModel):
    id: str
    name: str
    email: str
    role: str = "admin"
    member_since: str = "Jan 2024"
    activity: List[ActivityItem] = Field(default_factory=list)


@router.get("/profile", response_model=UserProfile)
def get_user_profile(
    db: Database = Depends(get_db),
):
    """
    Get current user profile.
    
    Note: This is a placeholder until full authentication is implemented.
    Returns activity based on recent events.
    """
    # Get recent events for activity
    events = db.list_recent_events(limit=10)
    
    activity = []
    for i, event in enumerate(events[:4]):
        activity.append(ActivityItem(
            id=str(i + 1),
            action=event.event_type.replace("_", " ").title(),
            target=event.message[:50] if event.message else event.event_type,
            time=event.created_at or "recently",
            icon="activity",
        ))
    
    profile = UserProfile(
        id=os.getenv("DEVGODZILLA_USER_ID", "default-user"),
        name=os.getenv("DEVGODZILLA_USER_NAME", "DevGodzilla User"),
        email=os.getenv("DEVGODZILLA_USER_EMAIL", "user@devgodzilla.dev"),
        role=os.getenv("DEVGODZILLA_USER_ROLE", "admin"),
        member_since=os.getenv("DEVGODZILLA_USER_MEMBER_SINCE", "Dec 2024"),
        activity=activity,
    )
    logger.info("profile_loaded", extra=log_extra(user_id=profile.id, activity_count=len(activity)))
    return profile
