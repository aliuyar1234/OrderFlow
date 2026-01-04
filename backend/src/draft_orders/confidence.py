"""Confidence score calculation for draft orders.

Implements confidence scoring formulas per SSOT §7.8:
- Extraction confidence (§7.8.1)
- Customer confidence (§7.8.2)
- Matching confidence (§7.8.3)
- Overall confidence score (§7.8.4)

SSOT Reference: §7.8 (Confidence Scoring)
"""

from decimal import Decimal
from typing import Dict, List, Any, Optional


def calculate_extraction_confidence(extraction_output: Dict[str, Any]) -> Decimal:
    """Calculate extraction confidence from extraction result.

    Formula per §7.8.1:
    - Header score: weighted avg of field confidences
    - Line score: avg of weighted line scores
    - Sanity penalties applied (no lines, low text coverage, anchor check failures)
    - Final: (0.40 * header + 0.60 * line) * penalties

    Args:
        extraction_output: Extraction result dict with confidence and lines

    Returns:
        Decimal confidence score in range [0.0, 1.0]

    SSOT Reference: §7.8.1 (FR-006)
    """
    if not extraction_output:
        return Decimal("0.0")

    # Field weights for header confidence (§7.8.1)
    header_field_weights = {
        "external_order_number": 0.20,
        "order_date": 0.15,
        "currency": 0.20,
        "customer_hint": 0.25,
        "requested_delivery_date": 0.10,
        "ship_to": 0.10,
    }

    # Calculate header score
    header_conf = extraction_output.get("confidence", {}).get("order", {})
    header_scores = []
    for field, weight in header_field_weights.items():
        field_conf = header_conf.get(field, 0.0)
        header_scores.append(Decimal(str(field_conf)) * Decimal(str(weight)))

    header_score = sum(header_scores) / Decimal(str(sum(header_field_weights.values())))

    # Calculate line score (§7.8.1)
    line_weights = {
        "customer_sku_raw": 0.30,
        "qty": 0.30,
        "uom": 0.20,
        "unit_price": 0.20,
    }

    lines_conf = extraction_output.get("confidence", {}).get("lines", [])
    if not lines_conf:
        line_score = Decimal("0.0")
    else:
        line_scores = []
        for line_conf in lines_conf:
            line_field_scores = []
            for field, weight in line_weights.items():
                field_conf = line_conf.get(field, 0.0)
                line_field_scores.append(Decimal(str(field_conf)) * Decimal(str(weight)))
            line_avg = sum(line_field_scores) / Decimal(str(sum(line_weights.values())))
            line_scores.append(line_avg)
        line_score = sum(line_scores) / Decimal(str(len(line_scores)))

    # Apply sanity penalties (§7.8.1)
    penalty = Decimal("1.0")

    # Penalty: No lines extracted
    lines = extraction_output.get("lines", [])
    if len(lines) == 0:
        penalty *= Decimal("0.60")

    # Penalty: Low text coverage without vision
    text_coverage = extraction_output.get("text_coverage_ratio", 1.0)
    used_vision = extraction_output.get("used_vision", False)
    if Decimal(str(text_coverage)) < Decimal("0.15") and not used_vision:
        penalty *= Decimal("0.50")

    # Penalty: Anchor check failures (§7.8.1)
    anchor_fail_rate = extraction_output.get("anchor_check_fail_rate", 0.0)
    if Decimal(str(anchor_fail_rate)) > Decimal("0.30"):
        penalty *= Decimal("0.70")

    # Final score: (0.40 * header + 0.60 * line) * penalties
    base_score = (Decimal("0.40") * header_score) + (Decimal("0.60") * line_score)
    final_score = base_score * penalty

    # Clamp to [0.0, 1.0]
    return max(Decimal("0.0"), min(Decimal("1.0"), final_score))


def calculate_customer_confidence(
    customer_detection_result: Optional[Dict[str, Any]],
    is_user_selected: bool = False
) -> Decimal:
    """Calculate customer confidence from detection result.

    Formula per §7.8.2:
    - Auto-selected: score from customer detection
    - User-selected: max(detection_score, 0.90)
    - None: 0.0

    Args:
        customer_detection_result: Customer detection result with score
        is_user_selected: Whether customer was manually selected

    Returns:
        Decimal confidence score in range [0.0, 1.0]

    SSOT Reference: §7.8.2 (FR-007)
    """
    if not customer_detection_result:
        return Decimal("0.0")

    score = Decimal(str(customer_detection_result.get("score", 0.0)))

    # User selection boosts confidence to at least 0.90 (§7.8.2)
    if is_user_selected:
        return max(score, Decimal("0.90"))

    return score


def calculate_matching_confidence(lines: List[Dict[str, Any]]) -> Decimal:
    """Calculate matching confidence from line matching results.

    Formula per §7.8.3:
    - Average of matching_confidence for all lines
    - Lines with internal_sku=null count as 0

    Args:
        lines: List of draft order lines with matching_confidence

    Returns:
        Decimal confidence score in range [0.0, 1.0]

    SSOT Reference: §7.8.3 (FR-008)
    """
    if not lines:
        return Decimal("0.0")

    # Collect matching confidence for all lines
    # Lines without internal_sku count as 0 confidence
    confidences = []
    for line in lines:
        if line.get("internal_sku"):
            match_conf = line.get("matching_confidence", 0.0)
            confidences.append(Decimal(str(match_conf)))
        else:
            confidences.append(Decimal("0.0"))

    if not confidences:
        return Decimal("0.0")

    # Return average
    return sum(confidences) / Decimal(str(len(confidences)))


def calculate_overall_confidence(
    extraction_confidence: Decimal,
    customer_confidence: Decimal,
    matching_confidence: Decimal
) -> Decimal:
    """Calculate overall confidence score from component scores.

    Formula per §7.8.4:
    confidence_score = 0.45*extraction + 0.20*customer + 0.35*matching

    Args:
        extraction_confidence: Extraction quality score
        customer_confidence: Customer detection score
        matching_confidence: SKU matching average score

    Returns:
        Decimal overall confidence in range [0.0, 1.0]

    SSOT Reference: §7.8.4 (FR-009)
    """
    # Weighted combination (§7.8.4)
    score = (
        Decimal("0.45") * extraction_confidence +
        Decimal("0.20") * customer_confidence +
        Decimal("0.35") * matching_confidence
    )

    # Clamp to [0.0, 1.0]
    return max(Decimal("0.0"), min(Decimal("1.0"), score))


def normalize_customer_sku(raw_sku: str) -> str:
    """Normalize customer SKU per §6.1.

    Normalization rules:
    - Trim whitespace
    - Convert to uppercase
    - Replace tabs, newlines, multiple spaces with single space
    - Remove all except A-Z0-9

    Args:
        raw_sku: Raw customer SKU string

    Returns:
        Normalized SKU string

    SSOT Reference: §6.1 (Customer SKU Normalization), FR-011

    Examples:
        " AB-12 / 34 " → "AB1234"
        "test_sku-001" → "TESTSKU001"
    """
    if not raw_sku:
        return ""

    import re

    # Trim and uppercase
    norm = raw_sku.strip().upper()

    # Replace tabs, newlines, multiple spaces
    norm = re.sub(r'[\t\n ]+', ' ', norm)

    # Remove all except A-Z0-9
    norm = re.sub(r'[^A-Z0-9]', '', norm)

    return norm
