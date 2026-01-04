"""Feedback API endpoints for mapping confirmation, customer selection, and line edits

This module provides API endpoints that capture feedback events:
- POST /sku-mappings/{id}/confirm - Confirm SKU mapping
- POST /sku-mappings/{id}/reject - Reject SKU mapping
- POST /draft-orders/{id}/select-customer - Select customer from candidates
- PATCH /draft-orders/{id}/lines/{line_id} - Edit draft line (captures corrections)
"""

from typing import Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models.user import User
from .services import FeedbackService


# Request/Response schemas
class ConfirmMappingRequest(BaseModel):
    """Request to confirm a SKU mapping"""
    customer_sku: str
    internal_sku: str
    draft_order_line_id: Optional[UUID] = None
    confidence: Optional[float] = None


class RejectMappingRequest(BaseModel):
    """Request to reject a SKU mapping"""
    customer_sku: str
    rejected_internal_sku: str
    draft_order_line_id: Optional[UUID] = None
    reason: Optional[str] = None


class SelectCustomerRequest(BaseModel):
    """Request to select a customer from candidates"""
    customer_id: UUID
    candidates: list  # List of candidate dicts


class LineEditRequest(BaseModel):
    """Request to edit a draft line"""
    internal_sku: Optional[str] = None
    qty: Optional[float] = None
    uom: Optional[str] = None
    unit_price: Optional[float] = None
    requested_delivery_date: Optional[str] = None
    line_notes: Optional[str] = None


# Router
router = APIRouter(prefix="/api/v1", tags=["feedback"])


@router.post("/sku-mappings/{mapping_id}/confirm")
def confirm_sku_mapping(
    mapping_id: UUID,
    request: ConfirmMappingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Confirm a SKU mapping suggestion.

    Creates a MAPPING_CONFIRMED feedback event and updates the mapping status.

    Per SSOT §7.10.2:
    - Sets sku_mapping.status = CONFIRMED
    - Sets confidence = 1.0
    - Increments support_count
    - Creates feedback_event
    """
    # TODO: Get actual SKU mapping from database
    # For now, create feedback event with provided data

    before_state = {
        "customer_sku": request.customer_sku,
        "status": "SUGGESTED",
        "confidence": request.confidence or 0.5
    }

    after_state = {
        "customer_sku": request.customer_sku,
        "internal_sku": request.internal_sku,
        "status": "CONFIRMED",
        "confidence": 1.0
    }

    sku_mapping_data = {
        "mapping_id": str(mapping_id),
        "customer_sku": request.customer_sku,
        "internal_sku": request.internal_sku
    }

    # Capture feedback event
    feedback_event = FeedbackService.capture_mapping_confirmed(
        db=db,
        org_id=current_user.org_id,
        actor_user_id=current_user.id,
        sku_mapping_data=sku_mapping_data,
        before_state=before_state,
        after_state=after_state,
        draft_order_line_id=request.draft_order_line_id
    )

    return {
        "id": str(mapping_id),
        "status": "CONFIRMED",
        "feedback_event_id": str(feedback_event.id)
    }


@router.post("/sku-mappings/{mapping_id}/reject")
def reject_sku_mapping(
    mapping_id: UUID,
    request: RejectMappingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reject a SKU mapping suggestion.

    Creates a MAPPING_REJECTED feedback event.
    """
    sku_mapping_data = {
        "mapping_id": str(mapping_id),
        "customer_sku": request.customer_sku,
        "rejected_sku": request.rejected_internal_sku,
        "reason": request.reason
    }

    # Capture feedback event
    feedback_event = FeedbackService.capture_mapping_rejected(
        db=db,
        org_id=current_user.org_id,
        actor_user_id=current_user.id,
        sku_mapping_data=sku_mapping_data,
        rejected_internal_sku=request.rejected_internal_sku,
        draft_order_line_id=request.draft_order_line_id
    )

    return {
        "id": str(mapping_id),
        "status": "REJECTED",
        "feedback_event_id": str(feedback_event.id)
    }


@router.post("/draft-orders/{draft_order_id}/select-customer")
def select_customer(
    draft_order_id: UUID,
    request: SelectCustomerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Select a customer from ambiguous candidates.

    Creates a CUSTOMER_SELECTED feedback event.

    Per SSOT §7.10.4:
    - Sets draft_order.customer_id
    - Marks candidate as SELECTED, others as REJECTED
    - Creates feedback_event
    """
    # Capture feedback event
    feedback_event = FeedbackService.capture_customer_selected(
        db=db,
        org_id=current_user.org_id,
        actor_user_id=current_user.id,
        candidates=request.candidates,
        selected_customer_id=request.customer_id,
        draft_order_id=draft_order_id
    )

    return {
        "draft_order_id": str(draft_order_id),
        "customer_id": str(request.customer_id),
        "feedback_event_id": str(feedback_event.id)
    }


@router.patch("/draft-orders/{draft_order_id}/lines/{line_id}")
def edit_draft_line(
    draft_order_id: UUID,
    line_id: UUID,
    request: LineEditRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Edit a draft order line.

    Captures EXTRACTION_LINE_CORRECTED feedback event for any field changes.

    Per SSOT §8.2:
    - Manual changes set match_status=OVERRIDDEN (if internal_sku changed)
    - Creates feedback_event for qty/uom/sku edits
    """
    # TODO: Get actual draft line from database
    # For now, create feedback event with provided data

    # Build before/after dictionaries based on what changed
    before_values = {}
    after_values = {}

    if request.internal_sku is not None:
        before_values["internal_sku"] = "OLD_SKU"  # TODO: Get from DB
        after_values["internal_sku"] = request.internal_sku

    if request.qty is not None:
        before_values["qty"] = 0  # TODO: Get from DB
        after_values["qty"] = request.qty

    if request.uom is not None:
        before_values["uom"] = "OLD_UOM"  # TODO: Get from DB
        after_values["uom"] = request.uom

    if request.unit_price is not None:
        before_values["unit_price"] = 0.0  # TODO: Get from DB
        after_values["unit_price"] = request.unit_price

    # Only capture feedback if something actually changed
    if before_values and after_values:
        # TODO: Get document_id and layout_fingerprint from draft_order
        feedback_event = FeedbackService.capture_line_corrected(
            db=db,
            org_id=current_user.org_id,
            actor_user_id=current_user.id,
            draft_order_id=draft_order_id,
            draft_order_line_id=line_id,
            before_values=before_values,
            after_values=after_values,
            document_id=None,  # TODO: Get from draft_order
            layout_fingerprint=None,  # TODO: Get from document
            input_snippet=None  # TODO: Get from document
        )

        return {
            "line_id": str(line_id),
            "updated": True,
            "feedback_event_id": str(feedback_event.id)
        }

    return {
        "line_id": str(line_id),
        "updated": False,
        "message": "No changes detected"
    }
