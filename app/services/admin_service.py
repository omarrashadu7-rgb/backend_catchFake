"""
services/admin_service.py
──────────────────────────
Business logic for admin-only operations:
  - List all users (with upload counts)
  - Delete a regular user and all their uploads
  - Promote a user to admin
  - Fetch and filter activity logs
  - Aggregate stats for the admin dashboard
"""

from typing import List, Optional
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.admin import (
    AdminUserResponse,
    ActivityLogResponse,
    ActivityStatsResponse,
    ActivityAction,
)
from app.middleware.activity_logger import log_activity
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def _serialize_log(doc: dict) -> dict:
    """Convert a raw MongoDB log document to a flat Python dict."""
    doc["id"] = str(doc.pop("_id"))
    return doc


def _serialize_user(doc: dict) -> dict:
    """Convert a raw MongoDB user document to a flat Python dict."""
    doc["id"] = str(doc.pop("_id"))
    if not doc.get("role"):
        doc["role"] = "user"
    return doc


class AdminService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.users = db["users"]
        self.uploads = db["uploads"]
        self.logs = db["activity_logs"]

    # ── Users ──────────────────────────────────────────────────────────────────

    async def get_all_users(self) -> List[AdminUserResponse]:
        """
        Return all users (both regular and admin) with their upload count.
        Sorted by creation date descending.
        """
        cursor = self.users.find({}).sort("created_at", -1)
        docs = await cursor.to_list(length=1000)

        result = []
        for doc in docs:
            s = _serialize_user(doc)
            user_id = s["id"]
            upload_count = await self.uploads.count_documents({"user_id": user_id})
            result.append(
                AdminUserResponse(
                    id=user_id,
                    name=s["name"],
                    email=s["email"],
                    role=s.get("role", "user"),
                    created_at=s["created_at"],
                    upload_count=upload_count,
                )
            )
        return result

    async def delete_user(
        self,
        target_user_id: str,
        admin_user_id: str,
        admin_email: str,
        admin_name: str,
        ip_address: Optional[str] = None,
    ) -> dict:
        """
        Permanently delete a regular user and all their uploads.

        Raises:
            404 — if the target user does not exist.
            403 — if trying to delete an admin account.
            400 — if trying to self-delete.
        """
        if target_user_id == admin_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot delete your own admin account.",
            )

        try:
            oid = ObjectId(target_user_id)
        except InvalidId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format.",
            )

        target_doc = await self.users.find_one({"_id": oid})
        if not target_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        if target_doc.get("role") == "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete another admin account.",
            )

        # Delete all uploads belonging to this user
        uploads_result = await self.uploads.delete_many({"user_id": target_user_id})
        logger.info(
            f"[Admin] Deleted {uploads_result.deleted_count} uploads "
            f"for user {target_user_id}"
        )

        # Delete the user document
        await self.users.delete_one({"_id": oid})
        logger.info(f"[Admin] User {target_user_id} deleted by admin {admin_user_id}")

        # Log the action
        await log_activity(
            db=self.db,
            user_id=admin_user_id,
            user_email=admin_email,
            user_name=admin_name,
            action=ActivityAction.DELETE_USER,
            details={
                "deleted_user_id":    target_user_id,
                "deleted_user_email": target_doc.get("email"),
                "deleted_user_name":  target_doc.get("name"),
                "uploads_removed":    uploads_result.deleted_count,
            },
            ip_address=ip_address,
        )

        return {
            "deleted_user_id":    target_user_id,
            "deleted_user_email": target_doc.get("email"),
            "uploads_removed":    uploads_result.deleted_count,
        }

    async def promote_user(
        self,
        target_user_id: str,
        admin_user_id: str,
        admin_email: str,
        admin_name: str,
        ip_address: Optional[str] = None,
    ) -> AdminUserResponse:
        """
        Promote a regular user to admin role.

        Raises:
            404 — if the target user does not exist.
            400 — if the user is already an admin.
        """
        try:
            oid = ObjectId(target_user_id)
        except InvalidId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format.",
            )

        target_doc = await self.users.find_one({"_id": oid})
        if not target_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        if target_doc.get("role") == "admin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already an admin.",
            )

        await self.users.update_one({"_id": oid}, {"$set": {"role": "admin"}})
        logger.info(f"[Admin] User {target_user_id} promoted to admin by {admin_user_id}")

        # Log the action
        await log_activity(
            db=self.db,
            user_id=admin_user_id,
            user_email=admin_email,
            user_name=admin_name,
            action=ActivityAction.PROMOTE_USER,
            details={
                "promoted_user_id":    target_user_id,
                "promoted_user_email": target_doc.get("email"),
                "promoted_user_name":  target_doc.get("name"),
            },
            ip_address=ip_address,
        )

        upload_count = await self.uploads.count_documents({"user_id": target_user_id})
        return AdminUserResponse(
            id=target_user_id,
            name=target_doc["name"],
            email=target_doc["email"],
            role="admin",
            created_at=target_doc["created_at"],
            upload_count=upload_count,
        )

    # ── Activity Logs ──────────────────────────────────────────────────────────

    async def get_activity_logs(
        self,
        action_filter: Optional[str] = None,
        user_id_filter: Optional[str] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> List[ActivityLogResponse]:
        """
        Return activity logs with optional filters.

        Args:
            action_filter:  Filter by action type (e.g. "login", "upload_image").
            user_id_filter: Filter by a specific user's ID.
            limit:          Maximum number of records to return (max 500).
            skip:           Offset for pagination.
        """
        query: dict = {}
        if action_filter:
            query["action"] = action_filter
        if user_id_filter:
            query["user_id"] = user_id_filter

        limit = min(limit, 500)  # Hard cap
        cursor = self.logs.find(query).sort("timestamp", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)

        return [ActivityLogResponse(**_serialize_log(doc)) for doc in docs]

    # ── Stats ──────────────────────────────────────────────────────────────────

    async def get_stats(self) -> ActivityStatsResponse:
        """Aggregate dashboard statistics from users, uploads, and logs."""
        total_users   = await self.users.count_documents({"role": {"$ne": "admin"}})
        total_admins  = await self.users.count_documents({"role": "admin"})
        total_uploads = await self.uploads.count_documents({})
        total_images  = await self.uploads.count_documents({"file_type": "image"})
        total_videos  = await self.uploads.count_documents({"file_type": "video"})
        total_logins  = await self.logs.count_documents({"action": "login"})
        total_signups = await self.logs.count_documents({"action": "signup"})
        total_deletes = await self.logs.count_documents({"action": "delete_user"})

        return ActivityStatsResponse(
            total_users=total_users,
            total_admins=total_admins,
            total_uploads=total_uploads,
            total_images=total_images,
            total_videos=total_videos,
            total_logins=total_logins,
            total_signups=total_signups,
            total_deletions=total_deletes,
        )


async def get_admin_service() -> AdminService:
    """FastAPI dependency that provides a ready-to-use AdminService."""
    from app.database.mongodb import get_db
    return AdminService(await get_db())
