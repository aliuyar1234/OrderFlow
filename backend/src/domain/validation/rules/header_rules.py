"""Header-level validation rules (SSOT §7.4)"""

from typing import Any

from domain.validation.models import (
    ValidationIssue,
    ValidationIssueType,
    ValidationIssueSeverity,
    ValidationContext
)


def validate_header_rules(draft_order: Any, context: ValidationContext) -> list[ValidationIssue]:
    """Validate header-level fields of a draft order.

    Rules implemented (SSOT §7.4):
    - MISSING_CUSTOMER: customer_id must be set
    - MISSING_CURRENCY: currency must be set

    Args:
        draft_order: Draft order with header fields (customer_id, currency, etc.)
        context: Validation context

    Returns:
        List of ValidationIssue objects for header violations
    """
    issues = []

    # Rule: customer_id must be set (SSOT §6.3)
    if not draft_order.customer_id:
        issues.append(ValidationIssue(
            type=ValidationIssueType.MISSING_CUSTOMER,
            severity=ValidationIssueSeverity.ERROR,
            message="Customer must be selected before order can be approved",
            draft_order_id=draft_order.id,
            org_id=context.org_id,
            details={"field": "customer_id"}
        ))

    # Rule: currency must be set (SSOT §6.3)
    if not draft_order.currency:
        issues.append(ValidationIssue(
            type=ValidationIssueType.MISSING_CURRENCY,
            severity=ValidationIssueSeverity.ERROR,
            message="Currency must be specified",
            draft_order_id=draft_order.id,
            org_id=context.org_id,
            details={"field": "currency"}
        ))

    return issues


def validate_currency_consistency(draft_order: Any, context: ValidationContext) -> list[ValidationIssue]:
    """Validate that all lines use the same currency as header.

    This is a consistency check mentioned in spec.md US3.

    Args:
        draft_order: Draft order with lines
        context: Validation context

    Returns:
        List of ValidationIssue objects for currency inconsistencies
    """
    issues = []

    if not draft_order.currency:
        # Already flagged by MISSING_CURRENCY
        return issues

    header_currency = draft_order.currency

    for line in draft_order.lines:
        if line.currency and line.currency != header_currency:
            issues.append(ValidationIssue(
                type=ValidationIssueType.LLM_OUTPUT_INVALID,  # Use generic type
                severity=ValidationIssueSeverity.WARNING,
                message=f"Line {line.line_no} currency '{line.currency}' differs from header '{header_currency}'",
                draft_order_id=draft_order.id,
                draft_order_line_id=line.id,
                line_no=line.line_no,
                org_id=context.org_id,
                details={
                    "field": "currency",
                    "line_currency": line.currency,
                    "header_currency": header_currency
                }
            ))

    return issues
