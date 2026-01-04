"""Line-level validation rules (SSOT §7.4)"""

from decimal import Decimal
from typing import Any

from ..models import (
    ValidationIssue,
    ValidationIssueType,
    ValidationIssueSeverity,
    ValidationContext
)


def validate_line_rules(draft_order: Any, context: ValidationContext) -> list[ValidationIssue]:
    """Validate line-level fields of a draft order.

    Rules implemented (SSOT §7.4):
    - MISSING_SKU: internal_sku must be set
    - UNKNOWN_PRODUCT: internal_sku must exist in product catalog
    - MISSING_QTY: qty must be set
    - INVALID_QTY: qty must be > 0
    - MISSING_UOM: uom must be set
    - UNKNOWN_UOM: uom must be in canonical UoM list

    Args:
        draft_order: Draft order with lines
        context: Validation context with products_by_sku

    Returns:
        List of ValidationIssue objects for line violations
    """
    issues = []

    for line in draft_order.lines:
        # Rule: internal_sku must be set (SSOT §6.3)
        if not line.internal_sku:
            issues.append(ValidationIssue(
                type=ValidationIssueType.MISSING_SKU,
                severity=ValidationIssueSeverity.ERROR,
                message=f"Line {line.line_no}: Product SKU mapping is required",
                draft_order_id=draft_order.id,
                draft_order_line_id=line.id,
                line_no=line.line_no,
                org_id=context.org_id,
                details={
                    "field": "internal_sku",
                    "customer_sku": line.customer_sku_norm or line.customer_sku_raw
                }
            ))
        else:
            # Rule: internal_sku must exist in product catalog (SSOT §7.4)
            product = context.products_by_sku.get(line.internal_sku)
            if not product:
                issues.append(ValidationIssue(
                    type=ValidationIssueType.UNKNOWN_PRODUCT,
                    severity=ValidationIssueSeverity.ERROR,
                    message=f"Line {line.line_no}: Product '{line.internal_sku}' not found in catalog",
                    draft_order_id=draft_order.id,
                    draft_order_line_id=line.id,
                    line_no=line.line_no,
                    org_id=context.org_id,
                    details={
                        "field": "internal_sku",
                        "internal_sku": line.internal_sku
                    }
                ))
            elif hasattr(product, 'active') and not product.active:
                # Product exists but is inactive
                issues.append(ValidationIssue(
                    type=ValidationIssueType.UNKNOWN_PRODUCT,
                    severity=ValidationIssueSeverity.ERROR,
                    message=f"Line {line.line_no}: Product '{line.internal_sku}' is inactive",
                    draft_order_id=draft_order.id,
                    draft_order_line_id=line.id,
                    line_no=line.line_no,
                    org_id=context.org_id,
                    details={
                        "field": "internal_sku",
                        "internal_sku": line.internal_sku,
                        "reason": "inactive"
                    }
                ))

        # Rule: qty must be set (SSOT §6.3)
        if line.qty is None:
            issues.append(ValidationIssue(
                type=ValidationIssueType.MISSING_QTY,
                severity=ValidationIssueSeverity.ERROR,
                message=f"Line {line.line_no}: Quantity is required",
                draft_order_id=draft_order.id,
                draft_order_line_id=line.id,
                line_no=line.line_no,
                org_id=context.org_id,
                details={"field": "qty"}
            ))
        else:
            # Rule: qty must be > 0 (SSOT §7.4)
            try:
                qty_decimal = Decimal(str(line.qty))
                if qty_decimal <= 0:
                    issues.append(ValidationIssue(
                        type=ValidationIssueType.INVALID_QTY,
                        severity=ValidationIssueSeverity.ERROR,
                        message=f"Line {line.line_no}: Quantity must be greater than 0 (got {line.qty})",
                        draft_order_id=draft_order.id,
                        draft_order_line_id=line.id,
                        line_no=line.line_no,
                        org_id=context.org_id,
                        details={
                            "field": "qty",
                            "qty": str(line.qty)
                        }
                    ))
            except (ValueError, TypeError):
                issues.append(ValidationIssue(
                    type=ValidationIssueType.INVALID_QTY,
                    severity=ValidationIssueSeverity.ERROR,
                    message=f"Line {line.line_no}: Invalid quantity format '{line.qty}'",
                    draft_order_id=draft_order.id,
                    draft_order_line_id=line.id,
                    line_no=line.line_no,
                    org_id=context.org_id,
                    details={
                        "field": "qty",
                        "qty": str(line.qty)
                    }
                ))

        # Rule: uom must be set (SSOT §6.3)
        if not line.uom:
            issues.append(ValidationIssue(
                type=ValidationIssueType.MISSING_UOM,
                severity=ValidationIssueSeverity.ERROR,
                message=f"Line {line.line_no}: Unit of measure is required",
                draft_order_id=draft_order.id,
                draft_order_line_id=line.id,
                line_no=line.line_no,
                org_id=context.org_id,
                details={"field": "uom"}
            ))
        else:
            # Rule: uom must be in canonical UoM list (SSOT §7.4)
            if line.uom not in context.canonical_uoms:
                issues.append(ValidationIssue(
                    type=ValidationIssueType.UNKNOWN_UOM,
                    severity=ValidationIssueSeverity.ERROR,
                    message=f"Line {line.line_no}: Unknown unit of measure '{line.uom}'",
                    draft_order_id=draft_order.id,
                    draft_order_line_id=line.id,
                    line_no=line.line_no,
                    org_id=context.org_id,
                    details={
                        "field": "uom",
                        "uom": line.uom,
                        "canonical_uoms": sorted(list(context.canonical_uoms))
                    }
                ))

    return issues


def validate_duplicate_lines(draft_order: Any, context: ValidationContext) -> list[ValidationIssue]:
    """Check for duplicate lines (same SKU + qty + uom).

    This is listed in SSOT §7.3 as DUPLICATE_LINE warning.

    Args:
        draft_order: Draft order with lines
        context: Validation context

    Returns:
        List of ValidationIssue objects for duplicates
    """
    issues = []
    seen_keys = {}

    for line in draft_order.lines:
        if not line.internal_sku:
            continue

        # Create key from SKU + qty + uom
        key = (line.internal_sku, str(line.qty), line.uom)

        if key in seen_keys:
            first_line_no = seen_keys[key]
            issues.append(ValidationIssue(
                type=ValidationIssueType.DUPLICATE_LINE,
                severity=ValidationIssueSeverity.WARNING,
                message=f"Line {line.line_no}: Duplicate of line {first_line_no} (same SKU, qty, UoM)",
                draft_order_id=draft_order.id,
                draft_order_line_id=line.id,
                line_no=line.line_no,
                org_id=context.org_id,
                details={
                    "internal_sku": line.internal_sku,
                    "qty": str(line.qty),
                    "uom": line.uom,
                    "duplicate_of_line": first_line_no
                }
            ))
        else:
            seen_keys[key] = line.line_no

    return issues
