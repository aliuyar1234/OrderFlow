"""Hallucination guards for LLM extraction (SSOT §7.5.4)."""

import re
from typing import Any


def normalize_text(text: str) -> str:
    """Normalize text for anchor checking.

    Converts to uppercase and collapses whitespace.
    """
    return re.sub(r'\s+', ' ', text.upper()).strip()


def anchor_check(line: dict[str, Any], source_text: str) -> bool:
    """Check if line data appears in source text (hallucination detection).

    Per SSOT §7.5.4: At least one of the following must appear in source:
    - customer_sku_raw (exact match, case-insensitive)
    - 8+ character token from product_description
    - qty as string

    Args:
        line: Order line dict
        source_text: Source PDF text

    Returns:
        True if line passes anchor check, False if likely hallucinated
    """
    source_norm = normalize_text(source_text)

    # Check 1: customer_sku_raw
    if line.get("customer_sku_raw"):
        sku_norm = normalize_text(line["customer_sku_raw"])
        # Also check without spaces/hyphens for fuzzy match
        sku_compact = sku_norm.replace(" ", "").replace("-", "")
        source_compact = source_norm.replace(" ", "").replace("-", "")

        if sku_norm in source_norm or sku_compact in source_compact:
            return True

    # Check 2: product_description (8+ char tokens)
    if line.get("product_description"):
        desc = line["product_description"]
        tokens = desc.split()
        for token in tokens:
            if len(token) >= 8:
                token_norm = normalize_text(token)
                if token_norm in source_norm:
                    return True

    # Check 3: qty as string
    if line.get("qty") is not None:
        qty_str = str(line["qty"])
        # Remove decimal point for checking (e.g., "10.0" -> "10")
        qty_int = qty_str.split(".")[0]
        if qty_int in source_text or qty_str in source_text:
            return True

    return False


def range_check_qty(qty: float | None, max_qty: int = 1_000_000) -> tuple[float | None, str | None]:
    """Validate quantity is within reasonable range.

    Per SSOT §7.5.4: qty must be 0 < qty <= max_qty.

    Args:
        qty: Quantity value
        max_qty: Maximum allowed quantity

    Returns:
        Tuple of (validated_qty, warning_message)
        If invalid, qty is set to None with warning.
    """
    if qty is None:
        return qty, None

    if qty <= 0:
        return None, f"Quantity {qty} is <= 0 (invalid)"

    if qty > max_qty:
        return None, f"Quantity {qty} exceeds maximum {max_qty} (suspicious)"

    return qty, None


def lines_count_check(
    lines_count: int,
    page_count: int | None,
    max_lines_per_page: int = 100
) -> tuple[bool, str | None]:
    """Check if line count is suspicious given page count.

    Per SSOT §7.5.4: If lines_count > 200 and page_count <= 2, suspicious.

    Args:
        lines_count: Number of extracted lines
        page_count: Number of PDF pages
        max_lines_per_page: Maximum expected lines per page

    Returns:
        Tuple of (is_suspicious, warning_message)
    """
    if page_count is None or page_count == 0:
        return False, None

    # Heuristic: >200 lines with <=2 pages is very suspicious
    if lines_count > 200 and page_count <= 2:
        return True, f"Suspicious: {lines_count} lines extracted from only {page_count} pages"

    # Additional check: extremely high lines per page
    lines_per_page = lines_count / page_count
    if lines_per_page > max_lines_per_page:
        return True, f"Suspicious: {lines_per_page:.0f} lines per page (max expected: {max_lines_per_page})"

    return False, None


def apply_hallucination_guards(
    extraction_output: dict[str, Any],
    source_text: str,
    page_count: int | None = None,
    max_qty: int = 1_000_000
) -> dict[str, Any]:
    """Apply all hallucination guards to extraction output.

    Modifies extraction_output in place:
    - Reduces line confidence for failed anchor checks
    - Sets qty to null for range violations
    - Reduces overall confidence for suspicious line counts
    - Adds warnings

    Args:
        extraction_output: Parsed extraction output dict
        source_text: Source PDF text
        page_count: Number of PDF pages
        max_qty: Maximum allowed quantity

    Returns:
        Modified extraction_output with guards applied
    """
    lines = extraction_output.get("lines", [])
    confidence = extraction_output.get("confidence", {})
    warnings = extraction_output.get("warnings", [])

    # Track anchor check failures
    anchor_failures = 0

    # Apply guards to each line
    for idx, line in enumerate(lines):
        # Anchor check
        if not anchor_check(line, source_text):
            anchor_failures += 1

            # Reduce line confidence by 50% (SSOT §7.5.4)
            line_conf = confidence.get("lines", [])[idx] if idx < len(confidence.get("lines", [])) else {}
            for field in ["customer_sku_raw", "qty", "uom", "unit_price"]:
                if field in line_conf:
                    line_conf[field] = line_conf[field] * 0.5

            warnings.append({
                "code": "ANCHOR_CHECK_FAILED",
                "message": f"Line {line.get('line_no', idx+1)}: Data not found in source (possible hallucination)"
            })

        # Range check for qty
        validated_qty, qty_warning = range_check_qty(line.get("qty"), max_qty)
        if qty_warning:
            line["qty"] = validated_qty
            warnings.append({
                "code": "QTY_RANGE_VIOLATION",
                "message": f"Line {line.get('line_no', idx+1)}: {qty_warning}"
            })

    # Lines count check
    if lines:
        is_suspicious, count_warning = lines_count_check(
            lines_count=len(lines),
            page_count=page_count
        )
        if is_suspicious:
            # Reduce overall confidence by 30% (SSOT §7.5.4)
            if "overall" in confidence:
                confidence["overall"] = confidence["overall"] * 0.7

            warnings.append({
                "code": "LINES_COUNT_SUSPICIOUS",
                "message": count_warning or "Line count is suspicious"
            })

    # If >30% of lines fail anchor check, reduce overall confidence (SSOT §7.5.4)
    if lines and anchor_failures / len(lines) > 0.3:
        if "overall" in confidence:
            confidence["overall"] = confidence["overall"] * 0.7

        warnings.append({
            "code": "HIGH_ANCHOR_FAILURE_RATE",
            "message": f"{anchor_failures}/{len(lines)} lines failed anchor check (>30%)"
        })

    extraction_output["confidence"] = confidence
    extraction_output["warnings"] = warnings

    return extraction_output
