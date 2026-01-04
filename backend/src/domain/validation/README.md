# Validation Engine

The Validation Engine is the gatekeeper for order quality in OrderFlow. It implements 14+ deterministic business rules that validate draft orders against catalog data, business constraints, and customer prices.

## Overview

Per SSOT §7.3 and §7.4, the validation engine:

1. **Validates** draft orders against business rules
2. **Creates** validation_issue records for violations
3. **Computes** ready_check_json to determine if draft can be approved
4. **Auto-resolves** issues when underlying problems are fixed
5. **Blocks** READY status when ERROR-level issues exist

## Architecture

```
┌─────────────────────────────────────┐
│ ValidatorPort (Interface)           │
│ - validate(draft_order) -> issues   │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ ValidationEngine (Service)          │
│ - Orchestrates rule execution       │
│ - Aggregates issues                 │
│ - Computes ready_check_json         │
└──────────────┬──────────────────────┘
               │
       ┌───────┴─────────┬──────────────┬──────────────┐
       ▼                 ▼              ▼              ▼
  HeaderRules      LineRules     PriceRules      UoMRules
  - customer       - product     - tolerance     - conversions
  - currency       - qty/uom     - tier match    - compatibility
```

## Validation Rules

### Header Rules (SSOT §7.4)

| Rule | Type | Severity | Description |
|------|------|----------|-------------|
| MISSING_CUSTOMER | Header | ERROR | customer_id must be set |
| MISSING_CURRENCY | Header | ERROR | currency must be set |

### Line Rules (SSOT §7.4)

| Rule | Type | Severity | Description |
|------|------|----------|-------------|
| MISSING_SKU | Line | ERROR | internal_sku must be set |
| UNKNOWN_PRODUCT | Line | ERROR | internal_sku must exist in product catalog |
| MISSING_QTY | Line | ERROR | qty must be set |
| INVALID_QTY | Line | ERROR | qty must be > 0 |
| MISSING_UOM | Line | ERROR | uom must be set |
| UNKNOWN_UOM | Line | ERROR | uom must be in canonical UoM list (ST, M, KG, etc.) |
| DUPLICATE_LINE | Line | WARNING | Same SKU + qty + uom appears multiple times |

### UoM Compatibility Rules (SSOT §7.4)

| Rule | Type | Severity | Description |
|------|------|----------|-------------|
| UOM_INCOMPATIBLE | Line | ERROR | line.uom must match product.base_uom OR have conversion defined |

### Price Validation Rules (SSOT §7.4, spec.md US2)

| Rule | Type | Severity | Description |
|------|------|----------|-------------|
| MISSING_PRICE | Line | WARNING | unit_price not specified (MVP: warning, not error) |
| PRICE_MISMATCH | Line | WARNING/ERROR | Price deviation exceeds tolerance (org setting) |

#### Price Tier Selection Algorithm

For a line with qty=150 and customer prices with tiers:

1. Filter customer_prices by: customer_id, internal_sku, currency, uom
2. Filter by date validity: valid_from <= today <= valid_to (or NULL)
3. Find tiers where min_qty <= 150
4. Select tier with **max(min_qty)** (best match for this quantity)
5. Compare line.unit_price vs tier.unit_price using tolerance

Example:
```
Tiers: [1→€10, 100→€9, 500→€8]
Line qty=150 → Uses €9 tier (100 is max min_qty <= 150)
```

## Severity Levels (SSOT §5.2.6)

- **ERROR**: Blocks READY status. Must be resolved before approval.
- **WARNING**: Does not block READY. Informational feedback.
- **INFO**: Informational only.

## Issue Status (SSOT §5.2.7)

- **OPEN**: New issue, not yet addressed
- **ACKNOWLEDGED**: Operator has seen it, but not resolved (still blocks if ERROR)
- **RESOLVED**: Issue fixed (auto or manual)
- **OVERRIDDEN**: Operator decided to override (future)

## Ready-Check Logic (SSOT §6.3)

A draft order can only transition to READY status when:

1. **Header complete**: customer_id and currency are set
2. **All lines complete**: qty, uom, internal_sku are set
3. **No ERROR issues**: Zero OPEN ERROR-level validation issues

The ready_check_json structure:
```json
{
  "is_ready": true,
  "blocking_reasons": [],
  "checked_at": "2025-12-27T10:00:00Z"
}
```

When ERROR issues exist:
```json
{
  "is_ready": false,
  "blocking_reasons": ["MISSING_CUSTOMER", "UNKNOWN_PRODUCT"],
  "checked_at": "2025-12-27T10:00:00Z"
}
```

## Usage Example

```python
from domain.validation import ValidationEngine, ValidationContext
from infrastructure.repositories import ValidationRepository

# Setup
engine = ValidationEngine()
context = ValidationContext(
    org_id=org.id,
    products_by_sku={p.internal_sku: p for p in products},
    customer_prices=customer_prices,
    org_settings=org.settings_json
)

# Run validation
issues = engine.validate(draft_order, context)

# Persist issues
repo = ValidationRepository(db)
for issue in issues:
    repo.create_issue(issue)

# Compute ready-check
ready_check = engine.compute_ready_check(draft_order, issues)

# Update draft order
draft_order.ready_check_json = ready_check.to_dict()
db.commit()
```

## API Endpoints

### GET /validation/draft-orders/{id}/issues

Get all validation issues for a draft order.

Query parameters:
- `status`: Filter by status (OPEN, ACKNOWLEDGED, RESOLVED, OVERRIDDEN)

Response:
```json
{
  "issues": [
    {
      "id": "uuid",
      "type": "UNKNOWN_PRODUCT",
      "severity": "ERROR",
      "status": "OPEN",
      "message": "Product ABC-999 not found in catalog",
      "line_no": 3,
      "details": {"internal_sku": "ABC-999"}
    }
  ],
  "total": 1
}
```

### GET /validation/draft-orders/{id}/issues/summary

Get summary counts by severity and status.

Response:
```json
{
  "total": 5,
  "error_count": 2,
  "warning_count": 3,
  "info_count": 0,
  "open_count": 4,
  "acknowledged_count": 1,
  "resolved_count": 0
}
```

### PATCH /validation/issues/{id}/acknowledge

Acknowledge an issue (changes status to ACKNOWLEDGED).

**Important**: Acknowledgement does NOT resolve the issue or affect READY blocking (spec.md US3).

### POST /validation/issues/{id}/resolve

Manually resolve an issue (operator override).

## Auto-Resolution

When underlying problems are fixed, issues are automatically resolved:

```python
# Example: SKU is set → auto-resolve MISSING_SKU issues
repo.auto_resolve_by_type_and_line(
    org_id=org.id,
    draft_order_id=draft.id,
    issue_type=ValidationIssueType.MISSING_SKU,
    line_id=line.id
)
```

## Configuration

### Organization Settings

Price validation settings in `org.settings_json`:

```json
{
  "price_tolerance_percent": 5.0,
  "price_mismatch_severity": "WARNING"
}
```

- `price_tolerance_percent`: Allowable price deviation percentage (default: 5%)
- `price_mismatch_severity`: "WARNING" or "ERROR" (default: "WARNING")

## Testing

Unit tests for each rule:
```bash
pytest backend/tests/unit/validation/test_header_rules.py
pytest backend/tests/unit/validation/test_line_rules.py
pytest backend/tests/unit/validation/test_price_rules.py
pytest backend/tests/unit/validation/test_uom_rules.py
pytest backend/tests/unit/validation/test_ready_check.py
```

Integration tests:
```bash
pytest backend/tests/integration/validation/test_validation_flow.py
pytest backend/tests/integration/validation/test_auto_resolution.py
```

## Performance

- **Ready-Check target**: < 200ms for 100-line drafts
- **Validation target**: < 500ms for full validation run
- **Fail-open pattern**: If a rule fails, log error and continue (don't block entire validation)

## References

- SSOT §5.4.13: validation_issue table schema
- SSOT §5.2.6-5.2.7: Severity and status enums
- SSOT §7.3: Issue types list
- SSOT §7.4: Validation rules
- SSOT §6.3: Ready-check logic
- spec.md US1-US4: User stories and acceptance scenarios
- plan.md: Implementation architecture and patterns
