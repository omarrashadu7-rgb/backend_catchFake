from fastapi import APIRouter, Depends, status
from app.services.auth_service import AuthService, get_auth_service
from app.models.user import UserCreate, UserLogin, TokenResponse
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
