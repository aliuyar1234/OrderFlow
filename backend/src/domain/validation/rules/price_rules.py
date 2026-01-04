"""Price validation rules with tier selection (SSOT §7.4, spec.md US2)"""

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from domain.validation.models import (
    ValidationIssue,
    ValidationIssueType,
    ValidationIssueSeverity,
    ValidationContext
)


def validate_price_rules(draft_order: Any, context: ValidationContext) -> list[ValidationIssue]:
    """Validate prices against customer price list with tier selection.

    Rules (SSOT §7.4, spec.md US2):
    - MISSING_PRICE: warning if unit_price is missing (MVP: warning, not error)
    - PRICE_MISMATCH: warning/error if price deviation exceeds tolerance

    Price tier matching algorithm (spec.md §Implementation Notes):
    1. Filter customer_prices by customer_id, internal_sku, currency
    2. Filter by date range: valid_from <= today <= valid_to_or_null
    3. Find max(min_qty) where min_qty <= line.qty → applicable tier
    4. Compare line.unit_price vs tier.unit_price using tolerance

    Args:
        draft_order: Draft order with lines and customer_id
        context: Validation context with customer_prices, org_settings

    Returns:
        List of ValidationIssue objects for price violations
    """
    issues = []

    # Can't validate prices without customer
    if not draft_order.customer_id:
        return issues

    # Get price tolerance from org settings
    price_tolerance_percent = _get_price_tolerance(context.org_settings)

    for line in draft_order.lines:
        # Skip if no internal_sku (already flagged)
        if not line.internal_sku:
            continue

        # Rule: missing price is a warning (SSOT §7.4)
        if line.unit_price is None:
            issues.append(ValidationIssue(
                type=ValidationIssueType.MISSING_PRICE,
                severity=ValidationIssueSeverity.WARNING,
                message=f"Line {line.line_no}: Unit price not specified",
                draft_order_id=draft_order.id,
                draft_order_line_id=line.id,
                line_no=line.line_no,
                org_id=context.org_id,
                details={
                    "field": "unit_price",
                    "internal_sku": line.internal_sku
                }
            ))
            continue

        # Find applicable customer price tier
        expected_price = _find_customer_price_tier(
            customer_id=draft_order.customer_id,
            internal_sku=line.internal_sku,
            currency=line.currency or draft_order.currency,
            uom=line.uom,
            qty=line.qty,
            customer_prices=context.customer_prices
        )

        if expected_price is None:
            # No customer price available - can't validate
            continue

        # Calculate deviation
        try:
            line_price = Decimal(str(line.unit_price))
            expected = Decimal(str(expected_price))

            if expected == 0:
                # Avoid division by zero
                continue

            deviation_percent = abs((line_price - expected) / expected) * 100

            if deviation_percent > price_tolerance_percent:
                # Determine severity based on org settings
                severity = _get_price_mismatch_severity(context.org_settings)

                issues.append(ValidationIssue(
                    type=ValidationIssueType.PRICE_MISMATCH,
                    severity=severity,
                    message=(
                        f"Line {line.line_no}: Price {line.currency or draft_order.currency} {line_price:.2f} "
                        f"deviates {deviation_percent:.1f}% from expected {expected:.2f} "
                        f"(tolerance: {price_tolerance_percent:.1f}%)"
                    ),
                    draft_order_id=draft_order.id,
                    draft_order_line_id=line.id,
                    line_no=line.line_no,
                    org_id=context.org_id,
                    details={
                        "field": "unit_price",
                        "actual_price": str(line_price),
                        "expected_price": str(expected),
                        "deviation_percent": float(deviation_percent),
                        "tolerance_percent": float(price_tolerance_percent),
                        "currency": line.currency or draft_order.currency,
                        "internal_sku": line.internal_sku
                    }
                ))
        except (ValueError, TypeError, ArithmeticError):
            # Invalid price format - skip validation
            continue

    return issues


def _find_customer_price_tier(
    customer_id: Any,
    internal_sku: str,
    currency: Optional[str],
    uom: Optional[str],
    qty: Optional[Any],
    customer_prices: list[Any]
) -> Optional[Decimal]:
    """Find the applicable customer price tier for a line.

    Algorithm (spec.md):
    1. Filter by customer_id, internal_sku, currency, uom
    2. Filter by date validity
    3. Select tier with max(min_qty) where min_qty <= line.qty
    4. Return tier.unit_price

    Args:
        customer_id: Customer UUID
        internal_sku: Product internal SKU
        currency: Line or header currency
        uom: Line UoM
        qty: Line quantity
        customer_prices: List of customer price records

    Returns:
        Decimal unit_price of applicable tier, or None if not found
    """
    if not currency or not uom or qty is None:
        return None

    try:
        line_qty = Decimal(str(qty))
    except (ValueError, TypeError):
        return None

    today = date.today()
    applicable_tiers = []

    for price in customer_prices:
        # Filter by customer, SKU, currency, UoM
        if (price.customer_id != customer_id or
            price.internal_sku != internal_sku or
            price.currency != currency or
            price.uom != uom):
            continue

        # Filter by date validity
        if price.valid_from and price.valid_from > today:
            continue
        if price.valid_to and price.valid_to < today:
            continue

        # Filter by quantity tier
        min_qty = Decimal(str(price.min_qty or 1))
        if min_qty <= line_qty:
            applicable_tiers.append((min_qty, price.unit_price))

    if not applicable_tiers:
        return None

    # Select tier with highest min_qty (best match for this quantity)
    applicable_tiers.sort(key=lambda x: x[0], reverse=True)
    return Decimal(str(applicable_tiers[0][1]))


def _get_price_tolerance(org_settings: dict[str, Any]) -> Decimal:
    """Get price tolerance percentage from org settings.

    Default: 5% (SSOT mentions this in spec.md US2)

    Args:
        org_settings: Organization settings JSONB

    Returns:
        Price tolerance as Decimal percentage (e.g., 5.0 for 5%)
    """
    default_tolerance = Decimal("5.0")

    try:
        tolerance = org_settings.get("price_tolerance_percent")
        if tolerance is not None:
            return Decimal(str(tolerance))
    except (ValueError, TypeError):
        pass

    return default_tolerance


def _get_price_mismatch_severity(org_settings: dict[str, Any]) -> ValidationIssueSeverity:
    """Get severity for price mismatch from org settings.

    Default: WARNING (SSOT §7.3 says WARNING/ERROR depending on org setting)

    Args:
        org_settings: Organization settings JSONB

    Returns:
        ValidationIssueSeverity
    """
    severity_str = org_settings.get("price_mismatch_severity", "WARNING")

    if severity_str == "ERROR":
        return ValidationIssueSeverity.ERROR
    else:
        return ValidationIssueSeverity.WARNING
