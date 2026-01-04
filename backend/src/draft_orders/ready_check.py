"""Ready-check logic for draft orders.

Validates whether a draft order is ready for approval by checking:
- Header completeness (customer_id, currency)
- Line validity (qty > 0, uom present, internal_sku present)
- Absence of blocking validation errors

SSOT Reference: §6.3 (Ready-Check Logic)
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from uuid import UUID


def run_ready_check(draft_order, lines: List, validation_issues: List) -> Dict[str, Any]:
    """Execute ready-check validation on a draft order.

    Args:
        draft_order: DraftOrder model instance
        lines: List of DraftOrderLine instances
        validation_issues: List of ValidationIssue instances (ERROR severity, OPEN status)

    Returns:
        Ready-check result dict with:
            - is_ready (bool): Whether draft passes all checks
            - blocking_reasons (List[str]): List of reasons why not ready
            - passed_at (str|None): ISO timestamp when ready-check passed

    SSOT Reference: §6.3 (FR-005), FR-012, FR-013
    """
    blocking_reasons = []

    # Header checks (§6.3 FR-005)
    if not draft_order.customer_id:
        blocking_reasons.append("customer_id missing")

    if not draft_order.currency:
        blocking_reasons.append("currency missing")

    # Line checks (§6.3 FR-005)
    if not lines:
        blocking_reasons.append("No order lines")
    else:
        for line in lines:
            # Quantity validation
            if not line.qty or line.qty <= 0:
                blocking_reasons.append(f"Line {line.line_no}: invalid qty")

            # UoM validation
            if not line.uom:
                blocking_reasons.append(f"Line {line.line_no}: missing uom")

            # Internal SKU validation (MVP strict per §6.3)
            if not line.internal_sku:
                blocking_reasons.append(f"Line {line.line_no}: missing internal_sku")

    # Validation issue checks (§6.3 FR-005)
    # Check for ERROR severity issues that are OPEN
    error_issues = [
        issue for issue in validation_issues
        if issue.severity == "ERROR" and issue.status == "OPEN"
    ]
    if error_issues:
        # Group by type to avoid cluttering the UI
        issue_types = set(issue.type for issue in error_issues)
        for issue_type in issue_types:
            count = sum(1 for issue in error_issues if issue.type == issue_type)
            if count == 1:
                blocking_reasons.append(f"Issue: {issue_type}")
            else:
                blocking_reasons.append(f"{count} issues: {issue_type}")

    # Determine ready status
    is_ready = len(blocking_reasons) == 0
    passed_at = datetime.utcnow().isoformat() if is_ready else None

    return {
        "is_ready": is_ready,
        "blocking_reasons": blocking_reasons,
        "passed_at": passed_at,
    }


def determine_status_from_ready_check(
    current_status: str,
    ready_check_result: Dict[str, Any]
) -> Optional[str]:
    """Determine new status based on ready-check result.

    Implements status transition logic per §6.3 (FR-013):
    - If was EXTRACTED and now ready → READY
    - If was EXTRACTED and not ready → NEEDS_REVIEW
    - If was NEEDS_REVIEW and now ready → READY
    - If was READY and no longer ready → NEEDS_REVIEW

    Args:
        current_status: Current DraftOrderStatus value
        ready_check_result: Result from run_ready_check()

    Returns:
        New status string, or None if no status change needed

    SSOT Reference: §6.3 (FR-013)
    """
    is_ready = ready_check_result.get("is_ready", False)

    # EXTRACTED → READY or NEEDS_REVIEW
    if current_status == "EXTRACTED":
        return "READY" if is_ready else "NEEDS_REVIEW"

    # NEEDS_REVIEW → READY (when issues resolved)
    if current_status == "NEEDS_REVIEW" and is_ready:
        return "READY"

    # READY → NEEDS_REVIEW (when new blocking issue appears)
    if current_status == "READY" and not is_ready:
        return "NEEDS_REVIEW"

    # No status change needed
    return None


def should_run_ready_check(event: str) -> bool:
    """Determine if ready-check should run based on event type.

    Ready-check is triggered by (§6.3 FR-012):
    - Extraction completion
    - Line add/edit/delete
    - Customer selection
    - Issue resolution/override
    - Matching update

    Args:
        event: Event type string

    Returns:
        True if ready-check should run
    """
    trigger_events = {
        "extraction_complete",
        "line_added",
        "line_updated",
        "line_deleted",
        "customer_selected",
        "issue_resolved",
        "issue_overridden",
        "matching_updated",
    }
    return event in trigger_events
