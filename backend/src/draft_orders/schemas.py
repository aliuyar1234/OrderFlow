"""Pydantic schemas for Draft Orders API

Request/response models for draft order endpoints following SSOT §8.6.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# Draft Order Line Schemas
# ============================================================================

class DraftOrderLineBase(BaseModel):
    """Base schema for draft order line (shared fields)"""
    customer_sku_raw: Optional[str] = None
    product_description: Optional[str] = None
    qty: Optional[Decimal] = None
    uom: Optional[str] = None
    unit_price: Optional[Decimal] = None
    currency: Optional[str] = None
    requested_delivery_date: Optional[date] = None
    line_notes: Optional[str] = None


class DraftOrderLineUpdate(BaseModel):
    """Schema for updating a draft order line (PATCH /draft-orders/{id}/lines/{line_id})"""
    internal_sku: Optional[str] = Field(None, description="Internal SKU to match to")
    qty: Optional[Decimal] = Field(None, gt=0, description="Quantity must be > 0")
    uom: Optional[str] = None
    unit_price: Optional[Decimal] = Field(None, ge=0, description="Price must be >= 0")
    requested_delivery_date: Optional[date] = None
    line_notes: Optional[str] = None

    model_config = ConfigDict(extra='forbid')


class MatchSuggestion(BaseModel):
    """Match candidate suggestion for a line"""
    internal_sku: str
    score: float = Field(..., ge=0.0, le=1.0)
    method: str  # exact_mapping, trigram, embedding, hybrid
    reason: Optional[str] = None
    product_name: Optional[str] = None


class DraftOrderLineResponse(DraftOrderLineBase):
    """Response schema for draft order line"""
    id: UUID
    org_id: UUID
    draft_order_id: UUID
    line_no: int
    customer_sku_norm: Optional[str] = None
    internal_sku: Optional[str] = None
    match_status: str  # UNMATCHED, SUGGESTED, MATCHED, OVERRIDDEN
    match_confidence: float = Field(0.0, ge=0.0, le=1.0)
    match_method: Optional[str] = None
    match_debug_json: Dict[str, Any] = Field(default_factory=dict)
    suggestions: List[MatchSuggestion] = Field(default_factory=list, description="Top match candidates")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Draft Order Header Schemas
# ============================================================================

class DraftOrderBase(BaseModel):
    """Base schema for draft order header (shared fields)"""
    external_order_number: Optional[str] = None
    order_date: Optional[date] = None
    currency: Optional[str] = Field(None, max_length=3, description="ISO 4217 code (EUR, CHF, USD)")
    requested_delivery_date: Optional[date] = None
    notes: Optional[str] = None


class DraftOrderUpdate(BaseModel):
    """Schema for updating draft order header (PATCH /draft-orders/{id})"""
    customer_id: Optional[UUID] = None
    external_order_number: Optional[str] = None
    order_date: Optional[date] = None
    currency: Optional[str] = Field(None, max_length=3)
    requested_delivery_date: Optional[date] = None
    ship_to_json: Optional[Dict[str, Any]] = None
    bill_to_json: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

    model_config = ConfigDict(extra='forbid')


class CustomerCandidate(BaseModel):
    """Customer detection candidate"""
    customer_id: UUID
    customer_name: str
    score: float = Field(..., ge=0.0, le=1.0)
    signals: Dict[str, Any] = Field(
        default_factory=dict,
        description="Signal badges: domain_match, email_match, doc_number, name_similarity"
    )


class ConfidenceScores(BaseModel):
    """Confidence scores for draft order"""
    overall: float = Field(0.0, ge=0.0, le=1.0)
    extraction: float = Field(0.0, ge=0.0, le=1.0)
    customer: float = Field(0.0, ge=0.0, le=1.0)
    matching: float = Field(0.0, ge=0.0, le=1.0)


class ValidationIssue(BaseModel):
    """Validation issue"""
    id: UUID
    type: str  # MISSING_CUSTOMER, UNKNOWN_PRODUCT, MISSING_PRICE, etc.
    severity: str  # ERROR, WARNING, INFO
    status: str  # OPEN, ACKNOWLEDGED, RESOLVED
    message: str
    details_json: Dict[str, Any] = Field(default_factory=dict)
    draft_order_id: Optional[UUID] = None
    draft_order_line_id: Optional[UUID] = None
    created_at: datetime


class DraftOrderResponse(DraftOrderBase):
    """Response schema for single draft order with details"""
    id: UUID
    org_id: UUID
    customer_id: Optional[UUID] = None
    inbound_message_id: Optional[UUID] = None
    document_id: UUID
    ship_to_json: Dict[str, Any] = Field(default_factory=dict)
    bill_to_json: Dict[str, Any] = Field(default_factory=dict)
    status: str  # NEW, EXTRACTED, NEEDS_REVIEW, READY, APPROVED, PUSHING, PUSHED, ERROR
    confidence: ConfidenceScores
    ready_check_json: Dict[str, Any] = Field(default_factory=dict)
    customer_candidates: List[CustomerCandidate] = Field(default_factory=list)
    approved_by_user_id: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    erp_order_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DraftOrderDetailResponse(BaseModel):
    """Response schema for GET /draft-orders/{id} with lines and issues"""
    draft_order: DraftOrderResponse
    lines: List[DraftOrderLineResponse] = Field(default_factory=list)
    issues: List[ValidationIssue] = Field(default_factory=list)


class DraftOrderListItem(BaseModel):
    """Response schema for draft order in list (GET /draft-orders)"""
    id: UUID
    external_order_number: Optional[str] = None
    customer_id: Optional[UUID] = None
    customer_name: Optional[str] = None
    status: str
    currency: Optional[str] = None
    order_date: Optional[date] = None
    line_count: int = 0
    confidence: ConfidenceScores
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DraftOrderListResponse(BaseModel):
    """Paginated response for GET /draft-orders"""
    items: List[DraftOrderListItem]
    total: int
    page: int
    per_page: int
    total_pages: int


# ============================================================================
# Action Schemas
# ============================================================================

class ApproveResponse(BaseModel):
    """Response for POST /draft-orders/{id}/approve"""
    status: str
    approved_at: datetime
    approved_by_user_id: UUID


class SelectCustomerRequest(BaseModel):
    """Request for POST /draft-orders/{id}/select-customer"""
    customer_id: UUID


class ActionQueuedResponse(BaseModel):
    """Generic response for async actions"""
    status: str = "queued"
    message: Optional[str] = None
