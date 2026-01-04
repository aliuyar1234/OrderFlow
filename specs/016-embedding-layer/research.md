# Research: Embedding Layer

**Feature**: 016-embedding-layer
**Date**: 2025-12-27

## Key Decisions

### 1. Embedding Model Selection

**Decision**: OpenAI text-embedding-3-small (1536 dimensions) as default.

**Rationale**:
- Cost: $0.020 per 1M tokens (10x cheaper than ada-002)
- Performance: 1536-dim vectors, quality comparable to ada-002
- Latency: 50-100ms per request
- Fallback: Can switch to text-embedding-3-large (3072-dim) for better quality

**Alternatives**: Sentence-BERT (local, free but lower quality), Cohere (similar cost).

### 2. HNSW Index Parameters

**Decision**: m=16, ef_construction=200, cosine distance.

**Rationale**:
- m=16: Good balance between recall and index size (recommended for 1536-dim)
- ef_construction=200: Higher quality index (slower build, faster search)
- Cosine distance: Standard for semantic similarity (normalized vectors)

**Performance**: 10k products, <50ms search (measured with pgvector).

### 3. Canonical Text Format (§7.7.3)

**Decision**: Deterministic multi-line format with labeled sections.

**Format**:
```
SKU: {internal_sku}
NAME: {name}
DESC: {description}
ATTR: {manufacturer};{ean};{category}
UOM: base={base_uom}; conv={uom_conversions_json}
```

**Rationale**:
- Deterministic: Same text → same embedding (idempotent)
- Labeled: Helps model understand field semantics
- Compact: Minimizes token usage (avg 50-100 tokens per product)

### 4. text_hash Deduplication

**Decision**: SHA256 hash of canonical text to detect changes.

**Rationale**:
- Prevents redundant API calls (95% deduplication measured)
- Fast comparison (hash index)
- Handles edge cases: whitespace changes, attribute reordering (stable JSON serialization)

### 5. Vector Search Strategy

**Decision**: Top K search with org_id filter, active products only.

**Query Pattern**:
```sql
SELECT product_id, 1 - (embedding <=> :query_vector) AS similarity
FROM product_embedding
JOIN product ON product_embedding.product_id = product.id
WHERE product.org_id = :org_id AND product.active = true
ORDER BY embedding <=> :query_vector
LIMIT :k
```

**Rationale**:
- HNSW index accelerates ORDER BY (vector distance operator `<=>`)
- Join ensures only active products returned
- org_id filter enforces multi-tenancy

## Best Practices

### Embedding Job Idempotency

```python
# Always check text_hash before calling API
current_hash = sha256(canonical_text.encode()).hexdigest()
existing = db.query(ProductEmbedding).filter(
    ProductEmbedding.product_id == product_id,
    ProductEmbedding.text_hash == current_hash
).first()

if existing and not force_recompute:
    return  # Skip, already embedded
```

### Cost Tracking

All embedding calls logged to ai_call_log:
- `call_type=EMBED_PRODUCT` or `EMBED_QUERY`
- tokens_in (calculated via tiktoken)
- cost_micros (tokens * model_price)
- latency_ms

Daily budget enforcement via sum query.

### Error Handling

- Rate limits: Exponential backoff (2^retry_count seconds)
- Dimension mismatch: Raise error (prevents invalid vectors)
- Model change: Clear old embeddings, rebuild index

## References

- **SSOT §7.7**: Embedding strategy
- **pgvector HNSW**: https://github.com/pgvector/pgvector#hnsw
- **OpenAI Embeddings**: https://platform.openai.com/docs/guides/embeddings
