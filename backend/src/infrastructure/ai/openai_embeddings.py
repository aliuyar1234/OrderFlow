"""OpenAI Embedding Adapter - Implementation of EmbeddingProviderPort using OpenAI API.

This adapter provides embeddings using OpenAI's text-embedding-3-small model (1536 dimensions).

SSOT Reference: §7.7.1 (Embedding Model), §3.5 (EmbeddingProviderPort)
Architecture: Hexagonal - Infrastructure adapter implementing domain port
"""

import os
import time
from typing import Optional

import openai
from openai import OpenAI, APIError, APITimeoutError, RateLimitError, AuthenticationError

from src.domain.ai.ports import (
    EmbeddingProviderPort,
    EmbeddingResult,
    EmbeddingTimeoutError,
    EmbeddingRateLimitError,
    EmbeddingAuthError,
    EmbeddingServiceError,
    EmbeddingInvalidResponseError,
)


class OpenAIEmbeddingAdapter(EmbeddingProviderPort):
    """OpenAI implementation of EmbeddingProviderPort.

    Uses OpenAI's embeddings API with text-embedding-3-small model by default.

    Configuration (environment variables):
        OPENAI_API_KEY: OpenAI API key (required)
        OPENAI_EMBEDDING_TIMEOUT: Request timeout in seconds (default: 30)

    Pricing (as of 2024):
        text-embedding-3-small: $0.020 per 1M tokens

    Token Limits:
        text-embedding-3-small: 8191 tokens max input

    Example Usage:
        adapter = OpenAIEmbeddingAdapter()
        result = adapter.embed_text("Cable NYM-J 3x1.5mm²")
        # result.embedding is list[float] of length 1536
        # result.tokens is number of tokens used
        # result.cost_micros is cost in micros
    """

    def __init__(self, api_key: Optional[str] = None, timeout: int = 30):
        """Initialize OpenAI embedding adapter.

        Args:
            api_key: OpenAI API key (if None, reads from OPENAI_API_KEY env var)
            timeout: Request timeout in seconds (default: 30)

        Raises:
            EmbeddingAuthError: If API key is not provided and not in environment
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise EmbeddingAuthError("OPENAI_API_KEY not provided and not found in environment")

        self.timeout = timeout
        self.client = OpenAI(api_key=self.api_key, timeout=self.timeout)

    def embed_text(
        self,
        text: str,
        model: str = "text-embedding-3-small"
    ) -> EmbeddingResult:
        """Generate embedding vector for text using OpenAI API.

        Args:
            text: Text to embed (max 8191 tokens for text-embedding-3-small)
            model: Embedding model name (default: text-embedding-3-small)

        Returns:
            EmbeddingResult with vector, tokens, cost, and metadata

        Raises:
            ValueError: If text is empty
            EmbeddingTimeoutError: Request timed out
            EmbeddingRateLimitError: Rate limit exceeded
            EmbeddingAuthError: Authentication failed
            EmbeddingServiceError: OpenAI service error
            EmbeddingInvalidResponseError: Invalid response from API

        Notes:
            - Input text >8191 tokens will be rejected by OpenAI API
            - Caller should truncate long text before calling
            - Empty text raises ValueError
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        start_time = time.time()

        try:
            response = self.client.embeddings.create(
                model=model,
                input=text,
            )

            # Extract embedding and metadata
            if not response.data or len(response.data) == 0:
                raise EmbeddingInvalidResponseError("No embedding returned from API")

            embedding = response.data[0].embedding
            tokens = response.usage.total_tokens if response.usage else 0

            # Calculate cost (OpenAI pricing: $0.020 per 1M tokens for text-embedding-3-small)
            cost_per_million = self._get_cost_per_million_tokens(model)
            cost_micros = int((tokens / 1_000_000) * cost_per_million * 1_000_000)

            latency_ms = int((time.time() - start_time) * 1000)

            return EmbeddingResult(
                embedding=embedding,
                model=model,
                dimension=len(embedding),
                tokens=tokens,
                cost_micros=cost_micros,
            )

        except AuthenticationError as e:
            raise EmbeddingAuthError(f"OpenAI authentication failed: {e}")
        except RateLimitError as e:
            raise EmbeddingRateLimitError(f"OpenAI rate limit exceeded: {e}")
        except APITimeoutError as e:
            raise EmbeddingTimeoutError(f"OpenAI request timed out: {e}")
        except APIError as e:
            raise EmbeddingServiceError(f"OpenAI API error: {e}")
        except Exception as e:
            raise EmbeddingInvalidResponseError(f"Unexpected error from OpenAI: {e}")

    def batch_embed_texts(
        self,
        texts: list[str],
        model: str = "text-embedding-3-small"
    ) -> list[EmbeddingResult]:
        """Generate embeddings for multiple texts in batch using OpenAI API.

        Batch embedding is more efficient than individual calls.

        Args:
            texts: List of texts to embed (max 2048 texts per batch)
            model: Embedding model name

        Returns:
            List of EmbeddingResult, one per input text (same order)

        Raises:
            ValueError: If texts is empty or contains empty strings
            EmbeddingTimeoutError: Request timed out
            EmbeddingRateLimitError: Rate limit exceeded
            EmbeddingAuthError: Authentication failed
            EmbeddingServiceError: OpenAI service error
            EmbeddingInvalidResponseError: Invalid response from API

        Notes:
            - OpenAI batch limit: 2048 texts per request
            - Caller should chunk larger batches
            - All texts must be non-empty
            - If any text fails, entire batch fails
        """
        if not texts:
            raise ValueError("Texts list cannot be empty")

        if any(not t or not t.strip() for t in texts):
            raise ValueError("All texts must be non-empty")

        if len(texts) > 2048:
            raise ValueError("Batch size exceeds OpenAI limit of 2048 texts")

        start_time = time.time()

        try:
            response = self.client.embeddings.create(
                model=model,
                input=texts,
            )

            # Extract embeddings
            if not response.data or len(response.data) != len(texts):
                raise EmbeddingInvalidResponseError(
                    f"Expected {len(texts)} embeddings, got {len(response.data) if response.data else 0}"
                )

            # Sort by index to ensure correct order
            sorted_data = sorted(response.data, key=lambda x: x.index)

            total_tokens = response.usage.total_tokens if response.usage else 0

            # Calculate cost
            cost_per_million = self._get_cost_per_million_tokens(model)
            total_cost_micros = int((total_tokens / 1_000_000) * cost_per_million * 1_000_000)

            # Distribute tokens and cost proportionally across results
            # (approximation: divide evenly, in reality some texts use more tokens)
            tokens_per_text = total_tokens // len(texts)
            cost_per_text = total_cost_micros // len(texts)

            results = []
            for data in sorted_data:
                embedding = data.embedding
                results.append(EmbeddingResult(
                    embedding=embedding,
                    model=model,
                    dimension=len(embedding),
                    tokens=tokens_per_text,
                    cost_micros=cost_per_text,
                ))

            return results

        except AuthenticationError as e:
            raise EmbeddingAuthError(f"OpenAI authentication failed: {e}")
        except RateLimitError as e:
            raise EmbeddingRateLimitError(f"OpenAI rate limit exceeded: {e}")
        except APITimeoutError as e:
            raise EmbeddingTimeoutError(f"OpenAI request timed out: {e}")
        except APIError as e:
            raise EmbeddingServiceError(f"OpenAI API error: {e}")
        except Exception as e:
            raise EmbeddingInvalidResponseError(f"Unexpected error from OpenAI: {e}")

    def _get_cost_per_million_tokens(self, model: str) -> float:
        """Get cost per million tokens for a given model.

        Args:
            model: Model name

        Returns:
            Cost in dollars per 1M tokens

        Notes:
            Pricing as of January 2025:
            - text-embedding-3-small: $0.020 per 1M tokens
            - text-embedding-3-large: $0.130 per 1M tokens
            - text-embedding-ada-002: $0.100 per 1M tokens (legacy)
        """
        pricing = {
            "text-embedding-3-small": 0.020,
            "text-embedding-3-large": 0.130,
            "text-embedding-ada-002": 0.100,
        }

        return pricing.get(model, 0.020)  # Default to small model pricing
