# Research: Draft Orders Core

**Feature**: 013-draft-orders-core
**Date**: 2025-12-27

## Key Decisions

### Decision 1: State Machine Design

**Choice**: Enum-based state with explicit transition map (ALLOWED_TRANSITIONS dict).

**Rationale**: Type-safe, self-documenting, prevents invalid transitions at code level. Easy to visualize and test.

**State Flow**:
```
NEW → EXTRACTED → NEEDS_REVIEW → READY → APPROVED → PUSHING → PUSHED
              ↓         ↓
           READY     REJECTED
```

### Decision 2: Ready-Check Timing

**Choice**: Run ready-check after every mutation (line add/edit/delete, customer set, issue resolved).

**Rationale**: Ensures status is always current. Ops never sees stale "READY" status when draft is actually incomplete.

### Decision 3: Confidence Formula Weights

**Choice**: Extraction=0.45, Customer=0.20, Matching=0.35 (per §7.8.4).

**Rationale**: Extraction quality most important (foundational data). Matching second (correct SKUs critical). Customer third (can be corrected easily).

### Decision 4: Ready-Check Strictness (MVP)

**Choice**: Strict mode: ALL lines must have internal_sku. No exceptions.

**Rationale**: Prevents incomplete orders from reaching ERP. Post-MVP can relax (allow partial mapping with warnings).

### Decision 5: Customer SKU Normalization

**Choice**: Remove all non-alphanumeric, uppercase, no special chars.

**Rationale**: Handles variations ("AB-12", "AB 12", "ab12" → "AB12"). Enables fuzzy matching.

## Best Practices

### State Machine Testing
- Test all valid transitions
- Test all invalid transitions (expect rejection)
- Test concurrent transitions (locking)

### Ready-Check Validation
- Test all blocking conditions independently
- Test edge cases (0 lines, missing customer, ERROR issues)
- Ensure no false positives (ready when not actually ready)

### Confidence Scoring
- Validate formula against spec exactly
- Test edge cases (0.0, 1.0, component missing)
- Ensure clamping to [0.0, 1.0]

### Performance Optimization
- Index on (org_id, status, created_at) for dashboard queries
- Index on (org_id, confidence_score) for sort/filter
- Use pagination for large result sets

## Testing Strategy

### Unit Tests
```python
def test_state_transition_valid():
    draft = DraftOrder(status=NEEDS_REVIEW)
    transition_status(draft, READY)
    assert draft.status == READY

def test_state_transition_invalid():
    draft = DraftOrder(status=PUSHED)
    with pytest.raises(ValueError):
        transition_status(draft, NEEDS_REVIEW)  # Terminal state

def test_ready_check_missing_customer():
    draft = DraftOrder(customer_id=None)
    result = run_ready_check(draft)
    assert result["is_ready"] == False
    assert "customer_id missing" in result["blocking_reasons"]
```

### Integration Tests
- Extract → Draft created → status determined
- Edit line → ready-check runs → status updated
- Approve → status=APPROVED → push → status=PUSHED
