"""
core/security.py
────────────────
FastAPI dependency for JWT-based request authentication.

Usage in any protected endpoint:
    from core.security import get_current_user
    from models.user import UserInDB

    @router.get("/me")
    def me(current_user: UserInDB = Depends(get_current_user)):
        return {"id": current_user.id, "email": current_user.email}
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.models.user import UserInDB
from app.services.auth_service import AuthService, get_auth_service, decode_access_token

# Tells FastAPI to look for "Authorization: Bearer <token>" in request headers.
# auto_error=True means FastAPI will return 403 automatically if the header is missing.
_bearer_scheme = HTTPBearer(auto_error=True)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    service: AuthService = Depends(get_auth_service),
) -> UserInDB:
    """
    Auth middleware / dependency.

    Validates the Bearer JWT, extracts the user ID from the *sub* claim,
    fetches the matching user from MongoDB, and returns a ``UserInDB`` instance.

    Raises:
        401  — token is missing, malformed, or expired
        401  — token belongs to a user that no longer exists in the DB
    """
    user_id = decode_access_token(credentials.credentials)

    user = service.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with this token no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
