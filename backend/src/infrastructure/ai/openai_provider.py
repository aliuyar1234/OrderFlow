"""
OpenAI Provider - Concrete implementation of LLMProviderPort for OpenAI.

Implements LLM extraction using OpenAI's GPT models (gpt-4o-mini, gpt-4o).

SSOT Reference: §7.5.1 (Provider Interface), §7.5.2 (Model Selection)
"""

import os
import time
import json
import base64
from typing import Optional

from openai import OpenAI, APIError, RateLimitError, APIConnectionError, APITimeoutError, AuthenticationError

from domain.ai.ports import (
    LLMProviderPort,
    LLMExtractionResult,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMAuthError,
    LLMServiceError,
    LLMInvalidResponseError
)
from .cost_calculator import CostCalculator
from .token_estimator import TokenEstimator


class OpenAIProvider(LLMProviderPort):
    """
    OpenAI implementation of LLMProviderPort.

    Uses OpenAI Python SDK (v1.x+) with structured output (JSON mode).
    Handles authentication, request formatting, response parsing, error handling.

    SSOT Reference: §7.5.1-7.5.2
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)

        Raises:
            ValueError: If API key is not provided
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not provided. Set OPENAI_API_KEY environment variable.")

        self.client = OpenAI(api_key=self.api_key)
        self.default_text_model = "gpt-4o-mini"
        self.default_vision_model = "gpt-4o"

    def extract_order_from_pdf_text(
        self,
        text: str,
        context: dict
    ) -> LLMExtractionResult:
        """
        Extract order data from PDF text using GPT-4o-mini.

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
        model = context.get("model", self.default_text_model)

        # Build prompt (simplified for MVP - full prompt template in §7.5.3)
        system_prompt = """Extract purchase order information from the text below.
Return a JSON object with these fields:
- customer_name: string or null
- order_date: string (ISO date) or null
- customer_reference: string or null
- lines: array of {customer_sku: string, description: string, qty: number, uom: string, unit_price: number or null}

Return ONLY valid JSON, no markdown formatting."""

        user_prompt = f"Extract order from this text:\n\n{text}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        return self._make_completion_call(
            model=model,
            messages=messages,
            context=context
        )

    def extract_order_from_pdf_images(
        self,
        images: list[bytes],
        context: dict
    ) -> LLMExtractionResult:
        """
        Extract order data from PDF images using GPT-4o (vision).

        Args:
            images: List of image bytes (one per page)
            context: Additional context (org_id, document metadata, etc)

        Returns:
            LLMExtractionResult with extraction output and metadata

        Raises:
            LLMTimeoutError: Request timed out
            LLMRateLimitError: Rate limit exceeded
            LLMAuthError: Authentication failed
            LLMServiceError: Provider service unavailable
        """
        model = context.get("model", self.default_vision_model)

        # Build vision prompt
        system_prompt = """Extract purchase order information from the images below.
Return a JSON object with these fields:
- customer_name: string or null
- order_date: string (ISO date) or null
- customer_reference: string or null
- lines: array of {customer_sku: string, description: string, qty: number, uom: string, unit_price: number or null}

Return ONLY valid JSON, no markdown formatting."""

        # Build content with images
        content = [
            {"type": "text", "text": "Extract order from these document images:"}
        ]

        # Add images (base64 encoded)
        for img_bytes in images[:5]:  # Limit to first 5 pages for cost control
            b64_image = base64.b64encode(img_bytes).decode('utf-8')
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{b64_image}"
                }
            })

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content}
        ]

        return self._make_completion_call(
            model=model,
            messages=messages,
            context=context
        )

    def repair_invalid_json(
        self,
        previous_output: str,
        error: str,
        context: dict
    ) -> str:
        """
        Attempt to repair invalid JSON from previous LLM output.

        SSOT: §7.5.4 - One repair attempt allowed

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
        model = context.get("model", self.default_text_model)

        system_prompt = """You are a JSON repair assistant. Fix the invalid JSON below.
Return ONLY the corrected JSON, no explanations, no markdown formatting."""

        user_prompt = f"""The following JSON is invalid:

{previous_output}

Error: {error}

Fix the JSON and return only the corrected version."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        result = self._make_completion_call(
            model=model,
            messages=messages,
            context=context
        )

        return result.raw_output

    def _make_completion_call(
        self,
        model: str,
        messages: list,
        context: dict
    ) -> LLMExtractionResult:
        """
        Internal method to make OpenAI completion call with error handling.

        Args:
            model: Model name
            messages: Chat messages
            context: Additional context

        Returns:
            LLMExtractionResult

        Raises:
            LLMTimeoutError, LLMRateLimitError, LLMAuthError, LLMServiceError
        """
        start_time = time.perf_counter()
        warnings = []

        try:
            # Make API call with JSON mode
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.0,  # Deterministic for extraction
                timeout=30.0  # 30 second timeout
            )

            # Calculate latency
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Extract response
            raw_output = response.choices[0].message.content

            # Parse JSON
            parsed_json = None
            try:
                parsed_json = json.loads(raw_output)
            except json.JSONDecodeError as e:
                warnings.append(f"Failed to parse LLM JSON output: {str(e)}")

            # Extract token usage
            usage = response.usage
            prompt_tokens = usage.prompt_tokens if usage else None
            completion_tokens = usage.completion_tokens if usage else None

            # Calculate cost
            cost_micros = 0
            if prompt_tokens and completion_tokens:
                try:
                    cost_micros = CostCalculator.calculate_cost_micros(
                        provider="openai",
                        model=model,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens
                    )
                except ValueError as e:
                    warnings.append(f"Failed to calculate cost: {str(e)}")

            return LLMExtractionResult(
                raw_output=raw_output,
                parsed_json=parsed_json,
                provider="openai",
                model=model,
                tokens_in=prompt_tokens,
                tokens_out=completion_tokens,
                latency_ms=latency_ms,
                cost_micros=cost_micros,
                warnings=warnings
            )

        except APITimeoutError as e:
            raise LLMTimeoutError(f"OpenAI API timeout: {str(e)}")

        except RateLimitError as e:
            raise LLMRateLimitError(f"OpenAI rate limit exceeded: {str(e)}")

        except AuthenticationError as e:
            raise LLMAuthError(f"OpenAI authentication failed: {str(e)}")

        except (APIConnectionError, APIError) as e:
            raise LLMServiceError(f"OpenAI service error: {str(e)}")

        except Exception as e:
            raise LLMServiceError(f"Unexpected error calling OpenAI: {str(e)}")
