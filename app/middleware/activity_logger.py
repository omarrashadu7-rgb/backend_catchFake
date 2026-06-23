"""
middleware/activity_logger.py
──────────────────────────────
Shared helper for writing Activity Log documents to MongoDB.

Usage (in any service):
    from app.middleware.activity_logger import log_activity
    from app.models.admin import ActivityAction

    await log_activity(
        db=self.db,
        user_id=user.id,
        user_email=user.email,
        user_name=user.name,
        action=ActivityAction.LOGIN,
        details={"ip": "1.2.3.4"},
        ip_address=request.client.host,
    )
"""

from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.admin import ActivityAction
from app.core.logging_config import get_logger

logger = get_logger(__name__)


async def log_activity(
    db: AsyncIOMotorDatabase,
    user_id: str,
    user_email: str,
    user_name: str,
    action: ActivityAction,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> None:
    """
    Insert a single activity log document into the ``activity_logs`` collection.
    Failures are swallowed so a logging error never breaks the main request.
    """
    try:
        doc = {
            "user_id":    user_id,
            "user_email": user_email,
            "user_name":  user_name,
            "action":     action.value,
            "details":    details or {},
            "ip_address": ip_address,
            "timestamp":  datetime.now(timezone.utc),
        }
        await db["activity_logs"].insert_one(doc)
        logger.debug(f"[ActivityLog] {action.value} — user={user_email}")
    except Exception as exc:
        logger.error(f"[ActivityLog] Failed to write log: {exc}", exc_info=True)
