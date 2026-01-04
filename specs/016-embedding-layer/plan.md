# Implementation Plan: Embedding Layer (Semantic Product Search)

**Branch**: `016-embedding-layer` | **Date**: 2025-12-27 | **Spec**: [spec.md](./spec.md)

## Summary

Embedding Layer provides semantic product search via vector embeddings. Products are automatically embedded using OpenAI's text-embedding-3-small model when imported/updated. Canonical embedding text includes SKU, name, description, attributes, and UoM conversions (§7.7.3). Embeddings are stored in PostgreSQL with pgvector HNSW index for fast cosine similarity search (<50ms for 10k products). Query embeddings are generated from customer_sku + description + uom for draft line matching. text_hash deduplication prevents redundant API calls. All embedding operations are logged to ai_call_log with token usage and cost tracking. EmbeddingProviderPort abstraction enables provider swapping (OpenAI, local models, etc.).

**Technical Approach**: Python backend with pgvector extension, OpenAI API adapter, Celery async jobs for embedding generation. HNSW index (m=16, ef_construction=200) for vector search. sha256 text_hash for change detection.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: pgvector, openai SDK, SQLAlchemy, Celery
**Storage**: PostgreSQL 16 with pgvector extension (VECTOR type)
**Testing**: pytest with mocked OpenAI API, semantic accuracy tests
**Target Platform**: Linux server
**Project Type**: Backend service (embedding generation + vector search)
**Performance Goals**: Embed product <100ms p95, vector search <50ms, HNSW index build <5min for 10k products
**Constraints**: Multi-tenant isolation, cost tracking, idempotent jobs
**Scale/Scope**: 10k products per org, 30k embedding API calls/day, 1536-dim vectors

## Constitution Check

| Principle | Compliance | Notes |
|-----------|------------|-------|
| **I. SSOT-First** | ✅ Pass | Embedding schema §5.5.2, canonical text §7.7.3, HNSW config §7.7.2 |
| **II. Hexagonal Architecture** | ✅ Pass | EmbeddingProviderPort (§3.5), OpenAI adapter, swappable providers |
| **III. Multi-Tenant Isolation** | ✅ Pass | product_embedding.org_id, vector queries filter by org_id |
| **IV. Idempotent Processing** | ✅ Pass | text_hash check prevents redundant embeddings, upsert on product_id+model |
| **V. AI-Layer Deterministic Control** | ✅ Pass | All calls logged, budget gates enforced, retry with backoff, error handling |
| **VI. Observability First-Class** | ✅ Pass | ai_call_log entries, Prometheus metrics for embedding jobs |
| **VII. Test Pyramid Discipline** | ✅ Pass | Unit (text generation, hash calculation), Integration (E2E embedding flow), Accuracy (semantic similarity tests) |

## Project Structure

### Documentation

```text
specs/016-embedding-layer/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── openapi.yaml
└── spec.md
```

### Source Code

```text
backend/
├── src/
│   ├── models/
│   │   └── product_embedding.py    # ProductEmbedding SQLAlchemy model (§5.5.2)
│   ├── services/
│   │   └── embedding/
│   │       ├── provider_port.py    # EmbeddingProviderPort interface
│   │       ├── openai_adapter.py   # OpenAI implementation
│   │       ├── text_generator.py   # Canonical text generation (§7.7.3)
│   │       ├── vector_search.py    # pgvector search service
│   │       └── __tests__/
│   ├── workers/
│   │   └── tasks/
│   │       └── embed_product.py    # Celery task for async embedding
│   ├── api/
│   │   └── v1/
│   │       └── embeddings.py       # Admin endpoints (rebuild, status)
│   └── lib/
│       └── ai_call_logger.py       # ai_call_log helper
└── tests/
    ├── unit/
    │   ├── test_text_generator.py
    │   └── test_openai_adapter.py
    ├── integration/
    │   └── test_embedding_flow.py
    └── accuracy/
        └── test_semantic_similarity.py  # 100 test queries with known matches
```

**Structure Decision**: Embedding layer follows ports & adapters pattern with clear provider abstraction. Text generation isolated for determinism testing. Vector search separated for reuse in matching engine.

## Complexity Tracking

> **No violations to justify**
