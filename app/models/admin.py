"""
models/admin.py
───────────────
Pydantic models for the Admin panel and Activity Logging system.
"""

from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
from enum import Enum


# ── Action Types ────────────────────────────────────────────────────────────────

class ActivityAction(str, Enum):
    """All loggable activity types in the system."""
    SIGNUP          = "signup"
    LOGIN           = "login"
    LOGOUT          = "logout"
    UPLOAD_IMAGE    = "upload_image"
    UPLOAD_VIDEO    = "upload_video"
    DELETE_USER     = "delete_user"
    PROMOTE_USER    = "promote_user"


# ── Activity Log ────────────────────────────────────────────────────────────────

class ActivityLogCreate(BaseModel):
    """Internal model used when inserting a log document into MongoDB."""
    user_id: str
    user_email: str
    user_name: str
    action: ActivityAction
    details: Optional[dict] = None          # e.g. filename, prediction, target_user_id
    ip_address: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.utcnow())


class ActivityLogResponse(BaseModel):
    """Safe log representation returned to the admin."""
    id: str
    user_id: str
    user_email: str
    user_name: str
    action: str
    details: Optional[dict] = None
    ip_address: Optional[str] = None
    timestamp: datetime

    class Config:
        populate_by_name = True


# ── Admin User Views ─────────────────────────────────────────────────────────────

class AdminUserResponse(BaseModel):
    """Enriched user document returned in admin user-listing."""
    id: str
    name: str
    email: str
    role: str
    created_at: datetime
    upload_count: int = 0                  # total uploads by this user

    class Config:
        populate_by_name = True


# ── Log Stats ────────────────────────────────────────────────────────────────────

class ActivityStatsResponse(BaseModel):
    """Aggregate statistics shown on the admin dashboard."""
    total_users: int = 0
    total_admins: int = 0
    total_uploads: int = 0
    total_images: int = 0
    total_videos: int = 0
    total_logins: int = 0
    total_signups: int = 0
    total_deletions: int = 0
