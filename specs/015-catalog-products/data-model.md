# Data Model: Catalog & Products Management

**Feature**: 015-catalog-products
**Date**: 2025-12-27

## SQLAlchemy Models

### Product Entity (§5.4.10)

```python
from sqlalchemy import Column, String, Text, Boolean, TIMESTAMP, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid

class Product(Base):
    __tablename__ = 'product'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    internal_sku = Column(String(255), nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    base_uom = Column(String(10), nullable=False)  # Canonical UoM
    uom_conversions_json = Column(JSONB, nullable=False, default={})
    active = Column(Boolean, nullable=False, default=True)
    attributes_json = Column(JSONB, nullable=False, default={})
    updated_source_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('org_id', 'internal_sku', name='uq_product_org_sku'),
        Index('idx_product_search', 'org_id', 'active'),
        Index('idx_product_trgm', func.to_tsvector('simple', name + ' ' + func.coalesce(description, '')), postgresql_using='gin'),
        Index('idx_product_attributes', 'attributes_json', postgresql_using='gin'),
    )

    def __repr__(self):
        return f"<Product {self.internal_sku}: {self.name}>"
```

### CustomerPrice Entity (§5.4.11)

```python
class CustomerPrice(Base):
    __tablename__ = 'customer_price'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey('customer.id'), nullable=False)
    internal_sku = Column(String(255), nullable=False)  # FK to product
    currency = Column(String(3), nullable=False)  # EUR, CHF, USD
    uom = Column(String(10), nullable=False)
    unit_price = Column(Numeric(15, 4), nullable=False)
    min_qty = Column(Numeric(15, 4), nullable=False, default=1)
    valid_from = Column(TIMESTAMP(timezone=True), nullable=True)
    valid_to = Column(TIMESTAMP(timezone=True), nullable=True)
    source = Column(String(50), nullable=False, default='IMPORT')
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('org_id', 'customer_id', 'internal_sku', 'min_qty', name='uq_customer_price'),
        Index('idx_customer_price_lookup', 'org_id', 'customer_id', 'internal_sku', 'min_qty'),
    )
```

## Canonical UoM Constants

```python
CANONICAL_UOMS = {
    'ST',   # Stück (piece)
    'M',    # Meter
    'CM',   # Centimeter
    'MM',   # Millimeter
    'KG',   # Kilogram
    'G',    # Gram
    'L',    # Liter
    'ML',   # Milliliter
    'KAR',  # Karton (carton/box)
    'PAL',  # Palette (pallet)
    'SET',  # Set
}

def is_canonical_uom(uom: str) -> bool:
    return uom.upper() in CANONICAL_UOMS
```

## CSV Import DTOs

```python
from pydantic import BaseModel, validator
from typing import Dict, Any, Optional

class ProductImportRow(BaseModel):
    internal_sku: str
    name: str
    base_uom: str
    description: Optional[str] = None
    manufacturer: Optional[str] = None
    EAN: Optional[str] = None
    category: Optional[str] = None
    uom_conversions: Optional[str] = None  # JSON string

    @validator('base_uom')
    def validate_base_uom(cls, v):
        if v.upper() not in CANONICAL_UOMS:
            raise ValueError(f"Invalid UoM: {v}. Must be one of {CANONICAL_UOMS}")
        return v.upper()

    @validator('uom_conversions')
    def validate_uom_conversions(cls, v):
        if v:
            try:
                conv = json.loads(v)
                for uom, data in conv.items():
                    if uom.upper() not in CANONICAL_UOMS:
                        raise ValueError(f"Invalid conversion UoM: {uom}")
                    if 'to_base' not in data or not isinstance(data['to_base'], (int, float)):
                        raise ValueError(f"Invalid conversion format for {uom}")
                return conv
            except json.JSONDecodeError:
                raise ValueError("uom_conversions must be valid JSON")
        return {}

class CustomerPriceImportRow(BaseModel):
    customer_id: Optional[str] = None  # UUID
    customer_erp_number: Optional[str] = None  # Lookup if customer_id not provided
    internal_sku: str
    currency: str
    uom: str
    unit_price: float
    min_qty: float = 1.0
    valid_from: Optional[str] = None  # ISO date
    valid_to: Optional[str] = None  # ISO date

    @validator('currency')
    def validate_currency(cls, v):
        if v.upper() not in ['EUR', 'CHF', 'USD']:
            raise ValueError(f"Invalid currency: {v}")
        return v.upper()

    @validator('unit_price', 'min_qty')
    def validate_positive(cls, v):
        if v < 0:
            raise ValueError("Must be non-negative")
        return v
```

## API Response Schemas

```python
class ImportResult(BaseModel):
    total_rows: int
    imported_count: int
    error_count: int
    error_rows: List[Dict[str, Any]]  # [{row_number, internal_sku, error_message}]
    error_csv_url: Optional[str] = None  # Downloadable error CSV

class ProductSearchResult(BaseModel):
    products: List[Product]
    total: int
```

## Relationships

- Product (1) ← (many) CustomerPrice (via internal_sku, soft FK)
- Product (1) → (1) ProductEmbedding (from 016-embedding-layer)
- Customer (1) → (many) CustomerPrice
