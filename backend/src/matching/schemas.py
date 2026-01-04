"""Pydantic schemas for matching endpoints.

SSOT Reference: §7.7 (Hybrid Search), §7.10 (Learning Loop)
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from uuid import UUID
from decimal import Decimal
from datetime import datetime


class MatchInputSchema(BaseModel):
    """Input schema for matching request."""
    customer_id: UUID
    customer_sku_norm: str
    customer_sku_raw: str
    product_description: Optional[str] = None
    uom: Optional[str] = None
    unit_price: Optional[Decimal] = None
    qty: Optional[Decimal] = None
    currency: Optional[str] = None
    order_date: Optional[str] = None


class MatchCandidateSchema(BaseModel):
    """Match candidate with confidence and features."""
    internal_sku: str
    product_id: UUID
    product_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    method: str
    features: Dict[str, Any]


class MatchResultSchema(BaseModel):
    """Result of matching operation."""
    internal_sku: Optional[str]
    product_id: Optional[UUID]
    confidence: float = Field(ge=0.0, le=1.0)
    method: Optional[str]
    status: str
    candidates: List[MatchCandidateSchema]


class ConfirmMappingRequest(BaseModel):
    """Request to confirm a mapping."""
    customer_id: UUID
    customer_sku_norm: str
    customer_sku_raw: str
    internal_sku: str
    uom_from: Optional[str] = None
    uom_to: Optional[str] = None
    pack_factor: Optional[Decimal] = None


class ConfirmMappingResponse(BaseModel):
    """Response after confirming mapping."""
    id: UUID
    customer_id: UUID
    customer_sku_norm: str
    internal_sku: str
    status: str
    confidence: float
    support_count: int
    message: str


class SkuMappingSchema(BaseModel):
    """SKU mapping schema for list responses."""
    id: UUID
    customer_id: UUID
    customer_sku_norm: str
    customer_sku_raw_sample: Optional[str]
    internal_sku: str
    uom_from: Optional[str]
    uom_to: Optional[str]
    pack_factor: Optional[Decimal]
    status: str
    confidence: float
    support_count: int
    reject_count: int
    last_used_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class SkuMappingListResponse(BaseModel):
    """Paginated list of SKU mappings."""
    items: List[SkuMappingSchema]
    total: int
    page: int
    page_size: int
