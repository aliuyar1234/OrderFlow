"""Confidence calculation for extraction quality.

Confidence score indicates extraction data completeness and quality.
Used to route drafts to automatic processing vs. manual review.

Formula (SSOT §7.8.1):
- header_confidence = extracted_fields / required_fields
- line_confidence = avg(fields_present / 3) for each line
- overall_confidence = 0.4 * header_confidence + 0.6 * line_confidence

SSOT Reference: §7.8 (Confidence Calculation)
"""

from typing import List, Tuple

from .canonical_output import CanonicalExtractionOutput, ExtractionLineItem, ExtractionOrderHeader


def calculate_header_confidence(header: ExtractionOrderHeader) -> float:
    """Calculate header completeness score.

    Required fields: order_number, order_date, currency
    Optional fields add bonus points but aren't required.

    Args:
        header: Extracted order header

    Returns:
        Score between 0.0 and 1.0
    """
    # Required fields for basic header
    required_fields = ['order_number', 'order_date', 'currency']

    fields_present = 0
    for field_name in required_fields:
        value = getattr(header, field_name, None)
        if value is not None:
            fields_present += 1

    if not required_fields:
        return 1.0

    return fields_present / len(required_fields)


def calculate_line_confidence(line: ExtractionLineItem) -> float:
    """Calculate single line completeness score.

    Essential fields: customer_sku, qty, description
    Each field contributes 1/3 to the score.

    Args:
        line: Single line item

    Returns:
        Score between 0.0 and 1.0
    """
    essential_fields = ['customer_sku', 'qty', 'description']

    fields_present = 0
    for field_name in essential_fields:
        value = getattr(line, field_name, None)
        if value is not None:
            fields_present += 1

    return fields_present / len(essential_fields)


def calculate_lines_confidence(lines: List[ExtractionLineItem]) -> float:
    """Calculate average line completeness across all lines.

    Args:
        lines: List of extracted line items

    Returns:
        Average score between 0.0 and 1.0, or 0.0 if no lines
    """
    if not lines:
        return 0.0

    line_scores = [calculate_line_confidence(line) for line in lines]
    return sum(line_scores) / len(line_scores)


def calculate_confidence(
    output: CanonicalExtractionOutput,
    header_weight: float = 0.4,
    lines_weight: float = 0.6
) -> Tuple[float, dict]:
    """Calculate overall extraction confidence score.

    Combines header and lines completeness into weighted average.
    Weights are configurable but default to 40% header, 60% lines.

    Args:
        output: Canonical extraction output
        header_weight: Weight for header score (default 0.4)
        lines_weight: Weight for lines score (default 0.6)

    Returns:
        Tuple of (overall_score, breakdown_dict)
        - overall_score: Weighted confidence between 0.0 and 1.0
        - breakdown_dict: Individual scores for debugging

    Example:
        >>> output = CanonicalExtractionOutput(...)
        >>> score, breakdown = calculate_confidence(output)
        >>> print(f"Confidence: {score:.3f}")
        >>> print(f"Header: {breakdown['header_score']:.3f}")
        >>> print(f"Lines: {breakdown['lines_score']:.3f}")
    """
    # Validate weights sum to 1.0
    if abs(header_weight + lines_weight - 1.0) > 0.01:
        raise ValueError(f"Weights must sum to 1.0, got {header_weight + lines_weight}")

    # Calculate component scores
    header_score = calculate_header_confidence(output.order)
    lines_score = calculate_lines_confidence(output.lines)

    # Weighted average
    overall_score = (header_weight * header_score) + (lines_weight * lines_score)

    # Round to 3 decimal places (SSOT requirement)
    overall_score = round(overall_score, 3)

    # Breakdown for debugging/logging
    breakdown = {
        'header_score': round(header_score, 3),
        'lines_score': round(lines_score, 3),
        'lines_count': len(output.lines),
        'header_weight': header_weight,
        'lines_weight': lines_weight,
    }

    return overall_score, breakdown
