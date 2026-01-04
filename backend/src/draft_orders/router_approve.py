"""Draft Orders API Router - Approve & Push endpoints.

Implements API endpoints for draft order approval and ERP push operations.

SSOT Reference: §8.6 (approve/push endpoints), §6.4-6.5 (Approve/Push Rules)
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from database import get_db
from auth.dependencies import get_current_user, require_role
from auth.roles import UserRole
from models.user import User
from models.draft_order import DraftOrder
from models.erp_export import ERPExport, ERPExportStatus
from .approval import approve_draft_order, revoke_approval
from .push import push_draft_order, retry_push
from workers.export_worker import enqueue_export_job


router = APIRouter(prefix="/draft-orders", tags=["draft_orders"])


# Response schemas
class ApproveResponse(BaseModel):
    """Response for approve endpoint."""
    id: str = Field(..., description="Draft order ID")
    status: str = Field(..., description="New status (APPROVED)")
    approved_at: str = Field(..., description="Approval timestamp (ISO 8601)")
    approved_by_user_id: str = Field(..., description="User ID who approved")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "APPROVED",
                "approved_at": "2025-12-27T10:30:00Z",
                "approved_by_user_id": "987e6543-e21b-12d3-a456-426614174111"
            }
        }


class PushResponse(BaseModel):
    """Response for push endpoint."""
    export_id: str = Field(..., description="ERP export ID")
    draft_order_id: str = Field(..., description="Draft order ID")
    status: str = Field(..., description="Export status (PENDING/SENT)")
    is_duplicate: bool = Field(default=False, description="True if idempotent duplicate")

    class Config:
        json_schema_extra = {
            "example": {
                "export_id": "456e7890-e12b-34d5-a678-426614174222",
                "draft_order_id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "PENDING",
                "is_duplicate": False
            }
        }


@router.post(
    "/{draft_id}/approve",
    response_model=ApproveResponse,
    status_code=200,
    summary="Approve a draft order",
    description="""
    Approve a READY draft order, transitioning it to APPROVED status.

    **Requirements:**
    - Draft must be in READY status
    - Draft must have passed all validations (ready_check_json.ready = true)
    - Draft must have a customer assigned
    - User must have OPS role or higher

    **State Transition:** READY → APPROVED

    **Audit Log:** Creates DRAFT_APPROVED entry

    **SSOT Reference:** §6.4 (FR-001 to FR-004), §8.6
    """
)
def approve(
    draft_id: UUID,
    request: Request,
    current_user: User = Depends(require_role(UserRole.OPS)),
    db: Session = Depends(get_db)
) -> ApproveResponse:
    """Approve a draft order (READY → APPROVED).

    Args:
        draft_id: Draft order ID to approve
        request: FastAPI request (for IP/User-Agent extraction)
        current_user: Authenticated user (OPS role or higher)
        db: Database session

    Returns:
        ApproveResponse: Approval confirmation

    Raises:
        404: Draft order not found
        409: Draft not in READY status or validation failed
        403: User lacks OPS role
    """
    # Extract client info for audit log
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")

    # Approve draft order
    draft = approve_draft_order(
        db=db,
        draft_id=draft_id,
        org_id=current_user.org_id,
        user_id=current_user.id,
        ip_address=ip_address,
        user_agent=user_agent
    )

    # Commit transaction
    db.commit()

    return ApproveResponse(
        id=str(draft.id),
        status=draft.status,
        approved_at=draft.approved_at.isoformat(),
        approved_by_user_id=str(draft.approved_by_user_id)
    )


@router.post(
    "/{draft_id}/push",
    response_model=PushResponse,
    status_code=200,
    summary="Push draft order to ERP",
    description="""
    Push an APPROVED draft order to ERP via configured connector.

    **Requirements:**
    - Draft must be in APPROVED status
    - Organization must have an active ERP connector configured
    - User must have OPS role or higher

    **State Transition:** APPROVED → PUSHING → PUSHED (or ERROR)

    **Idempotency:** Supports `Idempotency-Key` header (24-hour cache)
    - Duplicate requests with same key return same export_id
    - Prevents double-exports during retries/double-clicks

    **Background Processing:** Creates ERPExport record and enqueues worker job

    **Audit Log:** Creates DRAFT_PUSHED entry

    **SSOT Reference:** §6.5 (FR-005 to FR-016), §8.6
    """
)
def push(
    draft_id: UUID,
    request: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: User = Depends(require_role(UserRole.OPS)),
    db: Session = Depends(get_db)
) -> JSONResponse:
    """Push draft order to ERP (APPROVED → PUSHING).

    Args:
        draft_id: Draft order ID to push
        request: FastAPI request (for IP/User-Agent)
        idempotency_key: Optional idempotency key for duplicate detection
        current_user: Authenticated user (OPS role or higher)
        db: Database session

    Returns:
        PushResponse: Export confirmation
            - 200: Export created or idempotent duplicate
            - 202: Export already in progress (idempotent duplicate, PENDING status)

    Raises:
        404: Draft order not found
        409: Draft not in APPROVED status, or export already in progress
        400: No active ERP connector configured
        403: User lacks OPS role
    """
    # Extract client info
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")

    # Push draft order
    export, is_duplicate = push_draft_order(
        db=db,
        draft_id=draft_id,
        org_id=current_user.org_id,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        ip_address=ip_address,
        user_agent=user_agent
    )

    # Commit transaction
    db.commit()

    # Enqueue background export job (if not duplicate)
    if not is_duplicate:
        enqueue_export_job(export.id, current_user.org_id)

    # Return appropriate status code
    response_data = PushResponse(
        export_id=str(export.id),
        draft_order_id=str(draft_id),
        status=export.status,
        is_duplicate=is_duplicate
    )

    # 202 Accepted if export still PENDING (idempotent duplicate)
    if is_duplicate and export.status == ERPExportStatus.PENDING.value:
        return JSONResponse(
            status_code=202,
            content=response_data.dict()
        )

    # 200 OK for new exports or completed duplicates
    return JSONResponse(
        status_code=200,
        content=response_data.dict()
    )


@router.post(
    "/{draft_id}/retry-push",
    response_model=PushResponse,
    status_code=200,
    summary="Retry failed ERP push",
    description="""
    Retry a failed ERP push for a draft in ERROR status.

    **Requirements:**
    - Draft must be in ERROR status (previous push failed)
    - Organization must have an active ERP connector configured
    - User must have OPS role or higher

    **State Transition:** ERROR → PUSHING → PUSHED (or ERROR again)

    **Behavior:**
    - Creates NEW ERPExport record (retries don't mutate failed export)
    - Enqueues new background worker job
    - Resets draft status to PUSHING

    **Audit Log:** Creates DRAFT_PUSH_RETRIED entry

    **SSOT Reference:** §6.5 (FR-017 to FR-019), §8.6
    """
)
def retry_push_endpoint(
    draft_id: UUID,
    request: Request,
    current_user: User = Depends(require_role(UserRole.OPS)),
    db: Session = Depends(get_db)
) -> PushResponse:
    """Retry a failed push (ERROR → PUSHING).

    Args:
        draft_id: Draft order ID to retry
        request: FastAPI request (for IP/User-Agent)
        current_user: Authenticated user (OPS role or higher)
        db: Database session

    Returns:
        PushResponse: New export confirmation

    Raises:
        404: Draft order not found
        409: Draft not in ERROR status, or already succeeded
        400: No active ERP connector configured
        403: User lacks OPS role
    """
    # Extract client info
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")

    # Retry push
    export, _ = retry_push(
        db=db,
        draft_id=draft_id,
        org_id=current_user.org_id,
        user_id=current_user.id,
        ip_address=ip_address,
        user_agent=user_agent
    )

    # Commit transaction
    db.commit()

    # Enqueue background export job
    enqueue_export_job(export.id, current_user.org_id)

    return PushResponse(
        export_id=str(export.id),
        draft_order_id=str(draft_id),
        status=export.status,
        is_duplicate=False
    )


@router.delete(
    "/{draft_id}/approval",
    status_code=204,
    summary="Revoke draft approval",
    description="""
    Revoke approval from an APPROVED draft (before push).

    **Requirements:**
    - Draft must be in APPROVED status (not yet PUSHING or PUSHED)
    - User must have OPS role or higher

    **State Transition:** APPROVED → NEEDS_REVIEW

    **Behavior:**
    - Clears approved_by_user_id and approved_at
    - Reverts status to NEEDS_REVIEW
    - Used when draft needs editing after approval

    **Audit Log:** Creates DRAFT_APPROVAL_REVOKED entry

    **SSOT Reference:** §6.4 (FR-021)
    """
)
def revoke_approval_endpoint(
    draft_id: UUID,
    request: Request,
    current_user: User = Depends(require_role(UserRole.OPS)),
    db: Session = Depends(get_db)
) -> None:
    """Revoke approval from draft (APPROVED → NEEDS_REVIEW).

    Args:
        draft_id: Draft order ID
        request: FastAPI request
        current_user: Authenticated user (OPS role or higher)
        db: Database session

    Raises:
        404: Draft order not found
        409: Draft not in APPROVED status
        403: User lacks OPS role
    """
    # Extract client info
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")

    # Revoke approval
    revoke_approval(
        db=db,
        draft_id=draft_id,
        org_id=current_user.org_id,
        user_id=current_user.id,
        reason="Manual revocation by operator",
        ip_address=ip_address,
        user_agent=user_agent
    )

    # Commit transaction
    db.commit()
