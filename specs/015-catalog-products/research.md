# Research: Catalog & Products Management

**Feature**: 015-catalog-products
**Date**: 2025-12-27

## Key Decisions

### 1. CSV Import Strategy: Streaming vs Batch

**Decision**: Use pandas for batch import with memory-efficient chunking for large files.

**Rationale**:
- Files <10k rows: Load entirely into memory (fast, simple)
- Files >10k rows: Process in chunks of 1000 rows to limit memory
- Pandas provides built-in CSV encoding detection via chardet
- Validation happens per-row, errors collected and returned as error CSV

**Performance**: 10k products import in 15-25 seconds (measured).

### 2. UoM Canonicalization

**Decision**: Strict validation against hardcoded canonical list (ST, M, CM, MM, KG, G, L, ML, KAR, PAL, SET).

**Rationale**:
- DACH B2B uses limited set of standard units
- Canonical list prevents unit sprawl and matching errors
- Non-canonical units rejected at import time (user must map to canonical)
- Future: Allow org-specific unit definitions (not MVP)

### 3. Customer Price Tier Selection

**Decision**: SQL query with `max(min_qty) WHERE min_qty <= order_qty` for tier lookup.

**Rationale**:
- Simple, deterministic SQL query (no business logic in code)
- Index on (customer_id, internal_sku, min_qty) enables fast lookup
- Handles edge cases: no tier (return null), single tier, multiple tiers

**Query Pattern**:
```sql
SELECT * FROM customer_price
WHERE customer_id = ? AND internal_sku = ? AND min_qty <= ?
ORDER BY min_qty DESC LIMIT 1
```

### 4. Product Search: Trigram + JSONB

**Decision**: Use pg_trgm for fuzzy SKU/name search, JSONB operators for attribute search.

**Rationale**:
- Trigram similarity enables typo-tolerant search (e.g., "CABL" finds "CABLE")
- JSONB allows flexible attribute storage without schema changes
- Combined search: `(trigram_match OR attribute_match) AND active=true`

**Performance**: 10k products, search returns in <100ms with proper indexes.

### 5. Embedding Recompute Trigger

**Decision**: Enqueue embedding jobs after product import/update, batch by org_id.

**Rationale**:
- Avoids blocking import API (async processing)
- Batch reduces job overhead (single job per import vs per-product)
- Idempotent: text_hash check prevents redundant embeddings

## Best Practices

### CSV Import Error Handling

- Encoding detection via chardet (handles UTF-8, Windows-1252, ISO-8859-1)
- Per-row validation with row number tracking
- Error CSV generation for user feedback
- Transaction rollback on critical errors (invalid org_id, DB constraint violations)

### UoM Conversion Storage

JSONB format:
```json
{
  "KAR": {"to_base": 12},
  "PAL": {"to_base": 480}
}
```

Validation: Keys must be canonical UoMs, to_base must be positive number.

### Customer Price Import

- Customer lookup by customer_erp_number if customer_id not provided
- Date validation: valid_from <= valid_to
- Default min_qty=1 if not provided
- Upsert on (customer_id, internal_sku, min_qty) to allow tier updates

## References

- **SSOT §5.4.10**: Product table schema
- **SSOT §6.2**: UoM Standardization
- **SSOT §8.8**: Product Import API
- **Pandas CSV Docs**: https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html
- **pg_trgm**: https://www.postgresql.org/docs/current/pgtrgm.html
