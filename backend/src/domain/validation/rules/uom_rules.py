"""UoM compatibility validation rules (SSOT §7.4)"""

from typing import Any

from ..models import (
    ValidationIssue,
    ValidationIssueType,
    ValidationIssueSeverity,
    ValidationContext
)


def validate_uom_rules(draft_order: Any, context: ValidationContext) -> list[ValidationIssue]:
    """Validate UoM compatibility with product base UoM.

    Rule (SSOT §7.4):
    - If line.uom != product.base_uom:
      - Allowed only if product.uom_conversions_json has an entry for line.uom
      - Otherwise: UOM_INCOMPATIBLE error

    Args:
        draft_order: Draft order with lines
        context: Validation context with products_by_sku

    Returns:
        List of ValidationIssue objects for UoM incompatibilities
    """
    issues = []

    for line in draft_order.lines:
        # Skip if no internal_sku or uom (already flagged by line_rules)
        if not line.internal_sku or not line.uom:
            continue

        # Get product
        product = context.products_by_sku.get(line.internal_sku)
        if not product:
            # Already flagged by UNKNOWN_PRODUCT
            continue

        # Check UoM compatibility
        if line.uom != product.base_uom:
            # Check if conversion exists
            uom_conversions = product.uom_conversions_json or {}

            if line.uom not in uom_conversions:
                issues.append(ValidationIssue(
                    type=ValidationIssueType.UOM_INCOMPATIBLE,
                    severity=ValidationIssueSeverity.ERROR,
                    message=(
                        f"Line {line.line_no}: UoM '{line.uom}' is incompatible with "
                        f"product base UoM '{product.base_uom}' (no conversion defined)"
                    ),
                    draft_order_id=draft_order.id,
                    draft_order_line_id=line.id,
                    line_no=line.line_no,
                    org_id=context.org_id,
                    details={
                        "line_uom": line.uom,
                        "product_base_uom": product.base_uom,
                        "internal_sku": line.internal_sku,
                        "available_conversions": list(uom_conversions.keys())
                    }
                ))

    return issues
