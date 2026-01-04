# Customer Detection Module

## Overview

The Customer Detection module provides multi-signal customer identification for incoming order documents. It automatically detects the correct customer using email metadata, document content, and optional LLM hints.

## Quick Start

```python
from backend.src.domain.customer_detection.service import CustomerDetectionService
from backend.src.database import get_db

# Initialize service
db = next(get_db())
org_id = UUID("...")
service = CustomerDetectionService(db, org_id)

# Run detection
result = service.detect_customer(
    from_email="buyer@customer-a.com",
    document_text="Kundennr: 4711\nACME GmbH\n...",
    llm_hint={"erp_customer_number": "4711"},
    auto_select_threshold=0.90,
    min_gap=0.07
)

# Check result
if result.auto_selected:
    print(f"Auto-selected: {result.selected_customer_id}")
    print(f"Confidence: {result.confidence:.1%}")
elif result.ambiguous:
    print(f"Ambiguous: {result.reason}")
    print(f"Top candidates: {len(result.candidates)}")
```

## Architecture

### Components

1. **SignalExtractor** (`signal_extractor.py`)
   - Extracts detection signals from raw data
   - Implements S1-S6 signal types
   - Handles regex patterns, fuzzy matching setup

2. **CustomerDetectionService** (`service.py`)
   - Main orchestrator
   - Queries database for matches
   - Aggregates signals probabilistically
   - Determines auto-selection

3. **Domain Models** (`models.py`)
   - `DetectionSignal`: Individual evidence piece
   - `Candidate`: Customer with aggregated signals
   - `DetectionResult`: Complete detection output

### Signal Types

| Signal | Type | Score | Description |
|--------|------|-------|-------------|
| S1 | from_email_exact | 0.95 | Exact email match in contacts |
| S2 | from_domain | 0.75 | Domain match (excludes generic) |
| S3 | to_address_token | 0.98 | (MVP: disabled) |
| S4 | doc_customer_number | 0.98 | Regex-extracted customer # |
| S5 | doc_company_name | 0.40-0.85 | Trigram fuzzy name match |
| S6 | llm_hint | Variable | LLM extraction hints |

## Database Schema

### customer_detection_candidate

Stores detection results for each draft order.

```sql
CREATE TABLE customer_detection_candidate (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES org(id),
    draft_order_id UUID NOT NULL,
    customer_id UUID NOT NULL REFERENCES customer(id),
    score FLOAT NOT NULL,
    signals_json JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'CANDIDATE',
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    UNIQUE (draft_order_id, customer_id)
);
```

**Indexes:**
- `idx_customer_detection_draft` on `draft_order_id`
- `idx_customer_detection_org` on `org_id`
- `idx_customer_detection_status` on `status`

**Required Extensions:**
- `pg_trgm` (trigram similarity for fuzzy name matching)

## API Usage

### POST /api/v1/customer-detection/detect

**Request:**
```json
{
  "from_email": "buyer@customer-a.com",
  "document_text": "Kundennr: 4711\nACME GmbH\n...",
  "llm_hint": {
    "erp_customer_number": "4711",
    "name": "ACME GmbH"
  },
  "auto_select_threshold": 0.90,
  "min_gap": 0.07
}
```

**Response:**
```json
{
  "candidates": [
    {
      "customer_id": "550e8400-e29b-41d4-a716-446655440000",
      "customer_name": "ACME GmbH",
      "aggregate_score": 0.995,
      "signals": [
        {
          "signal_type": "from_email_exact",
          "value": "buyer@customer-a.com",
          "score": 0.95,
          "metadata": {}
        },
        {
          "signal_type": "doc_customer_number",
          "value": "4711",
          "score": 0.98,
          "metadata": {"pattern": "Kundennr: (.*)"}
        }
      ],
      "signal_badges": ["Email Match", "Customer # in Doc"]
    }
  ],
  "selected_customer_id": "550e8400-e29b-41d4-a716-446655440000",
  "confidence": 0.995,
  "auto_selected": true,
  "ambiguous": false,
  "reason": "Auto-selected with 99.5% confidence"
}
```

## Configuration

Org-level settings in `org.settings_json`:

```json
{
  "customer_detection": {
    "auto_select_threshold": 0.90,
    "min_gap": 0.07,
    "enable_llm_hints": true,
    "fuzzy_name_min_similarity": 0.40
  }
}
```

## Testing

### Unit Tests

```bash
pytest backend/tests/unit/customer_detection/
```

Tests cover:
- Signal extraction (S1-S6)
- Probabilistic aggregation
- Auto-select logic
- Edge cases (generic domains, typos, etc.)

### Integration Tests

```bash
pytest backend/tests/integration/customer_detection/
```

Tests cover:
- End-to-end detection flow
- Database queries with fixtures
- Performance benchmarks

## Performance

**Expected Latency (p95):**
- Detection on single inbound: <100ms
- Fuzzy name search (1000 customers): <50ms
- Regex extraction (10-page PDF): <10ms

**Optimization:**
- Use GIN trigram index on `customer.name`
- Cache org settings
- Limit fuzzy search to top 5 results

## Error Handling

### No Candidates Found
- Returns `ambiguous=True`
- `reason`: "No customer matches found"
- UI shows manual search/selection

### Multiple Close Matches
- Returns top 5 candidates ranked by score
- `ambiguous=True` if gap < min_gap
- `reason`: "Insufficient gap to #2"
- UI shows dropdown for selection

### Database Errors
- Service logs error
- API returns 500 with error message
- Graceful degradation (manual selection always available)

## Observability

### Logging

```python
logger.info(f"Auto-selected customer {customer_id} (score={score:.3f}, gap={gap:.3f})")
logger.info(f"Ambiguous: insufficient gap ({gap:.3f} < {min_gap})")
logger.debug(f"Email signal {email} matched {count} contacts")
```

### Metrics (Future)

- `orderflow_detection_auto_selected_total`
- `orderflow_detection_ambiguous_total`
- `orderflow_detection_latency_ms`
- `orderflow_detection_signals_extracted_total{signal_type}`

## Common Patterns

### Pattern 1: Detection in Extraction Pipeline

```python
# After document extraction
extraction_result = extractor.extract(document)

# Run customer detection
detection_result = service.detect_customer(
    from_email=inbound_message.from_email,
    document_text=extraction_result.raw_text,
    llm_hint=extraction_result.order.get("customer_hint")
)

# Store candidates
for candidate in detection_result.candidates:
    db_candidate = CustomerDetectionCandidate(
        org_id=org_id,
        draft_order_id=draft_order.id,
        customer_id=candidate.customer_id,
        score=candidate.aggregate_score,
        signals_json={"signals": [s.to_dict() for s in candidate.signals]},
        status="SELECTED" if candidate.customer_id == detection_result.selected_customer_id else "CANDIDATE"
    )
    db.add(db_candidate)

# Set draft order customer
if detection_result.auto_selected:
    draft_order.customer_id = detection_result.selected_customer_id
    draft_order.customer_confidence = detection_result.confidence
```

### Pattern 2: Manual Customer Selection

```python
# User selects customer from UI
selected_customer_id = request.customer_id

# Update candidate status
candidates = db.query(CustomerDetectionCandidate).filter_by(
    draft_order_id=draft_order.id
).all()

for candidate in candidates:
    if candidate.customer_id == selected_customer_id:
        candidate.status = "SELECTED"
    else:
        candidate.status = "REJECTED"

# Update draft order
draft_order.customer_id = selected_customer_id
draft_order.customer_confidence = max(
    candidate.score if candidate else 0.0,
    0.90  # Human override baseline
)

db.commit()
```

## Migration

Migration file: `backend/migrations/versions/005_create_customer_detection_candidate.py`

Includes:
- Table creation
- Indexes
- pg_trgm extension
- GIN trigram index on customer.name
- updated_at trigger

## Related Documentation

- **Algorithm Details:** `specs/018-customer-detection/ALGORITHM.md`
- **Feature Spec:** `specs/018-customer-detection/spec.md`
- **Implementation Plan:** `specs/018-customer-detection/plan.md`
- **SSOT Reference:** `SSOT_SPEC.md` §7.6
