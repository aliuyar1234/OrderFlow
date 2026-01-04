"""OpenAI LLM provider implementation."""

import base64
import json
import time
from typing import Any

from openai import OpenAI, APIError, Timeout, RateLimitError

from ..ports import (
    LLMProviderPort,
    LLMExtractionResult,
    LLMProviderError,
    LLMTimeoutError,
    LLMRateLimitError,
)
from ...extraction.prompts import (
    build_text_extraction_prompt,
    build_vision_extraction_prompt,
    build_json_repair_prompt,
)


class OpenAIProvider(LLMProviderPort):
    """OpenAI LLM provider implementation.

    Implements text and vision extraction using OpenAI models.
    Default models (SSOT §7.5.2):
    - Text: gpt-4o-mini
    - Vision: gpt-4o
    """

    def __init__(
        self,
        api_key: str,
        model_text: str = "gpt-4o-mini",
        model_vision: str = "gpt-4o",
        timeout_seconds: int = 40,
    ):
        """Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key
            model_text: Model for text extraction
            model_vision: Model for vision extraction
            timeout_seconds: Request timeout
        """
        self.client = OpenAI(api_key=api_key, timeout=timeout_seconds)
        self.model_text = model_text
        self.model_vision = model_vision
        self.timeout_seconds = timeout_seconds

    def extract_order_from_pdf_text(
        self,
        text: str,
        context: dict[str, Any]
    ) -> LLMExtractionResult:
        """Extract order from PDF text using LLM."""
        start_ms = int(time.time() * 1000)

        # Build prompts
        system_prompt, user_prompt = build_text_extraction_prompt(
            pdf_text=text,
            from_email=context.get("from_email"),
            subject=context.get("subject"),
            default_currency=context.get("default_currency", "EUR"),
            known_customer_numbers_csv=context.get("known_customer_numbers_csv", ""),
            hint_examples=context.get("hint_examples", ""),
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model_text,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,  # Deterministic
                response_format={"type": "json_object"},  # Force JSON mode
            )

            raw_output = response.choices[0].message.content or ""
            latency_ms = int(time.time() * 1000) - start_ms

            # Parse JSON
            parsed_json = None
            try:
                parsed_json = json.loads(raw_output)
            except json.JSONDecodeError:
                # Will be handled by caller (repair attempt)
                pass

            # Calculate cost (approximate)
            cost_micros = self._calculate_cost(
                model=self.model_text,
                tokens_in=response.usage.prompt_tokens if response.usage else None,
                tokens_out=response.usage.completion_tokens if response.usage else None,
            )

            return LLMExtractionResult(
                raw_output=raw_output,
                parsed_json=parsed_json,
                provider="openai",
                model=self.model_text,
                tokens_in=response.usage.prompt_tokens if response.usage else None,
                tokens_out=response.usage.completion_tokens if response.usage else None,
                latency_ms=latency_ms,
                cost_micros=cost_micros,
                warnings=[],
            )

        except Timeout as e:
            raise LLMTimeoutError(f"OpenAI request timed out: {e}") from e
        except RateLimitError as e:
            raise LLMRateLimitError(f"OpenAI rate limit exceeded: {e}") from e
        except APIError as e:
            raise LLMProviderError(f"OpenAI API error: {e}") from e

    def extract_order_from_pdf_images(
        self,
        images: list[bytes],
        context: dict[str, Any]
    ) -> LLMExtractionResult:
        """Extract order from PDF images using vision LLM."""
        start_ms = int(time.time() * 1000)

        # Build prompts
        system_prompt, user_prompt = build_vision_extraction_prompt(
            from_email=context.get("from_email"),
            subject=context.get("subject"),
            default_currency=context.get("default_currency", "EUR"),
            known_customer_numbers_csv=context.get("known_customer_numbers_csv", ""),
            hint_examples=context.get("hint_examples", ""),
        )

        # Encode images as base64
        image_contents = []
        for idx, image_bytes in enumerate(images):
            base64_image = base64.b64encode(image_bytes).decode("utf-8")
            image_contents.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{base64_image}",
                    "detail": "high",  # High detail for tables
                }
            })

        # Build user message with text + images
        user_message_content = [{"type": "text", "text": user_prompt}] + image_contents

        try:
            response = self.client.chat.completions.create(
                model=self.model_vision,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message_content},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            )

            raw_output = response.choices[0].message.content or ""
            latency_ms = int(time.time() * 1000) - start_ms

            # Parse JSON
            parsed_json = None
            try:
                parsed_json = json.loads(raw_output)
            except json.JSONDecodeError:
                pass

            # Calculate cost
            cost_micros = self._calculate_cost(
                model=self.model_vision,
                tokens_in=response.usage.prompt_tokens if response.usage else None,
                tokens_out=response.usage.completion_tokens if response.usage else None,
            )

            return LLMExtractionResult(
                raw_output=raw_output,
                parsed_json=parsed_json,
                provider="openai",
                model=self.model_vision,
                tokens_in=response.usage.prompt_tokens if response.usage else None,
                tokens_out=response.usage.completion_tokens if response.usage else None,
                latency_ms=latency_ms,
                cost_micros=cost_micros,
                warnings=[],
            )

        except Timeout as e:
            raise LLMTimeoutError(f"OpenAI request timed out: {e}") from e
        except RateLimitError as e:
            raise LLMRateLimitError(f"OpenAI rate limit exceeded: {e}") from e
        except APIError as e:
            raise LLMProviderError(f"OpenAI API error: {e}") from e

    def repair_invalid_json(
        self,
        previous_output: str,
        error: str,
        context: dict[str, Any]
    ) -> str:
        """Attempt to repair invalid JSON."""
        # Build repair prompt
        system_prompt, user_prompt = build_json_repair_prompt(
            invalid_json=previous_output,
            validation_error=error,
            schema_json=context.get("schema_json", "{}"),
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model_text,  # Use text model for repair
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                response_format={"type": "json_object"},
            )

            return response.choices[0].message.content or ""

        except Timeout as e:
            raise LLMTimeoutError(f"OpenAI request timed out: {e}") from e
        except RateLimitError as e:
            raise LLMRateLimitError(f"OpenAI rate limit exceeded: {e}") from e
        except APIError as e:
            raise LLMProviderError(f"OpenAI API error: {e}") from e

    def _calculate_cost(
        self,
        model: str,
        tokens_in: int | None,
        tokens_out: int | None,
    ) -> int | None:
        """Calculate approximate cost in micros (1/1,000,000 of currency unit).

        Pricing as of 2025 (approximate):
        - gpt-4o-mini: $0.15/1M input, $0.60/1M output
        - gpt-4o: $2.50/1M input, $10.00/1M output

        Returns cost in micros (EUR cents * 10,000).
        """
        if tokens_in is None or tokens_out is None:
            return None

        # Pricing in micros per token
        pricing = {
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4o": {"input": 2.50, "output": 10.00},
        }

        if model not in pricing:
            return None

        cost_usd = (
            (tokens_in / 1_000_000) * pricing[model]["input"] +
            (tokens_out / 1_000_000) * pricing[model]["output"]
        )

        # Convert to micros (assuming USD ≈ EUR for simplicity)
        return int(cost_usd * 1_000_000)
