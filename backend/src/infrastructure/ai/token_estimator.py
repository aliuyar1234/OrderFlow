"""
Token Estimator - Conservative token usage estimation for budget gates.

Estimates token usage before making LLM calls to enforce budget limits.

SSOT Reference: §7.2.3 (Token Estimation)
"""

import math


class TokenEstimator:
    """
    Conservative token estimator for LLM inputs.

    Uses simple heuristics to estimate token usage before making API calls.
    Actual token counts will vary based on tokenizer, but these estimates
    provide ~20-30% buffer for safety.

    SSOT: §7.2.3
    - Text LLM: estimated_tokens = ceil(len(text)/4)
    - Vision LLM: estimated_tokens = 1500 * page_count + 500 base
    """

    @staticmethod
    def estimate_text_tokens(text: str, add_buffer: bool = True) -> int:
        """
        Estimate tokens for text-based LLM input.

        Args:
            text: Input text
            add_buffer: Add 20% safety buffer (default: True)

        Returns:
            Estimated token count (conservative)

        SSOT: Text tokens ≈ len(text)/4 with 20% overhead buffer
        """
        # Base estimate: 4 characters per token (conservative)
        base_estimate = math.ceil(len(text) / 4)

        # Add 20% buffer for prompt template overhead
        if add_buffer:
            return math.ceil(base_estimate * 1.2)

        return base_estimate

    @staticmethod
    def estimate_vision_tokens(page_count: int, add_buffer: bool = True) -> int:
        """
        Estimate tokens for vision LLM input (images).

        Args:
            page_count: Number of PDF pages/images
            add_buffer: Add 20% safety buffer (default: True)

        Returns:
            Estimated token count (conservative)

        SSOT: Vision tokens ≈ 1500 * page_count + 500 base
        """
        # Base: 500 tokens for system prompt + 1500 per image
        base_estimate = 500 + (1500 * page_count)

        # Add 20% buffer for prompt template overhead
        if add_buffer:
            return math.ceil(base_estimate * 1.2)

        return base_estimate

    @staticmethod
    def estimate_repair_tokens(previous_output: str, error_msg: str) -> int:
        """
        Estimate tokens for JSON repair call.

        Args:
            previous_output: Invalid JSON from previous attempt
            error_msg: Error message describing parsing failure

        Returns:
            Estimated token count
        """
        # Repair prompt includes: system prompt (~100 tokens) + previous output + error
        system_tokens = 100
        output_tokens = TokenEstimator.estimate_text_tokens(previous_output, add_buffer=False)
        error_tokens = TokenEstimator.estimate_text_tokens(error_msg, add_buffer=False)

        # Add 20% buffer
        return math.ceil((system_tokens + output_tokens + error_tokens) * 1.2)
