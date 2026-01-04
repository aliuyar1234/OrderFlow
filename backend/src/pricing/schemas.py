"""Pydantic schemas for customer pricing"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from uuid import UUID
from datetime import datetime, date
from decimal import Decimal


class CustomerPriceCreate(BaseModel):
    """Schema for creating a new customer price"""
    customer_id: UUID
    internal_sku: str = Field(..., min_length=1, max_length=200)
    currency: str = Field(..., min_length=3, max_length=3)
    uom: str = Field(..., min_length=1, max_length=20)
    unit_price: Decimal = Field(..., gt=0, decimal_places=4)
    min_qty: Decimal = Field(default=Decimal("1.000"), gt=0, decimal_places=3)
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    source: str = Field(default="IMPORT", max_length=50)

    @field_validator('currency')
    @classmethod
    def validate_currency(cls, v: str) -> str:
        """Validate and normalize currency code"""
        return v.upper()

    @field_validator('internal_sku')
    @classmethod
    def normalize_sku(cls, v: str) -> str:
        """Normalize SKU (trim whitespace)"""
        return v.strip()

    @field_validator('valid_to')
    @classmethod
    def validate_date_range(cls, v: Optional[date], info) -> Optional[date]:
        """Validate that valid_to is after valid_from"""
        if v is not None and 'valid_from' in info.data:
            valid_from = info.data['valid_from']
            if valid_from is not None and v < valid_from:
                raise ValueError("valid_to must be after valid_from")
        return v

    class Config:
        from_attributes = True


class CustomerPriceUpdate(BaseModel):
    """Schema for updating an existing customer price (partial updates)"""
    unit_price: Optional[Decimal] = Field(None, gt=0, decimal_places=4)
    min_qty: Optional[Decimal] = Field(None, gt=0, decimal_places=3)
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    source: Optional[str] = Field(None, max_length=50)

    @field_validator('valid_to')
    @classmethod
    def validate_date_range(cls, v: Optional[date], info) -> Optional[date]:
        """Validate that valid_to is after valid_from"""
        if v is not None and 'valid_from' in info.data:
            valid_from = info.data['valid_from']
            if valid_from is not None and v < valid_from:
                raise ValueError("valid_to must be after valid_from")
        return v

    class Config:
        from_attributes = True


class CustomerPriceResponse(BaseModel):
    """Schema for customer price response"""
    id: UUID
    org_id: UUID
    customer_id: UUID
    internal_sku: str
    currency: str
    uom: str
    unit_price: Decimal
    min_qty: Decimal
    valid_from: Optional[date]
    valid_to: Optional[date]
    source: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomerPriceListResponse(BaseModel):
    """Schema for paginated customer price list response"""
    items: list[CustomerPriceResponse]
    total: int
    page: int
    per_page: int
    total_pages: int

    class Config:
        from_attributes = True


class PriceImportRow(BaseModel):
    """Schema for a single row in customer price CSV import"""
    erp_customer_number: Optional[str] = None
    customer_name: Optional[str] = None
    internal_sku: str
    currency: str
    uom: str
    unit_price: Decimal
    min_qty: Decimal = Decimal("1.000")
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None

    @field_validator('internal_sku')
    @classmethod
    def normalize_sku(cls, v: str) -> str:
        """Normalize SKU"""
        return v.strip()

    @field_validator('currency')
    @classmethod
    def normalize_currency(cls, v: str) -> str:
        """Normalize currency code"""
        return v.upper()

    class Config:
        from_attributes = True


class PriceImportResult(BaseModel):
    """Schema for CSV import result"""
    imported: int = 0
    updated: int = 0
    failed: int = 0
    errors: list[dict] = Field(default_factory=list)

    class Config:
        from_attributes = True


class PriceLookupRequest(BaseModel):
    """Schema for price lookup request"""
    customer_id: UUID
    internal_sku: str
    currency: str
    uom: str
    qty: Decimal
    date: Optional[date] = None

    class Config:
        from_attributes = True


class PriceLookupResponse(BaseModel):
    """Schema for price lookup response"""
    found: bool
    unit_price: Optional[Decimal] = None
    min_qty: Optional[Decimal] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    price_id: Optional[UUID] = None

    class Config:
        from_attributes = True
