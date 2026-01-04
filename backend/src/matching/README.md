# Matching Module

**Feature**: 017-matching-engine
**SSOT References**: §7.7 (Hybrid Search), §7.7.6 (Scoring Formula), §7.10 (Learning Loop)

## Overview

The matching module implements hybrid SKU matching for OrderFlow, combining:
- **Confirmed mappings** (learning loop with 0.99 confidence)
- **Trigram similarity** (pg_trgm on SKU and description)
- **Vector embeddings** (pgvector cosine similarity - stub for future)
- **UoM and price penalties** (prevent incompatible matches)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    HybridMatcher                            │
│  (implements MatcherPort)                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Check confirmed_mapping (sku_mapping WHERE CONFIRMED)  │
│     └─> Return immediately if found (confidence=0.99)      │
│                                                             │
│  2. Trigram search (pg_trgm)                               │
│     ├─> SKU similarity                                     │
│     └─> Description similarity                             │
│                                                             │
│  3. Vector search (pgvector) [stub for future]             │
│     └─> Cosine similarity on embeddings                    │
│                                                             │
│  4. Merge candidates (union by product_id)                 │
│                                                             │
│  5. Score candidates (MatchScorer)                         │
│     ├─> S_tri = max(S_tri_sku, 0.7*S_tri_desc)            │
│     ├─> S_emb = clamp((cosine_sim+1)/2, 0..1)             │
│     ├─> S_hybrid = 0.62*S_tri + 0.38*S_emb                │
│     ├─> P_uom = 1.0 | 0.9 | 0.2                            │
│     ├─> P_price = 1.0 | 0.85 | 0.65                        │
│     └─> confidence = S_hybrid * P_uom * P_price            │
│                                                             │
│  6. Rank by confidence DESC                                 │
│                                                             │
│  7. Auto-apply if confidence >= 0.92 AND gap >= 0.10       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Files

- **`ports.py`**: MatcherPort interface, MatchInput/Result/Candidate dataclasses
- **`hybrid_matcher.py`**: HybridMatcher implementation
- **`scorer.py`**: MatchScorer with penalty calculations
- **`schemas.py`**: Pydantic schemas for API requests/responses
- **`router.py`**: FastAPI endpoints (suggest, confirm, list)
- **`ALGORITHM.md`**: Detailed algorithm documentation
- **`README.md`**: This file

## API Endpoints

### POST /api/v1/mappings/suggest

Suggest product matches for a customer SKU.

**Request**:
```json
{
  "customer_id": "uuid",
  "customer_sku_norm": "ABC123",
  "customer_sku_raw": "AB-123",
  "product_description": "Cable 3x1.5mm",
  "uom": "ST",
  "unit_price": 10.50,
  "qty": 100,
  "currency": "EUR"
}
```

**Response**:
```json
{
  "internal_sku": "PROD-123",
  "product_id": "uuid",
  "confidence": 0.95,
  "method": "hybrid",
  "status": "SUGGESTED",
  "candidates": [
    {
      "internal_sku": "PROD-123",
      "product_id": "uuid",
      "product_name": "Cable 3x1.5mm 100m",
      "confidence": 0.95,
      "method": "hybrid",
      "features": {
        "S_tri": 0.88,
        "S_emb": 0.85,
        "P_uom": 1.0,
        "P_price": 1.0
      }
    }
  ]
}
```

### POST /api/v1/mappings/confirm

Confirm a SKU mapping (learning loop).

**Request**:
```json
{
  "customer_id": "uuid",
  "customer_sku_norm": "ABC123",
  "customer_sku_raw": "AB-123",
  "internal_sku": "PROD-123",
  "uom_from": "KAR",
  "uom_to": "ST",
  "pack_factor": 12.0
}
```

**Response**:
```json
{
  "id": "uuid",
  "customer_id": "uuid",
  "customer_sku_norm": "ABC123",
  "internal_sku": "PROD-123",
  "status": "CONFIRMED",
  "confidence": 1.0,
  "support_count": 1,
  "message": "Mapping created and confirmed"
}
```

### GET /api/v1/mappings

List SKU mappings with filtering.

**Query Parameters**:
- `customer_id`: Filter by customer (optional)
- `status`: Filter by status (CONFIRMED, SUGGESTED, REJECTED, DEPRECATED)
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 50, max: 100)

**Response**:
```json
{
  "items": [...],
  "total": 150,
  "page": 1,
  "page_size": 50
}
```

## Database Schema

### sku_mapping Table

```sql
CREATE TABLE sku_mapping (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES org(id),
    customer_id UUID NOT NULL REFERENCES customer(id),
    customer_sku_norm TEXT NOT NULL,
    customer_sku_raw_sample TEXT,
    internal_sku TEXT NOT NULL,
    uom_from TEXT,
    uom_to TEXT,
    pack_factor NUMERIC(18, 6),
    status TEXT NOT NULL,  -- SUGGESTED, CONFIRMED, REJECTED, DEPRECATED
    confidence NUMERIC(5, 4) NOT NULL DEFAULT 0.0,
    support_count INTEGER NOT NULL DEFAULT 0,
    reject_count INTEGER NOT NULL DEFAULT 0,
    last_used_at TIMESTAMPTZ,
    created_by UUID REFERENCES user(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Unique constraint for active mappings only
CREATE UNIQUE INDEX uq_sku_mapping_customer_sku_active
ON sku_mapping(org_id, customer_id, customer_sku_norm)
WHERE status IN ('CONFIRMED', 'SUGGESTED');
```

## Usage Example

```python
from matching import HybridMatcher, MatchInput
from database import get_db

# Create matcher
with get_db() as db:
    matcher = HybridMatcher(db)

    # Create input
    match_input = MatchInput(
        org_id=org_uuid,
        customer_id=customer_uuid,
        customer_sku_norm="ABC123",
        customer_sku_raw="AB-123",
        product_description="Cable 3x1.5mm",
        uom="ST",
        unit_price=Decimal("10.50"),
        qty=Decimal("100"),
        currency="EUR",
        order_date="2025-12-27"
    )

    # Run matching
    result = matcher.match(match_input)

    print(f"Status: {result.status}")
    print(f"Top match: {result.internal_sku} (confidence: {result.confidence})")
    print(f"Candidates: {len(result.candidates)}")
```

## Learning Loop

When Ops confirms a mapping:
1. `sku_mapping` is created/updated with `status=CONFIRMED`, `confidence=1.0`
2. `support_count` is incremented
3. Future matches with same `customer_sku_norm` → auto-matched with `confidence=0.99`

This creates a positive feedback loop where the system learns from user corrections.

## Performance

**Expected Latency** (per line):
- Confirmed mapping lookup: < 5ms
- Trigram search: < 50ms (with GIN index)
- Vector search: < 50ms (with HNSW index)
- Scoring: < 10ms
- **Total**: < 500ms p95

**Required Indexes**:
```sql
-- Trigram indexes (GIN)
CREATE INDEX idx_product_internal_sku_trgm
ON product USING gin (internal_sku gin_trgm_ops);

CREATE INDEX idx_product_name_desc_trgm
ON product USING gin ((name || ' ' || COALESCE(description, '')) gin_trgm_ops);
```

## Future Enhancements

1. **Vector Embeddings**: Complete integration when embedding feature (016) is ready
2. **Price Penalties**: Implement when `customer_price` table exists
3. **Feedback Events**: Log to `feedback_event` table for analytics
4. **Batch Optimization**: Optimize `match_batch()` with bulk queries
5. **Caching**: Cache confirmed mappings in Redis for faster lookup
6. **Rejection Tracking**: Auto-deprecate mappings when `reject_count >= threshold`

## Testing

Run matching tests:
```bash
pytest backend/tests/unit/matching/
pytest backend/tests/integration/matching/
```

## References

- **SSOT**: §7.7.5-7.7.7 (Hybrid Search, Scoring, Thresholds)
- **SSOT**: §7.10.1 (Confirmed Mappings)
- **SSOT**: §5.4.12 (sku_mapping schema)
- **Spec**: `specs/017-matching-engine/spec.md`
- **Algorithm**: `backend/src/matching/ALGORITHM.md`
