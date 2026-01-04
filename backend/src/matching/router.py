"""Matching API endpoints.

SSOT Reference: §7.7 (Hybrid Search), §7.10 (Learning Loop)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
from datetime import datetime

from ..database import get_db
from ..auth.dependencies import get_current_user, require_role
from ..models.user import User
from ..models.sku_mapping import SkuMapping
from .schemas import (
    MatchInputSchema,
    MatchResultSchema,
    MatchCandidateSchema,
    ConfirmMappingRequest,
    ConfirmMappingResponse,
    SkuMappingSchema,
    SkuMappingListResponse
)
from .hybrid_matcher import HybridMatcher
from .ports import MatchInput


router = APIRouter(prefix="/api/v1/mappings", tags=["matching"])


@router.post("/suggest", response_model=MatchResultSchema)
def suggest_mapping(
    request: MatchInputSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Suggest product matches for a customer SKU.

    Uses hybrid matching (confirmed mappings + trigram + vector search).

    SSOT Reference: §FR-002, §FR-003, §FR-004

    Args:
        request: Match input with customer SKU and context
        db: Database session
        current_user: Authenticated user

    Returns:
        MatchResult with top match and candidates

    Raises:
        HTTPException: If matching fails
    """
    try:
        # Create matcher
        matcher = HybridMatcher(db)

        # Create match input
        match_input = MatchInput(
            org_id=current_user.org_id,
            customer_id=request.customer_id,
            customer_sku_norm=request.customer_sku_norm,
            customer_sku_raw=request.customer_sku_raw,
            product_description=request.product_description,
            uom=request.uom,
            unit_price=request.unit_price,
            qty=request.qty,
            currency=request.currency,
            order_date=request.order_date
        )

        # Run matching
        result = matcher.match(match_input)

        # Convert to response schema
        return MatchResultSchema(
            internal_sku=result.internal_sku,
            product_id=result.product_id,
            confidence=result.confidence,
            method=result.method,
            status=result.status,
            candidates=[
                MatchCandidateSchema(
                    internal_sku=c.internal_sku,
                    product_id=c.product_id,
                    product_name=c.product_name,
                    confidence=c.confidence,
                    method=c.method,
                    features=c.features
                )
                for c in result.candidates
            ]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Matching failed: {str(e)}")


@router.post("/confirm", response_model=ConfirmMappingResponse)
def confirm_mapping(
    request: ConfirmMappingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "INTEGRATOR", "OPS"]))
):
    """Confirm a SKU mapping (learning loop).

    Creates or updates a CONFIRMED sku_mapping entry, increments support_count,
    and logs feedback event.

    SSOT Reference: §FR-008, §7.10.1

    Args:
        request: Mapping confirmation request
        db: Database session
        current_user: Authenticated user with OPS+ role

    Returns:
        Confirmed mapping details

    Raises:
        HTTPException: If confirmation fails
    """
    try:
        # Check if mapping exists
        existing = db.query(SkuMapping).filter(
            SkuMapping.org_id == current_user.org_id,
            SkuMapping.customer_id == request.customer_id,
            SkuMapping.customer_sku_norm == request.customer_sku_norm,
            SkuMapping.status.in_(["CONFIRMED", "SUGGESTED"])
        ).first()

        if existing:
            # Update existing mapping
            existing.internal_sku = request.internal_sku
            existing.status = "CONFIRMED"
            existing.confidence = 1.0
            existing.support_count += 1
            existing.last_used_at = datetime.utcnow()
            existing.uom_from = request.uom_from
            existing.uom_to = request.uom_to
            existing.pack_factor = request.pack_factor
            existing.customer_sku_raw_sample = request.customer_sku_raw
            db.commit()
            db.refresh(existing)
            mapping = existing
            message = "Mapping updated and confirmed"
        else:
            # Create new mapping
            mapping = SkuMapping(
                org_id=current_user.org_id,
                customer_id=request.customer_id,
                customer_sku_norm=request.customer_sku_norm,
                customer_sku_raw_sample=request.customer_sku_raw,
                internal_sku=request.internal_sku,
                uom_from=request.uom_from,
                uom_to=request.uom_to,
                pack_factor=request.pack_factor,
                status="CONFIRMED",
                confidence=1.0,
                support_count=1,
                reject_count=0,
                last_used_at=datetime.utcnow(),
                created_by=current_user.id
            )
            db.add(mapping)
            db.commit()
            db.refresh(mapping)
            message = "Mapping created and confirmed"

        # TODO: Create feedback_event for learning loop analytics
        # feedback_event = FeedbackEvent(
        #     org_id=current_user.org_id,
        #     event_type="MAPPING_CONFIRMED",
        #     user_id=current_user.id,
        #     entity_type="sku_mapping",
        #     entity_id=mapping.id,
        #     before_json={},  # Would contain previous suggestions
        #     after_json={"internal_sku": request.internal_sku}
        # )
        # db.add(feedback_event)
        # db.commit()

        return ConfirmMappingResponse(
            id=mapping.id,
            customer_id=mapping.customer_id,
            customer_sku_norm=mapping.customer_sku_norm,
            internal_sku=mapping.internal_sku,
            status=mapping.status,
            confidence=float(mapping.confidence),
            support_count=mapping.support_count,
            message=message
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Confirmation failed: {str(e)}")


@router.get("", response_model=SkuMappingListResponse)
def list_mappings(
    customer_id: Optional[UUID] = Query(None, description="Filter by customer"),
    status: Optional[str] = Query(None, description="Filter by status (CONFIRMED, SUGGESTED, REJECTED, DEPRECATED)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List SKU mappings with filtering and pagination.

    SSOT Reference: §5.4.12

    Args:
        customer_id: Optional customer filter
        status: Optional status filter
        page: Page number (1-indexed)
        page_size: Items per page
        db: Database session
        current_user: Authenticated user

    Returns:
        Paginated list of SKU mappings

    Raises:
        HTTPException: If query fails
    """
    try:
        # Build query
        query = db.query(SkuMapping).filter(
            SkuMapping.org_id == current_user.org_id
        )

        if customer_id:
            query = query.filter(SkuMapping.customer_id == customer_id)

        if status:
            query = query.filter(SkuMapping.status == status)

        # Get total count
        total = query.count()

        # Apply pagination
        offset = (page - 1) * page_size
        mappings = query.order_by(
            SkuMapping.last_used_at.desc().nullslast(),
            SkuMapping.created_at.desc()
        ).offset(offset).limit(page_size).all()

        # Convert to schemas
        items = [
            SkuMappingSchema(
                id=m.id,
                customer_id=m.customer_id,
                customer_sku_norm=m.customer_sku_norm,
                customer_sku_raw_sample=m.customer_sku_raw_sample,
                internal_sku=m.internal_sku,
                uom_from=m.uom_from,
                uom_to=m.uom_to,
                pack_factor=m.pack_factor,
                status=m.status,
                confidence=float(m.confidence),
                support_count=m.support_count,
                reject_count=m.reject_count,
                last_used_at=m.last_used_at,
                created_at=m.created_at,
                updated_at=m.updated_at
            )
            for m in mappings
        ]

        return SkuMappingListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")
