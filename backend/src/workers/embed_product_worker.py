"""Product Embedding Worker - Generate embeddings for products.

Celery task for asynchronous embedding generation with deduplication and retry logic.

SSOT Reference: §7.7.4 (Indexing Strategy), T-407 (Product Embedding Jobs)
"""

import hashlib
from datetime import datetime
from typing import Dict, Any
from uuid import UUID

from celery import Task
from sqlalchemy.orm import Session

from src.workers.base import celery_app, validate_org_id, get_scoped_session
from src.models import Product, ProductEmbedding
from src.infrastructure.ai import OpenAIEmbeddingAdapter
from src.services.embedding import generate_product_embedding_text, calculate_text_hash
from src.domain.ai import (
    EmbeddingError,
    EmbeddingTimeoutError,
    EmbeddingRateLimitError,
    AICallLogger,
    AICallType,
)


class EmbedProductTask(Task):
    """Base task class for embedding generation with retry configuration.

    Retry policy:
    - Max retries: 3
    - Backoff: Exponential (2^n seconds)
    - Retry on: Timeout, RateLimitError, generic EmbeddingError
    - No retry on: AuthError, InvalidResponse (permanent failures)
    """
    autoretry_for = (EmbeddingTimeoutError, EmbeddingRateLimitError, EmbeddingError)
    retry_kwargs = {'max_retries': 3, 'countdown': 5}
    retry_backoff = True
    retry_backoff_max = 600  # 10 minutes max
    retry_jitter = True


@celery_app.task(base=EmbedProductTask, bind=True)
def embed_product(
    self: Task,
    product_id: str,
    org_id: str,
    force_recompute: bool = False,
    embedding_model: str = "text-embedding-3-small"
) -> Dict[str, Any]:
    """Generate embedding for a product.

    Idempotent: Checks text_hash before generating embedding. If text unchanged, skips API call.

    SSOT Reference: §7.7.4 (Indexing Strategy), FR-015 (Idempotent Processing)

    Args:
        product_id: UUID string of product to embed
        org_id: UUID string of organization (multi-tenant isolation)
        force_recompute: If True, bypass text_hash check and always recompute (default: False)
        embedding_model: Embedding model to use (default: text-embedding-3-small)

    Returns:
        Dict with keys:
            - product_id: Product UUID
            - embedding_id: ProductEmbedding UUID (or None if skipped)
            - status: 'created', 'updated', 'skipped', or 'failed'
            - text_hash: Hash of canonical text
            - tokens: Tokens used (0 if skipped)
            - cost_micros: Cost in micros (0 if skipped)

    Raises:
        ValueError: If org_id or product_id is invalid
        EmbeddingError: If embedding generation fails after retries

    Example:
        >>> embed_product.delay(
        ...     product_id=str(product.id),
        ...     org_id=str(product.org_id)
        ... )

    Notes:
        - Task is idempotent via text_hash deduplication
        - Retries automatically on timeout/rate limit (3x with backoff)
        - Logs to ai_call_log for cost tracking
        - Updates updated_at_source for staleness detection
    """
    # Validate org_id
    org_uuid = validate_org_id(org_id)
    product_uuid = UUID(product_id)

    # Get scoped session
    session: Session = get_scoped_session(org_uuid)

    try:
        # Fetch product with org_id filter
        product = session.query(Product).filter(
            Product.id == product_uuid,
            Product.org_id == org_uuid
        ).first()

        if not product:
            raise ValueError(f"Product {product_id} not found in org {org_id}")

        # Generate canonical text
        text = generate_product_embedding_text(
            internal_sku=product.internal_sku,
            name=product.name,
            description=product.description,
            base_uom=product.base_uom,
            attributes_json=product.attributes_json,
            uom_conversions_json=product.uom_conversions_json,
        )

        # Calculate text hash
        text_hash = calculate_text_hash(text)

        # Check if embedding already exists with same text_hash (deduplication)
        if not force_recompute:
            existing = session.query(ProductEmbedding).filter(
                ProductEmbedding.product_id == product_uuid,
                ProductEmbedding.embedding_model == embedding_model,
                ProductEmbedding.text_hash == text_hash
            ).first()

            if existing:
                # Text unchanged, skip API call
                session.commit()
                return {
                    'product_id': product_id,
                    'embedding_id': str(existing.id),
                    'status': 'skipped',
                    'text_hash': text_hash,
                    'tokens': 0,
                    'cost_micros': 0,
                    'reason': 'text_hash_match',
                }

        # Generate embedding via OpenAI adapter
        adapter = OpenAIEmbeddingAdapter()

        try:
            result = adapter.embed_text(text, model=embedding_model)

            # Log AI call
            logger = AICallLogger(session)
            logger.log_call(
                org_id=org_uuid,
                call_type=AICallType.EMBEDDING_PRODUCT,
                provider="openai",
                model=result.model,
                document_id=None,  # Not tied to specific document
                tokens_in=result.tokens,
                tokens_out=0,  # Embeddings don't have output tokens
                cost_micros=result.cost_micros,
                status="SUCCEEDED",
                latency_ms=0,  # Tracked inside adapter
                input_hash=text_hash,
            )

            # Upsert embedding
            embedding = session.query(ProductEmbedding).filter(
                ProductEmbedding.product_id == product_uuid,
                ProductEmbedding.embedding_model == result.model
            ).first()

            if embedding:
                # Update existing embedding
                embedding.embedding = result.embedding
                embedding.text_hash = text_hash
                embedding.embedding_dim = result.dimension
                embedding.updated_at = datetime.utcnow()
                embedding.updated_at_source = product.updated_source_at
                status = 'updated'
            else:
                # Create new embedding
                embedding = ProductEmbedding(
                    org_id=org_uuid,
                    product_id=product_uuid,
                    embedding_model=result.model,
                    embedding_dim=result.dimension,
                    embedding=result.embedding,
                    text_hash=text_hash,
                    updated_at_source=product.updated_source_at,
                )
                session.add(embedding)
                status = 'created'

            session.commit()

            return {
                'product_id': product_id,
                'embedding_id': str(embedding.id),
                'status': status,
                'text_hash': text_hash,
                'tokens': result.tokens,
                'cost_micros': result.cost_micros,
            }

        except EmbeddingError as e:
            # Log failed AI call
            logger = AICallLogger(session)
            logger.log_call(
                org_id=org_uuid,
                call_type=AICallType.EMBEDDING_PRODUCT,
                provider="openai",
                model=embedding_model,
                document_id=None,
                tokens_in=0,
                tokens_out=0,
                cost_micros=0,
                status="FAILED",
                latency_ms=0,
                input_hash=text_hash,
                error_json={'error': str(e), 'error_type': type(e).__name__},
            )
            session.commit()

            # Re-raise for Celery retry logic
            raise

    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()


@celery_app.task
def batch_embed_products(
    product_ids: list[str],
    org_id: str,
    force_recompute: bool = False,
    embedding_model: str = "text-embedding-3-small"
) -> Dict[str, Any]:
    """Enqueue embedding jobs for multiple products.

    Spawns individual embed_product tasks for each product.
    Use for bulk embedding (e.g., after product import).

    Args:
        product_ids: List of product UUID strings
        org_id: Organization UUID string
        force_recompute: Force recompute for all products
        embedding_model: Embedding model to use

    Returns:
        Dict with keys:
            - total: Total number of products
            - enqueued: Number of tasks enqueued

    Example:
        >>> product_ids = [str(p.id) for p in products]
        >>> batch_embed_products.delay(product_ids, str(org_id))

    Notes:
        - Each product gets separate task (enables parallel processing)
        - Tasks are idempotent (safe to enqueue duplicates)
        - Consider chunking very large batches (>1000 products)
    """
    # Validate org_id
    org_uuid = validate_org_id(org_id)

    enqueued = 0
    for product_id in product_ids:
        # Enqueue individual task
        embed_product.delay(
            product_id=product_id,
            org_id=org_id,
            force_recompute=force_recompute,
            embedding_model=embedding_model
        )
        enqueued += 1

    return {
        'total': len(product_ids),
        'enqueued': enqueued,
    }


@celery_app.task
def rebuild_embeddings_for_org(
    org_id: str,
    embedding_model: str = "text-embedding-3-small"
) -> Dict[str, Any]:
    """Rebuild all embeddings for an organization.

    Use for model migration or full index rebuild.

    SSOT Reference: FR-020 (Rebuild trigger), US6 (Embedding Rebuild)

    Args:
        org_id: Organization UUID string
        embedding_model: Embedding model to use

    Returns:
        Dict with keys:
            - org_id: Organization UUID
            - total_products: Total products found
            - enqueued: Number of tasks enqueued

    Example:
        >>> rebuild_embeddings_for_org.delay(str(org_id))

    Notes:
        - Sets force_recompute=True (bypasses text_hash check)
        - Expensive operation (budget gate should check before calling)
        - Consider running during off-peak hours for large catalogs
    """
    # Validate org_id
    org_uuid = validate_org_id(org_id)

    # Get scoped session
    session: Session = get_scoped_session(org_uuid)

    try:
        # Query all active products for org
        products = session.query(Product).filter(
            Product.org_id == org_uuid,
            Product.active == True
        ).all()

        product_ids = [str(p.id) for p in products]

        # Batch enqueue with force_recompute
        result = batch_embed_products(
            product_ids=product_ids,
            org_id=org_id,
            force_recompute=True,  # Force recompute for rebuild
            embedding_model=embedding_model
        )

        session.commit()

        return {
            'org_id': org_id,
            'total_products': len(products),
            'enqueued': result['enqueued'],
        }

    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()
