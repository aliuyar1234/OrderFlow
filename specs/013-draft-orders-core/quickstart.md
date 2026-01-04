# Quickstart: Draft Orders Core

**Feature**: 013-draft-orders-core
**Date**: 2025-12-27

## Prerequisites

- Completed specs 010 (extractors rule-based), 011 (LLM provider), 012 (extractors LLM)
- Database migrations applied

## Step 1: Database Migration

```bash
cd backend
alembic revision --autogenerate -m "Add draft_order and draft_order_line tables"
alembic upgrade head
```

## Step 2: Create Draft from Extraction

```python
# Example: Create draft after extraction completes
from src.services.draft_order_service import DraftOrderService

service = DraftOrderService()

extraction_output = {
    "order": {
        "external_order_number": "PO-123",
        "order_date": "2024-12-20",
        "currency": "EUR"
    },
    "lines": [
        {
            "line_no": 1,
            "customer_sku_raw": "ABC-1",
            "product_description": "Widget",
            "qty": 10,
            "uom": "ST",
            "unit_price": 45.50
        }
    ],
    "confidence": {
        "overall": 0.85,
        "order": {...},
        "lines": [...]
    }
}

draft = service.create_from_extraction(
    org_id=your_org_id,
    document_id=your_doc_id,
    extraction_output=extraction_output
)

print(f"Draft created: {draft.id}")
print(f"Status: {draft.status}")  # Expected: EXTRACTED or READY
print(f"Confidence: {draft.confidence_score}")
```

## Step 3: Test State Transitions

```python
# Transition to READY
service.transition_status(draft.id, DraftOrderStatus.READY)

# Approve
service.approve_draft(draft.id, user_id=your_user_id)
assert draft.status == DraftOrderStatus.APPROVED

# Start push
service.transition_status(draft.id, DraftOrderStatus.PUSHING)

# Complete push
service.complete_push(draft.id, erp_order_id="ERP-456")
assert draft.status == DraftOrderStatus.PUSHED
```

## Step 4: Test Ready-Check

```python
# Draft without customer → not ready
draft = service.create_draft(org_id, document_id)
ready = service.run_ready_check(draft.id)
assert ready["is_ready"] == False
assert "customer_id missing" in ready["blocking_reasons"]

# Set customer → ready
service.set_customer(draft.id, customer_id)
ready = service.run_ready_check(draft.id)
assert ready["is_ready"] == True
```

## Step 5: Test Line CRUD

```python
# Add line
line = service.add_line(
    draft_id=draft.id,
    customer_sku_raw="XYZ-2",
    qty=5,
    uom="ST"
)

# Edit line
service.update_line(line.id, qty=10)

# Delete line
service.delete_line(line.id)

# Verify ready-check runs after each operation
```

## API Endpoints

```bash
# Get drafts for review
curl http://localhost:8000/api/draft-orders?status=NEEDS_REVIEW \
  -H "Authorization: Bearer $TOKEN"

# Get specific draft
curl http://localhost:8000/api/draft-orders/{draft_id} \
  -H "Authorization: Bearer $TOKEN"

# Approve draft
curl -X POST http://localhost:8000/api/draft-orders/{draft_id}/approve \
  -H "Authorization: Bearer $TOKEN"

# Add line
curl -X POST http://localhost:8000/api/draft-orders/{draft_id}/lines \
  -H "Content-Type: application/json" \
  -d '{"customer_sku_raw": "NEW-1", "qty": 10, "uom": "ST"}'
```

## Common Issues

### Issue 1: Draft Status Stuck in NEEDS_REVIEW

**Solution**: Check blocking reasons in ready_check_json. Fix issues (add customer, map SKUs, resolve errors).

### Issue 2: Confidence Score is NULL

**Solution**: Ensure extraction_confidence, customer_confidence, matching_confidence are all set. Run recalculation.

### Issue 3: Invalid State Transition Error

**Solution**: Check ALLOWED_TRANSITIONS map. Ensure current state allows target state.

## Testing Checklist

- [ ] Draft created from extraction
- [ ] State transitions enforced
- [ ] Ready-check blocks invalid drafts
- [ ] Confidence score calculated correctly
- [ ] Line CRUD operations work
- [ ] Audit log records state changes
- [ ] API endpoints return correct data
