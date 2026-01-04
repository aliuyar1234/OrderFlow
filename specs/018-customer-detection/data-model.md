# Data Model: Customer Detection

**Feature**: Customer Detection (Multi-Signal Detection & Disambiguation)
**Date**: 2025-12-27

## Entity Definitions

### CustomerDetectionCandidate

**Purpose**: Represents a candidate customer identified during detection, with aggregated score and signal provenance.

**Lifecycle**: Created when detection runs on draft order. Status updated when operator selects customer (SELECTED) or rejects (REJECTED).

**Relationships**:
- Belongs to Organization (org_id)
- Belongs to DraftOrder (draft_order_id)
- References Customer (customer_id)

**Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() | Unique identifier |
| org_id | UUID | NOT NULL, REFERENCES organization(id) | Multi-tenant isolation |
| draft_order_id | UUID | NOT NULL, REFERENCES draft_order(id) | Draft this candidate belongs to |
| customer_id | UUID | NOT NULL, REFERENCES customer(id) | Candidate customer |
| score | NUMERIC(5,4) | NOT NULL, CHECK (score >= 0 AND score <= 0.999) | Aggregated confidence score (0.0000-0.9990) |
| signals_json | JSONB | NOT NULL | Signal provenance (which signals triggered, values) |
| status | TEXT | NOT NULL, DEFAULT 'CANDIDATE' | Candidate status: CANDIDATE, SELECTED, REJECTED |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Creation timestamp |

**Indexes**:
```sql
CREATE INDEX idx_candidate_draft ON customer_detection_candidate(org_id, draft_order_id, score DESC);
CREATE INDEX idx_candidate_customer ON customer_detection_candidate(org_id, customer_id);
```

**Example signals_json**:
```json
{
  "from_email_exact": true,
  "from_domain": "muster.com",
  "doc_erp_number": "4711",
  "doc_name_fuzzy": "Muster GmbH",
  "name_sim": 0.85
}
```

**Status Values**:
- `CANDIDATE`: Initial state. Customer is a potential match.
- `SELECTED`: Operator selected this customer (or auto-selected).
- `REJECTED`: Operator chose a different customer, this candidate was not selected.

---

### DraftOrder (Extended Fields)

**Purpose**: Draft order entity extended with customer detection metadata.

**New Fields**:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| customer_candidates_json | JSONB | NULL | Top 5 candidates for UI quick access (denormalized) |
| customer_confidence | NUMERIC(5,4) | NULL, CHECK (customer_confidence >= 0 AND customer_confidence <= 0.999) | Confidence in customer_id assignment |

**Example customer_candidates_json**:
```json
[
  {
    "customer_id": "uuid-1",
    "name": "Muster GmbH",
    "score": 0.93,
    "signals": {
      "from_email_exact": true,
      "from_domain": "muster.com"
    }
  },
  {
    "customer_id": "uuid-2",
    "name": "Muster GmbH & Co. KG",
    "score": 0.75,
    "signals": {
      "from_domain": "muster.com"
    }
  }
]
```

**Notes**:
- `customer_candidates_json` is updated whenever detection runs
- Only stores Top 5 to optimize payload size
- Includes denormalized customer name for UI rendering (avoids JOIN)

---

## Signal Definitions

### Signal S1: From-Email Exact Match

**Description**: Inbound email sender exactly matches a customer_contact.email.

**Score**: 0.95

**Extraction**:
```python
if inbound_message.from_email:
    contacts = db.query(CustomerContact).filter(
        CustomerContact.org_id == org_id,
        CustomerContact.email == inbound_message.from_email
    ).all()

    for contact in contacts:
        candidates.append(Candidate(
            customer_id=contact.customer_id,
            signals={"from_email_exact": True},
            score=0.95
        ))
```

**Example**: Email from `buyer@muster.com` → matches `customer_contact.email='buyer@muster.com'` → score=0.95

---

### Signal S2: From-Domain Match

**Description**: Inbound email domain (part after @) matches domain of any customer_contact.email.

**Score**: 0.75

**Extraction**:
```python
if inbound_message.from_email:
    domain = inbound_message.from_email.split('@')[1]

    contacts = db.query(CustomerContact).filter(
        CustomerContact.org_id == org_id,
        CustomerContact.email.like(f'%@{domain}')
    ).all()

    for contact in contacts:
        if contact.customer_id not in existing_candidate_ids:
            candidates.append(Candidate(
                customer_id=contact.customer_id,
                signals={"from_domain": domain},
                score=0.75
            ))
```

**Example**: Email from `another-buyer@muster.com` → no exact match, but domain `muster.com` matches existing contact → score=0.75

**Edge Case**: Generic domains (gmail.com, outlook.com) trigger S2 for many customers → likely causes ambiguity.

---

### Signal S3: To-Address Token (MVP Disabled)

**Description**: Email delivered to customer-specific inbox (e.g., orders+customer-4711@orderflow.ai).

**Score**: 0.98

**MVP Status**: Disabled. Org-level routing only (single inbox per org).

**Future Implementation**: Parse to_address for customer token, lookup customer by token.

---

### Signal S4: Document Customer Number

**Description**: Regex extracts customer number from document text, matches customer.erp_customer_number.

**Score**: 0.98

**Extraction**:
```python
patterns = [
    r'Kundennr[.:]?\s*([A-Z0-9-]{3,20})',
    r'Customer No[.:]?\s*([A-Z0-9-]{3,20})',
    r'Debitor[.:]?\s*([A-Z0-9-]{3,20})',
]

doc_text = get_document_text(draft_order.document_id)

for pattern in patterns:
    match = re.search(pattern, doc_text, re.IGNORECASE)
    if match:
        erp_number = match.group(1).strip()
        customer = db.query(Customer).filter(
            Customer.org_id == org_id,
            Customer.erp_customer_number == erp_number
        ).first()

        if customer:
            candidates.append(Candidate(
                customer_id=customer.id,
                signals={"doc_erp_number": erp_number},
                score=0.98
            ))
            break
```

**Example**: PDF contains "Kundennr: 4711" → matches `customer.erp_customer_number='4711'` → score=0.98

---

### Signal S5: Document Company Name Fuzzy Match

**Description**: Extracts company name from document header (heuristic or LLM), fuzzy matches against customer.name using pg_trgm similarity.

**Score**: 0.40 + 0.60 * name_sim (clamped at 0.85)

**Extraction**:
```python
company_name = extract_company_name(doc_text)  # Heuristic: first non-email line in header

if company_name:
    results = db.execute(
        """
        SELECT id, name, similarity(name, :query) AS sim
        FROM customer
        WHERE org_id = :org_id
          AND similarity(name, :query) > 0.40
        ORDER BY sim DESC
        LIMIT 5
        """,
        {"org_id": org_id, "query": company_name}
    ).fetchall()

    for row in results:
        score = min(0.85, 0.40 + 0.60 * row.sim)
        candidates.append(Candidate(
            customer_id=row.id,
            signals={
                "doc_name_fuzzy": company_name,
                "name_sim": row.sim
            },
            score=score
        ))
```

**Example**: PDF contains "Muster GmbH" → similarity("Muster GmbH", "Muster GmbH & Co. KG") = 0.80 → score = 0.40 + 0.60*0.80 = 0.88 (clamped to 0.85)

**Index Requirement**:
```sql
CREATE INDEX idx_customer_name_trgm ON customer USING GIN (name gin_trgm_ops);
```

---

### Signal S6: LLM Customer Hint (Fallback)

**Description**: Uses customer_hint from LLM extraction output (name, email, erp_customer_number) when other signals yield no strong candidates.

**Score**: Depends on hint type (same as S1/S4/S5)

**Extraction**:
```python
if not candidates or max(c.score for c in candidates) < 0.60:
    hint = extraction_output.get("order", {}).get("customer_hint", {})

    # Hint: erp_customer_number (same as S4)
    if hint.get("erp_customer_number"):
        customer = db.query(Customer).filter(
            Customer.org_id == org_id,
            Customer.erp_customer_number == hint["erp_customer_number"]
        ).first()
        if customer:
            candidates.append(Candidate(
                customer_id=customer.id,
                signals={"llm_hint_erp": hint["erp_customer_number"]},
                score=0.98
            ))

    # Hint: email (same as S1)
    if hint.get("email"):
        # ... lookup contact by email
        candidates.append(Candidate(..., score=0.95))

    # Hint: name (same as S5)
    if hint.get("name"):
        # ... fuzzy name match
        candidates.append(Candidate(..., score=0.40 + 0.60*name_sim))
```

**Example**: LLM extraction provides `customer_hint.erp_customer_number='4711'` → matches customer → score=0.98 (same as S4, but marked as llm_hint in signals_json)

---

## Aggregation Formula

**Probabilistic Combination**: When multiple signals apply to the same customer, scores are combined using:

```
score(c) = 1 - Π(1 - score_i)
```

Where:
- `c` = candidate customer
- `score_i` = individual signal scores (S1-S6)
- `Π` = product (multiply all terms)

**Example**:
- Candidate has S2 (domain match) = 0.75 and S4 (doc customer number) = 0.98
- Combined score = 1 - (1 - 0.75) * (1 - 0.98)
- Combined score = 1 - 0.25 * 0.02 = 1 - 0.005 = 0.995

**Clamping**: Final score is clamped to [0.0000, 0.9990] to prevent 1.0 (absolute certainty).

**Implementation**:
```python
def aggregate_candidates(candidates: list[Candidate]) -> list[Candidate]:
    by_customer = {}
    for c in candidates:
        if c.customer_id not in by_customer:
            by_customer[c.customer_id] = []
        by_customer[c.customer_id].append(c)

    aggregated = []
    for customer_id, cands in by_customer.items():
        complement_product = 1.0
        signals = {}

        for cand in cands:
            complement_product *= (1 - cand.score)
            signals.update(cand.signals)

        score = min(0.999, 1 - complement_product)
        aggregated.append(Candidate(
            customer_id=customer_id,
            signals=signals,
            score=score
        ))

    return aggregated
```

---

## Auto-Selection Logic

**Conditions** (all must be true):
1. `top1.score >= org.settings.customer_detection.auto_select_threshold` (default: 0.90)
2. `top1.score - top2.score >= org.settings.customer_detection.min_gap` (default: 0.07)

**Actions**:
- Set `draft_order.customer_id = top1.customer_id`
- Set `draft_order.customer_confidence = top1.score`
- Update `candidate.status = 'SELECTED'` for top1
- Update `candidate.status = 'REJECTED'` for all others

**Ambiguity Handling** (if auto-selection fails):
- Set `draft_order.customer_id = NULL`
- Set `draft_order.customer_confidence = 0.0`
- Create `validation_issue` with type='CUSTOMER_AMBIGUOUS', severity='ERROR'
- Set `draft_order.status = 'NEEDS_REVIEW'`

**Example Scenarios**:

| Top1 | Top2 | Gap | Threshold | Result |
|------|------|-----|-----------|--------|
| 0.95 | 0.60 | 0.35 | 0.90 | ✅ Auto-select (high score + large gap) |
| 0.92 | 0.88 | 0.04 | 0.90 | ❌ Ambiguous (gap too small) |
| 0.85 | 0.50 | 0.35 | 0.90 | ❌ Ambiguous (top1 below threshold) |
| 0.90 | 0.82 | 0.08 | 0.90 | ✅ Auto-select (gap meets min_gap=0.07) |

---

## SQLAlchemy Models

### CustomerDetectionCandidate Model

```python
from sqlalchemy import Column, String, Numeric, ForeignKey, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

class CustomerDetectionCandidate(Base):
    __tablename__ = "customer_detection_candidate"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    org_id = Column(UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False)
    draft_order_id = Column(UUID(as_uuid=True), ForeignKey("draft_order.id"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customer.id"), nullable=False)
    score = Column(Numeric(5, 4), nullable=False)
    signals_json = Column(JSONB, nullable=False)
    status = Column(String, nullable=False, default="CANDIDATE")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationships
    organization = relationship("Organization")
    draft_order = relationship("DraftOrder")
    customer = relationship("Customer")

    # Constraints
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 0.999", name="ck_candidate_score_range"),
        CheckConstraint("status IN ('CANDIDATE', 'SELECTED', 'REJECTED')", name="ck_candidate_status"),
        Index("idx_candidate_draft", "org_id", "draft_order_id", score.desc()),
        Index("idx_candidate_customer", "org_id", "customer_id"),
    )
```

### DraftOrder Model Extensions

```python
class DraftOrder(Base):
    # ... existing fields ...

    customer_candidates_json = Column(JSONB, nullable=True)
    customer_confidence = Column(Numeric(5, 4), nullable=True)

    __table_args__ = (
        # ... existing constraints ...
        CheckConstraint("customer_confidence >= 0 AND customer_confidence <= 0.999", name="ck_customer_confidence_range"),
    )
```

---

## Database Migration

```sql
-- Migration: Add customer detection support

-- Create customer_detection_candidate table
CREATE TABLE customer_detection_candidate (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organization(id),
    draft_order_id UUID NOT NULL REFERENCES draft_order(id),
    customer_id UUID NOT NULL REFERENCES customer(id),
    score NUMERIC(5,4) NOT NULL,
    signals_json JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'CANDIDATE',
    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT ck_candidate_score_range CHECK (score >= 0 AND score <= 0.999),
    CONSTRAINT ck_candidate_status CHECK (status IN ('CANDIDATE', 'SELECTED', 'REJECTED'))
);

CREATE INDEX idx_candidate_draft ON customer_detection_candidate(org_id, draft_order_id, score DESC);
CREATE INDEX idx_candidate_customer ON customer_detection_candidate(org_id, customer_id);

-- Add fields to draft_order
ALTER TABLE draft_order
    ADD COLUMN customer_candidates_json JSONB NULL,
    ADD COLUMN customer_confidence NUMERIC(5,4) NULL,
    ADD CONSTRAINT ck_customer_confidence_range CHECK (customer_confidence >= 0 AND customer_confidence <= 0.999);

-- Add trigram index for fuzzy name matching
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_customer_name_trgm ON customer USING GIN (name gin_trgm_ops);
```

---

## Relationships and Constraints

### Foreign Key Relationships

```
customer_detection_candidate
├── org_id → organization.id (ON DELETE CASCADE)
├── draft_order_id → draft_order.id (ON DELETE CASCADE)
└── customer_id → customer.id (ON DELETE RESTRICT)

draft_order
└── customer_id → customer.id (ON DELETE RESTRICT)
```

**Rationale**:
- `ON DELETE CASCADE` for org and draft: If draft is deleted, candidates should be deleted too.
- `ON DELETE RESTRICT` for customer: Cannot delete customer if referenced by candidates or drafts (data integrity).

### Uniqueness Constraints

No UNIQUE constraint on `(draft_order_id, customer_id)` because:
- Same customer may appear multiple times with different signals during iterative detection
- Status transitions (CANDIDATE → SELECTED) are updates, not inserts
- Historical tracking: May want to see how scores changed over time

**Implementation**: Application-level upsert logic handles deduplication during candidate generation.

---

## Performance Considerations

### Query Optimization

**Top 5 Candidates for UI**:
```sql
SELECT c.id, c.name, cdc.score, cdc.signals_json
FROM customer_detection_candidate cdc
JOIN customer c ON c.id = cdc.customer_id
WHERE cdc.org_id = :org_id
  AND cdc.draft_order_id = :draft_id
ORDER BY cdc.score DESC
LIMIT 5;
```

**Optimization**: Use `draft_order.customer_candidates_json` instead (no JOIN, faster):
```python
# Pre-computed in detection service
draft_order.customer_candidates_json = [
    {
        "customer_id": str(c.customer_id),
        "name": c.customer.name,  # Denormalized
        "score": c.score,
        "signals": c.signals_json
    }
    for c in top_5_candidates
]
```

### Index Usage

- `idx_candidate_draft (org_id, draft_order_id, score DESC)`: Covers Top 5 query
- `idx_candidate_customer (org_id, customer_id)`: Supports analytics (which customers are frequently ambiguous?)
- `idx_customer_name_trgm (name gin_trgm_ops)`: Enables fast fuzzy name search

### Estimated Row Counts

- **customer_detection_candidate**: ~5-10 candidates per draft × 10k drafts/month = 50k-100k rows/month
- **Retention**: Archive candidates after 90 days (only keep for active drafts + recent history)

---

## Validation Rules

### Candidate Validation

- `score` must be in [0.0000, 0.9990] (enforced by CHECK constraint)
- `signals_json` must be valid JSON object (enforced by JSONB type)
- `status` must be one of: CANDIDATE, SELECTED, REJECTED (enforced by CHECK constraint)
- Only one candidate per draft can have `status='SELECTED'` (enforced by application logic)

### Draft Order Validation

- `customer_confidence` must be in [0.0000, 0.9990] if not NULL (enforced by CHECK constraint)
- If `customer_id` is set, `customer_confidence` should be > 0 (enforced by application logic)
- If `customer_id` is NULL and no CUSTOMER_AMBIGUOUS issue exists, detection has not run yet (enforced by application logic)
