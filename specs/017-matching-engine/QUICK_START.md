# Quick Start: Matching Engine

## 5-Minute Overview

The matching engine maps customer SKUs to internal product SKUs using a hybrid approach.

## How It Works

```
Customer SKU "ABC-123" → Internal SKU "PROD-999"
                ↓
    [1] Check confirmed_mapping table
        └─> If found: return immediately (confidence 0.99)
                ↓
    [2] Search products with trigram similarity
        ├─> SKU similarity: "ABC-123" vs "PROD-999" 
        └─> Description similarity: "Cable 3mm" vs "Cable 3x1.5mm"
                ↓
    [3] Score candidates
        ├─> Hybrid: 62% trigram + 38% embedding
        ├─> UoM penalty: compatible = 1.0, incompatible = 0.2
        └─> Price penalty: within tolerance = 1.0, mismatch = 0.65
                ↓
    [4] Auto-apply if confidence >= 0.92 AND gap >= 0.10
        └─> Status: SUGGESTED
```

## API Usage

### 1. Suggest Matches

```bash
POST /api/v1/mappings/suggest
{
  "customer_id": "uuid",
  "customer_sku_norm": "ABC123",
  "product_description": "Cable 3x1.5mm"
}

→ Returns top 5 candidates with confidence scores
```

### 2. Confirm Mapping (Learning Loop)

```bash
POST /api/v1/mappings/confirm
{
  "customer_id": "uuid",
  "customer_sku_norm": "ABC123",
  "internal_sku": "PROD-999"
}

→ Creates confirmed mapping
→ Future matches auto-apply this mapping
```

### 3. List Mappings

```bash
GET /api/v1/mappings?customer_id=uuid&status=CONFIRMED

→ Returns paginated list of mappings
```

## Integration Example

```python
from matching import HybridMatcher, MatchInput

# In your draft processing worker
matcher = HybridMatcher(db)

for line in draft_order.lines:
    result = matcher.match(MatchInput(
        org_id=org_id,
        customer_id=customer_id,
        customer_sku_norm=line.customer_sku_norm,
        customer_sku_raw=line.customer_sku_raw,
        product_description=line.description,
        uom=line.uom
    ))
    
    # Update line with match result
    line.internal_sku = result.internal_sku
    line.match_confidence = result.confidence
    line.match_status = result.status
    line.match_candidates_json = [c.to_dict() for c in result.candidates]
```

## Setup Requirements

1. **Database Migration**:
   ```bash
   alembic upgrade head
   ```

2. **PostgreSQL Extensions**:
   ```sql
   CREATE EXTENSION IF NOT EXISTS pg_trgm;
   ```

3. **Indexes** (for performance):
   ```sql
   CREATE INDEX idx_product_internal_sku_trgm
   ON product USING gin (internal_sku gin_trgm_ops);
   
   CREATE INDEX idx_product_name_desc_trgm
   ON product USING gin ((name || ' ' || COALESCE(description, '')) gin_trgm_ops);
   ```

4. **Router Registration**:
   ```python
   # backend/src/main.py
   from matching import matching_router
   app.include_router(matching_router)
   ```

## Key Concepts

**Confirmed Mapping**: User-confirmed SKU mapping with highest priority (0.99 confidence)

**Trigram Similarity**: Fast string matching using PostgreSQL pg_trgm (works for alphanumeric codes)

**Hybrid Score**: 62% trigram + 38% embedding (embedding stub for future)

**Penalties**: UoM incompatibility and price mismatches reduce confidence to prevent bad auto-applies

**Auto-Apply**: If top match has confidence ≥ 0.92 AND 0.10 gap to second match → auto-suggest

**Learning Loop**: Confirmed mappings bypass algorithmic search → system learns from user

## Statuses

- **MATCHED**: Confirmed mapping applied (bypassed search)
- **SUGGESTED**: Auto-applied match (high confidence)
- **UNMATCHED**: No auto-apply, manual review required

## Files to Know

- `backend/src/matching/hybrid_matcher.py` - Main matching logic
- `backend/src/matching/scorer.py` - Confidence calculation
- `backend/src/matching/router.py` - API endpoints
- `backend/src/matching/ALGORITHM.md` - Detailed algorithm docs

## Performance

- **Confirmed mapping lookup**: < 5ms
- **Trigram search**: < 50ms (with indexes)
- **Total per line**: < 500ms p95

## What's Deferred

- Vector embeddings (needs embedding feature 016)
- Price penalties (needs customer_price table)
- Feedback event logging (needs feedback_event table)
- Rejection tracking and auto-deprecation

All stubs ready, just waiting for dependencies.
