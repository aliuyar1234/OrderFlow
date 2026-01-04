"""
LLM Provider Port - Abstract interface for LLM providers.

Hexagonal Architecture: This is a domain port that infrastructure adapters implement.
Business logic depends on this port, not on concrete implementations (OpenAI, Anthropic, etc).

SSOT Reference: §3.5 (LLMProviderPort), §7.5.1 (Provider Interface)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMMessage:
    """
    Message format for LLM conversations.

    Attributes:
        role: Message role ('system', 'user', 'assistant')
        content: Text content or vision payload
        image_data: Optional base64-encoded image for vision models
    """
    role: str
    content: str
    image_data: Optional[bytes] = None


@dataclass
class LLMExtractionResult:
    """
    Result from LLM extraction call.

    Contains both raw output and parsed result, plus metadata for logging/tracking.

    SSOT Reference: §7.5.1 (LLMExtractionResult structure)

    Attributes:
        raw_output: Raw string response from LLM
        parsed_json: Parsed JSON dict if successful, None if parsing failed
        provider: Provider name (e.g., 'openai', 'anthropic')
        model: Model name (e.g., 'gpt-4o-mini')
        tokens_in: Input tokens used (None if provider doesn't report)
        tokens_out: Output tokens used (None if provider doesn't report)
        latency_ms: Latency in milliseconds
        cost_micros: Cost in micros (1 micro = 1/1,000,000 EUR)
        warnings: List of non-critical warnings
    """
    raw_output: str
    parsed_json: Optional[dict]
    provider: str
    model: str
    tokens_in: Optional[int]
    tokens_out: Optional[int]
    latency_ms: int
    cost_micros: int
    warnings: list[str]


class LLMProviderPort(ABC):
    """
    Abstract interface for LLM providers.

    Implementations must handle:
    - API authentication
    - Request formatting for provider
    - Response parsing
    - Error handling (timeouts, rate limits, invalid responses)
    - Token/cost tracking
    """

    @abstractmethod
    def extract_order_from_pdf_text(
        self,
        text: str,
        context: dict
    ) -> LLMExtractionResult:
        """
        Extract order data from PDF text using LLM.

        Args:
            text: Extracted text from PDF
            context: Additional context (org_id, document metadata, etc)

        Returns:
            LLMExtractionResult with extraction output and metadata

        Raises:
            LLMTimeoutError: Request timed out
            LLMRateLimitError: Rate limit exceeded
            LLMAuthError: Authentication failed
            LLMServiceError: Provider service unavailable
        """
        pass

    @abstractmethod
    def extract_order_from_pdf_images(
        self,
        images: list[bytes],
        context: dict
    ) -> LLMExtractionResult:
        """
        Extract order data from PDF images using vision LLM.

        Args:
            images: List of base64-encoded image bytes (one per page)
            context: Additional context (org_id, document metadata, etc)

        Returns:
            LLMExtractionResult with extraction output and metadata

        Raises:
            LLMTimeoutError: Request timed out
            LLMRateLimitError: Rate limit exceeded
            LLMAuthError: Authentication failed
            LLMServiceError: Provider service unavailable
        """
        pass

    @abstractmethod
    def repair_invalid_json(
        self,
        previous_output: str,
        error: str,
        context: dict
    ) -> str:
        """
        Attempt to repair invalid JSON from previous LLM output.

        SSOT Reference: §7.5.4 (JSON Repair with 1 retry)

        Args:
            previous_output: Invalid JSON string from previous call
            error: Parse error message
            context: Additional context

        Returns:
            Repaired JSON string (caller must parse/validate)

        Raises:
            LLMTimeoutError: Request timed out
            LLMRateLimitError: Rate limit exceeded
            LLMAuthError: Authentication failed
            LLMServiceError: Provider service unavailable
        """
        pass


# Custom exceptions for LLM operations
class LLMError(Exception):
    """Base exception for LLM operations"""
    pass


class LLMTimeoutError(LLMError):
    """LLM request timed out"""
    pass


class LLMRateLimitError(LLMError):
    """Rate limit exceeded"""
    pass


class LLMAuthError(LLMError):
    """Authentication failed"""
    pass


class LLMServiceError(LLMError):
    """Provider service unavailable or returned error"""
    pass


class LLMInvalidResponseError(LLMError):
    """Provider returned invalid/unexpected response"""
    pass
