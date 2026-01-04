"""Draft Orders API Router - List, Detail, Approve & Push endpoints.

Implements API endpoints for draft order viewing, approval, and ERP push operations.

SSOT Reference: §8.6 (Draft Orders API), §6.4-6.5 (Approve/Push Rules)
"""

from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ..database import get_db
from ..auth.dependencies import get_current_user, require_role
from ..auth.roles import UserRole
from ..models.user import User
from ..models.draft_order import DraftOrder
from ..models.erp_export import ERPExport, ERPExportStatus
from .approval import approve_draft_order, revoke_approval
from .push import push_draft_order, retry_push
from .service import DraftOrderService
from .schemas import (
    DraftOrderListResponse,
    DraftOrderListItem,
    DraftOrderDetailResponse,
    DraftOrderResponse,
    DraftOrderLineResponse,
    ConfidenceScores
)
from ..workers.export_worker import enqueue_export_job


router = APIRouter(prefix="/draft-orders", tags=["draft_orders"])


@router.get(
    "",
    response_model=DraftOrderListResponse,
    status_code=200,
    summary="List draft orders",
    description="""
    List draft orders with filtering, pagination, and sorting.

    **Filters:**
    - status: Filter by draft status (NEW, EXTRACTED, NEEDS_REVIEW, READY, APPROVED, PUSHING, PUSHED)
    - customer_id: Filter by customer

    **Pagination:**
    - page: Page number (1-indexed, default 1)
    - per_page: Results per page (default 50, max 200)

    **Sorting:**
    - order_by: Field to sort by (created_at, updated_at, confidence_score, status)
    - order_desc: Sort descending if true (default true)

    **Permissions:** Requires VIEWER role or higher

    **SSOT Reference:** §8.6 (Draft Orders API)
    """
)
def list_draft_orders(
    status: Optional[str] = Query(None, description="Filter by status"),
    customer_id: Optional[UUID] = Query(None, description="Filter by customer"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    per_page: int = Query(50, ge=1, le=200, description="Results per page"),
    order_by: str = Query("created_at", description="Field to sort by"),
    order_desc: bool = Query(True, description="Sort descending"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> DraftOrderListResponse:
    """List draft orders with filtering and pagination.

    Args:
        status: Filter by status (optional)
        customer_id: Filter by customer (optional)
        page: Page number (1-indexed)
        per_page: Results per page
        order_by: Field to sort by
        order_desc: Sort descending if true
        current_user: Authenticated user
        db: Database session

    Returns:
        DraftOrderListResponse with paginated results

    Raises:
        403: User lacks VIEWER role
    """
    service = DraftOrderService(db)

    # Calculate offset from page number
    offset = (page - 1) * per_page

    # Get draft orders
    drafts, total = service.list_draft_orders(
        org_id=current_user.org_id,
        status=status,
        customer_id=customer_id,
        limit=per_page,
        offset=offset,
        order_by=order_by,
        order_desc=order_desc
    )

    # Convert to response schema
    items = []
    for draft in drafts:
        items.append(DraftOrderListItem(
            id=draft.id,
            external_order_number=draft.external_order_number,
            customer_id=draft.customer_id,
            customer_name=draft.customer.name if draft.customer else None,
            status=draft.status,
            currency=draft.currency,
            order_date=draft.order_date,
            line_count=len(draft.lines) if draft.lines else 0,
            confidence=ConfidenceScores(
                overall=float(draft.confidence_score or 0),
                extraction=float(draft.extraction_confidence or 0),
                customer=float(draft.customer_confidence or 0),
                matching=float(draft.matching_confidence or 0)
            ),
            created_at=draft.created_at,
            updated_at=draft.updated_at
        ))

    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page

    return DraftOrderListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@router.get(
    "/{draft_id}",
    response_model=DraftOrderDetailResponse,
    status_code=200,
    summary="Get draft order details",
    description="""
    Get detailed draft order including header, lines, and validation issues.

    **Includes:**
    - Draft order header with all fields
    - All order lines with matching information
    - Validation issues (ERROR/WARNING/INFO)
    - Customer detection candidates
    - Ready-check result
    - Confidence scores

    **Permissions:** Requires VIEWER role or higher

    **SSOT Reference:** §8.6 (Draft Orders API)
    """
)
def get_draft_order(
    draft_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> DraftOrderDetailResponse:
    """Get draft order details with lines and issues.

    Args:
        draft_id: Draft order ID
        current_user: Authenticated user
        db: Database session

    Returns:
        DraftOrderDetailResponse with full details

    Raises:
        404: Draft order not found
        403: User lacks VIEWER role
    """
    service = DraftOrderService(db)

    # Get draft order with lines
    draft = service.get_draft_order(
        org_id=current_user.org_id,
        draft_order_id=draft_id,
        include_lines=True
    )

    if not draft:
        raise HTTPException(
            status_code=404,
            detail=f"Draft order {draft_id} not found"
        )

    # Convert to response schema
    draft_response = DraftOrderResponse(
        id=draft.id,
        org_id=draft.org_id,
        customer_id=draft.customer_id,
        inbound_message_id=draft.inbound_message_id,
        document_id=draft.document_id,
        external_order_number=draft.external_order_number,
        order_date=draft.order_date,
        currency=draft.currency,
        requested_delivery_date=draft.requested_delivery_date,
        ship_to_json=draft.ship_to_json or {},
        bill_to_json=draft.bill_to_json or {},
        notes=draft.notes,
        status=draft.status,
        confidence=ConfidenceScores(
            overall=float(draft.confidence_score or 0),
            extraction=float(draft.extraction_confidence or 0),
            customer=float(draft.customer_confidence or 0),
            matching=float(draft.matching_confidence or 0)
        ),
        ready_check_json=draft.ready_check_json or {},
        customer_candidates=[],  # TODO: Load from customer_detection_candidate table
        approved_by_user_id=draft.approved_by_user_id,
        approved_at=draft.approved_at,
        erp_order_id=draft.erp_order_id,
        created_at=draft.created_at,
        updated_at=draft.updated_at
    )

    # Convert lines
    lines = []
    for line in draft.lines:
        lines.append(DraftOrderLineResponse(
            id=line.id,
            org_id=line.org_id,
            draft_order_id=line.draft_order_id,
            line_no=line.line_no,
            customer_sku_raw=line.customer_sku_raw,
            customer_sku_norm=line.customer_sku_norm,
            product_description=line.product_description,
            qty=line.qty,
            uom=line.uom,
            unit_price=line.unit_price,
            currency=line.currency,
            internal_sku=line.internal_sku,
            match_status=line.match_status,
            match_confidence=float(line.match_confidence or 0),
            match_method=line.match_method,
            match_debug_json=line.match_debug_json or {},
            suggestions=[],  # TODO: Load from matching suggestions
            created_at=line.created_at,
            updated_at=line.updated_at
        ))

    # TODO: Load validation issues from validation_issue table
    issues = []

    return DraftOrderDetailResponse(
        draft_order=draft_response,
        lines=lines,
        issues=issues
    )


@router.patch(
    "/{draft_id}",
    response_model=DraftOrderResponse,
    status_code=200,
    summary="Update draft order header",
    description="""
    Update draft order header fields.

    **Editable Fields:**
    - customer_id
    - external_order_number
    - order_date
    - currency
    - requested_delivery_date
    - ship_to_json, bill_to_json
    - notes

    **Triggers:**
    - Customer change triggers ready-check
    - Audit log created for changes
    - Feedback event if customer manually selected

    **Permissions:** Requires OPS role or higher (editing after extraction)

    **SSOT Reference:** §8.6 PATCH /draft-orders/{id}
    """
)
def update_draft_order_header(
    draft_id: UUID,
    update_data: dict,
    current_user: User = Depends(require_role(UserRole.OPS)),
    db: Session = Depends(get_db)
) -> DraftOrderResponse:
    """Update draft order header fields.

    Args:
        draft_id: Draft order ID
        update_data: Fields to update
        current_user: Authenticated user (OPS role or higher)
        db: Database session

    Returns:
        DraftOrderResponse with updated data

    Raises:
        404: Draft order not found
        400: Draft in non-editable status (PUSHING, PUSHED)
        403: User lacks OPS role
    """
    service = DraftOrderService(db)

    try:
        draft = service.update_draft_order_header(
            org_id=current_user.org_id,
            draft_order_id=draft_id,
            update_data=update_data,
            user_id=current_user.id
        )
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )

    # Convert to response
    return DraftOrderResponse(
        id=draft.id,
        org_id=draft.org_id,
        customer_id=draft.customer_id,
        inbound_message_id=draft.inbound_message_id,
        document_id=draft.document_id,
        external_order_number=draft.external_order_number,
        order_date=draft.order_date,
        currency=draft.currency,
        requested_delivery_date=draft.requested_delivery_date,
        ship_to_json=draft.ship_to_json or {},
        bill_to_json=draft.bill_to_json or {},
        notes=draft.notes,
        status=draft.status,
        confidence=ConfidenceScores(
            overall=float(draft.confidence_score or 0),
            extraction=float(draft.extraction_confidence or 0),
            customer=float(draft.customer_confidence or 0),
            matching=float(draft.matching_confidence or 0)
        ),
        ready_check_json=draft.ready_check_json or {},
        customer_candidates=[],
        approved_by_user_id=draft.approved_by_user_id,
        approved_at=draft.approved_at,
        erp_order_id=draft.erp_order_id,
        created_at=draft.created_at,
        updated_at=draft.updated_at
    )


@router.patch(
    "/{draft_id}/lines/{line_id}",
    response_model=DraftOrderLineResponse,
    status_code=200,
    summary="Update draft order line",
    description="""
    Update draft order line fields.

    **Editable Fields:**
    - internal_sku (marks as OVERRIDDEN, logs feedback)
    - qty (must be > 0)
    - uom
    - unit_price (must be >= 0)
    - requested_delivery_date
    - line_notes

    **Special Behavior:**
    - Changing internal_sku sets match_status to OVERRIDDEN
    - Sets match_method to "manual"
    - Triggers ready-check after update
    - Creates audit log entry

    **Permissions:** Requires OPS role or higher

    **SSOT Reference:** §8.6 PATCH /draft-orders/{id}/lines/{line_id}
    """
)
def update_draft_order_line(
    draft_id: UUID,
    line_id: UUID,
    update_data: dict,
    current_user: User = Depends(require_role(UserRole.OPS)),
    db: Session = Depends(get_db)
) -> DraftOrderLineResponse:
    """Update draft order line fields.

    Args:
        draft_id: Draft order ID
        line_id: Line ID to update
        update_data: Fields to update
        current_user: Authenticated user (OPS role or higher)
        db: Database session

    Returns:
        DraftOrderLineResponse with updated data

    Raises:
        404: Draft order or line not found
        400: Draft in non-editable status
        403: User lacks OPS role
    """
    service = DraftOrderService(db)

    try:
        line = service.update_draft_order_line(
            org_id=current_user.org_id,
            draft_order_id=draft_id,
            line_id=line_id,
            update_data=update_data,
            user_id=current_user.id
        )
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )

    # Convert to response
    return DraftOrderLineResponse(
        id=line.id,
        org_id=line.org_id,
        draft_order_id=line.draft_order_id,
        line_no=line.line_no,
        customer_sku_raw=line.customer_sku_raw,
        customer_sku_norm=line.customer_sku_norm,
        product_description=line.product_description,
        qty=line.qty,
        uom=line.uom,
        unit_price=line.unit_price,
        currency=line.currency,
        internal_sku=line.internal_sku,
        match_status=line.match_status,
        match_confidence=float(line.match_confidence or 0),
        match_method=line.match_method,
        match_debug_json=line.match_debug_json or {},
        suggestions=[],
        created_at=line.created_at,
        updated_at=line.updated_at
    )


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
