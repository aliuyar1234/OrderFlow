# Data Model: Draft Orders Core

**Feature**: 013-draft-orders-core
**Date**: 2025-12-27

## Entity Definitions

### draft_order

```python
class DraftOrderStatus(str, Enum):
    NEW = "NEW"
    EXTRACTED = "EXTRACTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    READY = "READY"
    APPROVED = "APPROVED"
    PUSHING = "PUSHING"
    PUSHED = "PUSHED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"

class DraftOrder(Base):
    __tablename__ = "draft_order"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False, index=True)

    # Source
    document_id = Column(UUID(as_uuid=True), ForeignKey("document.id"), nullable=False)
    inbound_message_id = Column(UUID(as_uuid=True), ForeignKey("inbound_message.id"), nullable=True)

    # Header
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customer.id"), nullable=True)
    external_order_number = Column(String(200), nullable=True)
    order_date = Column(DATE, nullable=True)
    currency = Column(String(3), nullable=True)  # ISO 4217
    requested_delivery_date = Column(DATE, nullable=True)

    ship_to_json = Column(JSONB, nullable=True)
    bill_to_json = Column(JSONB, nullable=True)
    notes = Column(TEXT, nullable=True)

    # State & Workflow
    status = Column(String(20), nullable=False, default=DraftOrderStatus.NEW, index=True)
    ready_check_json = Column(JSONB, nullable=True)  # {"is_ready": bool, "blocking_reasons": [...]}

    # Confidence
    confidence_score = Column(Numeric(5, 4), nullable=True, index=True)  # Overall [0..1]
    extraction_confidence = Column(Numeric(5, 4), nullable=True)
    customer_confidence = Column(Numeric(5, 4), nullable=True)
    matching_confidence = Column(Numeric(5, 4), nullable=True)

    # Approval
    approved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    approved_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # ERP Push
    erp_order_id = Column(String(200), nullable=True)  # ERP's order number

    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default="now()")
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default="now()", onupdate="now()")

    # Relationships
    lines = relationship("DraftOrderLine", back_populates="draft_order", cascade="all, delete-orphan")
    issues = relationship("ValidationIssue", back_populates="draft_order")

    __table_args__ = (
        Index("idx_draft_order_status", "org_id", "status", "created_at"),
        Index("idx_draft_order_confidence", "org_id", "confidence_score"),
    )
```

### draft_order_line

```python
class MatchStatus(str, Enum):
    UNMATCHED = "UNMATCHED"
    SUGGESTED = "SUGGESTED"
    MATCHED = "MATCHED"
    OVERRIDDEN = "OVERRIDDEN"

class DraftOrderLine(Base):
    __tablename__ = "draft_order_line"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False, index=True)
    draft_order_id = Column(UUID(as_uuid=True), ForeignKey("draft_order.id"), nullable=False, index=True)

    line_no = Column(Integer, nullable=False)

    # Customer Data (extracted)
    customer_sku_raw = Column(String(500), nullable=True)
    customer_sku_norm = Column(String(500), nullable=True, index=True)  # Normalized
    product_description = Column(TEXT, nullable=True)

    qty = Column(Numeric(15, 4), nullable=True)
    uom = Column(String(20), nullable=True)
    unit_price = Column(Numeric(15, 4), nullable=True)
    currency = Column(String(3), nullable=True)
    requested_delivery_date = Column(DATE, nullable=True)

    # Matching
    internal_sku = Column(String(200), nullable=True, index=True)
    match_status = Column(String(20), nullable=False, default=MatchStatus.UNMATCHED)
    match_confidence = Column(Numeric(5, 4), nullable=True)
    match_method = Column(String(50), nullable=True)  # trigram, embedding, manual
    match_debug_json = Column(JSONB, nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default="now()")
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default="now()", onupdate="now()")

    # Relationships
    draft_order = relationship("DraftOrder", back_populates="lines")

    __table_args__ = (
        Index("idx_draft_line_lookup", "draft_order_id", "line_no"),
        UniqueConstraint("draft_order_id", "line_no", name="uq_draft_line_no"),
    )
```

## Relationships

- DraftOrder 1:N DraftOrderLine (cascade delete)
- DraftOrder 1:N ValidationIssue
- DraftOrder N:1 Customer (nullable)
- DraftOrder N:1 Document
- DraftOrder N:1 InboundMessage (nullable)

## SQL Queries

### Get Drafts for Review (Sorted by Confidence)

```sql
SELECT *
FROM draft_order
WHERE org_id = $1
  AND status IN ('NEEDS_REVIEW', 'READY')
ORDER BY confidence_score ASC, created_at ASC
LIMIT 50;
```

### Run Ready-Check

```python
def run_ready_check(draft_id: UUID) -> dict:
    draft = db.query(DraftOrder).get(draft_id)
    blocking_reasons = []

    if not draft.customer_id:
        blocking_reasons.append("customer_id missing")
    if not draft.currency:
        blocking_reasons.append("currency missing")
    if not draft.lines:
        blocking_reasons.append("No order lines")

    for line in draft.lines:
        if not line.qty or line.qty <= 0:
            blocking_reasons.append(f"Line {line.line_no}: invalid qty")
        if not line.uom:
            blocking_reasons.append(f"Line {line.line_no}: missing uom")
        if not line.internal_sku:
            blocking_reasons.append(f"Line {line.line_no}: missing internal_sku")

    error_issues = db.query(ValidationIssue).filter(
        ValidationIssue.draft_order_id == draft_id,
        ValidationIssue.severity == "ERROR",
        ValidationIssue.status == "OPEN"
    ).count()

    if error_issues > 0:
        blocking_reasons.append(f"{error_issues} ERROR-level issues")

    is_ready = len(blocking_reasons) == 0

    return {
        "is_ready": is_ready,
        "blocking_reasons": blocking_reasons,
        "passed_at": datetime.now(UTC).isoformat() if is_ready else None
    }
```
