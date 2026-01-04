# Feedback & Learning - Quick Reference

**Status:** ✅ Implementation Complete
**Date:** 2026-01-04

## Prerequisites

- Python 3.12+
- PostgreSQL 16
- OrderFlow backend installed

## Installation

### 1. Database Migration

```bash
cd backend
alembic upgrade head
```

Verify tables created:
```sql
\d feedback_event
\d doc_layout_profile
```

### 2. Import Services

```python
from backend.src.feedback.services import (
    FeedbackService,
    LayoutService,
    LearningService
)
```

## Common Operations

### Capture Mapping Confirmation

```python
# When user confirms a SKU mapping
feedback_event = FeedbackService.capture_mapping_confirmed(
    db=db,
    org_id=current_user.org_id,
    actor_user_id=current_user.id,
    sku_mapping_data={"mapping_id": str(mapping_id), "customer_sku": "ABC-123"},
    before_state={"status": "SUGGESTED", "confidence": 0.5},
    after_state={"status": "CONFIRMED", "confidence": 1.0}
)
```

### Capture Line Edit Corrections

```python
# When user edits qty from 10 to 12
feedback_event = FeedbackService.capture_line_corrected(
    db=db,
    org_id=current_user.org_id,
    actor_user_id=current_user.id,
    draft_order_id=draft_order_id,
    draft_order_line_id=line_id,
    before_values={"qty": 10},
    after_values={"qty": 12},
    layout_fingerprint=document.layout_fingerprint,
    input_snippet=pdf_text[:1500]  # First 1500 chars
)
```

### Generate Layout Fingerprint

```python
# When processing a PDF document
document_metadata = {
    "page_count": 2,
    "page_dimensions": [(595, 842), (595, 842)],
    "table_count": 1,
    "text_coverage_ratio": 0.65
}

fingerprint = LayoutService.generate_fingerprint(document_metadata)
document.layout_fingerprint = fingerprint

profile = LayoutService.create_or_update_profile(
    db=db,
    org_id=org_id,
    document_id=document.id,
    layout_fingerprint=fingerprint,
    fingerprint_method="PDF_TEXT_SHA256",
    anchors={"keywords": ["Bestellnummer"], "page_count": 2}
)
```

### Get Few-Shot Examples

```python
# Before calling LLM for extraction
examples = LearningService.get_few_shot_examples(
    db=db,
    org_id=org_id,
    layout_fingerprint=document.layout_fingerprint,
    limit=3  # Last 3 corrections
)

# Inject into LLM prompt
llm_context = {
    "document_text": pdf_text,
    "hint_examples": json.dumps(examples) if examples else ""
}
```

### Get Learning Analytics

```python
# For admin dashboard
from datetime import datetime, timedelta

analytics = LearningService.get_learning_analytics(
    db=db,
    org_id=org_id,
    start_date=datetime.utcnow() - timedelta(days=30),
    end_date=datetime.utcnow()
)
```

## API Endpoints

### Feedback Capture

```bash
# Confirm mapping
POST /api/v1/sku-mappings/{mapping_id}/confirm
Content-Type: application/json
{
  "customer_sku": "ABC-123",
  "internal_sku": "INT-999"
}

# Select customer
POST /api/v1/draft-orders/{draft_order_id}/select-customer
{
  "customer_id": "uuid",
  "candidates": [...]
}

# Edit line (captures corrections)
PATCH /api/v1/draft-orders/{draft_order_id}/lines/{line_id}
{
  "qty": 12
}
```

### Analytics (ADMIN/INTEGRATOR only)

```bash
# Get learning analytics
GET /api/v1/analytics/learning?start_date=2025-12-01&end_date=2026-01-04

# Get few-shot examples
GET /api/v1/analytics/learning/few-shot-examples/{fingerprint}?limit=3
```

## Event Types

| Event Type | Trigger | Use Case |
|------------|---------|----------|
| `MAPPING_CONFIRMED` | User confirms mapping | Auto-apply in future |
| `MAPPING_REJECTED` | User rejects mapping | Improve matching |
| `EXTRACTION_LINE_CORRECTED` | User edits line | Few-shot learning |
| `CUSTOMER_SELECTED` | User selects customer | Customer detection |

## Testing

### Manual Testing

```bash
# 1. Process PDF and generate fingerprint
curl -X POST http://localhost:8000/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@order.pdf"

# Check fingerprint created
psql -c "SELECT id, layout_fingerprint FROM document ORDER BY created_at DESC LIMIT 1;"

# 2. Create feedback event
curl -X POST http://localhost:8000/sku-mappings/{id}/confirm \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"customer_sku": "ABC", "internal_sku": "INT"}'

# Verify feedback
psql -c "SELECT event_type, before_json FROM feedback_event ORDER BY created_at DESC LIMIT 1;"

# 3. View analytics
curl "http://localhost:8000/analytics/learning?start_date=2025-12-01" \
  -H "Authorization: Bearer $TOKEN"
```

### Unit Tests

```bash
pytest tests/unit/test_fingerprint.py -v
pytest tests/unit/test_example_selection.py -v
```

### Integration Tests

```bash
pytest tests/integration/test_feedback_capture.py -v
```

## Performance SLAs

| Operation | Target | Notes |
|-----------|--------|-------|
| Feedback capture | < 50ms | INSERT only |
| Few-shot lookup | < 10ms | LIMIT 3 |
| Analytics dashboard | < 2s | 90 days data |

## Multi-Tenant Isolation

⚠️ **CRITICAL:** Always filter by `org_id`

```python
# ✅ Correct
events = db.query(FeedbackEvent).filter(
    FeedbackEvent.org_id == current_user.org_id
).all()

# ❌ Wrong - no org filter!
events = db.query(FeedbackEvent).all()
```

## Troubleshooting

**No few-shot examples returned?**
- Check `document.layout_fingerprint` is set
- Verify feedback events exist for same fingerprint
- Ensure org_id matches (no cross-tenant examples)

**Feedback events not captured?**
- Run migration: `alembic upgrade head`
- Check database permissions
- Verify org_id is set correctly

## Documentation

- Full docs: `backend/src/feedback/README.md`
- Integration guide: `specs/024-feedback-learning/IMPLEMENTATION.md`
- SSOT: `SSOT_SPEC.md` §5.5.3, §5.5.5, §7.10
