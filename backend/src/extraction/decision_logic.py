"""Decision logic for extraction method selection (SSOT §7.2)."""

import logging
from typing import Literal


logger = logging.getLogger(__name__)


ExtractionMethod = Literal["rule_based", "llm_text", "llm_vision"]


def decide_extraction_method(
    text_coverage_ratio: float | None,
    page_count: int,
    rule_based_confidence: float | None = None,
    llm_trigger_confidence: float = 0.60,
    scan_threshold: float = 0.15,
    max_pages_for_llm: int = 20,
) -> ExtractionMethod:
    """Decide which extraction method to use for a PDF.

    Per SSOT §7.2 & §7.5.7:
    1. If text_coverage_ratio < scan_threshold → vision LLM
    2. Else try rule-based first
    3. If rule-based confidence < llm_trigger_confidence → text LLM

    Args:
        text_coverage_ratio: Ratio of text content in PDF (0-1)
        page_count: Number of pages
        rule_based_confidence: Confidence from rule-based extraction (if already run)
        llm_trigger_confidence: Threshold to trigger LLM fallback
        scan_threshold: Threshold to consider PDF as scanned
        max_pages_for_llm: Maximum pages allowed for LLM

    Returns:
        Extraction method to use
    """
    # Check page count limit
    if page_count > max_pages_for_llm:
        logger.warning(
            f"PDF has {page_count} pages, exceeding LLM limit of {max_pages_for_llm}. "
            "Falling back to rule-based only."
        )
        return "rule_based"

    # Decision 1: Scanned PDF → vision LLM
    if text_coverage_ratio is not None and text_coverage_ratio < scan_threshold:
        logger.info(
            f"Text coverage {text_coverage_ratio:.2f} < {scan_threshold}, "
            "using vision LLM for scanned PDF"
        )
        return "llm_vision"

    # Decision 2: Rule-based confidence low → text LLM
    if rule_based_confidence is not None and rule_based_confidence < llm_trigger_confidence:
        logger.info(
            f"Rule-based confidence {rule_based_confidence:.2f} < {llm_trigger_confidence}, "
            "falling back to text LLM"
        )
        return "llm_text"

    # Default: rule-based
    return "rule_based"


def should_trigger_llm_fallback(
    rule_based_confidence: float,
    lines_count: int,
    llm_trigger_confidence: float = 0.60,
) -> bool:
    """Check if LLM fallback should be triggered after rule-based extraction.

    Per SSOT §7.5.5:
    - Trigger if confidence < 0.60 OR lines_count == 0

    Args:
        rule_based_confidence: Confidence from rule-based extraction
        lines_count: Number of lines extracted
        llm_trigger_confidence: Threshold to trigger LLM

    Returns:
        True if LLM fallback should be triggered
    """
    if lines_count == 0:
        logger.info("Rule-based extraction returned 0 lines, triggering LLM fallback")
        return True

    if rule_based_confidence < llm_trigger_confidence:
        logger.info(
            f"Rule-based confidence {rule_based_confidence:.2f} < {llm_trigger_confidence}, "
            "triggering LLM fallback"
        )
        return True

    return False


def check_budget_gate(
    org_id: str,
    daily_budget_micros: int,
    used_micros: int,
    estimated_cost_micros: int,
) -> tuple[bool, str | None]:
    """Check if LLM call is allowed based on budget.

    Args:
        org_id: Organization ID
        daily_budget_micros: Daily budget limit (0 = unlimited)
        used_micros: Already used budget today
        estimated_cost_micros: Estimated cost of this call

    Returns:
        Tuple of (is_allowed, reason_if_blocked)
    """
    if daily_budget_micros == 0:
        # Unlimited budget
        return True, None

    if used_micros + estimated_cost_micros > daily_budget_micros:
        remaining = daily_budget_micros - used_micros
        return False, (
            f"Daily budget exceeded: used {used_micros}, "
            f"remaining {remaining}, "
            f"estimated cost {estimated_cost_micros}"
        )

    return True, None


def estimate_llm_cost(
    method: ExtractionMethod,
    text_length: int = 0,
    page_count: int = 0,
) -> int:
    """Estimate LLM call cost in micros.

    Rough estimates based on average token counts:
    - Text LLM: ~0.75 tokens per char + prompt overhead
    - Vision LLM: ~1500 tokens per page + prompt overhead

    Args:
        method: Extraction method
        text_length: Length of text (for text LLM)
        page_count: Number of pages (for vision LLM)

    Returns:
        Estimated cost in micros
    """
    if method == "llm_text":
        # Estimate tokens: ~0.75 per char + 500 prompt tokens
        estimated_tokens_in = int(text_length * 0.75) + 500
        estimated_tokens_out = 2000  # Typical output

        # gpt-4o-mini pricing: $0.15/1M in, $0.60/1M out
        cost_in = (estimated_tokens_in / 1_000_000) * 0.15
        cost_out = (estimated_tokens_out / 1_000_000) * 0.60
        total_cost_usd = cost_in + cost_out

        return int(total_cost_usd * 1_000_000)

    elif method == "llm_vision":
        # Estimate: ~1500 tokens per page + prompt
        estimated_tokens_in = (page_count * 1500) + 500
        estimated_tokens_out = 2000

        # gpt-4o pricing: $2.50/1M in, $10.00/1M out
        cost_in = (estimated_tokens_in / 1_000_000) * 2.50
        cost_out = (estimated_tokens_out / 1_000_000) * 10.00
        total_cost_usd = cost_in + cost_out

        return int(total_cost_usd * 1_000_000)

    return 0
