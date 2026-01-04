"""ValidationEngine - orchestrates validation rules (SSOT §7.4)"""

from typing import Any
import logging

from .models import (
    ValidationIssue,
    ValidationIssueType,
    ValidationIssueSeverity,
    ValidationIssueStatus,
    ReadyCheckResult,
    ValidationContext
)
from .port import ValidatorPort
from .rules import (
    validate_header_rules,
    validate_line_rules,
    validate_price_rules,
    validate_uom_rules
)
from .rules.header_rules import validate_currency_consistency
from .rules.line_rules import validate_duplicate_lines


logger = logging.getLogger(__name__)


class ValidationEngine(ValidatorPort):
    """Concrete implementation of ValidatorPort.

    Orchestrates all validation rules and computes ready-check status.
    This is the main validation service used throughout the application.
    """

    def validate(self, draft_order: Any, context: ValidationContext) -> list[ValidationIssue]:
        """Run all validation rules on a draft order.

        This method executes all validation rule functions in sequence,
        aggregating their results. If a rule raises an exception, it is
        logged and skipped (fail-open pattern as described in spec.md).

        Args:
            draft_order: Draft order domain/DB model to validate
            context: Validation context with products, prices, settings

        Returns:
            List of all ValidationIssue objects found
        """
        all_issues = []

        # Define all rule functions to execute
        rule_functions = [
            ("header_rules", validate_header_rules),
            ("line_rules", validate_line_rules),
            ("uom_rules", validate_uom_rules),
            ("price_rules", validate_price_rules),
            ("currency_consistency", validate_currency_consistency),
            ("duplicate_lines", validate_duplicate_lines),
        ]

        for rule_name, rule_func in rule_functions:
            try:
                issues = rule_func(draft_order, context)
                all_issues.extend(issues)
                logger.debug(
                    f"Validation rule '{rule_name}' found {len(issues)} issues for draft {draft_order.id}"
                )
            except Exception as e:
                logger.error(
                    f"Validation rule '{rule_name}' failed for draft {draft_order.id}: {e}",
                    exc_info=True
                )
                # Add system warning issue (spec.md: fail-open pattern)
                all_issues.append(ValidationIssue(
                    type=ValidationIssueType.LLM_OUTPUT_INVALID,  # Generic error type
                    severity=ValidationIssueSeverity.WARNING,
                    message=f"Validation rule '{rule_name}' failed to execute",
                    draft_order_id=draft_order.id,
                    org_id=context.org_id,
                    details={
                        "rule_name": rule_name,
                        "error": str(e)
                    }
                ))

        logger.info(
            f"Validation completed for draft {draft_order.id}: {len(all_issues)} total issues"
        )

        return all_issues

    def compute_ready_check(self, draft_order: Any, issues: list[ValidationIssue]) -> ReadyCheckResult:
        """Compute ready-check status from validation issues.

        Logic (SSOT §6.3):
        - is_ready = True if NO ERROR-severity issues with status OPEN
        - blocking_reasons = list of issue types that block READY
        - checked_at = current timestamp

        Args:
            draft_order: Draft order being checked
            issues: Current validation issues (should be OPEN issues only)

        Returns:
            ReadyCheckResult with is_ready boolean and blocking reasons
        """
        # Filter for ERROR-severity OPEN issues
        blocking_issues = [
            issue for issue in issues
            if issue.severity == ValidationIssueSeverity.ERROR
            and issue.status == ValidationIssueStatus.OPEN
        ]

        is_ready = len(blocking_issues) == 0
        blocking_reasons = [issue.type.value for issue in blocking_issues]

        result = ReadyCheckResult(
            is_ready=is_ready,
            blocking_reasons=blocking_reasons
        )

        logger.info(
            f"Ready-check for draft {draft_order.id}: is_ready={is_ready}, "
            f"blocking={len(blocking_issues)}"
        )

        return result
