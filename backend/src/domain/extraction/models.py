"""
Domain models for extraction results following SSOT §7.1.
These are Pydantic models representing the canonical extraction output.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import date, datetime
from decimal import Decimal


class ShipToAddress(BaseModel):
    """Shipping address details"""
    company: Optional[str] = None
    street: Optional[str] = None
    zip: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None


class CustomerHint(BaseModel):
    """Customer detection hints from extraction"""
    name: Optional[str] = None
    email: Optional[str] = None
    erp_customer_number: Optional[str] = None


class OrderHeader(BaseModel):
    """Order header information per SSOT §7.1"""
    external_order_number: Optional[str] = None
    order_date: Optional[date] = None
    currency: Optional[str] = None
    requested_delivery_date: Optional[date] = None
    customer_hint: Optional[CustomerHint] = None
    notes: Optional[str] = None
    ship_to: Optional[ShipToAddress] = None


class OrderLine(BaseModel):
    """Order line item per SSOT §7.1"""
    line_no: int
    customer_sku_raw: Optional[str] = None
    product_description: Optional[str] = None
    qty: Optional[Decimal] = None
    uom: Optional[str] = None
    unit_price: Optional[Decimal] = None
    currency: Optional[str] = None
    requested_delivery_date: Optional[date] = None


class FieldConfidence(BaseModel):
    """Per-field confidence scores"""
    external_order_number: float = 0.0
    order_date: float = 0.0
    currency: float = 0.0
    customer_hint: float = 0.0


class LineConfidence(BaseModel):
    """Per-line field confidence scores"""
    customer_sku_raw: float = 0.0
    qty: float = 0.0
    uom: float = 0.0
    unit_price: float = 0.0


class ConfidenceScores(BaseModel):
    """Overall confidence structure per SSOT §7.1"""
    order: FieldConfidence
    lines: List[LineConfidence]
    overall: float = Field(ge=0.0, le=1.0)


class ExtractionWarning(BaseModel):
    """Warning message from extraction"""
    code: str
    message: str


class CanonicalExtractionOutput(BaseModel):
    """
    Canonical extraction output schema per SSOT §7.1.
    All extractors (rule-based and LLM) must output this format.
    """
    order: OrderHeader
    lines: List[OrderLine]
    confidence: ConfidenceScores
    warnings: List[ExtractionWarning] = Field(default_factory=list)
    extractor_version: str = "rule_v1"


class ExtractionMetrics(BaseModel):
    """Metrics collected during extraction"""
    runtime_ms: int
    page_count: Optional[int] = None
    text_chars_total: Optional[int] = None
    text_coverage_ratio: Optional[float] = None
    lines_extracted: int = 0
    warnings_count: int = 0

    # Format detection metadata
    detected_separator: Optional[str] = None
    detected_decimal_separator: Optional[str] = None
    detected_encoding: Optional[str] = None


class ExtractionResult(BaseModel):
    """
    Complete extraction result including canonical output and metadata.
    This is what extractors return.
    """
    canonical_output: CanonicalExtractionOutput
    metrics: ExtractionMetrics
    extracted_text_storage_key: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True
