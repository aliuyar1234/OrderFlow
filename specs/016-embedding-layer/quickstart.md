# Quickstart: Embedding Layer

**Feature**: 016-embedding-layer
**Date**: 2025-12-27

## Setup

### 1. Install pgvector Extension

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 2. Run Migration

```bash
alembic upgrade head
```

### 3. Configure OpenAI API Key

```bash
export OPENAI_API_KEY=sk-...
```

### 4. Start Celery Worker

```bash
celery -A src.workers worker --loglevel=info
```

## Testing

### Embed Product

```python
from src.services.embedding.text_generator import generate_product_embedding_text
from src.services.embedding.openai_adapter import OpenAIEmbeddingAdapter
from src.workers.tasks.embed_product import embed_product

# Trigger embedding job
embed_product.delay(product_id)
```

### Vector Search

```python
from src.services.embedding.vector_search import vector_search_products

query_vector = [0.1, 0.2, ...]  # 1536-dim vector
results = vector_search_products(db, org_id, query_vector, limit=30)
# Returns: [(product_id, similarity), ...]
```

## Performance

- Embedding generation: <100ms per product
- Vector search (10k products): <50ms p95
- HNSW index build (10k products): <5min

## Troubleshooting

**Issue**: Slow vector search
**Solution**: Verify HNSW index exists (`\di` in psql), increase `m` parameter

**Issue**: Dimension mismatch error
**Solution**: Ensure all embeddings use same model (rebuild if model changed)

## References

- **SSOT §7.7**: Embedding strategy
- **pgvector Docs**: https://github.com/pgvector/pgvector
