"""Pydantic schemas for User management endpoints.

These schemas define the request/response contracts for user CRUD operations.
All schemas exclude password_hash for security (never return in API responses).
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from uuid import UUID
from datetime import datetime
from typing import Optional


class UserCreate(BaseModel):
    """Request schema for creating a new user (POST /users).

    Only ADMIN users can create users. Email must be unique per organization.
    Password will be hashed before storage using Argon2id.
    """
    email: EmailStr = Field(
        ...,
        description="User's email address (unique per org, case-insensitive)",
        examples=["ops@acme.de"]
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="User's display name",
        examples=["Jane Doe"]
    )
    role: str = Field(
        ...,
        pattern="^(ADMIN|INTEGRATOR|OPS|VIEWER)$",
        description="User's role (determines permissions)",
        examples=["OPS"]
    )
    password: str = Field(
        ...,
        min_length=12,
        description="Password (min 12 chars, must meet NIST SP 800-63B requirements)",
        examples=["MySecurePassphrase2024!"]
    )

    class Config:
        json_schema_extra = {
            "example": {
                "email": "ops@acme.de",
                "name": "Operations User",
                "role": "OPS",
                "password": "MySecurePassphrase2024!"
            }
        }


class UserUpdate(BaseModel):
    """Request schema for updating an existing user (PATCH /users/{id}).

    Only ADMIN users can update users. All fields are optional.
    To change password, use a separate endpoint (not in MVP).
    """
    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=200,
        description="User's display name",
        examples=["Jane Doe"]
    )
    role: Optional[str] = Field(
        None,
        pattern="^(ADMIN|INTEGRATOR|OPS|VIEWER)$",
        description="User's role (triggers USER_ROLE_CHANGED audit event)",
        examples=["INTEGRATOR"]
    )
    status: Optional[str] = Field(
        None,
        pattern="^(ACTIVE|DISABLED)$",
        description="User status (DISABLED blocks login, triggers USER_DISABLED audit event)",
        examples=["ACTIVE"]
    )

    @field_validator('name', 'role', 'status')
    @classmethod
    def check_not_empty(cls, v):
        """Ensure fields are not empty strings if provided."""
        if v is not None and isinstance(v, str) and v.strip() == "":
            raise ValueError("Field cannot be empty string")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Jane Doe (updated)",
                "role": "INTEGRATOR",
                "status": "ACTIVE"
            }
        }


class UserResponse(BaseModel):
    """Response schema for user data.

    Returned by all user endpoints. Never includes password_hash for security.
    """
    id: UUID = Field(..., description="User's unique identifier")
    org_id: UUID = Field(..., description="Organization this user belongs to")
    email: str = Field(..., description="User's email address")
    name: str = Field(..., description="User's display name")
    role: str = Field(..., description="User's role (ADMIN|INTEGRATOR|OPS|VIEWER)")
    status: str = Field(..., description="User status (ACTIVE|DISABLED)")
    last_login_at: Optional[datetime] = Field(None, description="Last successful login timestamp")
    created_at: datetime = Field(..., description="User creation timestamp")
    updated_at: datetime = Field(..., description="Last modification timestamp")

    class Config:
        from_attributes = True  # Enable ORM model conversion
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "org_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
                "email": "ops@acme.de",
                "name": "Operations User",
                "role": "OPS",
                "status": "ACTIVE",
                "last_login_at": "2025-01-04T10:30:00Z",
                "created_at": "2025-01-01T12:00:00Z",
                "updated_at": "2025-01-04T10:30:00Z"
            }
        }


class UserListResponse(BaseModel):
    """Response schema for listing users (GET /users).

    Includes pagination metadata.
    """
    users: list[UserResponse] = Field(..., description="List of users in organization")
    total: int = Field(..., description="Total number of users in organization")

    class Config:
        json_schema_extra = {
            "example": {
                "users": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "org_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
                        "email": "admin@acme.de",
                        "name": "Admin User",
                        "role": "ADMIN",
                        "status": "ACTIVE",
                        "last_login_at": "2025-01-04T12:00:00Z",
                        "created_at": "2025-01-01T12:00:00Z",
                        "updated_at": "2025-01-04T12:00:00Z"
                    }
                ],
                "total": 1
            }
        }
