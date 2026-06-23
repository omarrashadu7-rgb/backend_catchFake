"""
routers/admin_router.py
───────────────────────
Admin-only endpoints — all routes require an active JWT whose user role == 'admin'.

Endpoints:
    GET    /admin/users                    — list all users with upload counts
    DELETE /admin/users/{user_id}          — delete a regular user + their uploads
    POST   /admin/users/{user_id}/promote  — promote a user to admin role
    GET    /admin/logs                     — browse activity logs (filterable)
    GET    /admin/logs/stats               — aggregate dashboard statistics
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status

from app.core.security import get_current_admin
from app.models.user import UserInDB
from app.services.admin_service import AdminService, get_admin_service
from app.utils.response_handler import success_response

router = APIRouter(prefix="/admin", tags=["Admin"])


# ── Users ──────────────────────────────────────────────────────────────────────

@router.get(
    "/users",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="List all users",
    description=(
        "**Admin only.** Returns every registered user together with their "
        "total upload count, sorted by registration date (newest first)."
    ),
)
async def list_users(
    admin: UserInDB = Depends(get_current_admin),
    service: AdminService = Depends(get_admin_service),
):
    users = await service.get_all_users()
    return success_response(
        data=[u.model_dump() for u in users],
        message=f"Retrieved {len(users)} users.",
    )


@router.delete(
    "/users/{user_id}",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Delete a regular user",
    description=(
        "**Admin only.** Permanently removes the specified user and all their "
        "uploaded files from the database. Cannot delete other admin accounts."
    ),
)
async def delete_user(
    user_id: str,
    request: Request,
    admin: UserInDB = Depends(get_current_admin),
    service: AdminService = Depends(get_admin_service),
):
    ip = request.client.host if request.client else None
    result = await service.delete_user(
        target_user_id=user_id,
        admin_user_id=admin.id,
        admin_email=admin.email,
        admin_name=admin.name,
        ip_address=ip,
    )
    return success_response(
        data=result,
        message=f"User {user_id} deleted successfully.",
    )


@router.post(
    "/users/{user_id}/promote",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Promote user to admin",
    description=(
        "**Admin only.** Grants admin role to a regular user, giving them "
        "access to all admin endpoints."
    ),
)
async def promote_user(
    user_id: str,
    request: Request,
    admin: UserInDB = Depends(get_current_admin),
    service: AdminService = Depends(get_admin_service),
):
    ip = request.client.host if request.client else None
    promoted = await service.promote_user(
        target_user_id=user_id,
        admin_user_id=admin.id,
        admin_email=admin.email,
        admin_name=admin.name,
        ip_address=ip,
    )
    return success_response(
        data=promoted.model_dump(),
        message=f"User {user_id} promoted to admin.",
    )


# ── Logs ───────────────────────────────────────────────────────────────────────

@router.get(
    "/logs",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Browse activity logs",
    description=(
        "**Admin only.** Returns activity logs with optional filters. "
        "Results are sorted newest-first and capped at 500 per request.\n\n"
        "**Available `action` values:** "
        "`signup`, `login`, `logout`, `upload_image`, `upload_video`, "
        "`delete_user`, `promote_user`"
    ),
)
async def get_logs(
    action: Optional[str] = Query(None, description="Filter by action type"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    limit: int = Query(50, ge=1, le=500, description="Number of records to return"),
    skip: int = Query(0, ge=0, description="Number of records to skip (pagination)"),
    admin: UserInDB = Depends(get_current_admin),
    service: AdminService = Depends(get_admin_service),
):
    logs = await service.get_activity_logs(
        action_filter=action,
        user_id_filter=user_id,
        limit=limit,
        skip=skip,
    )
    return success_response(
        data=[log.model_dump() for log in logs],
        message=f"Retrieved {len(logs)} log entries.",
    )


@router.get(
    "/logs/stats",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Activity & usage statistics",
    description=(
        "**Admin only.** Returns aggregate counts for users, uploads, "
        "logins, signups, and admin deletions."
    ),
)
async def get_stats(
    admin: UserInDB = Depends(get_current_admin),
    service: AdminService = Depends(get_admin_service),
):
    stats = await service.get_stats()
    return success_response(
        data=stats.model_dump(),
        message="Statistics retrieved successfully.",
    )
