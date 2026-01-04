"""Pydantic schemas for catalog domain (products, UoM)"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime


# Canonical UoM codes per SSOT §6.2
CANONICAL_UOMS = {"ST", "M", "CM", "MM", "KG", "G", "L", "ML", "KAR", "PAL", "SET"}


class UnitOfMeasureBase(BaseModel):
    """Base schema for UnitOfMeasure"""
    code: str = Field(..., min_length=1, max_length=10)
    name: str = Field(..., min_length=1, max_length=100)
    conversion_factor: Optional[float] = None


class UnitOfMeasureCreate(UnitOfMeasureBase):
    """Schema for creating a new UnitOfMeasure"""
    pass


class UnitOfMeasureUpdate(BaseModel):
    """Schema for updating a UnitOfMeasure"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    conversion_factor: Optional[float] = None


class UnitOfMeasureResponse(UnitOfMeasureBase):
    """Schema for UnitOfMeasure response"""
    id: UUID
    org_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductBase(BaseModel):
    """Base schema for Product"""
    internal_sku: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    base_uom: str = Field(..., min_length=1, max_length=10)
    uom_conversions_json: Dict[str, Any] = Field(default_factory=dict)
    active: bool = True
    attributes_json: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('base_uom')
    @classmethod
    def validate_base_uom(cls, v: str) -> str:
        """Validate base_uom is a canonical UoM code"""
        if v.upper() not in CANONICAL_UOMS:
            raise ValueError(
                f"Invalid base_uom: {v}. Must be one of: {', '.join(sorted(CANONICAL_UOMS))}"
            )
        return v.upper()

    @field_validator('uom_conversions_json')
    @classmethod
    def validate_uom_conversions(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate UoM conversions structure"""
        if not isinstance(v, dict):
            raise ValueError("uom_conversions_json must be a dictionary")

        for uom_code, conversion in v.items():
            if not isinstance(conversion, dict):
                raise ValueError(f"Conversion for {uom_code} must be a dictionary")
            if "to_base" not in conversion:
                raise ValueError(f"Conversion for {uom_code} must have 'to_base' key")
            if not isinstance(conversion["to_base"], (int, float)):
                raise ValueError(f"to_base for {uom_code} must be a number")
            if conversion["to_base"] <= 0:
                raise ValueError(f"to_base for {uom_code} must be positive")

        return v


class ProductCreate(ProductBase):
    """Schema for creating a new Product"""
    pass


class ProductUpdate(BaseModel):
    """Schema for updating a Product"""
    name: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    base_uom: Optional[str] = Field(None, min_length=1, max_length=10)
    uom_conversions_json: Optional[Dict[str, Any]] = None
    active: Optional[bool] = None
    attributes_json: Optional[Dict[str, Any]] = None

    @field_validator('base_uom')
    @classmethod
    def validate_base_uom(cls, v: Optional[str]) -> Optional[str]:
        """Validate base_uom is a canonical UoM code"""
        if v is not None and v.upper() not in CANONICAL_UOMS:
            raise ValueError(
                f"Invalid base_uom: {v}. Must be one of: {', '.join(sorted(CANONICAL_UOMS))}"
            )
        return v.upper() if v else None

    @field_validator('uom_conversions_json')
    @classmethod
    def validate_uom_conversions(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Validate UoM conversions structure"""
        if v is None:
            return v

        if not isinstance(v, dict):
            raise ValueError("uom_conversions_json must be a dictionary")

        for uom_code, conversion in v.items():
            if not isinstance(conversion, dict):
                raise ValueError(f"Conversion for {uom_code} must be a dictionary")
            if "to_base" not in conversion:
                raise ValueError(f"Conversion for {uom_code} must have 'to_base' key")
            if not isinstance(conversion["to_base"], (int, float)):
                raise ValueError(f"to_base for {uom_code} must be a number")
            if conversion["to_base"] <= 0:
                raise ValueError(f"to_base for {uom_code} must be positive")

        return v


class ProductResponse(ProductBase):
    """Schema for Product response"""
    id: UUID
    org_id: UUID
    updated_source_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductSearchParams(BaseModel):
    """Schema for product search parameters"""
    search: Optional[str] = Field(None, description="Search term for SKU, name, or description")
    active: Optional[bool] = Field(None, description="Filter by active status")
    limit: int = Field(50, ge=1, le=100, description="Number of results per page")
    offset: int = Field(0, ge=0, description="Number of results to skip")


class ProductImportRow(BaseModel):
    """Schema for a single product import row"""
    internal_sku: str
    name: str
    base_uom: str
    description: Optional[str] = None
    manufacturer: Optional[str] = None
    ean: Optional[str] = None
    category: Optional[str] = None
    uom_conversions: Optional[str] = None  # JSON string


class ProductImportError(BaseModel):
    """Schema for product import error"""
    row: int
    sku: Optional[str] = None
    error: str


class ProductImportResult(BaseModel):
    """Schema for product import result"""
    total_rows: int
    imported_count: int
    error_count: int
    errors: list[ProductImportError] = Field(default_factory=list)
