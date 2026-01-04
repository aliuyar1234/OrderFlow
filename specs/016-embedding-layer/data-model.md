# Data Model: Embedding Layer

**Feature**: 016-embedding-layer
**Date**: 2025-12-27

## SQLAlchemy Model

```python
from sqlalchemy import Column, String, Integer, Text, TIMESTAMP, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
import uuid

class ProductEmbedding(Base):
    __tablename__ = 'product_embedding'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey('product.id', ondelete='CASCADE'), nullable=False)
    embedding_model = Column(String(100), nullable=False)  # 'text-embedding-3-small'
    embedding_dim = Column(Integer, nullable=False, default=1536)
    embedding = Column(Vector(1536), nullable=False)
    text_hash = Column(String(64), nullable=False)  # SHA256 hash
    updated_at_source = Column(TIMESTAMP(timezone=True), nullable=True)  # From product.updated_source_at
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('org_id', 'product_id', 'embedding_model', name='uq_product_embedding'),
        Index('idx_product_embedding_hnsw', 'embedding', postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 200}, postgresql_ops={'embedding': 'vector_cosine_ops'}),
    )
```

## Migration (Alembic)

```python
# alembic/versions/xxx_add_product_embedding.py

def upgrade():
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Create table
    op.create_table(
        'product_embedding',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', UUID(as_uuid=True), nullable=False),
        sa.Column('product_id', UUID(as_uuid=True), nullable=False),
        sa.Column('embedding_model', sa.String(100), nullable=False),
        sa.Column('embedding_dim', sa.Integer, nullable=False, default=1536),
        sa.Column('embedding', Vector(1536), nullable=False),
        sa.Column('text_hash', sa.String(64), nullable=False),
        sa.Column('updated_at_source', sa.TIMESTAMP(timezone=True)),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['product_id'], ['product.id'], ondelete='CASCADE'),
    )

    # Create indexes
    op.create_index('idx_product_embedding_org', 'product_embedding', ['org_id'])
    op.create_index(
        'idx_product_embedding_hnsw',
        'product_embedding',
        ['embedding'],
        postgresql_using='hnsw',
        postgresql_with={'m': 16, 'ef_construction': 200},
        postgresql_ops={'embedding': 'vector_cosine_ops'}
    )
    op.create_unique_constraint('uq_product_embedding', 'product_embedding', ['org_id', 'product_id', 'embedding_model'])

def downgrade():
    op.drop_table('product_embedding')
    op.execute('DROP EXTENSION IF EXISTS vector')
```

## Provider Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

@dataclass
class EmbeddingResult:
    embedding: List[float]
    model: str
    dimension: int
    tokens: int
    cost_micros: int  # Cost in micro-dollars (e.g., 20 = $0.00002)

class EmbeddingProviderPort(ABC):
    @abstractmethod
    def embed_text(self, text: str, model: str) -> EmbeddingResult:
        """Generate embedding for text. Raises on API error."""
        pass
```

## OpenAI Adapter

```python
import openai
import tiktoken

class OpenAIEmbeddingAdapter(EmbeddingProviderPort):
    def __init__(self, api_key: str):
        openai.api_key = api_key

    def embed_text(self, text: str, model: str = "text-embedding-3-small") -> EmbeddingResult:
        # Count tokens
        encoding = tiktoken.encoding_for_model(model)
        tokens = len(encoding.encode(text))

        # Call API
        response = openai.embeddings.create(model=model, input=text)
        embedding = response.data[0].embedding

        # Calculate cost ($0.020 per 1M tokens for text-embedding-3-small)
        cost_per_token_micros = 20  # $0.020 / 1M tokens = 0.02 micros per token
        cost_micros = tokens * cost_per_token_micros

        return EmbeddingResult(
            embedding=embedding,
            model=model,
            dimension=len(embedding),
            tokens=tokens,
            cost_micros=cost_micros
        )
```

## Canonical Text Generator

```python
import hashlib
import json

def generate_product_embedding_text(product: Product) -> str:
    attrs = product.attributes_json or {}
    manufacturer = attrs.get("manufacturer", "")
    ean = attrs.get("EAN", "")
    category = attrs.get("category", "")

    # Stable JSON serialization (sorted keys, compact)
    uom_conv_compact = json.dumps(product.uom_conversions_json or {}, separators=(',', ':'), sort_keys=True)

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

def calculate_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
```

## Vector Search Service

```python
from sqlalchemy import func
from pgvector.sqlalchemy import Vector

def vector_search_products(
    db: Session,
    org_id: UUID,
    query_vector: List[float],
    limit: int = 30
) -> List[tuple[UUID, float]]:
    """
    Search products by vector similarity.
    Returns: [(product_id, similarity_score), ...]
    """
    results = db.query(
        ProductEmbedding.product_id,
        (1 - ProductEmbedding.embedding.cosine_distance(query_vector)).label("similarity")
    ).join(
        Product, ProductEmbedding.product_id == Product.id
    ).filter(
        Product.org_id == org_id,
        Product.active == True
    ).order_by(
        ProductEmbedding.embedding.cosine_distance(query_vector)
    ).limit(limit).all()

    return [(r.product_id, r.similarity) for r in results]
```

## Relationships

- ProductEmbedding (1) ← (1) Product (via product_id FK, CASCADE delete)
- ProductEmbedding queries filter by org_id (multi-tenant isolation)
