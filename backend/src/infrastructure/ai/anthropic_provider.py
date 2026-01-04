"""
Anthropic Provider - Stub implementation of LLMProviderPort for Anthropic Claude.

Future implementation will support Claude models (Opus, Sonnet, Haiku).
Currently raises NotImplementedError.

SSOT Reference: §7.5.1 (Provider Interface)
"""

from typing import Optional

from domain.ai.ports import (
    LLMProviderPort,
    LLMExtractionResult,
    LLMServiceError
)


class AnthropicProvider(LLMProviderPort):
    """
    Anthropic Claude implementation of LLMProviderPort (STUB).

    Future enhancement: Full implementation with Claude-3 models.
    For now, raises NotImplementedError to signal provider not yet supported.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key

        Raises:
            NotImplementedError: Provider not yet implemented
        """
        raise NotImplementedError(
            "Anthropic provider not yet implemented. Use OpenAI provider for MVP."
        )

    def extract_order_from_pdf_text(
        self,
        text: str,
        context: dict
    ) -> LLMExtractionResult:
        """Not implemented - raises NotImplementedError"""
        raise NotImplementedError("Anthropic provider not yet implemented")

    def extract_order_from_pdf_images(
        self,
        images: list[bytes],
        context: dict
    ) -> LLMExtractionResult:
        """Not implemented - raises NotImplementedError"""
        raise NotImplementedError("Anthropic provider not yet implemented")

    def repair_invalid_json(
        self,
        previous_output: str,
        error: str,
        context: dict
    ) -> str:
        """Not implemented - raises NotImplementedError"""
        raise NotImplementedError("Anthropic provider not yet implemented")
