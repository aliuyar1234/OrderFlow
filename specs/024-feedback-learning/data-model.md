# Data Model: Feedback & Learning Loop

## Entity Definitions

### FeedbackEvent

Captures operator corrections and confirmations with before/after snapshots.

**Purpose**: Records all manual operator actions that improve system quality. Used for few-shot learning and quality monitoring.

**Schema**:
```python
class FeedbackEvent(Base):
    __tablename__ = "feedback_event"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[UUID] = mapped_column(ForeignKey("organization.id"), nullable=False, index=True)

    # Actor
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("user.id"), nullable=True)

    # Event classification
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Types: MAPPING_CONFIRMED, MAPPING_REJECTED, EXTRACTION_LINE_CORRECTED,
    #        EXTRACTION_FIELD_CORRECTED, CUSTOMER_SELECTED

    # Entity reference
    entity_type: Mapped[str] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[UUID] = mapped_column(nullable=True, index=True)
    draft_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("draft_order.id"),
        nullable=True,
        index=True
    )

    # Layout linkage for few-shot learning
    layout_fingerprint: Mapped[str] = mapped_column(String(64), nullable=True, index=True)

    # Before/after snapshots
    before_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    after_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Additional context (input_snippet for few-shot examples)
    meta_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)

    # Relationships
    actor_user: Mapped["User"] = relationship()
    draft_order: Mapped["DraftOrder"] = relationship()
```

**Event Type Examples**:

MAPPING_CONFIRMED:
```json
{
  "event_type": "MAPPING_CONFIRMED",
  "entity_type": "sku_mapping",
  "entity_id": "...",
  "before_json": {"status": "SUGGESTED", "confidence": 0.85},
  "after_json": {"status": "CONFIRMED", "internal_sku": "INT-999", "confidence": 1.0}
}
```

EXTRACTION_LINE_CORRECTED:
```json
{
  "event_type": "EXTRACTION_LINE_CORRECTED",
  "entity_type": "draft_order_line",
  "entity_id": "...",
  "layout_fingerprint": "abc123...",
  "before_json": {"qty": 10, "uom": "EA", "price": 99.00},
  "after_json": {"qty": 12, "uom": "BOX", "price": 99.00},
  "meta_json": {
    "input_snippet": "Order #12345\nQty: 10 EA\nPrice: $99\n...",
    "corrected_fields": ["qty", "uom"]
  }
}
```

---

### DocLayoutProfile

Aggregates metadata for PDF layouts to support few-shot example selection.

**Purpose**: Groups documents with similar layouts, tracks feedback volume per layout.

**Schema**:
```python
class DocLayoutProfile(Base):
    __tablename__ = "doc_layout_profile"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[UUID] = mapped_column(ForeignKey("organization.id"), nullable=False, index=True)

    # Layout identifier
    layout_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Usage statistics
    seen_count: Mapped[int] = mapped_column(default=1, nullable=False)
    example_count: Mapped[int] = mapped_column(default=0, nullable=False)
    # example_count = count of feedback_events for this layout

    # Temporal tracking
    last_seen_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)

    # Aggregate statistics
    stats_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Example: {"avg_page_count": 3, "avg_text_coverage": 0.68, "dominant_supplier": "Acme Inc"}

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint('org_id', 'layout_fingerprint', name='uq_doc_layout_profile'),
    )
```

---

### Document (Extended)

The Document entity is extended with layout_fingerprint field.

**Purpose**: Links documents to layout profiles for few-shot example selection.

**Schema Extension**:
```python
class Document(Base):
    __tablename__ = "document"

    # ... existing fields ...

    # Layout fingerprint
    layout_fingerprint: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    # Computed during PDF processing via generate_layout_fingerprint()
```

---

## Relationships

### FeedbackEvent → DraftOrder (Many-to-One, Optional)

Feedback events may link to draft orders for context.

```python
# FeedbackEvent
draft_order: Mapped["DraftOrder"] = relationship()

# Query feedback for draft
feedback = db.query(FeedbackEvent).filter_by(draft_order_id=draft.id).all()
```

---

### FeedbackEvent → User (Many-to-One, Optional)

Tracks which operator made the correction.

```python
# FeedbackEvent
actor_user: Mapped["User"] = relationship()

# Query user's corrections
corrections = db.query(FeedbackEvent).filter_by(
    actor_user_id=user.id,
    event_type="EXTRACTION_LINE_CORRECTED"
).count()
```

---

### Document → DocLayoutProfile (Many-to-One via fingerprint)

Documents with same layout share profile (no foreign key, joined via fingerprint).

```python
# Query documents with same layout
docs = db.query(Document).filter_by(
    org_id=org_id,
    layout_fingerprint=fingerprint
).all()

# Query profile for layout
profile = db.query(DocLayoutProfile).filter_by(
    org_id=org_id,
    layout_fingerprint=fingerprint
).first()
```

---

## Indexes

```sql
-- Feedback event lookups
CREATE INDEX idx_feedback_event_layout ON feedback_event(org_id, layout_fingerprint, created_at DESC);
CREATE INDEX idx_feedback_event_type ON feedback_event(org_id, event_type, created_at DESC);
CREATE INDEX idx_feedback_event_draft ON feedback_event(draft_order_id);

-- Layout profile queries
CREATE INDEX idx_doc_layout_profile_org_fp ON doc_layout_profile(org_id, layout_fingerprint);
CREATE INDEX idx_doc_layout_profile_seen ON doc_layout_profile(org_id, seen_count DESC);

-- Document layout lookup
CREATE INDEX idx_document_layout_fp ON document(org_id, layout_fingerprint);
```

---

## Layout Fingerprint Generation

**Algorithm**:
```python
import hashlib
import json

def generate_layout_fingerprint(pdf_metadata: dict) -> str:
    """Generate SHA256 hash from PDF layout structure."""
    fingerprint_data = {
        "page_count": pdf_metadata.get("page_count"),
        "page_dimensions": pdf_metadata.get("page_dimensions"),  # [(width, height), ...]
        "table_count": pdf_metadata.get("table_count"),
        "text_coverage_ratio": round(pdf_metadata.get("text_coverage_ratio", 0), 2)
    }

    # Normalize to canonical JSON
    canonical_json = json.dumps(fingerprint_data, sort_keys=True)
    return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
```

**Example**:
```python
metadata = {
    "page_count": 3,
    "page_dimensions": [(612, 792), (612, 792), (612, 792)],  # US Letter
    "table_count": 2,
    "text_coverage_ratio": 0.68
}
fingerprint = generate_layout_fingerprint(metadata)
# Result: "a3f5b2c7d1e8f9..."
```

---

## Few-Shot Example Selection

**Query Logic**:
```python
def get_few_shot_examples(layout_fingerprint: str, org_id: UUID, limit: int = 3) -> list:
    """Retrieve last N feedback examples for layout."""
    feedback_events = db.query(FeedbackEvent).filter(
        FeedbackEvent.org_id == org_id,
        FeedbackEvent.layout_fingerprint == layout_fingerprint,
        FeedbackEvent.event_type.in_([
            "EXTRACTION_LINE_CORRECTED",
            "EXTRACTION_FIELD_CORRECTED"
        ])
    ).order_by(FeedbackEvent.created_at.desc()).limit(limit).all()

    examples = []
    for event in feedback_events:
        input_snippet = event.meta_json.get("input_snippet", "")[:1500]
        examples.append({
            "input_snippet": input_snippet,
            "output": event.after_json
        })

    return examples
```

**Example Result**:
```python
[
    {
        "input_snippet": "Order #12345\nQty: 10 EA\nPrice: $99\n...",
        "output": {"qty": 12, "uom": "BOX", "price": 99.00}
    },
    {
        "input_snippet": "PO-456\nQuantity: 5 CASES\nUnit Price: $50\n...",
        "output": {"qty": 5, "uom": "CS", "price": 50.00}
    },
    {
        "input_snippet": "Invoice 789\n20 pieces @ $10 each\n...",
        "output": {"qty": 20, "uom": "EA", "price": 10.00}
    }
]
```

---

## Migration Strategy

### Alembic Migration

```python
"""Add feedback and layout tables

Revision ID: 024_feedback_learning
Revises: 023_approve_push
Create Date: 2025-12-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

def upgrade():
    # Create feedback_event table
    op.create_table(
        'feedback_event',
        sa.Column('id', UUID, primary_key=True),
        sa.Column('org_id', UUID, sa.ForeignKey('organization.id'), nullable=False),
        sa.Column('actor_user_id', UUID, sa.ForeignKey('user.id'), nullable=True),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=True),
        sa.Column('entity_id', UUID, nullable=True),
        sa.Column('draft_order_id', UUID, sa.ForeignKey('draft_order.id'), nullable=True),
        sa.Column('layout_fingerprint', sa.String(64), nullable=True),
        sa.Column('before_json', JSONB, nullable=False, server_default='{}'),
        sa.Column('after_json', JSONB, nullable=False, server_default='{}'),
        sa.Column('meta_json', JSONB, nullable=False, server_default='{}'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False)
    )

    # Create doc_layout_profile table
    op.create_table(
        'doc_layout_profile',
        sa.Column('id', UUID, primary_key=True),
        sa.Column('org_id', UUID, sa.ForeignKey('organization.id'), nullable=False),
        sa.Column('layout_fingerprint', sa.String(64), nullable=False),
        sa.Column('seen_count', sa.Integer, nullable=False, server_default='1'),
        sa.Column('example_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('last_seen_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('stats_json', JSONB, nullable=False, server_default='{}'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.UniqueConstraint('org_id', 'layout_fingerprint', name='uq_doc_layout_profile')
    )

    # Add layout_fingerprint to document table
    op.add_column('document', sa.Column('layout_fingerprint', sa.String(64), nullable=True))

    # Create indexes
    op.create_index('idx_feedback_event_layout', 'feedback_event', ['org_id', 'layout_fingerprint', 'created_at'])
    op.create_index('idx_feedback_event_type', 'feedback_event', ['org_id', 'event_type', 'created_at'])
    op.create_index('idx_doc_layout_profile_org_fp', 'doc_layout_profile', ['org_id', 'layout_fingerprint'])
    op.create_index('idx_document_layout_fp', 'document', ['org_id', 'layout_fingerprint'])

def downgrade():
    op.drop_table('feedback_event')
    op.drop_table('doc_layout_profile')
    op.drop_column('document', 'layout_fingerprint')
```
