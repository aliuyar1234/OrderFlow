"""Pydantic schemas for authentication endpoints"""

from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from datetime import datetime
from typing import Optional


class LoginRequest(BaseModel):
    """Request schema for user login.

    Attributes:
        org_slug: Organization slug for multi-tenant isolation
        email: User's email address
        password: User's password (plain text, will be verified against hash)
    """
    org_slug: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    """Response schema for successful login.

    Attributes:
        access_token: JWT access token
        token_type: Token type (always "bearer")
        expires_in: Token expiry in seconds
    """
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


class TokenPayload(BaseModel):
    """Decoded JWT token payload.

    Attributes:
        sub: Subject (user_id)
        org_id: Organization ID
        role: User role
        email: User email
        exp: Expiration timestamp
        iat: Issued at timestamp
    """
    sub: str  # user_id as string
    org_id: str  # org_id as string
    role: str
    email: str
    exp: int
    iat: int


class UserResponse(BaseModel):
    """User information response (excludes password_hash).

    Attributes:
        id: User UUID
        org_id: Organization UUID
        email: User email
        name: User display name
        role: User role
        status: Account status (ACTIVE, DISABLED)
        last_login_at: Last successful login timestamp
        created_at: Account creation timestamp
        updated_at: Last modification timestamp
    """
    id: UUID
    org_id: UUID
    email: str
    name: str
    role: str
    status: str
    last_login_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MeResponse(BaseModel):
    """Response schema for GET /auth/me endpoint.

    Attributes:
        user: Current user information
    """
    user: UserResponse
