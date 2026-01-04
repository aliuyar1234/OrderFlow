# Data Model: Validation Engine

**Feature**: Validation Engine
**Date**: 2025-12-27

## Entity Definitions

### ValidationIssue

**Purpose**: Represents a single validation rule violation.

**Fields**:
- `id`: UUID PRIMARY KEY
- `org_id`: UUID NOT NULL (multi-tenant)
- `draft_order_id`: UUID NOT NULL REFERENCES draft_order
- `draft_order_line_id`: UUID NULL REFERENCES draft_order_line (NULL for header issues)
- `type`: TEXT NOT NULL (e.g., UNKNOWN_PRODUCT, PRICE_MISMATCH)
- `severity`: TEXT NOT NULL (INFO, WARNING, ERROR)
- `status`: TEXT NOT NULL (OPEN, ACKNOWLEDGED, RESOLVED, OVERRIDDEN)
- `message`: TEXT NOT NULL
- `details_json`: JSONB NULL (issue-specific metadata)
- `resolved_at`: TIMESTAMPTZ NULL
- `resolved_by_user_id`: UUID NULL
- `created_at`: TIMESTAMPTZ DEFAULT NOW()

**Indexes**:
```sql
CREATE INDEX idx_issue_draft ON validation_issue(org_id, draft_order_id, status);
CREATE INDEX idx_issue_type ON validation_issue(org_id, type, status);
```

### ReadyCheckResult (Embedded in draft_order.ready_check_json)

**Structure**:
```json
{
  "is_ready": false,
  "blocking_reasons": ["UNKNOWN_PRODUCT", "MISSING_CUSTOMER"],
  "checked_at": "2025-12-27T10:00:00Z"
}
```

## Validation Rule Types (from SSOT §7.3)

### Header Rules
- `MISSING_CUSTOMER`: customer_id is NULL
- `MISSING_CURRENCY`: currency is NULL
- `INVALID_CURRENCY`: currency not in allowed list

### Line Rules
- `UNKNOWN_PRODUCT`: internal_sku not found in product catalog
- `INVALID_QTY`: qty <= 0 or non-numeric
- `UNKNOWN_UOM`: uom not in canonical UoM list
- `UOM_INCOMPATIBLE`: line.uom != product.base_uom and no conversion exists
- `MISSING_PRICE`: unit_price is NULL when customer_price exists
- `PRICE_MISMATCH`: unit_price deviates from customer_price beyond tolerance

## SQLAlchemy Model

```python
class ValidationIssue(Base):
    __tablename__ = "validation_issue"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    org_id = Column(UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False)
    draft_order_id = Column(UUID(as_uuid=True), ForeignKey("draft_order.id"), nullable=False)
    draft_order_line_id = Column(UUID(as_uuid=True), ForeignKey("draft_order_line.id"), nullable=True)
    type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    status = Column(String, nullable=False, default="OPEN")
    message = Column(Text, nullable=False)
    details_json = Column(JSONB, nullable=True)
    resolved_at = Column(TIMESTAMP(timezone=True), nullable=True)
    resolved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("severity IN ('INFO', 'WARNING', 'ERROR')", name="ck_issue_severity"),
        CheckConstraint("status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED', 'OVERRIDDEN')", name="ck_issue_status"),
        Index("idx_issue_draft", "org_id", "draft_order_id", "status"),
    )
```
