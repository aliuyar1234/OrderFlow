# Data Model: LLM-Based Extractors

**Feature**: 012-extractors-llm
**Date**: 2025-12-27

## Entity Extensions

### Document (Additional Fields)

```python
class Document(Base):
    # ... existing fields ...

    # LLM extraction specific
    layout_fingerprint = Column(String(64), nullable=True, index=True)  # SHA256 of structural metadata

    # Relationships
    feedback_events = relationship("FeedbackEvent", back_populates="document")
```

### FeedbackEvent

Stores user corrections for learning (few-shot examples).

```python
class FeedbackEventType(str, Enum):
    EXTRACTION_LINE_CORRECTED = "EXTRACTION_LINE_CORRECTED"
    CUSTOMER_CORRECTED = "CUSTOMER_CORRECTED"
    MATCH_CORRECTED = "MATCH_CORRECTED"

class FeedbackEvent(Base):
    __tablename__ = "feedback_event"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    document_id = Column(UUID(as_uuid=True), ForeignKey("document.id"), nullable=True)
    draft_order_id = Column(UUID(as_uuid=True), ForeignKey("draft_order.id"), nullable=True)

    layout_fingerprint = Column(String(64), nullable=True, index=True)
    before_json = Column(JSONB, nullable=True)  # Before correction
    after_json = Column(JSONB, nullable=True)   # After correction

    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default="now()")

    __table_args__ = (
        Index("idx_feedback_layout", "org_id", "layout_fingerprint", "event_type"),
    )
```

### DocLayoutProfile (Aggregated)

Aggregates feedback per layout fingerprint.

```python
class DocLayoutProfile(Base):
    __tablename__ = "doc_layout_profile"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False)
    layout_fingerprint = Column(String(64), nullable=False, index=True)

    sample_document_id = Column(UUID(as_uuid=True), ForeignKey("document.id"), nullable=True)
    occurrence_count = Column(Integer, default=1)
    correction_count = Column(Integer, default=0)

    avg_extraction_confidence = Column(Numeric(5, 4), nullable=True)
    last_seen_at = Column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "layout_fingerprint", name="uq_layout_profile"),
    )
```

## Canonical LLM Extraction Output (§7.1)

Same schema as rule-based, with additional fields:

```json
{
  "extractor_version": "llm_v1",
  "order": {...},
  "lines": [...],
  "confidence": {...},
  "warnings": [
    "Line 3: anchor check failed for SKU 'ABC-999'",
    "Estimated tokens: 5000, actual: 5200 (+4%)"
  ],
  "metadata": {
    "llm_provider": "openai",
    "llm_model": "gpt-4o-mini",
    "tokens_in": 4500,
    "tokens_out": 700,
    "cost_micros": 945,
    "latency_ms": 3200,
    "anchor_check_pass_rate": 0.92,
    "used_vision": false,
    "layout_fingerprint": "a3f8...",
    "few_shot_examples_count": 2
  }
}
```

## SQL Queries

### Retrieve Few-Shot Examples

```sql
-- Get last 3 corrections for matching layout fingerprint
SELECT
    before_json,
    after_json
FROM feedback_event
WHERE org_id = $1
  AND layout_fingerprint = $2
  AND event_type = 'EXTRACTION_LINE_CORRECTED'
ORDER BY created_at DESC
LIMIT 3;
```

### Update Layout Profile

```sql
-- Upsert doc_layout_profile
INSERT INTO doc_layout_profile (org_id, layout_fingerprint, occurrence_count, last_seen_at)
VALUES ($1, $2, 1, NOW())
ON CONFLICT (org_id, layout_fingerprint)
DO UPDATE SET
    occurrence_count = doc_layout_profile.occurrence_count + 1,
    last_seen_at = NOW();
```
