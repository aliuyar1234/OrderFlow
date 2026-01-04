# Feedback & Learning Loop Module

This module implements the feedback capture and learning loop for OrderFlow, enabling continuous improvement without model retraining.

## Architecture Overview

The feedback system captures operator corrections and confirmations to:
1. **Improve matching** - Confirmed SKU mappings increase confidence for future matches
2. **Improve extraction** - Few-shot learning injects correction examples into LLM prompts
3. **Monitor quality** - Analytics track correction rates and identify problem areas

## Components

### Models (`models.py`)

**FeedbackEvent** (SSOT §5.5.5)
- Captures every operator correction or confirmation
- Stores before/after snapshots for learning
- Links to documents, drafts, and layout fingerprints

**DocLayoutProfile** (SSOT §5.5.3)
- Tracks unique PDF layouts by fingerprint
- Aggregates usage statistics (seen_count)
- Enables layout-aware few-shot learning

### Services (`services.py`)

**FeedbackService**
- `capture_mapping_confirmed()` - Records mapping confirmations
- `capture_mapping_rejected()` - Records mapping rejections
- `capture_customer_selected()` - Records customer selection from candidates
- `capture_line_corrected()` - Records line edits (qty, price, SKU)
- `capture_field_corrected()` - Records field-level corrections

**LayoutService**
- `generate_fingerprint()` - Creates SHA256 hash from PDF structure
- `create_or_update_profile()` - Tracks layout usage

**LearningService**
- `get_few_shot_examples()` - Retrieves last 3 corrections for a layout
- `get_learning_analytics()` - Aggregates metrics for dashboards

### API Endpoints

**Feedback Capture** (`endpoints.py`)
- `POST /api/v1/sku-mappings/{id}/confirm` - Confirm mapping
- `POST /api/v1/sku-mappings/{id}/reject` - Reject mapping
- `POST /api/v1/draft-orders/{id}/select-customer` - Select customer
- `PATCH /api/v1/draft-orders/{id}/lines/{line_id}` - Edit line (captures corrections)

**Analytics** (`analytics.py`)
- `GET /api/v1/analytics/learning` - Dashboard metrics
- `GET /api/v1/analytics/learning/layouts/{fingerprint}` - Layout-specific feedback
- `GET /api/v1/analytics/learning/few-shot-examples/{fingerprint}` - Preview examples

## Data Flow

### 1. Mapping Confirmation Flow

```
User confirms mapping in UI
    ↓
POST /sku-mappings/{id}/confirm
    ↓
FeedbackService.capture_mapping_confirmed()
    ↓
Creates FeedbackEvent (event_type=MAPPING_CONFIRMED)
    ↓
Updates sku_mapping: status=CONFIRMED, confidence=1.0, support_count += 1
    ↓
Future drafts auto-apply this mapping with match_method=exact_mapping
```

### 2. Few-Shot Learning Flow

```
PDF document ingested
    ↓
LayoutService.generate_fingerprint() → SHA256 hash
    ↓
Store in document.layout_fingerprint
    ↓
LayoutService.create_or_update_profile() → increment seen_count
    ↓
Before LLM extraction:
    ↓
LearningService.get_few_shot_examples(layout_fingerprint) → last 3 corrections
    ↓
Inject examples into LLM prompt as hint_examples
    ↓
LLM receives:
{
  "input_snippet": "...",
  "hint_examples": [
    {"input_snippet": "Pos 1 AB-123 10 ST", "output": {"lines": [{"sku": "AB123", "qty": 10}]}}
  ]
}
```

### 3. Line Correction Flow

```
Operator edits qty from 10 to 12 in UI
    ↓
PATCH /draft-orders/{id}/lines/{line_id} with qty=12
    ↓
FeedbackService.capture_line_corrected()
    ↓
Creates FeedbackEvent:
  - event_type=EXTRACTION_LINE_CORRECTED
  - before_json={"qty": 10}
  - after_json={"qty": 12}
  - layout_fingerprint=<from document>
  - meta_json.input_snippet=<first 1500 chars of PDF>
    ↓
Next PDF with same layout uses this as few-shot example
```

## Event Types (SSOT §5.5.5)

- **MAPPING_CONFIRMED** - User confirms suggested SKU mapping
- **MAPPING_REJECTED** - User rejects suggested SKU mapping
- **EXTRACTION_LINE_CORRECTED** - User edits entire line (qty, sku, uom, price)
- **EXTRACTION_FIELD_CORRECTED** - User edits single field
- **CUSTOMER_SELECTED** - User selects customer from ambiguous candidates
- **ISSUE_OVERRIDDEN** - User overrides validation issue

## Layout Fingerprinting

Layout fingerprints enable few-shot learning by grouping similar documents.

**Fingerprint Algorithm** (SSOT §7.10.3):
```python
fingerprint_data = {
    "page_count": 2,
    "page_dimensions": [(595, 842), (595, 842)],  # A4
    "table_count": 1,
    "text_coverage_ratio": 0.65
}
canonical_json = json.dumps(fingerprint_data, sort_keys=True)
fingerprint = hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
```

Documents from the same supplier typically have identical layouts, so corrections
on one document improve extraction on subsequent documents.

## Few-Shot Example Format

Examples injected into LLM prompts follow this format:

```json
{
  "hint_examples": [
    {
      "input_snippet": "Bestellnummer: 12345\nPos 1: AB-123 10 ST @5.50 EUR",
      "output": {
        "order": {"order_number": "12345"},
        "lines": [
          {
            "position": "1",
            "customer_sku": "AB-123",
            "qty": 10,
            "uom": "ST",
            "unit_price": 5.50,
            "currency": "EUR"
          }
        ]
      }
    }
  ]
}
```

## Analytics Metrics

The learning analytics dashboard provides:

**Events by Day** - Volume of feedback events over time (trend analysis)
**Top Corrected Fields** - Which fields are most frequently corrected (qty, sku, price)
**Event Type Distribution** - Breakdown by event type (mapping vs extraction corrections)
**Layout Coverage** - Number of unique layouts, seen_count, feedback_count

## Multi-Tenant Isolation

All feedback and examples are strictly isolated by `org_id`:
- Feedback events filter by `org_id`
- Few-shot examples only include same-org corrections
- Analytics aggregate only org-specific data
- Layout profiles are org-specific (same layout for different orgs = separate profiles)

## Performance Considerations

**Feedback Capture** - Must be < 50ms latency (SSOT SC-007)
- Feedback events are INSERT-only (no updates)
- Indexed on (org_id, created_at DESC)
- Async processing not needed (simple insert)

**Few-Shot Example Lookup** - Must be < 10ms (SSOT Implementation Notes)
- Indexed on (org_id, layout_fingerprint)
- Query limited to LIMIT 3
- No joins required (single table query)

**Analytics Dashboard** - Must load < 2s with 90 days of data (SSOT SC-006)
- Uses aggregation queries (COUNT, GROUP BY)
- Indexed on (org_id, event_type, created_at)
- Frontend caches results

## Data Retention

Per SSOT §11.5 and FR-019:
- Feedback events retained for **365 days**
- After retention period, events are deleted
- Layout profiles persist (no retention limit)
- Deletion is soft-delete or hard-delete based on compliance requirements

## Testing Strategy

**Unit Tests**
- Layout fingerprint generation with various metadata
- Few-shot example selection ordering and filtering
- Event serialization/deserialization

**Component Tests**
- FeedbackService methods create correct events
- LayoutService increments seen_count
- LearningService returns last 3 examples

**Integration Tests**
- End-to-end: confirm mapping → event exists → mapping updated
- End-to-end: correct line → process same layout → examples injected
- Analytics API queries return aggregated data

**E2E Tests**
- Operator confirms mapping in UI → auto-applied in next draft
- Operator corrects qty → analytics shows qty as top corrected field
- Admin views learning dashboard → charts render

## Future Enhancements

The current implementation provides foundation for:

**Active Learning** (T-024, T-025)
- Use corrections to retrain matching weights
- Build customer-specific SKU mappings
- Improve extraction confidence scoring

**LLM Fine-Tuning** (T-027)
- Export corrections as training data
- Fine-tune extraction models per layout
- Measure accuracy improvement (target: 15%+ per SSOT SC-005)

**Feedback Heatmaps** (T-029)
- Visualize correction patterns
- Identify problematic suppliers/layouts
- Prioritize improvement efforts

## Integration Points

**Matching Module** - Confirmed mappings update `sku_mapping` table
**Extraction Module** - Few-shot examples injected before LLM calls
**Draft Orders Module** - Line edits trigger feedback capture
**Customer Detection Module** - Customer selection creates feedback
**Auth Module** - Analytics restricted to ADMIN/INTEGRATOR roles

## References

- SSOT §5.5.3 - doc_layout_profile schema
- SSOT §5.5.5 - feedback_event schema
- SSOT §7.10 - Learning Loop requirements
- SSOT §7.10.2 - Mapping Feedback Loop
- SSOT §7.10.3 - Extraction Feedback (Layout-aware)
- SSOT §7.10.4 - Customer Selection Feedback
- SSOT T-704 - Feedback Event Capture acceptance criteria
- SSOT T-705 - Few-Shot Injection acceptance criteria
