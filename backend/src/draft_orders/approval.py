"""Approval service for draft orders.

Implements draft order approval logic per SSOT §6.4.
Handles state validation, approval metadata, and audit logging.

SSOT Reference: §6.4 (Approval Rules), §8.6 (approve endpoint)
"""

from datetime import datetime, timezone
from typing import Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from fastapi import HTTPException

from ..models.draft_order import DraftOrder
from .status import DraftOrderStatus, validate_transition, StateTransitionError
from ..audit.service import log_audit_event


class ApprovalError(Exception):
    """Raised when approval validation fails."""
    pass


def validate_ready_for_approval(draft: DraftOrder) -> None:
    """Validate that a draft order is ready for approval.

    Args:
        draft: Draft order to validate

    Raises:
        ApprovalError: If draft is not ready for approval

    SSOT Reference: §6.4 (FR-002)
    """
    # Check status is READY
    if draft.status != DraftOrderStatus.READY.value:
        raise ApprovalError(
            f"Draft must be READY to approve (current: {draft.status})"
        )

    # Check ready_check_json indicates READY
    ready_check = draft.ready_check_json or {}
    if not ready_check.get("ready", False):
        blocking_reasons = ready_check.get("blocking_reasons", [])
        raise ApprovalError(
            f"Draft failed ready check. Blocking reasons: {', '.join(blocking_reasons)}"
        )

    # Customer must be set
    if not draft.customer_id:
        raise ApprovalError("Draft must have a customer assigned before approval")


def approve_draft_order(
    db: Session,
    draft_id: UUID,
    org_id: UUID,
    user_id: UUID,
    ip_address: str | None = None,
    user_agent: str | None = None
) -> DraftOrder:
    """Approve a draft order.

    Validates draft is READY, transitions to APPROVED, and logs audit event.

    Args:
        db: Database session
        draft_id: Draft order ID to approve
        org_id: Organization ID (for multi-tenant isolation)
        user_id: User performing the approval
        ip_address: Client IP address for audit log
        user_agent: Client User-Agent for audit log

    Returns:
        DraftOrder: Approved draft order

    Raises:
        HTTPException: If draft not found or validation fails

    SSOT Reference: §6.4 (FR-001 to FR-004), §8.6 (approve endpoint)

    Example:
        draft = approve_draft_order(
            db=db,
            draft_id=UUID("..."),
            org_id=UUID("..."),
            user_id=UUID("..."),
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0..."
        )
    """
    # Fetch draft with org_id filter (multi-tenant isolation)
    draft = db.query(DraftOrder).filter(
        DraftOrder.id == draft_id,
        DraftOrder.org_id == org_id
    ).first()

    if not draft:
        raise HTTPException(
            status_code=404,
            detail=f"Draft order {draft_id} not found"
        )

    # Check if already approved
    if draft.status == DraftOrderStatus.APPROVED.value:
        raise HTTPException(
            status_code=409,
            detail="Draft already approved"
        )

    # Validate ready for approval
    try:
        validate_ready_for_approval(draft)
    except ApprovalError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # Validate state transition
    try:
        validate_transition(
            DraftOrderStatus(draft.status),
            DraftOrderStatus.APPROVED
        )
    except StateTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # Update draft status and approval metadata
    draft.status = DraftOrderStatus.APPROVED.value
    draft.approved_by_user_id = user_id
    draft.approved_at = datetime.now(timezone.utc)

    # Create audit log entry (SSOT §6.4 FR-004, §11.4)
    log_audit_event(
        db=db,
        org_id=org_id,
        action="DRAFT_APPROVED",
        actor_id=user_id,
        entity_type="draft_order",
        entity_id=draft_id,
        metadata={
            "draft_id": str(draft_id),
            "customer_id": str(draft.customer_id) if draft.customer_id else None,
            "external_order_number": draft.external_order_number
        },
        ip_address=ip_address,
        user_agent=user_agent
    )

    # Commit transaction
    db.flush()

    return draft


def revoke_approval(
    db: Session,
    draft_id: UUID,
    org_id: UUID,
    user_id: UUID,
    reason: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None
) -> DraftOrder:
    """Revoke approval from a draft order.

    Transitions draft back to NEEDS_REVIEW and clears approval metadata.
    Used when draft is edited after approval but before push.

    Args:
        db: Database session
        draft_id: Draft order ID
        org_id: Organization ID
        user_id: User revoking approval
        reason: Reason for revocation
        ip_address: Client IP for audit log
        user_agent: Client User-Agent for audit log

    Returns:
        DraftOrder: Updated draft order

    Raises:
        HTTPException: If draft not found or not approved

    SSOT Reference: §6.4 (FR-021 - approval reversion on edit)

    Example:
        draft = revoke_approval(
            db=db,
            draft_id=UUID("..."),
            org_id=UUID("..."),
            user_id=UUID("..."),
            reason="Draft edited - customer changed"
        )
    """
    # Fetch draft
    draft = db.query(DraftOrder).filter(
        DraftOrder.id == draft_id,
        DraftOrder.org_id == org_id
    ).first()

    if not draft:
        raise HTTPException(
            status_code=404,
            detail=f"Draft order {draft_id} not found"
        )

    # Check if approved
    if draft.status != DraftOrderStatus.APPROVED.value:
        raise HTTPException(
            status_code=409,
            detail="Draft is not approved"
        )

    # Validate transition
    try:
        validate_transition(
            DraftOrderStatus.APPROVED,
            DraftOrderStatus.NEEDS_REVIEW
        )
    except StateTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # Revert status and clear approval metadata
    draft.status = DraftOrderStatus.NEEDS_REVIEW.value
    draft.approved_by_user_id = None
    draft.approved_at = None

    # Audit log
    log_audit_event(
        db=db,
        org_id=org_id,
        action="DRAFT_APPROVAL_REVOKED",
        actor_id=user_id,
        entity_type="draft_order",
        entity_id=draft_id,
        metadata={
            "draft_id": str(draft_id),
            "reason": reason or "Draft edited after approval"
        },
        ip_address=ip_address,
        user_agent=user_agent
    )

    db.flush()

    return draft
