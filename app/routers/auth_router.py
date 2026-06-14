from fastapi import APIRouter, Depends, status
from app.services.auth_service import AuthService, get_auth_service
from app.models.user import UserCreate, UserLogin, RefreshTokenRequest
from app.utils.response_handler import success_response

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/signup",
    response_model=None,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description=(
        "Create a new account with **name**, **email**, and **password**. "
        "The password is hashed with bcrypt before storage. "
        "Returns a JWT access token on success."
    ),
)
async def signup(payload: UserCreate, service: AuthService = Depends(get_auth_service)):
    token_data = await service.signup(payload)
    return success_response(
        data=token_data.model_dump(),
        message="Account created successfully.",
    )


@router.post(
    "/login",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and obtain a JWT",
    description=(
        "Login with a registered **email** and **password**. "
        "Returns a signed JWT access token valid for the configured TTL."
    ),
)
async def login(payload: UserLogin, service: AuthService = Depends(get_auth_service)):
    token_data = await service.login(payload)
    return success_response(
        data=token_data.model_dump(),
        message="Login successful.",
    )


@router.post(
    "/refresh",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Refresh JWT tokens",
    description="Rotate refresh token and return a new access token.",
)
async def refresh(payload: RefreshTokenRequest, service: AuthService = Depends(get_auth_service)):
    token_data = await service.refresh(payload.refresh_token)
    return success_response(
        data=token_data.model_dump(),
        message="Token refreshed successfully.",
    )


@router.post(
    "/logout",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Logout and revoke refresh token",
    description="Invalidate the refresh token for the current session.",
)
async def logout(payload: RefreshTokenRequest, service: AuthService = Depends(get_auth_service)):
    await service.revoke_refresh_token(payload.refresh_token)
    return success_response(
        data=None,
        message="Logged out successfully.",
    )
