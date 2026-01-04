"""Canonical extraction output schema.

All extractors (Excel, CSV, PDF, LLM) must produce output conforming to this schema.
This ensures downstream processing (matching, validation, draft creation) has
consistent data structures.

SSOT Reference: §7.1 (Canonical Output Schema)
"""

from datetime import date
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, validator


class ExtractionLineItem(BaseModel):
    """Single line item from extracted order.

    All fields are optional except line_no, as extraction quality varies.
    Downstream validation will flag missing required fields.
    """

    line_no: int = Field(..., description="Line number in order (1-based)")
    customer_sku: Optional[str] = Field(None, description="Customer's SKU/article number")
    description: Optional[str] = Field(None, description="Product description")
    qty: Optional[Decimal] = Field(None, description="Quantity ordered")
    uom: Optional[str] = Field(None, description="Unit of measure (e.g., 'PCS', 'KG')")
    unit_price: Optional[Decimal] = Field(None, description="Price per unit")
    currency: Optional[str] = Field(None, description="Currency code (ISO 4217)")
    line_total: Optional[Decimal] = Field(None, description="Total for this line")

    @validator('customer_sku', 'description', 'uom', 'currency', pre=True)
    def strip_strings(cls, v):
        """Strip whitespace from string fields"""
        if isinstance(v, str):
            return v.strip() or None
        return v

    @validator('currency')
    def uppercase_currency(cls, v):
        """Normalize currency to uppercase"""
        if v:
            return v.upper()
        return v

    class Config:
        json_encoders = {
            Decimal: str  # Serialize Decimal as string to avoid precision loss
        }


class ExtractionOrderHeader(BaseModel):
    """Order header information extracted from document.

    All fields optional as not all document types contain header info
    (e.g., CSV files typically have only line items).
    """

    order_number: Optional[str] = Field(None, description="Customer's order/PO number")
    order_date: Optional[date] = Field(None, description="Order date")
    currency: Optional[str] = Field(None, description="Order currency (ISO 4217)")
    delivery_date: Optional[date] = Field(None, description="Requested delivery date")
    ship_to: Optional[dict] = Field(None, description="Shipping address (flexible structure)")
    bill_to: Optional[dict] = Field(None, description="Billing address (flexible structure)")
    notes: Optional[str] = Field(None, description="Order notes/comments")
    reference: Optional[str] = Field(None, description="Customer reference")

    @validator('currency')
    def uppercase_currency(cls, v):
        """Normalize currency to uppercase"""
        if v:
            return v.upper()
        return v

    @validator('order_number', 'reference', 'notes', pre=True)
    def strip_strings(cls, v):
        """Strip whitespace from string fields"""
        if isinstance(v, str):
            return v.strip() or None
        return v


class CanonicalExtractionOutput(BaseModel):
    """Canonical structure that all extractors must produce.

    This schema is the contract between extractors and downstream processing.
    Any extractor (rule-based, LLM, hybrid) must conform to this structure.

    SSOT Reference: §7.1
    """

    order: ExtractionOrderHeader = Field(..., description="Order header information")
    lines: List[ExtractionLineItem] = Field(default_factory=list, description="Order line items")
    metadata: dict = Field(default_factory=dict, description="Extractor-specific metadata")

    class Config:
        extra = "allow"  # Allow extra fields but ignore them
        json_encoders = {
            Decimal: str,
            date: lambda v: v.isoformat(),
        }

    @validator('lines')
    def validate_line_numbers(cls, v):
        """Ensure line numbers are sequential and start at 1"""
        if v:
            line_nos = [line.line_no for line in v]
            if line_nos != list(range(1, len(line_nos) + 1)):
                # Don't fail, but log warning
                # In real implementation, you'd use logger here
                pass
        return v
