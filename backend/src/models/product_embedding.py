"""ProductEmbedding Model - Vector embeddings for product semantic search.

SSOT Reference: §5.5.2 (product_embedding table), §7.7 (Embedding-based Matching)
"""

from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, String, Integer, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, TIMESTAMPTZ
from sqlalchemy.orm import relationship

from .base import Base


class ProductEmbedding(Base):
    """Product embedding vector for semantic search.

    Stores embedding vectors generated from product canonical text (SKU, name, description, etc).
    Uses pgvector for efficient cosine similarity search via HNSW index.

    SSOT Reference: §5.5.2 (product_embedding schema), §7.7.3 (Canonical Text)

    Key Design Principles:
    - Multi-tenant isolation via org_id (every query filters by org_id)
    - Deduplication via text_hash (prevents redundant embedding API calls)
    - HNSW index for fast k-NN search (<50ms for 10k products)
    - Support for model migration (embedding_model field allows multiple models)

    Attributes:
        id: Primary key (UUID)
        org_id: Organization UUID (multi-tenant isolation)
        product_id: Reference to product table
        embedding_model: Model used for embedding (e.g., 'text-embedding-3-small')
        embedding_dim: Embedding dimension (e.g., 1536 for text-embedding-3-small)
        embedding: Vector embedding (pgvector VECTOR type)
        text_hash: SHA256 hash of canonical text (for deduplication)
        updated_at_source: Timestamp from product.updated_source_at (for staleness detection)
        created_at: Creation timestamp
        updated_at: Last update timestamp

    Indexes:
        - UNIQUE(org_id, product_id, embedding_model): One embedding per product per model
        - HNSW(embedding): Fast cosine similarity search (m=16, ef_construction=200)

    Example Query (Top 5 similar products):
        SELECT product_id, 1 - (embedding <=> :query_vector) AS similarity
        FROM product_embedding
        WHERE org_id = :org_id
        ORDER BY embedding <=> :query_vector
        LIMIT 5
    """

    __tablename__ = "product_embedding"

    # Primary key
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )

    # Multi-tenant isolation
    org_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # Foreign key to product
    product_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("product.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Embedding metadata
    embedding_model = Column(String(100), nullable=False, index=True)
    embedding_dim = Column(Integer, nullable=False, default=1536)

    # Vector embedding (pgvector type)
    # Dimension must match embedding_dim (enforced at application level)
    embedding = Column(Vector(1536), nullable=False)

    # Deduplication and staleness tracking
    text_hash = Column(String(64), nullable=False, index=True)  # SHA256 hex = 64 chars
    updated_at_source = Column(TIMESTAMPTZ, nullable=True)  # From product.updated_source_at

    # Timestamps
    created_at = Column(TIMESTAMPTZ, nullable=False, default=datetime.utcnow, server_default=text("NOW()"))
    updated_at = Column(
        TIMESTAMPTZ,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=text("NOW()"),
    )

    # Relationship to product (optional, for eager loading)
    # Commented out to avoid circular imports - access via explicit joins in queries
    # product = relationship("Product", back_populates="embeddings")

    # Indexes defined via Index() for explicit control
    __table_args__ = (
        # Unique constraint: one embedding per product per model (allows model migration)
        Index(
            "idx_product_embedding_unique",
            "org_id",
            "product_id",
            "embedding_model",
            unique=True,
        ),
        # HNSW index for fast cosine similarity search
        # Created in migration with: CREATE INDEX ... USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=200)
        # Note: Cannot define HNSW index via SQLAlchemy declarative - created in migration
    )

    def __repr__(self) -> str:
        return (
            f"<ProductEmbedding(id={self.id}, product_id={self.product_id}, "
            f"model={self.embedding_model}, dim={self.embedding_dim})>"
        )
