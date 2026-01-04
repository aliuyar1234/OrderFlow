# Feature Specification: Validation Engine

**Feature Branch**: `019-validation-engine`
**Created**: 2025-12-27
**Status**: Draft
**Module**: validation
**SSOT References**: §5.4.13, §5.2.6-5.2.7, §7.3, §7.4, T-501, T-503, T-504

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automatic Validation on Draft Creation (Priority: P1)

When a draft order is created or modified, the system must automatically validate all header and line data against business rules, providing clear feedback on what prevents the order from being ready.

**Why this priority**: Validation is the foundation for the Ready-Check mechanism. Without automatic validation, operators cannot determine if a draft is complete and correct. This is the core blocker detection mechanism.

**Independent Test**: Can be fully tested by creating a draft order with missing/invalid data (e.g., unknown product SKU) and verifying that ERROR-level validation issues are created and block READY status.

**Acceptance Scenarios**:

1. **Given** a draft order line with `internal_sku="UNKNOWN-123"` (not in product catalog), **When** validation runs, **Then** a `UNKNOWN_PRODUCT` ERROR issue is created for that line
2. **Given** a draft order line with `qty=-5`, **When** validation runs, **Then** an `INVALID_QTY` ERROR issue is created
3. **Given** a draft order with no `customer_id`, **When** validation runs, **Then** a `MISSING_CUSTOMER` ERROR issue is created at header level
4. **Given** a draft order line with `uom="INVALID"` (not in canonical UoM list), **When** validation runs, **Then** an `UNKNOWN_UOM` ERROR issue is created
5. **Given** a draft order line where `line.uom != product.base_uom` and no UoM conversion exists, **When** validation runs, **Then** a `UOM_INCOMPATIBLE` ERROR issue is created

---

### User Story 2 - Price Validation with Tolerance (Priority: P2)

When customer prices are available and a draft line contains a unit price, the system should validate the price against expected customer prices, flagging mismatches beyond a configured tolerance threshold.

**Why this priority**: Price validation catches pricing errors early, preventing incorrect orders from being sent to ERP. However, it depends on customer price data being available, making it secondary to core validation.

**Independent Test**: Can be fully tested by importing customer prices, creating a draft with a price mismatch beyond tolerance, and verifying that a `PRICE_MISMATCH` WARNING/ERROR is created.

**Acceptance Scenarios**:

1. **Given** a customer price of €10.00 for SKU "ABC" with `price_tolerance_percent=5`, **When** a draft line has `unit_price=€10.30` (3% diff), **Then** no price issue is created
2. **Given** a customer price of €10.00 for SKU "ABC" with `price_tolerance_percent=5`, **When** a draft line has `unit_price=€12.00` (20% diff), **Then** a `PRICE_MISMATCH` WARNING issue is created
3. **Given** customer price tiers (min_qty: 1→€10, 100→€9, 500→€8), **When** a draft line has `qty=150` and `unit_price=€9.10`, **Then** the validator uses the €9 tier and validates within tolerance
4. **Given** a draft line with no `unit_price`, **When** validation runs, **Then** a `MISSING_PRICE` WARNING issue is created

---

### User Story 3 - Issue Management in UI (Priority: P2)

Operators need to see all validation issues in the Draft detail view, filter by severity, navigate to affected lines, and acknowledge issues (without resolving them).

**Why this priority**: Issue visibility and management are critical for operator workflow, but the underlying validation engine (P1) must exist first. Acknowledgement allows operators to document "known issues" without resolving them.

**Independent Test**: Can be fully tested by creating a draft with multiple validation issues, opening the UI, filtering by ERROR severity, clicking on an issue to focus the affected line, and marking it as ACKNOWLEDGED.

**Acceptance Scenarios**:

1. **Given** a draft with 3 ERROR issues and 2 WARNING issues, **When** operator filters by ERROR, **Then** only 3 issues are displayed
2. **Given** a validation issue for line 5, **When** operator clicks the issue badge, **Then** the UI scrolls/focuses to line 5
3. **Given** an OPEN validation issue, **When** operator clicks "Acknowledge", **Then** issue status changes to ACKNOWLEDGED and timestamp is recorded
4. **Given** an ACKNOWLEDGED ERROR issue, **When** Ready-Check runs, **Then** the issue still blocks READY (acknowledgement does not resolve)

---

### User Story 4 - Ready-Check Computation (Priority: P1)

The system must compute `ready_check_json` on every relevant draft update, determining if the draft can transition to READY status based on validation issues.

**Why this priority**: Ready-Check is the gatekeeper for Approve workflow. Without it, invalid drafts could be approved and pushed to ERP, causing downstream errors.

**Independent Test**: Can be fully tested by creating a draft with blocking issues, resolving them one by one, and verifying that `ready_check_json.is_ready` flips to `true` only when all blockers are resolved.

**Acceptance Scenarios**:

1. **Given** a draft with 1 ERROR issue and 2 WARNING issues, **When** Ready-Check runs, **Then** `ready_check_json.is_ready=false` and `blocking_reasons` contains the ERROR type
2. **Given** a draft with only WARNING issues (no ERRORs), **When** Ready-Check runs, **Then** `ready_check_json.is_ready=true` and `blocking_reasons=[]`
3. **Given** a draft with ERROR issues, **When** operator fixes all issues (e.g., sets valid `internal_sku`), **Then** the next validation run clears issues and Ready-Check sets `is_ready=true`
4. **Given** a draft changes from READY to NEEDS_REVIEW, **When** a line is edited to introduce an ERROR, **Then** status automatically transitions to NEEDS_REVIEW and `is_ready=false`

---

### Edge Cases

- What happens when a validation rule depends on external data (e.g., customer prices) that is later deleted? (Issue should remain until re-validation)
- How does system handle concurrent edits that resolve/introduce issues? (Last-write-wins with optimistic locking on draft)
- What if a product's `base_uom` or `uom_conversions_json` is changed after a draft is created? (Re-run validation manually or on next draft update)
- What if an operator overrides an `internal_sku` to a valid product, but then that product is deactivated? (Validation re-runs and creates UNKNOWN_PRODUCT again)
- What happens when `price_tolerance_percent` is changed mid-flight for an org? (Next validation run uses new tolerance; existing issues may be auto-resolved or new ones created)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST implement `ValidatorPort` interface with a `validate(draft_order) -> list[ValidationIssue]` method
- **FR-002**: System MUST run validation automatically after: draft creation, line updates, header updates, SKU mapping confirmation
- **FR-003**: System MUST create `validation_issue` records for each rule violation, referencing `draft_order_id` and optionally `draft_order_line_id`
- **FR-004**: System MUST implement all validation rules from §7.4 (product existence, qty validity, UoM compatibility, price checks)
- **FR-005**: System MUST classify issues by severity: INFO, WARNING, ERROR (per §5.2.6)
- **FR-006**: System MUST block READY status if any ERROR-severity issues exist with status OPEN
- **FR-007**: System MUST support issue status transitions: OPEN → ACKNOWLEDGED → RESOLVED → OVERRIDDEN (per §5.2.7)
- **FR-008**: System MUST compute `ready_check_json` containing `{is_ready: bool, blocking_reasons: [string], checked_at: timestamp}`
- **FR-009**: System MUST store `ready_check_json` in `draft_order` table for fast UI display
- **FR-010**: System MUST allow operators to acknowledge issues (sets status=ACKNOWLEDGED) without resolving them
- **FR-011**: System MUST auto-resolve issues when the underlying problem is fixed (e.g., unknown SKU is set to valid SKU)
- **FR-012**: System MUST implement price validation only when customer_prices exist for the customer+SKU combination
- **FR-013**: System MUST use org-level `price_tolerance_percent` setting for price mismatch detection
- **FR-014**: System MUST handle price tiers (min_qty) by selecting the best matching tier for validation
- **FR-015**: System MUST expose validation issues via Draft detail API (GET `/draft-orders/{id}`) including issue list
- **FR-016**: System MUST provide UI controls to filter issues by severity (ERROR, WARNING, INFO)
- **FR-017**: System MUST provide UI controls to click issue → focus affected line in draft editor
- **FR-018**: System MUST persist `details_json` JSONB field for issue-specific metadata (e.g., expected vs actual price)

### Key Entities *(include if feature involves data)*

- **ValidationIssue** (§5.4.13): Represents a single validation rule violation, linked to draft_order and optionally draft_order_line. Contains type (from §7.3 list), severity, status, message, details_json, resolution metadata.
- **ReadyCheckResult**: Embedded in `draft_order.ready_check_json`, contains `is_ready` boolean, `blocking_reasons` array, `checked_at` timestamp.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 14+ validation rule types from §7.3 are implemented and create deterministic issues (100% coverage in unit tests)
- **SC-002**: ERROR-level issues correctly block READY status in 100% of test cases
- **SC-003**: Ready-Check computation completes within 200ms for drafts with up to 100 lines
- **SC-004**: Price validation with tolerance correctly identifies mismatches in 100% of test cases (unit + integration)
- **SC-005**: Issue acknowledgement does not affect READY blocking behavior (verified in integration tests)
- **SC-006**: UI displays issues with < 100ms latency after draft update (measured in E2E tests)
- **SC-007**: Zero false positives in validation (issues only created for actual rule violations)

## Dependencies

- **Depends on**:
  - **001-database-setup**: Requires `validation_issue` table (§5.4.13) and `draft_order.ready_check_json` field
  - **002-auth**: Requires user context for `resolved_by_user_id` tracking
  - **010-draft-orders**: Requires draft_order and draft_order_line entities
  - **011-product-catalog**: Requires product table with base_uom and uom_conversions_json
  - **020-customer-prices**: (Optional) For price validation feature

- **Enables**:
  - **023-approve-push-flow**: Approve endpoint requires READY status (blocked by validation issues)
  - **018-draft-ui**: Draft detail UI displays validation issues and Ready indicator

## Implementation Notes

### Validation Engine Architecture

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

### Validation Rule Implementation Pattern

Each rule should be a discrete function/class with signature:
```python
def validate_rule(draft: DraftOrder, context: ValidationContext) -> list[ValidationIssue]:
    issues = []
    # Rule logic
    if violation:
        issues.append(ValidationIssue(
            type="UNKNOWN_PRODUCT",
            severity=ValidationIssueSeverity.ERROR,
            status=ValidationIssueStatus.OPEN,
            message="Product INT-999 not found in catalog",
            details_json={"internal_sku": "INT-999", "line_no": 5}
        ))
    return issues
```

### Ready-Check Computation

```python
def compute_ready_check(draft: DraftOrder, issues: list[ValidationIssue]) -> dict:
    error_issues = [i for i in issues if i.severity == ERROR and i.status == OPEN]
    return {
        "is_ready": len(error_issues) == 0,
        "blocking_reasons": [i.type for i in error_issues],
        "checked_at": datetime.utcnow().isoformat()
    }
```

### Price Validation Tier Matching

For a given line with qty=150:
1. Filter customer_prices by customer_id, internal_sku, currency
2. Filter by date range: `valid_from <= today <= valid_to_or_null`
3. Find max(min_qty) where min_qty <= 150 → this is the applicable tier
4. Compare line.unit_price vs tier.unit_price using tolerance

### Validation Rule Error Handling

If a rule function raises an exception:
1. Log error with rule_name, draft_id, and stack trace
2. Return empty issues list for that rule (fail-open)
3. Continue executing remaining rules
4. Add system ValidationIssue with severity=WARNING: 'Validation rule {rule_name} failed to execute'

This ensures one broken rule doesn't block entire validation.

### Issue Auto-Resolution

When a draft line is updated:
1. Fetch all OPEN issues for that line
2. Re-run validation rules
3. If new validation passes (no issue created), mark old issue as RESOLVED with `resolved_at=now`

### UI Integration

Draft detail API response includes:
```json
{
  "draft_order": {...},
  "ready_check": {
    "is_ready": false,
    "blocking_reasons": ["UNKNOWN_PRODUCT", "MISSING_CUSTOMER"],
    "checked_at": "2025-12-27T10:00:00Z"
  },
  "validation_issues": [
    {
      "id": "uuid",
      "type": "UNKNOWN_PRODUCT",
      "severity": "ERROR",
      "status": "OPEN",
      "message": "Product ABC-999 not found",
      "line_id": "uuid",
      "line_no": 3,
      "details": {"internal_sku": "ABC-999"}
    }
  ]
}
```

## Testing Strategy

### Unit Tests
- Each validation rule in isolation with fixtures
- Ready-Check computation with various issue combinations
- Price tier selection algorithm
- UoM compatibility check with conversion tables

### Component Tests
- ValidationEngine with mock repository
- End-to-end validation flow: draft → validate → issues created → ready_check updated

### Integration Tests
- API: PATCH draft line → validation runs → GET draft shows new issues
- Issue acknowledgement: POST acknowledge → status changes → READY still blocked
- Price validation: import customer_prices → create draft → price mismatch detected

### E2E Tests
- Full workflow: Create draft with errors → UI shows issues → Fix issues → READY status activates
- Issue filtering: Filter by ERROR → only ERROR badges shown
- Click issue → line focused in editor

## SSOT Compliance Checklist

- [ ] All issue types from §7.3 implemented
- [ ] All validation rules from §7.4 implemented
- [ ] Severity levels match §5.2.6 (INFO, WARNING, ERROR)
- [ ] Issue status transitions match §5.2.7 (OPEN, ACKNOWLEDGED, RESOLVED, OVERRIDDEN)
- [ ] `validation_issue` table schema matches §5.4.13
- [ ] Price validation uses org.settings_json.price_tolerance_percent
- [ ] UoM validation uses product.uom_conversions_json
- [ ] Ready-Check blocks READY status only on ERROR-level OPEN issues (§6.3)
- [ ] T-501 acceptance criteria met (deterministic issues, ERROR blocks READY)
- [ ] T-503 acceptance criteria met (acknowledge issue, READY still blocked)
- [ ] T-504 acceptance criteria met (ready_check_json computed on update, UI shows READY only when is_ready=true)
