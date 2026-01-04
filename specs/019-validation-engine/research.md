# Research: Validation Engine

**Feature**: Validation Engine
**Date**: 2025-12-27

## Key Decisions

### Decision 1: Discrete Rule Functions vs Rule Classes

**Selected**: Discrete functions with signature `validate_rule(draft, context) -> list[ValidationIssue]`

**Rationale**: Simpler than class hierarchies. Each rule is testable in isolation. Easy to add/remove rules. No shared state between rules.

### Decision 2: Auto-Resolution Strategy

**Selected**: On draft update, re-run rules and compare with existing OPEN issues. If rule passes, mark issue RESOLVED.

**Rationale**: Automatic cleanup prevents stale issues. Operator doesn't manually close issues after fixing data.

### Decision 3: Price Tier Selection Algorithm

**Selected**: `max(min_qty) WHERE min_qty <= line.qty`

**Rationale**: Standard quantity-break pricing. Highest tier that applies to the order quantity.

## Best Practices

### Rule Implementation Pattern

```python
def validate_product_exists(draft: DraftOrder, context: ValidationContext) -> list[ValidationIssue]:
    issues = []
    for line in draft.lines:
        product = context.product_repo.find_by_sku(line.internal_sku, draft.org_id)
        if not product:
            issues.append(ValidationIssue(
                type="UNKNOWN_PRODUCT",
                severity=ValidationIssueSeverity.ERROR,
                line_id=line.id,
                message=f"Product {line.internal_sku} not found"
            ))
    return issues
```

### Ready-Check Computation

```python
def compute_ready_check(issues: list[ValidationIssue]) -> ReadyCheckResult:
    error_issues = [i for i in issues if i.severity == ERROR and i.status == OPEN]
    return ReadyCheckResult(
        is_ready=len(error_issues) == 0,
        blocking_reasons=[i.type for i in error_issues],
        checked_at=datetime.utcnow()
    )
```

## References

- SSOT §7.3: Validation Issue Types
- SSOT §7.4: Validation Rules
- SSOT §5.2.6-5.2.7: Issue severity/status
