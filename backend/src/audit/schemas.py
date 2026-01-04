"""Pydantic schemas for audit log endpoints.

These schemas define the request/response contracts for audit log queries.
Audit logs are read-only (no create/update/delete operations).
"""

from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional


class AuditLogResponse(BaseModel):
    """Response schema for audit log entries.

    Returned by audit log query endpoints. All fields are read-only.
    """
    id: UUID = Field(..., description="Audit log entry unique identifier")
    org_id: UUID = Field(..., description="Organization ID")
    actor_id: Optional[UUID] = Field(None, description="User who performed the action (None for anonymous)")
    action: str = Field(..., description="Event action (LOGIN_SUCCESS, USER_CREATED, etc.)")
    entity_type: Optional[str] = Field(None, description="Type of entity affected (user, draft_order, etc.)")
    entity_id: Optional[UUID] = Field(None, description="ID of affected entity")
    metadata: Optional[dict] = Field(None, description="Additional context as JSON")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Client User-Agent header")
    created_at: datetime = Field(..., description="Event timestamp")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "org_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
                "actor_id": "123e4567-e89b-12d3-a456-426614174000",
                "action": "USER_CREATED",
                "entity_type": "user",
                "entity_id": "abc12345-6789-0abc-def0-123456789012",
                "metadata": {"email": "ops@acme.de", "role": "OPS"},
                "ip_address": "192.168.1.100",
                "user_agent": "Mozilla/5.0...",
                "created_at": "2025-01-04T12:00:00Z"
            }
        }


class AuditLogListResponse(BaseModel):
    """Response schema for audit log queries.

    Includes pagination metadata.
    """
    entries: list[AuditLogResponse] = Field(..., description="List of audit log entries")
    total: int = Field(..., description="Total number of entries matching filters")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Entries per page")

    class Config:
        json_schema_extra = {
            "example": {
                "entries": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "org_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
                        "actor_id": "123e4567-e89b-12d3-a456-426614174000",
                        "action": "LOGIN_SUCCESS",
                        "entity_type": None,
                        "entity_id": None,
                        "metadata": {"email": "admin@acme.de"},
                        "ip_address": "192.168.1.100",
                        "user_agent": "Mozilla/5.0...",
                        "created_at": "2025-01-04T12:00:00Z"
                    }
                ],
                "total": 1,
                "page": 1,
                "per_page": 50
            }
        }
