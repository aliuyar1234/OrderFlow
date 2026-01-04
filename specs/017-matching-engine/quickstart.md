# Quickstart: Matching Engine

**Feature**: 017-matching-engine
**Date**: 2025-12-27

## Setup

### 1. Enable PostgreSQL Extensions

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;  -- From 016-embedding-layer
```

### 2. Run Migration

```bash
alembic upgrade head
```

### 3. Create Trigram Indexes

```sql
CREATE INDEX idx_product_trgm_sku ON product USING gin (internal_sku gin_trgm_ops);
CREATE INDEX idx_product_trgm_desc ON product USING gin ((name || ' ' || COALESCE(description, '')) gin_trgm_ops);
```

## Testing

### Run Matching for Draft

```python
from src.services.matching.hybrid_matcher import HybridMatcher

matcher = HybridMatcher()
result = matcher.match_line(draft_line, customer_id)

print(f"Match: {result.internal_sku} (confidence: {result.confidence})")
print(f"Top 5 candidates: {result.candidates}")
```

### Confirm Mapping

```python
from src.services.matching.mapping_feedback import confirm_mapping

confirm_mapping(
    org_id=draft.org_id,
    customer_id=draft.customer_id,
    customer_sku_norm=line.customer_sku_norm,
    internal_sku="PROD-123"
)
```

### Reject Mapping

```python
from src.services.matching.mapping_feedback import reject_mapping

reject_mapping(
    org_id=draft.org_id,
    customer_id=draft.customer_id,
    customer_sku_norm=line.customer_sku_norm,
    suggested_sku="PROD-WRONG"
)
```

## Performance

- Hybrid matching: <500ms per line (p95)
- Trigram search: <50ms (10k products)
- Vector search: <50ms (10k products)
- Auto-apply rate: ~70% after 50 confirmed mappings

## Troubleshooting

**Issue**: Low match accuracy
**Solution**: Check trigram indexes, verify embedding quality, review penalty thresholds

**Issue**: Mappings not applied
**Solution**: Check sku_mapping.status=CONFIRMED, verify customer_sku_norm normalization

**Issue**: Slow matching
**Solution**: Verify trigram/HNSW indexes exist, check query plans with EXPLAIN ANALYZE

## References

- **SSOT §7.7.5-7.7.7**: Hybrid search strategy
- **SSOT §5.4.12**: sku_mapping schema
