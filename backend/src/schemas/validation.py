"""Pydantic schemas for validation API responses"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from ..domain.validation.models import (
    ValidationIssueSeverity,
    ValidationIssueStatus,
    ValidationIssueType
)


class ValidationIssueResponse(BaseModel):
    """Response schema for a single validation issue.

    Used in GET /draft-orders/{id}/issues and other validation endpoints.
    """
    id: UUID
    org_id: UUID
    draft_order_id: UUID
    draft_order_line_id: Optional[UUID] = None
    line_no: Optional[int] = None
    type: str
    severity: ValidationIssueSeverity
    status: ValidationIssueStatus
    message: str
    details: dict[str, Any] = Field(default_factory=dict)

    resolved_at: Optional[datetime] = None
    resolved_by_user_id: Optional[UUID] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by_user_id: Optional[UUID] = None

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        use_enum_values = True


class ValidationIssuesListResponse(BaseModel):
    """Response schema for list of validation issues."""
    issues: list[ValidationIssueResponse]
    total: int


class ReadyCheckResponse(BaseModel):
    """Response schema for ready-check status.

    Embedded in draft order responses (SSOT §6.3).
    """
    is_ready: bool
    blocking_reasons: list[str] = Field(default_factory=list)
    checked_at: str


class AcknowledgeIssueRequest(BaseModel):
    """Request schema for acknowledging a validation issue."""
    # No fields required - acknowledgement is implicit from PATCH call
    pass


class AcknowledgeIssueResponse(BaseModel):
    """Response schema after acknowledging an issue."""
    issue: ValidationIssueResponse
    message: str = "Issue acknowledged successfully"


class ValidationSummaryResponse(BaseModel):
    """Summary of validation issues by severity.

    Useful for dashboard/overview displays.
    """
    total: int
    error_count: int
    warning_count: int
    info_count: int
    open_count: int
    acknowledged_count: int
    resolved_count: int
