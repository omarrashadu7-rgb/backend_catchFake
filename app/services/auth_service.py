from datetime import datetime, timezone, timedelta
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from pymongo.database import Database

from app.models.user import UserCreate, UserLogin, UserInDB, UserResponse, TokenResponse
from app.core.config import get_settings

settings = get_settings()

# ── Password hashing ───────────────────────────────────────────────────────────
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return bcrypt hash of *plain* password."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches the stored *hashed* password."""
    return _pwd_context.verify(plain, hashed)


# ── JWT helpers ────────────────────────────────────────────────────────────────

def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Build a signed JWT whose *sub* claim is the user's string ID.

    Args:
        subject: The unique identifier to embed (user ObjectId string).
        expires_delta: Custom TTL; defaults to settings.jwt_expire_minutes.
    """
    delta = expires_delta or timedelta(minutes=settings.jwt_expire_minutes)
    expire = datetime.now(timezone.utc) + delta
    payload = {"sub": subject, "exp": expire, "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    """
    Decode and validate a JWT, returning the *sub* claim (user ID).

    Raises:
        HTTPException 401 if the token is invalid or expired.
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exc
        return user_id
    except JWTError:
        raise credentials_exc


# ── MongoDB helpers ────────────────────────────────────────────────────────────

def _serialize_user(doc: dict) -> dict:
    """Convert a raw MongoDB user document to a flat Python dict."""
    doc["id"] = str(doc.pop("_id"))
    return doc


def _get_user_by_email(db: Database, email: str) -> Optional[dict]:
    return db["users"].find_one({"email": email.lower()})


def _get_user_by_id(db: Database, user_id: str) -> Optional[dict]:
    try:
        oid = ObjectId(user_id)
    except InvalidId:
        return None
    return db["users"].find_one({"_id": oid})


# ── Auth Service ───────────────────────────────────────────────────────────────

class AuthService:
    def __init__(self, db: Database):
        self.db = db
        self.users = db["users"]

    # ── Signup ─────────────────────────────────────────────────────────────────
    def signup(self, payload: UserCreate) -> TokenResponse:
        """
        Register a new user.

        Raises:
            409 if the email is already taken.
        """
        email = payload.email.lower()

        if self.users.find_one({"email": email}):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Email '{email}' is already registered.",
            )

        now = datetime.now(timezone.utc)
        doc = {
            "name": payload.name.strip(),
            "email": email,
            "hashed_password": hash_password(payload.password),
            "created_at": now,
        }

        result = self.users.insert_one(doc)
        doc["_id"] = result.inserted_id

        serialized = _serialize_user(doc)
        user_resp = UserResponse(
            id=serialized["id"],
            name=serialized["name"],
            email=serialized["email"],
            created_at=serialized["created_at"],
        )
        token = create_access_token(subject=user_resp.id)
        return TokenResponse(access_token=token, user=user_resp)

    # ── Login ──────────────────────────────────────────────────────────────────
    def login(self, payload: UserLogin) -> TokenResponse:
        """
        Authenticate a user by email/password.

        Raises:
            401 if credentials are invalid (intentionally vague for security).
        """
        email = payload.email.lower()
        doc = self.users.find_one({"email": email})

        if not doc or not verify_password(payload.password, doc["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        serialized = _serialize_user(doc)
        user_resp = UserResponse(
            id=serialized["id"],
            name=serialized["name"],
            email=serialized["email"],
            created_at=serialized["created_at"],
        )
        token = create_access_token(subject=user_resp.id)
        return TokenResponse(access_token=token, user=user_resp)

    # ── Fetch current user ─────────────────────────────────────────────────────
    def get_user_by_id(self, user_id: str) -> Optional[UserInDB]:
        doc = _get_user_by_id(self.db, user_id)
        if not doc:
            return None
        s = _serialize_user(doc)
        return UserInDB(**s)


def get_auth_service() -> AuthService:
    """FastAPI dependency that provides a ready-to-use AuthService."""
    from app.database.mongodb import get_database
    return AuthService(get_database())
