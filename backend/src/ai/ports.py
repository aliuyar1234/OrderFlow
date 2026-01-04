"""Port interfaces for AI providers (Hexagonal Architecture)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMExtractionResult:
    """Result from LLM extraction call."""

    raw_output: str
    parsed_json: dict | None
    provider: str
    model: str
    tokens_in: int | None = None
    tokens_out: int | None = None
    latency_ms: int | None = None
    cost_micros: int | None = None
    warnings: list[str] | None = None


class LLMProviderPort(ABC):
    """Port interface for LLM providers.

    Synchronous interface (async usage in workers).
    Implementations must handle:
    - Timeouts
    - Rate limiting
    - Error recovery
    - Cost tracking
    """

    @abstractmethod
    def extract_order_from_pdf_text(
        self,
        text: str,
        context: dict[str, Any]
    ) -> LLMExtractionResult:
        """Extract order data from PDF text using LLM.

        Args:
            text: Extracted text from PDF
            context: Extraction context (from_email, subject, etc.)

        Returns:
            LLMExtractionResult with raw output and parsed JSON

        Raises:
            LLMTimeoutError: If request times out
            LLMRateLimitError: If rate limited
            LLMProviderError: For other provider errors
        """
        pass

    @abstractmethod
    def extract_order_from_pdf_images(
        self,
        images: list[bytes],
        context: dict[str, Any]
    ) -> LLMExtractionResult:
        """Extract order data from PDF page images using vision LLM.

        Args:
            images: List of PNG image bytes (one per page)
            context: Extraction context

        Returns:
            LLMExtractionResult with raw output and parsed JSON

        Raises:
            LLMTimeoutError: If request times out
            LLMRateLimitError: If rate limited
            LLMProviderError: For other provider errors
        """
        pass

    @abstractmethod
    def repair_invalid_json(
        self,
        previous_output: str,
        error: str,
        context: dict[str, Any]
    ) -> str:
        """Attempt to repair invalid JSON from LLM output.

        Args:
            previous_output: The invalid JSON string
            error: The validation error message
            context: Schema and other context

        Returns:
            Repaired JSON string (not validated)

        Raises:
            LLMTimeoutError: If request times out
            LLMRateLimitError: If rate limited
            LLMProviderError: For other provider errors
        """
        pass


class EmbeddingProviderPort(ABC):
    """Port interface for embedding providers."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Generate embedding vector for text.

        Args:
            text: Input text to embed

        Returns:
            Embedding vector (dimension must match configured dim)

        Raises:
            EmbeddingProviderError: For provider errors
        """
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for multiple texts (batch).

        Args:
            texts: List of input texts

        Returns:
            List of embedding vectors

        Raises:
            EmbeddingProviderError: For provider errors
        """
        pass


# Custom exceptions
class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""
    pass


class LLMTimeoutError(LLMProviderError):
    """LLM request timed out."""
    pass


class LLMRateLimitError(LLMProviderError):
    """LLM rate limit exceeded."""
    pass


class EmbeddingProviderError(Exception):
    """Base exception for embedding provider errors."""
    pass
