"""Validation API router with endpoints for validation issues"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user, get_current_org
from models.user import User
from models.org import Org
from infrastructure.repositories.validation_repository import ValidationRepository
from schemas.validation import (
    ValidationIssuesListResponse,
    ValidationIssueResponse,
    AcknowledgeIssueRequest,
    AcknowledgeIssueResponse,
    ValidationSummaryResponse
)
from domain.validation.models import ValidationIssueStatus

router = APIRouter(prefix="/validation", tags=["validation"])


@router.get("/draft-orders/{draft_order_id}/issues", response_model=ValidationIssuesListResponse)
def get_draft_order_issues(
    draft_order_id: UUID,
    status: Optional[str] = Query(None, description="Filter by status (OPEN, ACKNOWLEDGED, RESOLVED, OVERRIDDEN)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Org = Depends(get_current_org)
):
    """Get all validation issues for a draft order.

    This endpoint is used by the draft detail UI to display validation issues.
    Supports filtering by status.

    Args:
        draft_order_id: Draft order UUID
        status: Optional status filter (OPEN, ACKNOWLEDGED, RESOLVED, OVERRIDDEN)
        db: Database session
        current_user: Authenticated user
        current_org: Current organization (multi-tenant isolation)

    Returns:
        List of validation issues with total count
    """
    repo = ValidationRepository(db)

    # Parse status filter
    status_filter = None
    if status:
        try:
            status_enum = ValidationIssueStatus(status.upper())
            status_filter = [status_enum]
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Must be one of: OPEN, ACKNOWLEDGED, RESOLVED, OVERRIDDEN"
            )

    # Get issues from repository
    issues = repo.get_issues_by_draft_order(
        org_id=current_org.id,
        draft_order_id=draft_order_id,
        status_filter=status_filter
    )

    # Convert to response models
    issue_responses = [
        ValidationIssueResponse.model_validate(issue)
        for issue in issues
    ]

    return ValidationIssuesListResponse(
        issues=issue_responses,
        total=len(issue_responses)
    )


@router.get("/draft-orders/{draft_order_id}/issues/summary", response_model=ValidationSummaryResponse)
def get_draft_order_issues_summary(
    draft_order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Org = Depends(get_current_org)
):
    """Get summary of validation issues by severity and status.

    Useful for dashboard displays and quick overview.

    Args:
        draft_order_id: Draft order UUID
        db: Database session
        current_user: Authenticated user
        current_org: Current organization

    Returns:
        Summary counts by severity and status
    """
    repo = ValidationRepository(db)

    issues = repo.get_issues_by_draft_order(
        org_id=current_org.id,
        draft_order_id=draft_order_id
    )

    # Compute summary
    total = len(issues)
    error_count = sum(1 for i in issues if i.severity.value == "ERROR")
    warning_count = sum(1 for i in issues if i.severity.value == "WARNING")
    info_count = sum(1 for i in issues if i.severity.value == "INFO")

    open_count = sum(1 for i in issues if i.status.value == "OPEN")
    acknowledged_count = sum(1 for i in issues if i.status.value == "ACKNOWLEDGED")
    resolved_count = sum(1 for i in issues if i.status.value == "RESOLVED")

    return ValidationSummaryResponse(
        total=total,
        error_count=error_count,
        warning_count=warning_count,
        info_count=info_count,
        open_count=open_count,
        acknowledged_count=acknowledged_count,
        resolved_count=resolved_count
    )


@router.patch("/issues/{issue_id}/acknowledge", response_model=AcknowledgeIssueResponse)
def acknowledge_issue(
    issue_id: UUID,
    request: AcknowledgeIssueRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Org = Depends(get_current_org)
):
    """Acknowledge a validation issue.

    Changes status from OPEN to ACKNOWLEDGED. Per spec.md US3, acknowledgement
    does NOT resolve the issue or affect READY blocking behavior.

    Args:
        issue_id: Issue UUID
        request: Empty request body
        db: Database session
        current_user: Authenticated user
        current_org: Current organization

    Returns:
        Updated issue with acknowledgement metadata
    """
    repo = ValidationRepository(db)

    # Acknowledge the issue
    updated_issue = repo.acknowledge_issue(
        issue_id=issue_id,
        org_id=current_org.id,
        user_id=current_user.id
    )

    if not updated_issue:
        raise HTTPException(
            status_code=404,
            detail=f"Validation issue {issue_id} not found"
        )

    db.commit()

    return AcknowledgeIssueResponse(
        issue=ValidationIssueResponse.model_validate(updated_issue),
        message="Issue acknowledged successfully"
    )


@router.post("/issues/{issue_id}/resolve", response_model=AcknowledgeIssueResponse)
def resolve_issue(
    issue_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Org = Depends(get_current_org)
):
    """Manually resolve a validation issue.

    This is different from auto-resolution. Used when operator manually
    marks an issue as resolved (e.g., override decision).

    Args:
        issue_id: Issue UUID
        db: Database session
        current_user: Authenticated user
        current_org: Current organization

    Returns:
        Updated issue with resolution metadata
    """
    repo = ValidationRepository(db)

    # Resolve the issue
    updated_issue = repo.resolve_issue(
        issue_id=issue_id,
        org_id=current_org.id,
        user_id=current_user.id
    )

    if not updated_issue:
        raise HTTPException(
            status_code=404,
            detail=f"Validation issue {issue_id} not found"
        )

    db.commit()

    return AcknowledgeIssueResponse(
        issue=ValidationIssueResponse.model_validate(updated_issue),
        message="Issue resolved successfully"
    )
