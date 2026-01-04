# Data Model: Customer Prices

**Date**: 2025-12-27

## Entity: CustomerPrice

**Purpose**: Customer-specific pricing with tiered pricing support.

**Fields**:
- `id`: UUID PRIMARY KEY
- `org_id`: UUID NOT NULL
- `customer_id`: UUID NOT NULL REFERENCES customer
- `internal_sku`: TEXT NOT NULL (normalized)
- `currency`: TEXT NOT NULL (e.g., EUR, USD)
- `uom`: TEXT NOT NULL (e.g., PCE, KG)
- `unit_price`: NUMERIC(12,4) NOT NULL CHECK (unit_price > 0)
- `min_qty`: NUMERIC(12,3) NOT NULL DEFAULT 1.000 CHECK (min_qty > 0)
- `valid_from`: DATE NULL
- `valid_to`: DATE NULL
- `status`: TEXT DEFAULT 'ACTIVE' (ACTIVE | INACTIVE)
- `created_at`: TIMESTAMPTZ DEFAULT NOW()
- `updated_at`: TIMESTAMPTZ DEFAULT NOW()

**Constraints**:
```sql
CONSTRAINT uq_customer_price UNIQUE (
    org_id, customer_id, internal_sku, currency, uom, min_qty,
    COALESCE(valid_from, '1900-01-01'), COALESCE(valid_to, '9999-12-31')
)
```

**Indexes**:
```sql
CREATE INDEX idx_customer_price_lookup ON customer_price(
    org_id, customer_id, internal_sku, currency, uom, status
);
CREATE INDEX idx_customer_price_sku ON customer_price(org_id, internal_sku);
```

## SQLAlchemy Model

```python
class CustomerPrice(Base):
    __tablename__ = "customer_price"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    org_id = Column(UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customer.id"), nullable=False)
    internal_sku = Column(String, nullable=False)
    currency = Column(String, nullable=False)
    uom = Column(String, nullable=False)
    unit_price = Column(Numeric(12, 4), nullable=False)
    min_qty = Column(Numeric(12, 3), nullable=False, server_default="1.000")
    valid_from = Column(Date, nullable=True)
    valid_to = Column(Date, nullable=True)
    status = Column(String, nullable=False, server_default="ACTIVE")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("unit_price > 0", name="ck_unit_price_positive"),
        CheckConstraint("min_qty > 0", name="ck_min_qty_positive"),
        UniqueConstraint(
            "org_id", "customer_id", "internal_sku", "currency", "uom",
            "min_qty",
            func.coalesce("valid_from", date(1900, 1, 1)),
            func.coalesce("valid_to", date(9999, 12, 31)),
            name="uq_customer_price"
        ),
    )
```

## Example Data

**Single Tier**:
```
customer_id: uuid-1
internal_sku: SKU-ABC
currency: EUR
uom: PCE
unit_price: 10.00
min_qty: 1
valid_from: NULL
valid_to: NULL
```

**Multi-Tier**:
```
Tier 1: min_qty=1, unit_price=€10.00
Tier 2: min_qty=100, unit_price=€9.00
Tier 3: min_qty=500, unit_price=€8.00
```

**Date-Based**:
```
Old Price: valid_from=2024-01-01, valid_to=2024-12-31, unit_price=€10.00
New Price: valid_from=2025-01-01, valid_to=NULL, unit_price=€11.00
```
