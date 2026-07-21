"""
SmartHire AI — User & Auth Pydantic Schemas
"""

import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── User Schemas ──────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    """Schema for user registration."""
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255, strip_whitespace=True)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Enforce: at least one uppercase, one lowercase, one digit."""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v

    @field_validator("full_name")
    @classmethod
    def full_name_no_script(cls, v: str) -> str:
        """Basic XSS prevention on name field."""
        if "<" in v or ">" in v:
            raise ValueError("Name contains invalid characters")
        return v


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str = Field(min_length=1)


class UserResponse(BaseModel):
    """Schema for user data returned from API."""
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """Schema for updating user profile."""
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    current_password: Optional[str] = None
    new_password: Optional[str] = Field(None, min_length=8, max_length=128)


# ── Token Schemas ─────────────────────────────────────────────────────────────

class Token(BaseModel):
    """Response schema for login — contains both tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token TTL in seconds")


class TokenRefresh(BaseModel):
    """Request schema for token refresh."""
    refresh_token: str


class AccessToken(BaseModel):
    """Response schema for refresh endpoint — access token only."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
