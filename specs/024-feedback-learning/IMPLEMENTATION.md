# Feedback & Learning Implementation Guide

## Overview

This document provides guidance on integrating the feedback & learning module into the OrderFlow application.

## Files Created

### Backend Module: `backend/src/feedback/`

```
backend/src/feedback/
├── __init__.py          # Module exports
├── models.py            # FeedbackEvent and DocLayoutProfile SQLAlchemy models
├── services.py          # FeedbackService, LayoutService, LearningService
├── endpoints.py         # Feedback capture API endpoints
├── analytics.py         # Learning analytics API endpoints
└── README.md            # Module documentation
```

### Database Migration

```
backend/alembic/versions/001_create_feedback_tables.py
```

## Integration Steps

### 1. Database Migration

Run the Alembic migration to create the `feedback_event` and `doc_layout_profile` tables:

```bash
cd backend
alembic upgrade head
```

This creates:
- `feedback_event` table with indexes on (org_id, created_at), (org_id, event_type, created_at), (org_id, layout_fingerprint)
- `doc_layout_profile` table with unique index on (org_id, layout_fingerprint)

### 2. Import Models

The feedback models are automatically exported from `backend/src/models/__init__.py`:

```python
from backend.src.models import FeedbackEvent, DocLayoutProfile
```

### 3. Register API Routers

In your main FastAPI application (`backend/src/main.py` or similar), register the feedback routers:

```python
from backend.src.feedback.endpoints import router as feedback_router
from backend.src.feedback.analytics import router as analytics_router

app = FastAPI()

# Register feedback routers
app.include_router(feedback_router)
app.include_router(analytics_router)
```

### 4. Integrate Feedback Capture

#### A. Mapping Confirmation

When a user confirms a SKU mapping in the UI, call the feedback endpoint:

```typescript
// Frontend example
async function confirmMapping(mappingId: string, customerSku: string, internalSku: string) {
  const response = await fetch(`/api/v1/sku-mappings/${mappingId}/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      customer_sku: customerSku,
      internal_sku: internalSku,
      draft_order_line_id: lineId,  // optional
      confidence: 0.85  // optional
    })
  });
  return response.json();
}
```

Or capture feedback server-side:

```python
from backend.src.feedback.services import FeedbackService

# After confirming mapping in backend
feedback_event = FeedbackService.capture_mapping_confirmed(
    db=db,
    org_id=org_id,
    actor_user_id=user_id,
    sku_mapping_data={
        "mapping_id": str(mapping_id),
        "customer_sku": "ABC-123",
        "internal_sku": "INT-999"
    },
    before_state={"status": "SUGGESTED", "confidence": 0.5},
    after_state={"status": "CONFIRMED", "confidence": 1.0},
    draft_order_line_id=line_id
)
```

#### B. Customer Selection

When a user selects a customer from candidates:

```python
from backend.src.feedback.services import FeedbackService

feedback_event = FeedbackService.capture_customer_selected(
    db=db,
    org_id=org_id,
    actor_user_id=user_id,
    candidates=[
        {"customer_id": "...", "score": 0.9},
        {"customer_id": "...", "score": 0.7}
    ],
    selected_customer_id=selected_id,
    draft_order_id=draft_order_id
)
```

#### C. Line Edits

When a user edits a draft line (qty, price, SKU):

```python
from backend.src.feedback.services import FeedbackService

# In your PATCH /draft-orders/{id}/lines/{line_id} endpoint
feedback_event = FeedbackService.capture_line_corrected(
    db=db,
    org_id=org_id,
    actor_user_id=user_id,
    draft_order_id=draft_order_id,
    draft_order_line_id=line_id,
    before_values={"qty": 10, "unit_price": 5.50},
    after_values={"qty": 12, "unit_price": 5.50},
    document_id=document_id,
    layout_fingerprint=layout_fingerprint,  # from document
    input_snippet=pdf_text[:1500]  # first 1500 chars
)
```

### 5. Layout Fingerprinting for PDFs

When processing a PDF document, generate and store the layout fingerprint:

```python
from backend.src.feedback.services import LayoutService

# After extracting PDF metadata
document_metadata = {
    "page_count": 2,
    "page_dimensions": [(595, 842), (595, 842)],  # A4 pages
    "table_count": 1,
    "text_coverage_ratio": 0.65
}

# Generate fingerprint
layout_fingerprint = LayoutService.generate_fingerprint(document_metadata)

# Store in document record
document.layout_fingerprint = layout_fingerprint

# Create or update layout profile
profile = LayoutService.create_or_update_profile(
    db=db,
    org_id=org_id,
    document_id=document.id,
    layout_fingerprint=layout_fingerprint,
    fingerprint_method="PDF_TEXT_SHA256",
    anchors={
        "keywords": ["Bestellnummer", "Pos"],
        "page_count": 2,
        "text_chars": 4800
    }
)
```

### 6. Few-Shot Example Injection

Before calling the LLM for extraction, retrieve few-shot examples:

```python
from backend.src.feedback.services import LearningService

# Get few-shot examples for this layout
examples = LearningService.get_few_shot_examples(
    db=db,
    org_id=org_id,
    layout_fingerprint=document.layout_fingerprint,
    limit=3
)

# Inject into LLM prompt context
llm_context = {
    "document_text": pdf_text,
    "hint_examples": json.dumps(examples) if examples else ""
}

# Call LLM with enhanced context
result = llm_provider.extract(llm_context)
```

Example format injected into prompt:

```json
{
  "hint_examples": [
    {
      "input_snippet": "Bestellnummer: 12345\nPos 1: AB-123 10 ST",
      "output": {
        "order": {"order_number": "12345"},
        "lines": [{"position": "1", "customer_sku": "AB-123", "qty": 10, "uom": "ST"}]
      }
    }
  ]
}
```

### 7. Analytics Dashboard Integration

Create an admin dashboard that displays learning analytics:

```typescript
// Frontend example - fetch analytics
async function fetchLearningAnalytics(startDate: string, endDate: string) {
  const response = await fetch(
    `/api/v1/analytics/learning?start_date=${startDate}&end_date=${endDate}`
  );
  const data = await response.json();

  return {
    eventsByDay: data.events_by_day,
    correctedFields: data.corrected_fields,
    eventTypeDistribution: data.event_type_distribution,
    layoutStats: data.layout_stats
  };
}
```

Display charts for:
- **Events by Day** - Line chart showing feedback volume over time
- **Top Corrected Fields** - Bar chart showing which fields are most corrected (qty, sku, price)
- **Event Type Distribution** - Pie chart showing mapping vs extraction corrections
- **Layout Coverage** - Table showing unique layouts, seen_count, feedback_count

## API Reference

### Feedback Capture Endpoints

#### POST `/api/v1/sku-mappings/{mapping_id}/confirm`

Confirm a SKU mapping suggestion.

**Request:**
```json
{
  "customer_sku": "ABC-123",
  "internal_sku": "INT-999",
  "draft_order_line_id": "uuid",  // optional
  "confidence": 0.85  // optional
}
```

**Response:**
```json
{
  "id": "mapping-uuid",
  "status": "CONFIRMED",
  "feedback_event_id": "event-uuid"
}
```

#### POST `/api/v1/sku-mappings/{mapping_id}/reject`

Reject a SKU mapping suggestion.

**Request:**
```json
{
  "customer_sku": "ABC-123",
  "rejected_internal_sku": "INT-999",
  "draft_order_line_id": "uuid",  // optional
  "reason": "Wrong product category"  // optional
}
```

#### POST `/api/v1/draft-orders/{draft_order_id}/select-customer`

Select a customer from ambiguous candidates.

**Request:**
```json
{
  "customer_id": "uuid",
  "candidates": [
    {"customer_id": "uuid1", "score": 0.9},
    {"customer_id": "uuid2", "score": 0.7}
  ]
}
```

#### PATCH `/api/v1/draft-orders/{draft_order_id}/lines/{line_id}`

Edit a draft line (captures corrections).

**Request:**
```json
{
  "internal_sku": "INT-999",  // optional
  "qty": 12,  // optional
  "uom": "ST",  // optional
  "unit_price": 5.50  // optional
}
```

### Analytics Endpoints

#### GET `/api/v1/analytics/learning`

Get learning analytics (ADMIN/INTEGRATOR only).

**Query Parameters:**
- `start_date` (optional) - Start date (YYYY-MM-DD), defaults to 30 days ago
- `end_date` (optional) - End date (YYYY-MM-DD), defaults to today

**Response:**
```json
{
  "events_by_day": [
    {"date": "2026-01-01", "count": 45},
    {"date": "2026-01-02", "count": 52}
  ],
  "corrected_fields": [
    {"field": "qty", "count": 120},
    {"field": "sku", "count": 85}
  ],
  "event_type_distribution": [
    {"event_type": "MAPPING_CONFIRMED", "count": 250},
    {"event_type": "EXTRACTION_LINE_CORRECTED", "count": 180}
  ],
  "layout_stats": [
    {
      "fingerprint": "a1b2c3d4",
      "seen_count": 45,
      "feedback_count": 12,
      "last_seen_at": "2026-01-04T10:30:00Z"
    }
  ],
  "date_range": {
    "start_date": "2025-12-05",
    "end_date": "2026-01-04"
  }
}
```

#### GET `/api/v1/analytics/learning/layouts/{layout_fingerprint}`

Get feedback events for a specific layout.

**Query Parameters:**
- `limit` (optional) - Number of events (default 10, max 100)

#### GET `/api/v1/analytics/learning/few-shot-examples/{layout_fingerprint}`

Get few-shot examples for a layout (what LLM would receive).

**Query Parameters:**
- `limit` (optional) - Number of examples (default 3, max 10)

## Testing

### Unit Tests

Test layout fingerprint generation:

```python
def test_layout_fingerprint_generation():
    metadata = {
        "page_count": 2,
        "page_dimensions": [(595, 842), (595, 842)],
        "table_count": 1,
        "text_coverage_ratio": 0.65
    }

    fingerprint = LayoutService.generate_fingerprint(metadata)

    assert len(fingerprint) == 64  # SHA256 hex length
    assert fingerprint == LayoutService.generate_fingerprint(metadata)  # deterministic
```

Test few-shot example selection:

```python
def test_few_shot_example_selection(db_session, org_id, layout_fingerprint):
    # Create 5 feedback events
    for i in range(5):
        event = FeedbackEvent(
            org_id=org_id,
            event_type="EXTRACTION_LINE_CORRECTED",
            layout_fingerprint=layout_fingerprint,
            after_json={"qty": i},
            meta_json={"input_snippet": f"Example {i}"}
        )
        db_session.add(event)
    db_session.commit()

    # Get last 3
    examples = LearningService.get_few_shot_examples(
        db=db_session,
        org_id=org_id,
        layout_fingerprint=layout_fingerprint,
        limit=3
    )

    assert len(examples) == 3
    assert examples[0]["output"]["qty"] == 4  # Most recent
    assert examples[2]["output"]["qty"] == 2  # Third most recent
```

### Integration Tests

Test end-to-end feedback capture:

```python
def test_mapping_confirmation_creates_feedback(client, auth_headers, db_session):
    response = client.post(
        "/api/v1/sku-mappings/test-mapping-id/confirm",
        json={
            "customer_sku": "ABC-123",
            "internal_sku": "INT-999"
        },
        headers=auth_headers
    )

    assert response.status_code == 200

    # Verify feedback event was created
    event = db_session.query(FeedbackEvent).filter(
        FeedbackEvent.event_type == "MAPPING_CONFIRMED"
    ).first()

    assert event is not None
    assert event.after_json["internal_sku"] == "INT-999"
```

## Performance Considerations

### Feedback Capture

- Target latency: < 50ms (SSOT SC-007)
- Simple INSERT operations, no complex queries
- Indexed on (org_id, created_at) for fast writes

### Few-Shot Example Lookup

- Target latency: < 10ms (SSOT Implementation Notes)
- Indexed on (org_id, layout_fingerprint)
- LIMIT 3 query, minimal overhead
- No joins required

### Analytics Dashboard

- Target load time: < 2s for 90 days of data (SSOT SC-006)
- Aggregation queries use indexed fields
- Frontend caching recommended
- Consider pagination for large datasets

## Security & Multi-Tenancy

All queries are filtered by `org_id` to ensure tenant isolation:

```python
# ALWAYS filter by org_id
events = db.query(FeedbackEvent).filter(
    FeedbackEvent.org_id == current_user.org_id  # Tenant isolation
).all()
```

Analytics endpoints are restricted to ADMIN and INTEGRATOR roles:

```python
@router.get("/analytics/learning")
@require_role([Role.ADMIN, Role.INTEGRATOR])
def get_learning_analytics(...):
    # Only accessible to admins
```

## Data Retention

Per SSOT §11.5 and FR-019:
- Feedback events retained for **365 days**
- After retention period, run cleanup job to delete old events
- Layout profiles persist indefinitely (no retention limit)

Example cleanup job:

```python
from datetime import datetime, timedelta

def cleanup_old_feedback_events(db: Session):
    cutoff_date = datetime.utcnow() - timedelta(days=365)

    deleted = db.query(FeedbackEvent).filter(
        FeedbackEvent.created_at < cutoff_date
    ).delete()

    db.commit()
    return deleted
```

## Future Enhancements

This implementation provides the foundation for:

1. **Active Learning** - Use corrections to retrain matching weights
2. **Customer-Specific Mappings** - Build SKU mappings per customer from confirmations
3. **Extraction Confidence Scoring** - Improve confidence based on feedback patterns
4. **LLM Fine-Tuning** - Export corrections as training data for model improvement
5. **Correction Heatmaps** - Visualize problematic layouts and suppliers
6. **A/B Testing** - Measure accuracy improvement from few-shot learning

## Support

For questions or issues with the feedback module, refer to:
- Module documentation: `backend/src/feedback/README.md`
- SSOT specification: `SSOT_SPEC.md` §5.5.3, §5.5.5, §7.10
- Feature spec: `specs/024-feedback-learning/spec.md`
