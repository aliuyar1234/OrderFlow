"""Embedding Provider Port - Abstract interface for embedding providers.

Hexagonal Architecture: This is a domain port that infrastructure adapters implement.
Business logic depends on this port, not on concrete implementations (OpenAI, local models, etc).

SSOT Reference: §3.5 (EmbeddingProviderPort), §7.7 (Embedding-based Matching)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class EmbeddingResult:
    """Result from embedding generation call.

    Contains embedding vector and metadata for logging/tracking.

    SSOT Reference: §7.7.1 (Embedding Model), §7.7.3 (Canonical Text)

    Attributes:
        embedding: Vector embedding (list of floats, typically 1536-dim for OpenAI)
        model: Model name (e.g., 'text-embedding-3-small')
        dimension: Embedding dimension (e.g., 1536)
        tokens: Number of tokens used
        cost_micros: Cost in micros (1 micro = 1/1,000,000 EUR)
    """
    embedding: list[float]
    model: str
    dimension: int
    tokens: int
    cost_micros: int


class EmbeddingProviderPort(ABC):
    """Abstract interface for embedding providers.

    Implementations must handle:
    - API authentication
    - Request formatting for provider
    - Response parsing
    - Error handling (timeouts, rate limits, invalid responses)
    - Token/cost tracking

    Key Design Principles (SSOT §7.7):
    - Text embeddings for product search and matching
    - Deterministic canonical text format (§7.7.3)
    - Cost tracking and budget gates
    - Deduplication via text_hash

    Example Usage:
        provider = OpenAIEmbeddingAdapter()
        result = provider.embed_text("Cable NYM-J 3x1.5mm²", model="text-embedding-3-small")
        # result.embedding is list[float] of length 1536
    """

    @abstractmethod
    def embed_text(
        self,
        text: str,
        model: str = "text-embedding-3-small"
    ) -> EmbeddingResult:
        """Generate embedding vector for text.

        Args:
            text: Text to embed (product description, query, etc)
            model: Embedding model name (default: text-embedding-3-small)

        Returns:
            EmbeddingResult with vector and metadata

        Raises:
            EmbeddingTimeoutError: Request timed out
            EmbeddingRateLimitError: Rate limit exceeded
            EmbeddingAuthError: Authentication failed
            EmbeddingServiceError: Provider service unavailable
            EmbeddingInvalidResponseError: Provider returned invalid response

        Notes:
            - Input text length limits vary by provider (8191 tokens for OpenAI)
            - Long text should be truncated before calling
            - Empty text raises ValueError
        """
        pass

    @abstractmethod
    def batch_embed_texts(
        self,
        texts: list[str],
        model: str = "text-embedding-3-small"
    ) -> list[EmbeddingResult]:
        """Generate embeddings for multiple texts in batch.

        Batch embedding is more efficient than individual calls for large sets.

        Args:
            texts: List of texts to embed
            model: Embedding model name

        Returns:
            List of EmbeddingResult, one per input text (same order)

        Raises:
            EmbeddingTimeoutError: Request timed out
            EmbeddingRateLimitError: Rate limit exceeded
            EmbeddingAuthError: Authentication failed
            EmbeddingServiceError: Provider service unavailable
            EmbeddingInvalidResponseError: Provider returned invalid response

        Notes:
            - Batch size limits vary by provider (typically 2048 for OpenAI)
            - Caller should chunk large batches
            - If any text fails, entire batch may fail (depends on provider)
        """
        pass


# Custom exceptions for embedding operations
class EmbeddingError(Exception):
    """Base exception for embedding operations"""
    pass


class EmbeddingTimeoutError(EmbeddingError):
    """Embedding request timed out"""
    pass


class EmbeddingRateLimitError(EmbeddingError):
    """Rate limit exceeded"""
    pass


class EmbeddingAuthError(EmbeddingError):
    """Authentication failed"""
    pass


class EmbeddingServiceError(EmbeddingError):
    """Provider service unavailable or returned error"""
    pass


class EmbeddingInvalidResponseError(EmbeddingError):
    """Provider returned invalid/unexpected response"""
    pass
