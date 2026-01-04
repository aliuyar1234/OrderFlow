"""Vector Search Service - Semantic product search using pgvector.

Provides cosine similarity search over product embeddings using PostgreSQL pgvector HNSW index.

SSOT Reference: §7.7.2 (Vector Storage), §7.7.4 (Indexing Strategy)
"""

from typing import List, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from pgvector.sqlalchemy import Vector

from src.models import ProductEmbedding, Product


def vector_search_products(
    db: Session,
    org_id: UUID,
    query_vector: List[float],
    limit: int = 30,
    min_similarity: float = 0.0,
    active_only: bool = True,
) -> List[Tuple[UUID, float]]:
    """Search products by vector similarity using cosine distance.

    Uses pgvector HNSW index for fast k-NN search (<50ms for 10k products).

    SSOT Reference: §7.7.2 (HNSW index), FR-017 (Vector Search)

    Args:
        db: SQLAlchemy database session
        org_id: Organization UUID (multi-tenant isolation)
        query_vector: Query embedding vector (list of floats, typically 1536-dim)
        limit: Maximum number of results to return (default: 30)
        min_similarity: Minimum similarity threshold 0.0-1.0 (default: 0.0)
        active_only: Only return active products (default: True)

    Returns:
        List of tuples (product_id, similarity_score)
        Sorted by similarity descending (best matches first)
        Similarity is in range [0.0, 1.0] where 1.0 is identical

    Example:
        >>> from src.infrastructure.ai import OpenAIEmbeddingAdapter
        >>> adapter = OpenAIEmbeddingAdapter()
        >>> result = adapter.embed_text("Cable 3x1.5mm")
        >>> matches = vector_search_products(
        ...     db=db,
        ...     org_id=org_id,
        ...     query_vector=result.embedding,
        ...     limit=5,
        ...     min_similarity=0.7
        ... )
        >>> # [(uuid1, 0.95), (uuid2, 0.89), ...]

    Performance:
        - HNSW index enables <50ms search on 10k products (SSOT §7.7.2)
        - Query filters by org_id for multi-tenant isolation
        - Active products filter joins with product table

    Notes:
        - pgvector uses <=> operator for cosine distance (0 = identical, 2 = opposite)
        - Similarity = 1 - (distance / 2) to convert to [0, 1] range
        - Empty results if no embeddings exist for org
        - Dimension mismatch raises error (query must match stored embeddings)
    """
    # Build query with cosine distance
    # pgvector <=> operator: 0 = identical, 2 = opposite
    # Convert to similarity: 1 - (distance / 2) = [0, 1] where 1 is best
    query = (
        select(
            ProductEmbedding.product_id,
            (1 - (ProductEmbedding.embedding.cosine_distance(query_vector))).label('similarity')
        )
        .where(ProductEmbedding.org_id == org_id)
        .order_by(ProductEmbedding.embedding.cosine_distance(query_vector))
        .limit(limit)
    )

    # Filter by active products if requested
    if active_only:
        query = query.join(Product).where(Product.active == True)

    # Execute query
    results = db.execute(query).all()

    # Filter by minimum similarity and convert to list of tuples
    filtered_results = [
        (row.product_id, row.similarity)
        for row in results
        if row.similarity >= min_similarity
    ]

    return filtered_results


def vector_search_products_with_details(
    db: Session,
    org_id: UUID,
    query_vector: List[float],
    limit: int = 30,
    min_similarity: float = 0.0,
    active_only: bool = True,
) -> List[Tuple[Product, float]]:
    """Search products by vector similarity and return full Product objects.

    Same as vector_search_products but returns Product models instead of just IDs.

    Args:
        db: SQLAlchemy database session
        org_id: Organization UUID
        query_vector: Query embedding vector
        limit: Maximum number of results
        min_similarity: Minimum similarity threshold
        active_only: Only return active products

    Returns:
        List of tuples (Product, similarity_score)
        Sorted by similarity descending

    Example:
        >>> matches = vector_search_products_with_details(
        ...     db=db,
        ...     org_id=org_id,
        ...     query_vector=query_embedding,
        ...     limit=5
        ... )
        >>> for product, similarity in matches:
        ...     print(f"{product.name}: {similarity:.2f}")

    Notes:
        - More expensive than vector_search_products (fetches full Product rows)
        - Use when you need product details for display/matching logic
        - Consider pagination for large result sets
    """
    # Build query with Product join for full details
    query = (
        select(
            Product,
            (1 - (ProductEmbedding.embedding.cosine_distance(query_vector))).label('similarity')
        )
        .join(ProductEmbedding, Product.id == ProductEmbedding.product_id)
        .where(ProductEmbedding.org_id == org_id)
        .order_by(ProductEmbedding.embedding.cosine_distance(query_vector))
        .limit(limit)
    )

    # Filter by active products if requested
    if active_only:
        query = query.where(Product.active == True)

    # Execute query
    results = db.execute(query).all()

    # Filter by minimum similarity
    filtered_results = [
        (row.Product, row.similarity)
        for row in results
        if row.similarity >= min_similarity
    ]

    return filtered_results


def get_embedding_stats(db: Session, org_id: UUID) -> dict:
    """Get embedding statistics for an organization.

    Returns counts and metadata about product embeddings.

    Args:
        db: SQLAlchemy database session
        org_id: Organization UUID

    Returns:
        Dict with keys:
            - total_embeddings: Total number of product embeddings
            - total_products: Total number of products (for coverage %)
            - coverage_percent: Percentage of products with embeddings
            - models: Dict of {model_name: count}

    Example:
        >>> stats = get_embedding_stats(db, org_id)
        >>> print(f"Coverage: {stats['coverage_percent']:.1f}%")
        >>> print(f"Models: {stats['models']}")

    Notes:
        - Used for admin dashboard and monitoring
        - Coverage <100% indicates embedding jobs still running or failed
    """
    from sqlalchemy import func

    # Count embeddings by model
    model_counts = db.execute(
        select(
            ProductEmbedding.embedding_model,
            func.count(ProductEmbedding.id).label('count')
        )
        .where(ProductEmbedding.org_id == org_id)
        .group_by(ProductEmbedding.embedding_model)
    ).all()

    # Count total products
    total_products = db.execute(
        select(func.count(Product.id))
        .where(Product.org_id == org_id)
    ).scalar() or 0

    # Count total embeddings
    total_embeddings = sum(row.count for row in model_counts)

    # Calculate coverage
    coverage_percent = (total_embeddings / total_products * 100) if total_products > 0 else 0.0

    return {
        'total_embeddings': total_embeddings,
        'total_products': total_products,
        'coverage_percent': coverage_percent,
        'models': {row.embedding_model: row.count for row in model_counts},
    }
