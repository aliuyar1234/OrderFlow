"""AI domain layer - Ports and domain models for LLM/Embedding providers"""

from .ports import LLMProviderPort, LLMExtractionResult, LLMMessage
from .ports import (
    EmbeddingProviderPort,
    EmbeddingResult,
    EmbeddingError,
    EmbeddingTimeoutError,
    EmbeddingRateLimitError,
    EmbeddingAuthError,
    EmbeddingServiceError,
    EmbeddingInvalidResponseError,
)
from .models import AICallType
from .budget_gate import BudgetGate, BudgetGateError
from .ai_call_logger import AICallLogger

__all__ = [
    "LLMProviderPort",
    "LLMExtractionResult",
    "LLMMessage",
    "EmbeddingProviderPort",
    "EmbeddingResult",
    "EmbeddingError",
    "EmbeddingTimeoutError",
    "EmbeddingRateLimitError",
    "EmbeddingAuthError",
    "EmbeddingServiceError",
    "EmbeddingInvalidResponseError",
    "AICallType",
    "BudgetGate",
    "BudgetGateError",
    "AICallLogger",
]
