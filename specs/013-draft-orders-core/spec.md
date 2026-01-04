# Feature Specification: Draft Orders Core (Entity & State Machine)

**Feature Branch**: `013-draft-orders-core`
**Created**: 2025-12-27
**Status**: Draft
**Module**: draft_orders
**SSOT Refs**: §5.4.8 (draft_order), §5.4.9 (draft_order_line), §5.2.5 (Status State Machine), §6.3 (Ready-Check), §7.8 (Confidence), T-305

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Draft Order Creation from Extraction (Priority: P1)

After document extraction completes, the system automatically creates a DraftOrder with header data and lines, calculates confidence scores, and determines initial status (EXTRACTED, NEEDS_REVIEW, or READY).

**Why this priority**: Core entity for the entire order processing workflow. Every order becomes a Draft first.

**Independent Test**: Extraction completes with confidence=0.85 → DraftOrder created with status=READY, header fields populated, lines with match_status.

**Acceptance Scenarios**:

1. **Given** extraction output with header (external_order_number, order_date, currency) and 5 lines, **When** creating DraftOrder, **Then** draft_order and draft_order_line records are created with extracted data
2. **Given** extraction_confidence=0.85, customer_confidence=0.92, matching_confidence=0.88, **When** calculating overall confidence, **Then** confidence_score = 0.45*0.85 + 0.20*0.92 + 0.35*0.88 = 0.8755
3. **Given** DraftOrder with customer_id set, no ERROR issues, all lines have internal_sku, **When** running ready-check, **Then** status is set to READY

---

### User Story 2 - State Machine Transitions (Priority: P1)

The DraftOrder progresses through states (NEW → EXTRACTED → NEEDS_REVIEW → READY → APPROVED → PUSHING → PUSHED) based on extraction quality, validation results, and user actions.

**Why this priority**: State machine enforces process integrity and prevents invalid transitions (e.g., pushing unapproved draft).

**Independent Test**: Create Draft → extract → fix issues → approve → push → verify each transition is valid and logged.

**Acceptance Scenarios**:

1. **Given** Draft in NEW status, **When** extraction completes, **Then** status transitions to EXTRACTED (or NEEDS_REVIEW/READY based on ready-check)
2. **Given** Draft in NEEDS_REVIEW, **When** Ops resolves all ERROR issues, **Then** status transitions to READY
3. **Given** Draft in READY, **When** Ops clicks "Approve", **Then** status transitions to APPROVED, approved_by_user_id and approved_at are set
4. **Given** Draft in APPROVED, **When** push job starts, **Then** status transitions to PUSHING
5. **Given** Draft in PUSHING, **When** export succeeds, **Then** status transitions to PUSHED, erp_order_id is set
6. **Given** Draft in PUSHING, **When** export fails, **Then** status transitions to ERROR
7. **Given** Draft in READY, **When** Ops clicks "Reject", **Then** status transitions to REJECTED (terminal state)

---

### User Story 3 - Ready-Check Logic (Priority: P1)

The system continuously evaluates whether a Draft is ready for approval by checking header completeness, line validity, and absence of blocking errors.

**Why this priority**: Prevents pushing incomplete/invalid orders to ERP. Critical quality gate.

**Independent Test**: Draft with missing customer_id → ready-check fails → status=NEEDS_REVIEW. Set customer → ready-check passes → status=READY.

**Acceptance Scenarios**:

1. **Given** Draft without customer_id, **When** running ready-check, **Then** is_ready=false, blocking_reasons includes "customer_id missing"
2. **Given** Draft with customer_id but no currency, **When** running ready-check, **Then** is_ready=false, blocking_reasons includes "currency missing"
3. **Given** Draft with line where internal_sku=null, **When** running ready-check, **Then** is_ready=false, blocking_reasons includes "Line X: missing internal_sku"
4. **Given** Draft with ERROR severity issue, **When** running ready-check, **Then** is_ready=false, blocking_reasons includes issue type
5. **Given** Draft meeting all ready criteria, **When** running ready-check, **Then** is_ready=true, blocking_reasons=[], ready_check_json.passed_at is set

---

### User Story 4 - Confidence Score Calculation and Display (Priority: P2)

The system calculates and displays extraction_confidence, customer_confidence, matching_confidence, and overall confidence_score, helping Ops prioritize review of low-confidence drafts.

**Why this priority**: Enables risk-based review (focus on low-confidence orders first). Transparency into AI quality.

**Independent Test**: Query drafts ordered by confidence_score ASC → lowest confidence orders appear first for review.

**Acceptance Scenarios**:

1. **Given** extraction result with per-field confidence, **When** calculating extraction_confidence, **Then** formula per §7.8.1 is applied (weighted avg of header + lines)
2. **Given** customer auto-selected with score=0.93, **When** setting customer_confidence, **Then** customer_confidence=0.93
3. **Given** 5 lines with matching_confidence [0.95, 0.88, 0.72, 0.91, 0.85], **When** calculating overall matching_confidence, **Then** matching_confidence = avg(0.95, 0.88, 0.72, 0.91, 0.85) = 0.862
4. **Given** all component confidence scores calculated (extraction_confidence, customer_confidence, matching_confidence), **When** calculating overall confidence_score, **Then** confidence_score = 0.45*extraction_confidence + 0.20*customer_confidence + 0.35*matching_confidence, clamped to [0..1]

---

### User Story 5 - Draft Order Line Management (Priority: P1)

Ops can manually add, edit, or delete lines in a Draft. Changes trigger re-validation and ready-check.

**Why this priority**: Manual fallback for extraction failures. Ops needs full control over order content.

**Independent Test**: Add new line manually → validation runs → ready-check updates → status changes if needed.

**Acceptance Scenarios**:

1. **Given** Draft in NEEDS_REVIEW, **When** Ops adds new line with customer_sku_raw="NEW-SKU", qty=10, uom="ST", **Then** line is saved, matching runs, validation runs
2. **Given** Draft line with qty=5, **When** Ops edits qty to 50, **Then** line is updated, validation re-runs (price check, UoM compatibility)
3. **Given** Draft with 10 lines, **When** Ops deletes line 5, **Then** line is deleted, ready-check re-runs
4. **Given** line edit changes internal_sku, **When** saving, **Then** match_status is set to OVERRIDDEN, match_method="manual"

---

### Edge Cases

- What happens when extraction creates 0 lines (failed extraction)?
- How does system handle Draft with 500+ lines (max_lines limit)?
- What happens when ready-check is triggered mid-export (race condition)?
- How does system handle invalid state transitions (e.g., PUSHED → NEEDS_REVIEW)?
- What happens when customer_id is changed after matching already ran (re-match needed)?
- How does system handle Draft deletion (soft-delete? cascade to lines/issues?)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST create draft_order entity from extraction result with fields:
  - `customer_id` (from customer detection or null)
  - `document_id`, `inbound_message_id`
  - `external_order_number`, `order_date`, `currency`, `requested_delivery_date` (from extraction)
  - `ship_to_json`, `bill_to_json`, `notes` (from extraction)
  - `status` = initial status based on ready-check
  - `confidence_score` (overall score per §7.8.4), `extraction_confidence`, `customer_confidence`, `matching_confidence` (component scores)
  - `ready_check_json` = result of ready-check
- **FR-002**: System MUST create draft_order_line entities from extraction lines with fields:
  - `line_no` (sequential 1..n)
  - `customer_sku_raw`, `customer_sku_norm` (normalized per §6.1)
  - `product_description`, `qty`, `uom`, `unit_price`, `currency`
  - `internal_sku` (from matching, initially null)
  - `match_status` (UNMATCHED|SUGGESTED|MATCHED|OVERRIDDEN)
  - `matching_confidence`, `match_method`, `match_debug_json`
- **FR-003**: System MUST implement state machine per §5.2.5 with transitions:
  - NEW → EXTRACTED (extraction completes)
  - EXTRACTED → NEEDS_REVIEW | READY (based on ready-check)
  - NEEDS_REVIEW → READY | REJECTED (issues resolved or rejected)
  - READY → APPROVED (user approves)
  - APPROVED → PUSHING (export starts)
  - PUSHING → PUSHED | ERROR (export succeeds or fails)
  - ERROR → NEEDS_REVIEW | PUSHING (retry)
  - REJECTED = terminal (MVP, no reopen)
- **FR-004**: System MUST validate state transitions and reject invalid transitions with error
- **FR-005**: System MUST implement ready-check per §6.3 validating:
  - Header: customer_id NOT NULL, currency NOT NULL
  - Lines: ALL lines have qty>0, uom NOT NULL, internal_sku NOT NULL (MVP strict)
  - Issues: NO issues with severity=ERROR
  - Output: `ready_check_json = {"is_ready": bool, "blocking_reasons": [str], "passed_at": timestamp|null}`
- **FR-006**: System MUST calculate extraction_confidence per §7.8.1:
  - Header score: weighted avg of (external_order_number w=0.20, order_date w=0.15, currency w=0.20, customer_hint w=0.25, delivery_date w=0.10, ship_to w=0.10)
  - Line score: avg of weighted line scores (customer_sku w=0.30, qty w=0.30, uom w=0.20, unit_price w=0.20)
  - Sanity penalties: lines_count==0 → *0.60, text_coverage<0.15 (no vision) → *0.50, anchor_check fail >30% → *0.70
  - Final: (0.40*header + 0.60*line) * penalties, clamped [0..1]
- **FR-007**: System MUST calculate customer_confidence per §7.8.2:
  - Auto-selected: score from customer detection
  - User-selected: max(detection_score, 0.90)
  - None: 0.0
- **FR-008**: System MUST calculate matching_confidence per §7.8.3:
  - Avg of matching_confidence for all lines (lines with internal_sku=null count as 0)
- **FR-009**: System MUST calculate overall confidence_score per §7.8.4:
  - `0.45*extraction_confidence + 0.20*customer_confidence + 0.35*matching_confidence`, clamped [0..1]
- **FR-010**: System MUST support line CRUD operations:
  - Create: add new line with sequential line_no, trigger matching, validation, ready-check
  - Update: edit line fields, set match_status=OVERRIDDEN if internal_sku manually changed, re-validate, ready-check
  - Delete: remove line, re-number remaining lines, ready-check
- **FR-011**: System MUST normalize customer_sku_raw to customer_sku_norm per §6.1 on line creation/update
- **FR-012**: System MUST re-run ready-check after:
  - Extraction completion
  - Line add/edit/delete
  - Customer selection
  - Issue resolution/override
  - Matching update
- **FR-013**: System MUST transition status based on ready-check result:
  - If was EXTRACTED and now ready → READY
  - If was EXTRACTED and not ready → NEEDS_REVIEW
  - If was NEEDS_REVIEW and now ready → READY
  - If was READY and no longer ready → NEEDS_REVIEW
- **FR-014**: System MUST log state transitions in audit_log with before/after status
- **FR-015**: System MUST set approved_by_user_id and approved_at when transitioning to APPROVED
- **FR-016**: System MUST set erp_order_id when transitioning to PUSHED
- **FR-022**: Ready-check MUST be idempotent and handle concurrent edits. Implementation: Add 'version' column (INTEGER) to draft_order table. All updates MUST include WHERE version = expected_version. On version mismatch, retry ready-check with fresh data. Maximum 3 retries before returning 409 Conflict.
- **FR-023**: Draft deletion strategy:
  1. Soft-delete only (set deleted_at timestamp)
  2. Cascade soft-delete to draft_order_lines and validation_issues
  3. Preserve audit_log entries immutably
  4. Exclude soft-deleted records from all queries by default
  5. Retention: soft-deleted drafts purged after 7 years per data retention policy

### Key Entities

- **draft_order** (§5.4.8): Order header with status, confidence scores, ready_check_json
- **draft_order_line** (§5.4.9): Order line with matching info, confidence, debug data
- **DraftOrderStatus** (§5.2.5): State enum with defined transitions
- **ready_check_json**: Embedded JSON with is_ready flag, blocking_reasons array, passed_at timestamp

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of extractions result in DraftOrder creation (even if 0 lines)
- **SC-002**: State machine prevents 100% of invalid transitions (enforced at DB + service layer)
- **SC-003**: Ready-check accuracy: 0% false positives (ready when not actually ready for ERP)
- **SC-004**: Confidence calculation performance: <10ms per draft (tested with 200-line orders)
- **SC-005**: Line CRUD operations trigger validation + ready-check in <100ms
- **SC-006**: 100% of state transitions are logged in audit_log
- **SC-007**: Ops can sort/filter drafts by confidence_score, status, created_at in <500ms (10k+ drafts)
- **SC-008**: Ready-check detects all blocking conditions per §6.3 (tested with 50+ scenarios)

## Dependencies

- **Depends on**:
  - 010-extractors-rule-based (provides extraction results)
  - 012-extractors-llm (provides extraction results)
  - 018-customer-detection (sets customer_id, customer_confidence)
  - 017-matching-engine (sets internal_sku, match_confidence)
  - Validation service (creates validation_issue entities)
  - Database (draft_order, draft_order_line tables)

- **Blocks**:
  - 014-draft-orders-ui (needs draft entity with state machine)
  - ERP export service (requires APPROVED status before export)
  - Reporting/metrics (uses confidence scores, status)

## Technical Notes

### Implementation Guidance

**State Machine Implementation:**
```python
from enum import Enum
from typing import Optional

class DraftOrderStatus(str, Enum):
    NEW = "NEW"
    EXTRACTED = "EXTRACTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    READY = "READY"
    APPROVED = "APPROVED"
    PUSHING = "PUSHING"
    PUSHED = "PUSHED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"

ALLOWED_TRANSITIONS = {
    DraftOrderStatus.NEW: [DraftOrderStatus.EXTRACTED],
    DraftOrderStatus.EXTRACTED: [DraftOrderStatus.NEEDS_REVIEW, DraftOrderStatus.READY],
    DraftOrderStatus.NEEDS_REVIEW: [DraftOrderStatus.READY, DraftOrderStatus.REJECTED],
    DraftOrderStatus.READY: [DraftOrderStatus.APPROVED, DraftOrderStatus.NEEDS_REVIEW],
    DraftOrderStatus.APPROVED: [DraftOrderStatus.PUSHING],
    DraftOrderStatus.PUSHING: [DraftOrderStatus.PUSHED, DraftOrderStatus.ERROR],
    DraftOrderStatus.ERROR: [DraftOrderStatus.NEEDS_REVIEW, DraftOrderStatus.PUSHING],
    DraftOrderStatus.REJECTED: [],  # terminal
    DraftOrderStatus.PUSHED: [],  # terminal (MVP)
}

def transition_status(draft: DraftOrder, new_status: DraftOrderStatus, user_id: Optional[UUID] = None):
    if new_status not in ALLOWED_TRANSITIONS.get(draft.status, []):
        raise ValueError(f"Invalid transition: {draft.status} -> {new_status}")

    old_status = draft.status
    draft.status = new_status
    draft.updated_at = now()

    if new_status == DraftOrderStatus.APPROVED:
        draft.approved_by_user_id = user_id
        draft.approved_at = now()

    # Audit log
    create_audit_log(
        org_id=draft.org_id,
        actor_user_id=user_id,
        action="DRAFT_STATUS_CHANGED",
        entity_type="draft_order",
        entity_id=draft.id,
        before_json={"status": old_status},
        after_json={"status": new_status},
    )
```

**Ready-Check Logic:**
```python
def run_ready_check(draft: DraftOrder) -> dict:
    blocking_reasons = []

    # Header checks
    if not draft.customer_id:
        blocking_reasons.append("customer_id missing")
    if not draft.currency:
        blocking_reasons.append("currency missing")

    # Line checks
    if not draft.lines:
        blocking_reasons.append("No order lines")
    else:
        for line in draft.lines:
            if not line.qty or line.qty <= 0:
                blocking_reasons.append(f"Line {line.line_no}: invalid qty")
            if not line.uom:
                blocking_reasons.append(f"Line {line.line_no}: missing uom")
            if not line.internal_sku:  # MVP strict
                blocking_reasons.append(f"Line {line.line_no}: missing internal_sku")

    # Issue checks
    error_issues = db.query(ValidationIssue).filter(
        ValidationIssue.draft_order_id == draft.id,
        ValidationIssue.severity == "ERROR",
        ValidationIssue.status == "OPEN"
    ).all()
    if error_issues:
        blocking_reasons.extend([f"Issue: {issue.type}" for issue in error_issues])

    is_ready = len(blocking_reasons) == 0
    passed_at = now() if is_ready else None

    return {
        "is_ready": is_ready,
        "blocking_reasons": blocking_reasons,
        "passed_at": passed_at.isoformat() if passed_at else None,
    }
```

**Confidence Calculation (§7.8.1):**
```python
def calculate_extraction_confidence(extraction_output: dict) -> float:
    # Header score
    header_fields = {
        "external_order_number": 0.20,
        "order_date": 0.15,
        "currency": 0.20,
        "customer_hint": 0.25,
        "requested_delivery_date": 0.10,
        "ship_to": 0.10,
    }
    header_conf = extraction_output["confidence"]["order"]
    header_score = sum(
        header_conf.get(field, 0.0) * weight
        for field, weight in header_fields.items()
    ) / sum(header_fields.values())

    # Line score
    line_weights = {"customer_sku_raw": 0.30, "qty": 0.30, "uom": 0.20, "unit_price": 0.20}
    lines_conf = extraction_output["confidence"]["lines"]
    if not lines_conf:
        line_score = 0.0
    else:
        line_scores = [
            sum(lc.get(f, 0.0) * w for f, w in line_weights.items()) / sum(line_weights.values())
            for lc in lines_conf
        ]
        line_score = sum(line_scores) / len(line_scores)

    # Sanity penalties
    penalty = 1.0
    if len(extraction_output["lines"]) == 0:
        penalty *= 0.60
    if extraction_output.get("text_coverage_ratio", 1.0) < 0.15 and not extraction_output.get("used_vision"):
        penalty *= 0.50
    # Anchor check penalty (assume calculated elsewhere)
    if extraction_output.get("anchor_check_fail_rate", 0) > 0.30:
        penalty *= 0.70

    return max(0.0, min(1.0, (0.40 * header_score + 0.60 * line_score) * penalty))
```

**Customer SKU Normalization (§6.1):**
```python
import re

def normalize_customer_sku(raw: str) -> str:
    if not raw:
        return ""
    # Trim, uppercase
    norm = raw.strip().upper()
    # Replace tabs, newlines, multiple spaces
    norm = re.sub(r'[\t\n ]+', ' ', norm)
    # Remove all except A-Z0-9
    norm = re.sub(r'[^A-Z0-9]', '', norm)
    return norm

# Example: " AB-12 / 34 " → "AB1234"
```

### Testing Strategy

**Unit Tests:**
- State machine: all valid transitions, invalid transitions rejected
- Ready-check: all blocking conditions, edge cases (0 lines, missing fields)
- Confidence calculation: various extraction outputs, penalty scenarios
- Customer SKU normalization: various input formats

**Integration Tests:**
- End-to-end: extraction → Draft creation → status determination
- Line CRUD: add → validate → ready-check → status update
- State transitions: simulate full workflow (extract → review → approve → push)
- Audit logging: verify all transitions logged

**Test Data:**
- Extraction outputs with varying completeness (0%, 50%, 100% fields)
- Drafts with 0, 1, 50, 200 lines
- Various confidence score combinations
- Edge cases: missing customer, missing SKUs, ERROR issues

## SSOT References

- **§5.2.5**: DraftOrderStatus state machine and transitions
- **§5.4.8**: draft_order table schema
- **§5.4.9**: draft_order_line table schema
- **§6.1**: Customer SKU normalization
- **§6.3**: Ready-check logic and blocking conditions
- **§7.8**: Confidence scoring (all subsections)
- **§7.8.1**: Extraction confidence calculation formula
- **§7.8.2**: Customer confidence
- **§7.8.3**: Matching confidence
- **§7.8.4**: Overall confidence_score formula
- **T-305**: Draft Order Entity task
