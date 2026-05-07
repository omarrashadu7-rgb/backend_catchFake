from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


# ── Request Models ─────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    """Payload for POST /auth/signup."""
    name: str = Field(..., min_length=2, max_length=100, description="Full name")
    email: EmailStr = Field(..., description="Unique email address")
    password: str = Field(..., min_length=8, description="Plain-text password (hashed before storage)")


class UserLogin(BaseModel):
    """Payload for POST /auth/login."""
    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., description="Plain-text password")


# ── Response Models ────────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    """Safe user representation — never exposes the hashed password."""
    id: str = Field(..., description="User MongoDB ObjectId as string")
    name: str
    email: EmailStr
    created_at: datetime

    class Config:
        populate_by_name = True


class TokenResponse(BaseModel):
    """JWT token payload returned after successful authentication."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ── Internal DB Model ──────────────────────────────────────────────────────────

class UserInDB(BaseModel):
    """Full user document as stored in MongoDB (includes hashed_password)."""
    id: str
    name: str
    email: str
    hashed_password: str
    created_at: datetime

    class Config:
        populate_by_name = True
