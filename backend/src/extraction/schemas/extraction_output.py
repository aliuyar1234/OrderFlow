"""Pydantic schemas for LLM extraction output validation (SSOT §7.5.3)."""

from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field, field_validator


class CustomerHint(BaseModel):
    """Customer hint from LLM extraction."""

    name: str | None = None
    email: str | None = None
    erp_customer_number: str | None = None


class ShipTo(BaseModel):
    """Shipping address."""

    company: str | None = None
    street: str | None = None
    zip: str | None = None
    city: str | None = None
    country: str | None = None


class OrderHeader(BaseModel):
    """Order header extracted by LLM."""

    external_order_number: str | None = None
    order_date: date | None = None
    currency: str | None = None
    requested_delivery_date: date | None = None
    customer_hint: CustomerHint = Field(default_factory=CustomerHint)
    notes: str | None = None
    ship_to: ShipTo | None = None

    @field_validator('currency')
    @classmethod
    def validate_currency(cls, v: str | None) -> str | None:
        """Validate currency is ISO 4217."""
        if v is None:
            return v
        # Basic ISO 4217 validation (3-letter uppercase)
        if len(v) != 3 or not v.isupper():
            return None
        return v


class OrderLine(BaseModel):
    """Order line extracted by LLM."""

    line_no: Annotated[int, Field(ge=1)]
    customer_sku_raw: str | None = None
    product_description: str | None = None
    qty: Annotated[float | None, Field(gt=0, le=1_000_000)] = None
    uom: str | None = None
    unit_price: float | None = None
    currency: str | None = None
    requested_delivery_date: date | None = None

    @field_validator('currency')
    @classmethod
    def validate_currency(cls, v: str | None) -> str | None:
        """Validate currency is ISO 4217."""
        if v is None:
            return v
        if len(v) != 3 or not v.isupper():
            return None
        return v


class OrderHeaderConfidence(BaseModel):
    """Confidence scores for order header fields."""

    external_order_number: Annotated[float, Field(ge=0, le=1)] = 0.0
    order_date: Annotated[float, Field(ge=0, le=1)] = 0.0
    currency: Annotated[float, Field(ge=0, le=1)] = 0.0
    customer_hint: Annotated[float, Field(ge=0, le=1)] = 0.0


class LineConfidence(BaseModel):
    """Confidence scores for a single line."""

    customer_sku_raw: Annotated[float, Field(ge=0, le=1)] = 0.0
    qty: Annotated[float, Field(ge=0, le=1)] = 0.0
    uom: Annotated[float, Field(ge=0, le=1)] = 0.0
    unit_price: Annotated[float, Field(ge=0, le=1)] = 0.0


class ExtractionConfidence(BaseModel):
    """Confidence scores for entire extraction."""

    order: OrderHeaderConfidence = Field(default_factory=OrderHeaderConfidence)
    lines: list[LineConfidence] = Field(default_factory=list)
    overall: Annotated[float, Field(ge=0, le=1)] = 0.0


class ExtractionWarning(BaseModel):
    """Warning from extraction process."""

    code: str
    message: str


class ExtractionOutput(BaseModel):
    """Complete extraction output from LLM (SSOT §7.5.3 schema)."""

    order: OrderHeader
    lines: Annotated[list[OrderLine], Field(max_length=500)] = Field(default_factory=list)
    confidence: ExtractionConfidence = Field(default_factory=ExtractionConfidence)
    warnings: list[ExtractionWarning] = Field(default_factory=list)
    extractor_version: str = "llm_v1"

    @field_validator('lines')
    @classmethod
    def renumber_lines_if_needed(cls, lines: list[OrderLine]) -> list[OrderLine]:
        """Re-number lines sequentially if gaps/duplicates detected."""
        if not lines:
            return lines

        # Check for sequential numbering
        expected = list(range(1, len(lines) + 1))
        actual = [line.line_no for line in lines]

        if actual != expected:
            # Re-number
            for idx, line in enumerate(lines, start=1):
                line.line_no = idx

        return lines
