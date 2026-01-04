# Matching Algorithm Documentation

## Overview

The OrderFlow matching engine uses a hybrid approach combining confirmed mappings, trigram similarity, and vector embeddings to map customer SKUs to internal product SKUs.

**SSOT References**: §7.7 (Hybrid Search), §7.7.6 (Scoring Formula), §7.10 (Learning Loop)

## Pipeline

The matching pipeline executes in the following order:

### 1. Confirmed Mapping Lookup

**Priority**: Highest (confidence = 0.99)

Check `sku_mapping` table for a CONFIRMED mapping:

```sql
SELECT * FROM sku_mapping
WHERE org_id = :org_id
  AND customer_id = :customer_id
  AND customer_sku_norm = :customer_sku_norm
  AND status = 'CONFIRMED'
```

If found, return immediately with:
- `confidence = 0.99`
- `method = "exact_mapping"`
- `status = "MATCHED"`

This bypasses all algorithmic matching.

### 2. Trigram Search

**Technology**: PostgreSQL `pg_trgm` extension

Search products using trigram similarity on two axes:

#### SKU Similarity

```sql
SELECT id, similarity(internal_sku, :customer_sku_norm) AS sim
FROM product
WHERE org_id = :org_id
  AND active = true
  AND similarity(internal_sku, :customer_sku_norm) > 0.3
ORDER BY sim DESC
LIMIT 30
```

#### Description Similarity

```sql
SELECT id, similarity(name || ' ' || COALESCE(description, ''), :product_description) AS sim
FROM product
WHERE org_id = :org_id
  AND active = true
  AND similarity(name || ' ' || COALESCE(description, ''), :product_description) > 0.3
ORDER BY sim DESC
LIMIT 30
```

**Result**: Top 30 candidates from each search, merged by product ID.

### 3. Vector Search (Optional)

**Technology**: PostgreSQL `pgvector` extension

Search products using cosine similarity on embeddings:

```sql
SELECT id, embedding <=> :query_vector AS distance
FROM product_embedding
WHERE org_id = :org_id
ORDER BY embedding <=> :query_vector
LIMIT 30
```

**Result**: Top 30 candidates by vector similarity.

**Note**: This step is skipped if embeddings are not enabled or unavailable. The system works with trigram alone.

### 4. Candidate Merging

Merge trigram and vector candidates by product ID (union):

```python
product_map = {}
for product in trigram_candidates:
    product_map[product.id] = product
for product in vector_candidates:
    product_map[product.id] = product
```

**Result**: Unique list of product candidates.

### 5. Hybrid Scoring

For each candidate, calculate match confidence using the hybrid formula:

#### Formula Components

**Trigram Score (S_tri)**:
```
S_tri = max(S_tri_sku, 0.7 * S_tri_desc)
```

Where:
- `S_tri_sku`: Trigram similarity of customer SKU vs internal SKU
- `S_tri_desc`: Trigram similarity of product description vs product name+description

**Embedding Score (S_emb)**:
```
S_emb = clamp((cosine_similarity + 1) / 2, 0.0, 1.0)
```

Converts cosine similarity [-1, 1] to [0, 1].

**Mapping Score (S_map)**:
- `S_map = 1.0` if confirmed mapping exists
- `S_map = 0.0` otherwise

**Hybrid Raw Score (S_hybrid_raw)**:
```
if S_map > 0:
    S_hybrid_raw = 0.99 * S_map
else:
    S_hybrid_raw = 0.62 * S_tri + 0.38 * S_emb
```

Weights: 62% trigram (fast, exact-ish), 38% embedding (slow, semantic).

#### Penalties

**UoM Penalty (P_uom)**:
- `1.0`: Compatible (line UoM matches product base_uom or exists in uom_conversions_json)
- `0.9`: Missing/unknown UoM
- `0.2`: Incompatible UoM

**Price Penalty (P_price)**:
- `1.0`: Within tolerance or no reference price
- `0.85`: Mismatch > tolerance but <= 2× tolerance (warning)
- `0.65`: Mismatch > 2× tolerance (strong mismatch)

Default tolerance: 5%

**Note**: Price penalty requires `customer_price` table (not yet implemented). Currently returns `1.0` (no penalty).

#### Final Confidence

```
match_confidence = clamp(S_hybrid_raw * P_uom * P_price, 0.0, 1.0)
```

### 6. Ranking and Selection

Sort candidates by `match_confidence` DESC.

Store Top 5 candidates in `match_debug_json` for UI display and debugging.

### 7. Auto-Apply Logic

Check if top candidate should be auto-applied:

```python
auto_apply_threshold = 0.92  # org setting
auto_apply_gap = 0.10        # org setting

if top1.confidence >= auto_apply_threshold:
    gap = top1.confidence - (top2.confidence if top2 else 0.0)
    if gap >= auto_apply_gap:
        status = "SUGGESTED"
        internal_sku = top1.internal_sku
    else:
        status = "UNMATCHED"
        internal_sku = None
else:
    status = "UNMATCHED"
    internal_sku = None
```

**Status Values**:
- `MATCHED`: Confirmed mapping applied
- `SUGGESTED`: Auto-applied match (high confidence)
- `UNMATCHED`: No auto-apply, manual review required

## Learning Loop

When Ops confirms a mapping (clicks "Confirm Mapping" in UI):

1. **Upsert `sku_mapping`**:
   - If exists: increment `support_count`, update `last_used_at`
   - If new: create with `support_count = 1`, `status = CONFIRMED`, `confidence = 1.0`

2. **Feedback Event** (TODO):
   - Create `feedback_event` with `event_type = MAPPING_CONFIRMED`
   - Store before/after JSON for analytics

3. **Future Matches**:
   - Next line with same `customer_sku_norm` → automatically matched with `confidence = 0.99`

## Performance Characteristics

**Expected Latency** (per line):
- Confirmed mapping lookup: < 5ms
- Trigram search: < 50ms (with GIN index)
- Vector search: < 50ms (with HNSW index)
- Scoring: < 10ms
- **Total**: < 500ms p95

**Accuracy Goals**:
- Top 1 accuracy: ≥ 85%
- Top 3 accuracy: ≥ 95%
- Auto-apply error rate: < 2%

## Required Database Extensions

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;
```

## Required Indexes

```sql
-- Trigram indexes (GIN)
CREATE INDEX idx_product_internal_sku_trgm ON product USING gin (internal_sku gin_trgm_ops);
CREATE INDEX idx_product_name_desc_trgm ON product USING gin ((name || ' ' || COALESCE(description, '')) gin_trgm_ops);

-- Vector index (HNSW) - when embeddings implemented
-- CREATE INDEX idx_product_embedding_hnsw ON product_embedding USING hnsw (embedding vector_cosine_ops);
```

## Error Handling

**No Candidates Found**:
- Return `MatchResult` with `status = UNMATCHED`, `confidence = 0.0`, `candidates = []`
- Not treated as error (common during initial setup)

**Database Errors**:
- Raise `MatcherError` with details
- Return HTTP 500 to API caller

**Missing Extensions**:
- System logs warning
- Trigram queries will be slow without GIN index
- Vector search skipped if pgvector not installed

## Future Enhancements

1. **Vector Embeddings**: Complete integration when embedding system ready
2. **Price Penalties**: Implement when `customer_price` table exists
3. **Feedback Analytics**: Use `feedback_event` data for model tuning
4. **Batch Optimization**: Optimize `match_batch()` with bulk queries
5. **Caching**: Cache confirmed mappings in Redis for faster lookup
