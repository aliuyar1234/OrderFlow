# Feature Specification: Embedding Layer (Semantic Product Search)

**Feature Branch**: `016-embedding-layer`
**Created**: 2025-12-27
**Status**: Draft
**Module**: ai, matching
**SSOT Refs**: §3.5 (EmbeddingProviderPort), §5.5.2 (product_embedding), §7.7.1-7.7.4 (Embedding), T-406, T-407

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Product Embedding Generation on Import (Priority: P1)

When products are imported or updated, the system automatically generates semantic embeddings for each product, enabling fuzzy matching of customer SKUs and descriptions.

**Why this priority**: Foundation for semantic matching. Without embeddings, only exact/trigram matching works.

**Independent Test**: Import 100 products → embedding jobs enqueued → embeddings generated and stored in pgvector → vector search returns semantically similar products.

**Acceptance Scenarios**:

1. **Given** products imported via CSV, **When** import completes, **Then** embed_product jobs enqueued for all new/updated products
2. **Given** embed_product job runs, **When** processing product X, **Then** generates canonical text per §7.7.3, calls EmbeddingProvider, stores embedding vector in product_embedding table
3. **Given** product updated (name changed), **When** text_hash changes, **Then** existing embedding is updated (or new created if model changed)
4. **Given** product unchanged, **When** embed job runs, **Then** text_hash matches, no API call made (deduplication)

---

### User Story 2 - EmbeddingProvider Abstraction and Cost Tracking (Priority: P1)

The system uses an abstract EmbeddingProviderPort with OpenAI adapter as default. All embedding calls are logged with token usage and cost for budget tracking.

**Why this priority**: Decouples from specific embedding vendor. Enables cost monitoring similar to LLM layer.

**Independent Test**: Embed 10 products → ai_call_log shows 10 entries with call_type=EMBED_PRODUCT, tokens, cost_micros.

**Acceptance Scenarios**:

1. **Given** EmbeddingProviderPort configured with OpenAI adapter (text-embedding-3-small), **When** calling embed_text(), **Then** adapter calls OpenAI API, returns vector of dim=1536
2. **Given** embedding API call succeeds, **When** logging, **Then** ai_call_log entry created with call_type=EMBED_PRODUCT, provider="openai", model="text-embedding-3-small", tokens_in, cost_micros
3. **Given** embedding API call fails (rate limit), **When** handling error, **Then** job retries with exponential backoff, error logged
4. **Given** org configures different embedding model, **When** processing, **Then** system uses configured model, updates product_embedding.embedding_model field

---

### User Story 3 - pgvector HNSW Index for Fast Similarity Search (Priority: P1)

Product embeddings are stored in pgvector with HNSW index on cosine distance, enabling fast k-NN search for matching line queries.

**Why this priority**: Query performance is critical. HNSW enables <50ms search on 10k+ products.

**Independent Test**: Generate embedding for query "3x1.5mm cable" → search product_embedding using cosine similarity → returns Top 5 similar products in <50ms.

**Acceptance Scenarios**:

1. **Given** 10,000 products with embeddings, **When** creating HNSW index with m=16, ef_construction=200, **Then** index builds successfully
2. **Given** query embedding vector, **When** executing: `SELECT * FROM product_embedding ORDER BY embedding <=> :query_vector LIMIT 5`, **Then** returns Top 5 results in <50ms (p95)
3. **Given** HNSW index exists, **When** inserting new product embedding, **Then** index auto-updates, query performance maintained
4. **Given** embedding dimension mismatch (e.g., 1536 vs 768), **When** querying, **Then** error raised, system prevents mixed dimensions

---

### User Story 4 - Canonical Embedding Text Generation (Priority: P1)

The system generates deterministic embedding text from product data per §7.7.3 format, ensuring consistency and recompute detection via text_hash.

**Why this priority**: Deterministic text ensures embeddings are reproducible. text_hash enables efficient deduplication.

**Independent Test**: Product with SKU="ABC-123", name="Cable", base_uom="M" → embedding text is "SKU: ABC-123\nNAME: Cable\nDESC: \nATTR: ;;\nUOM: base=M; conv={}" → sha256 hash calculated.

**Acceptance Scenarios**:

1. **Given** product with all fields populated, **When** generating embedding text, **Then** format matches §7.7.3 exactly: "SKU: {sku}\nNAME: {name}\nDESC: {desc}\nATTR: {manufacturer};{ean};{category}\nUOM: base={base}; conv={json}"
2. **Given** product with missing optional fields (description=null, attributes={}), **When** generating text, **Then** fields are empty strings, format preserved
3. **Given** embedding text generated, **When** calculating text_hash, **Then** sha256(text) computed, stored in product_embedding.text_hash
4. **Given** product updated but embedding text unchanged, **When** checking for recompute, **Then** text_hash matches, embedding not regenerated

---

### User Story 5 - Query Embedding for Line Matching (Priority: P1)

When matching a draft line, the system generates a query embedding from customer_sku_raw + product_description + uom, enabling semantic similarity search.

**Why this priority**: Core of fuzzy matching. Enables finding products even when customer uses different terminology.

**Independent Test**: Draft line with customer_sku="XYZ-999", description="Stromkabel 3x1,5" → query text generated → embedding created → search finds product "Kabel NYM-J 3x1,5" with high similarity.

**Acceptance Scenarios**:

1. **Given** draft line with customer_sku_raw, product_description, uom, **When** generating query text, **Then** format per §7.7.3: "CUSTOMER_SKU: {sku}\nDESC: {desc}\nUOM: {uom}"
2. **Given** query text generated, **When** calling EmbeddingProvider, **Then** returns vector, logged as call_type=EMBED_QUERY
3. **Given** query embedding vector, **When** searching product_embedding, **Then** cosine similarity calculated, Top K products returned
4. **Given** query with only description (no SKU), **When** generating text, **Then** CUSTOMER_SKU field is empty, description still enables semantic match

---

### User Story 6 - Embedding Rebuild and Index Management (Priority: P3)

Admin can trigger full embedding rebuild (e.g., after model upgrade). System recomputes all embeddings, updates text_hash, rebuilds HNSW index.

**Why this priority**: Enables migration to better embedding models. Maintenance operation for data quality.

**Independent Test**: Admin clicks "Rebuild Embeddings" → job enqueued → all products re-embedded → index rebuilt → new embeddings used for matching.

**Acceptance Scenarios**:

1. **Given** Admin triggers rebuild, **When** job starts, **Then** queries all products, enqueues embed_product jobs with force_recompute=true
2. **Given** force_recompute=true, **When** embed job runs, **Then** bypasses text_hash check, always calls embedding API
3. **Given** all embeddings updated, **When** querying, **Then** HNSW index reflects new embeddings, search results change
4. **Given** model changed (e.g., text-embedding-3-small → text-embedding-3-large), **When** rebuilding, **Then** embedding_model and embedding_dim updated, old embeddings deleted

---

### Edge Cases

- What happens when embedding API returns vector with wrong dimension?
- How does system handle products with very long descriptions (>8k chars, exceeds token limit)?
- What happens when pgvector extension is not installed (deployment failure)?
- How does system handle concurrent embedding jobs for same product (race condition)?
- What happens when HNSW index build fails (OOM, disk space)?
- How does system handle mixed embedding models in same org (migration scenario)?

## Requirements *(mandatory)*

### Functional Requirements

**EmbeddingProvider Layer:**
- **FR-001**: System MUST define EmbeddingProviderPort interface with method:
  - `embed_text(text: str, model: str) -> EmbeddingResult`
- **FR-002**: System MUST implement OpenAI adapter for EmbeddingProviderPort supporting:
  - Model: text-embedding-3-small (default)
  - Dimension: 1536
  - Token counting and cost calculation
- **FR-003**: System MUST log every embedding call to ai_call_log with:
  - call_type (EMBED_PRODUCT or EMBED_QUERY)
  - provider, model, tokens_in, cost_micros, latency_ms, status
- **FR-004**: EmbeddingResult MUST contain:
  - embedding (vector array), model, dimension, tokens, cost_micros

**Product Embedding:**
- **FR-005**: System MUST generate canonical product text per §7.7.3:
  - Format: "SKU: {internal_sku}\nNAME: {name}\nDESC: {description}\nATTR: {manufacturer};{ean};{category}\nUOM: base={base_uom}; conv={uom_conversions_json}"
  - Missing fields replaced with empty string
- **FR-006**: System MUST calculate text_hash = sha256(canonical_text)
- **FR-007**: System MUST check if embedding exists with matching text_hash before API call
- **FR-008**: System MUST store embedding in product_embedding table with:
  - product_id, embedding_model, embedding_dim, embedding (VECTOR), text_hash, updated_at_source (from product.updated_source_at)
- **FR-009**: System MUST enforce UNIQUE constraint on (org_id, product_id, embedding_model)
- **FR-010**: System MUST create HNSW index on embedding column:
  - `CREATE INDEX idx_product_embedding_hnsw ON product_embedding USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=200)`

**Query Embedding:**
- **FR-011**: System MUST generate canonical query text per §7.7.3:
  - Format: "CUSTOMER_SKU: {customer_sku_raw}\nDESC: {product_description}\nUOM: {uom}"
- **FR-012**: System MUST embed query text and log as call_type=EMBED_QUERY
- **FR-013**: System MUST NOT cache query embeddings (lines are unique)

**Embedding Jobs:**
- **FR-014**: System MUST enqueue embed_product job when:
  - Product imported/created
  - Product updated (name, description, attributes, uom changed)
  - Admin triggers rebuild
- **FR-015**: System MUST process embed_product job idempotently:
  - Calculate current text_hash
  - If exists with matching text_hash → skip
  - Else → call EmbeddingProvider, upsert product_embedding
- **FR-016**: System MUST handle embedding failures:
  - Retry with exponential backoff (3 retries max)
  - Log error in ai_call_log
  - Mark product_embedding as stale if retries exhausted

**Vector Search:**
- **FR-017**: System MUST support cosine similarity search:
  - Query: `SELECT product_id, 1 - (embedding <=> :query_vector) AS similarity FROM product_embedding WHERE org_id=:org_id ORDER BY embedding <=> :query_vector LIMIT :k`
  - Returns Top K products with similarity scores [0..1]
- **FR-018**: System MUST filter by active products only (join with product table)
- **FR-019**: System MUST support filtering by org_id in all vector queries (multi-tenant isolation)

**Index Management:**
- **FR-020**: System MUST rebuild HNSW index when:
  - Large batch import (>1000 products)
  - Model changed
  - Admin triggers rebuild
- **FR-021**: System MUST validate embedding dimension matches configured model dimension
- **FR-022**: System MUST prevent queries with dimension mismatch (raise error)
- **FR-023**: Admin rebuild MUST check daily AI budget gate before starting. If budget insufficient for estimated rebuild cost, block with error 'Insufficient AI budget for rebuild. Estimated cost: $X.XX, Available: $Y.YY'. Log total rebuild cost to ai_call_log. Consider separate rebuild_budget_micros setting for large catalogs.

### Key Entities

- **product_embedding** (§5.5.2): Vector storage with pgvector VECTOR type
- **EmbeddingProviderPort**: Abstract interface for embedding providers
- **OpenAIEmbeddingAdapter**: Concrete implementation
- **EmbeddingResult**: Data class for embedding API results
- **HNSW Index**: pgvector index for fast k-NN search

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Product embedding generation completes in <100ms per product (p95)
- **SC-002**: Vector similarity search returns Top 30 results in <50ms for 10k product catalog
- **SC-003**: text_hash deduplication reduces redundant embedding calls by ≥95%
- **SC-004**: HNSW index build completes in <5 minutes for 10k products
- **SC-005**: Embedding API failures are retried successfully in ≥90% of cases
- **SC-006**: 100% of embedding calls are logged with cost tracking
- **SC-007**: Semantic search finds relevant products with ≥80% accuracy (manual evaluation on test set)
- **SC-008**: Embedding rebuild completes for 10k products in <30 minutes

## Dependencies

- **Depends on**:
  - 015-catalog-products (product entity, imports)
  - PostgreSQL with pgvector extension installed
  - OpenAI API credentials (OPENAI_API_KEY env var)
  - Worker queue (Celery) for async embedding jobs
  - ai_call_log table (from 011-llm-provider-layer)

- **Blocks**:
  - 017-matching-engine (hybrid search requires embeddings)

## Technical Notes

### Implementation Guidance

**Embedding Migration:** (1) When model changes dimensions (e.g., 768→1536), run full rebuild with force_recompute=true, (2) During migration window, queries handle both dimensions by checking product_embedding.dimension, (3) After cutoff (all products recomputed), enforce single dimension, (4) Log all dimension changes to audit_log.

**EmbeddingProviderPort Interface:**
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class EmbeddingResult:
    embedding: list[float]
    model: str
    dimension: int
    tokens: int
    cost_micros: int

class EmbeddingProviderPort(ABC):
    @abstractmethod
    def embed_text(self, text: str, model: str) -> EmbeddingResult:
        pass
```

**OpenAI Adapter:**
```python
import openai

class OpenAIEmbeddingAdapter(EmbeddingProviderPort):
    def embed_text(self, text: str, model: str = "text-embedding-3-small") -> EmbeddingResult:
        response = openai.embeddings.create(
            model=model,
            input=text
        )

        embedding = response.data[0].embedding
        tokens = response.usage.total_tokens
        # OpenAI pricing: $0.020 per 1M tokens for text-embedding-3-small
        cost_micros = int((tokens / 1_000_000) * 0.020 * 1_000_000)

        return EmbeddingResult(
            embedding=embedding,
            model=model,
            dimension=len(embedding),
            tokens=tokens,
            cost_micros=cost_micros
        )
```

**Canonical Text Generation (§7.7.3):**
```python
def generate_product_embedding_text(product: Product) -> str:
    attrs = product.attributes_json or {}
    manufacturer = attrs.get("manufacturer", "")
    ean = attrs.get("EAN", "")
    category = attrs.get("category", "")

    uom_conv_compact = json.dumps(product.uom_conversions_json or {}, separators=(',', ':'))

    text = (
        f"SKU: {product.internal_sku}\n"
        f"NAME: {product.name}\n"
        f"DESC: {product.description or ''}\n"
        f"ATTR: {manufacturer};{ean};{category}\n"
        f"UOM: base={product.base_uom}; conv={uom_conv_compact}\n"
    )
    return text

def generate_query_embedding_text(line: DraftOrderLine) -> str:
    text = (
        f"CUSTOMER_SKU: {line.customer_sku_raw or ''}\n"
        f"DESC: {line.product_description or ''}\n"
        f"UOM: {line.uom or ''}\n"
    )
    return text
```

**Embedding Job (Celery Task):**
```python
@celery_app.task(bind=True, max_retries=3)
def embed_product(self, product_id: UUID, force_recompute: bool = False):
    product = db.query(Product).get(product_id)
    if not product:
        return

    # Generate canonical text
    text = generate_product_embedding_text(product)
    text_hash = hashlib.sha256(text.encode()).hexdigest()

    # Check if already embedded with same text
    if not force_recompute:
        existing = db.query(ProductEmbedding).filter(
            ProductEmbedding.product_id == product_id,
            ProductEmbedding.text_hash == text_hash
        ).first()
        if existing:
            logger.info(f"Product {product_id} already embedded (text_hash match)")
            return

    # Call embedding provider
    try:
        provider = get_embedding_provider()
        model = get_org_setting(product.org_id, "ai.embeddings.model", "text-embedding-3-small")
        result = provider.embed_text(text, model)

        # Log AI call
        create_ai_call_log(
            org_id=product.org_id,
            call_type="EMBED_PRODUCT",
            provider="openai",
            model=result.model,
            document_id=None,
            tokens_in=result.tokens,
            tokens_out=0,
            cost_micros=result.cost_micros,
            status="SUCCEEDED"
        )

        # Upsert embedding
        embedding = db.query(ProductEmbedding).filter(
            ProductEmbedding.product_id == product_id,
            ProductEmbedding.embedding_model == result.model
        ).first()

        if embedding:
            embedding.embedding = result.embedding
            embedding.text_hash = text_hash
            embedding.embedding_dim = result.dimension
            embedding.updated_at = now()
        else:
            embedding = ProductEmbedding(
                org_id=product.org_id,
                product_id=product_id,
                embedding_model=result.model,
                embedding_dim=result.dimension,
                embedding=result.embedding,
                text_hash=text_hash,
                updated_at_source=product.updated_source_at
            )
            db.add(embedding)

        db.commit()

    except Exception as exc:
        # Log failure
        create_ai_call_log(
            org_id=product.org_id,
            call_type="EMBED_PRODUCT",
            provider="openai",
            status="FAILED",
            error_json={"error": str(exc)}
        )
        # Retry
        self.retry(exc=exc, countdown=2 ** self.request.retries)
```

**Vector Search Query:**
```python
from pgvector.sqlalchemy import Vector
from sqlalchemy import func

def vector_search_products(org_id: UUID, query_vector: list[float], limit: int = 30) -> list[tuple[UUID, float]]:
    results = db.query(
        ProductEmbedding.product_id,
        (1 - ProductEmbedding.embedding.cosine_distance(query_vector)).label("similarity")
    ).join(Product).filter(
        Product.org_id == org_id,
        Product.active == True
    ).order_by(
        ProductEmbedding.embedding.cosine_distance(query_vector)
    ).limit(limit).all()

    return [(r.product_id, r.similarity) for r in results]
```

**pgvector Setup (Migration):**
```sql
-- Enable extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create table
CREATE TABLE product_embedding (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL,
    product_id UUID NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    embedding_model TEXT NOT NULL,
    embedding_dim INT NOT NULL DEFAULT 1536,
    embedding VECTOR(1536) NOT NULL,
    text_hash TEXT NOT NULL,
    updated_at_source TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE UNIQUE INDEX idx_product_embedding_unique ON product_embedding(org_id, product_id, embedding_model);
CREATE INDEX idx_product_embedding_hnsw ON product_embedding USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=200);
```

### Testing Strategy

**Unit Tests:**
- Canonical text generation: various product field combinations
- text_hash calculation: deterministic output
- Embedding deduplication: text_hash match skips API call
- Query text generation: various line field combinations

**Integration Tests:**
- End-to-end: product import → embedding job → vector stored → searchable
- Vector search: query → Top K results with similarity scores
- HNSW index: verify fast search (<50ms)
- Failure retry: mock API failure → job retries → eventual success

**Semantic Quality Tests:**
- Prepare 100 test queries with known correct matches
- Measure Top 5 accuracy (relevant product in Top 5)
- Benchmark: ≥80% accuracy

**Performance Tests:**
- Embed 10k products: measure total time, p95 per-product latency
- Vector search on 10k products: p95 <50ms
- HNSW index build: 10k products in <5 minutes
- Concurrent embedding jobs: 10 workers embedding 100 products simultaneously

## SSOT References

- **§3.5**: Hexagonal Architecture - EmbeddingProviderPort
- **§5.5.2**: product_embedding table schema
- **§7.7**: Embedding-based Matching (full section)
- **§7.7.1**: Embedding Model (text-embedding-3-small, dim=1536)
- **§7.7.2**: Vector Storage (pgvector + HNSW)
- **§7.7.3**: Canonical embedding text formats (product & query)
- **§7.7.4**: Indexing Strategy (recompute on update, nightly fill gaps)
- **§10.1**: AI Settings (embeddings config)
- **T-406**: Embedding Provider Port task
- **T-407**: Product Embedding Jobs task
