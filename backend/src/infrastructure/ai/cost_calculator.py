"""
Cost Calculator - Calculate LLM API costs from token usage.

Calculates costs in micro-USD (1/1,000,000 USD) for tracking and budget enforcement.

SSOT Reference: §7.5.7 (Cost/Latency Considerations)
"""

from typing import Dict, Tuple


class CostCalculator:
    """
    Calculate LLM API costs based on provider pricing.

    Pricing stored as micro-USD per million tokens.
    Cost calculation: (tokens * rate_per_million) / 1_000_000 = cost in USD
    Then convert to micro-USD: cost_usd * 1_000_000

    SSOT Reference: §7.5.7 (FR-004)
    """

    # Pricing in USD per 1M tokens (as of 2026-01-04)
    # Updated when providers change rates
    PRICING: Dict[str, Dict[str, Tuple[float, float]]] = {
        "openai": {
            "gpt-4o-mini": (0.150, 0.600),  # (input, output) per 1M tokens
            "gpt-4o": (2.50, 10.00),
            "gpt-4-turbo": (10.00, 30.00),
            "gpt-3.5-turbo": (0.50, 1.50),
        },
        "anthropic": {
            "claude-3-opus": (15.00, 75.00),
            "claude-3-sonnet": (3.00, 15.00),
            "claude-3-haiku": (0.25, 1.25),
        },
    }

    @staticmethod
    def calculate_cost_micros(
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> int:
        """
        Calculate cost in micro-USD (1/1,000,000 USD).

        Args:
            provider: Provider name (e.g., 'openai', 'anthropic')
            model: Model name (e.g., 'gpt-4o-mini')
            prompt_tokens: Input tokens used
            completion_tokens: Output tokens used

        Returns:
            Cost in micro-USD (integer)

        Raises:
            ValueError: If provider or model not found in pricing table

        Example:
            >>> CostCalculator.calculate_cost_micros("openai", "gpt-4o-mini", 1000, 500)
            450  # 0.00045 USD = 450 micro-USD
        """
        provider_lower = provider.lower()
        model_lower = model.lower()

        # Lookup pricing
        if provider_lower not in CostCalculator.PRICING:
            raise ValueError(f"Unknown provider: {provider}")

        provider_pricing = CostCalculator.PRICING[provider_lower]
        if model_lower not in provider_pricing:
            raise ValueError(f"Unknown model for {provider}: {model}")

        input_rate, output_rate = provider_pricing[model_lower]

        # Calculate cost in USD
        input_cost_usd = (prompt_tokens * input_rate) / 1_000_000
        output_cost_usd = (completion_tokens * output_rate) / 1_000_000
        total_cost_usd = input_cost_usd + output_cost_usd

        # Convert to micro-USD (integer for precision)
        cost_micros = int(round(total_cost_usd * 1_000_000))

        return cost_micros

    @staticmethod
    def get_model_pricing(provider: str, model: str) -> Tuple[float, float]:
        """
        Get pricing for a specific model.

        Args:
            provider: Provider name
            model: Model name

        Returns:
            (input_rate, output_rate) in USD per 1M tokens

        Raises:
            ValueError: If provider or model not found
        """
        provider_lower = provider.lower()
        model_lower = model.lower()

        if provider_lower not in CostCalculator.PRICING:
            raise ValueError(f"Unknown provider: {provider}")

        provider_pricing = CostCalculator.PRICING[provider_lower]
        if model_lower not in provider_pricing:
            raise ValueError(f"Unknown model for {provider}: {model}")

        return provider_pricing[model_lower]

    @staticmethod
    def format_cost_usd(cost_micros: int) -> str:
        """
        Format micro-USD cost as human-readable USD string.

        Args:
            cost_micros: Cost in micro-USD

        Returns:
            Formatted string (e.g., "$0.0045")

        Example:
            >>> CostCalculator.format_cost_usd(450)
            "$0.000450"
        """
        cost_usd = cost_micros / 1_000_000
        return f"${cost_usd:.6f}"
