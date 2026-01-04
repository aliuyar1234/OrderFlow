# Feature Specification: Feedback & Learning Loop

**Feature Branch**: `024-feedback-learning`
**Created**: 2025-12-27
**Status**: Draft
**Module**: feedback, ai
**SSOT References**: §5.5.5 (feedback_event), §5.5.3 (doc_layout_profile), §7.10 (Learning Loop), T-704, T-705

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Capture Feedback Events (Priority: P1)

Every operator action that corrects or confirms AI/extraction output (mapping confirms, line edits, customer selection) must be captured as a feedback_event for learning and quality monitoring.

**Why this priority**: Feedback capture is the foundation for all learning features. Without it, the system cannot improve over time or detect quality degradation. This is the data collection layer for continuous improvement.

**Independent Test**: Can be fully tested by confirming a SKU mapping in UI, querying feedback_event table, and verifying that event contains before/after data and actor information.

**Acceptance Scenarios**:

1. **Given** operator clicks "Confirm Mapping" for a SKU mapping suggestion, **When** action completes, **Then** feedback_event is created with `event_type=MAPPING_CONFIRMED`, `before_json` (suggestions), `after_json` (chosen SKU)
2. **Given** operator edits a draft line's `qty` from 10 to 12, **When** PATCH request completes, **Then** feedback_event is created with `event_type=EXTRACTION_LINE_CORRECTED`, `before_json={"qty": 10}`, `after_json={"qty": 12}`
3. **Given** operator selects customer from ambiguous candidates, **When** customer_id is set, **Then** feedback_event is created with `event_type=CUSTOMER_SELECTED`, `before_json` (candidates), `after_json` (selected customer_id)
4. **Given** operator rejects a mapping suggestion, **When** action completes, **Then** feedback_event is created with `event_type=MAPPING_REJECTED`, `details_json` contains rejected internal_sku
5. **Given** feedback_event is created, **When** querying database, **Then** record contains `org_id`, `actor_user_id`, `event_type`, `before_json`, `after_json`, `created_at`

---

### User Story 2 - Layout Fingerprinting for PDFs (Priority: P1)

When a PDF is processed, the system must generate a layout fingerprint (hash of structure/dimensions) to group similar documents for targeted learning.

**Why this priority**: Layout fingerprinting enables few-shot learning. Documents with the same layout (e.g., from same supplier) benefit from corrections made on previous documents. This is the clustering mechanism for layout-aware prompts.

**Independent Test**: Can be fully tested by processing two PDFs with identical layouts, verifying that both have the same `layout_fingerprint`, and confirming that `doc_layout_profile` aggregates them.

**Acceptance Scenarios**:

1. **Given** a PDF with specific page dimensions and table structure, **When** document is processed, **Then** `document.layout_fingerprint` is computed as SHA256 hash of layout metadata
2. **Given** two PDFs from same supplier (same layout), **When** both are processed, **Then** both have identical `layout_fingerprint`
3. **Given** a PDF with a unique layout, **When** processed, **Then** new `doc_layout_profile` record is created with `layout_fingerprint`, `seen_count=1`
4. **Given** second PDF with same fingerprint is processed, **When** layout is detected, **Then** existing `doc_layout_profile.seen_count` increments to 2
5. **Given** layout fingerprint is computed, **When** stored in `document` table, **Then** fingerprint is indexed for fast lookup

---

### User Story 3 - Few-Shot Example Injection (Priority: P1)

When extracting a PDF with a known layout fingerprint, the system must inject the last 3 corrected examples (from feedback_events) into the LLM prompt to improve extraction accuracy.

**Why this priority**: Few-shot learning is the primary improvement mechanism for LLM extraction. By showing the LLM past corrections for the same layout, accuracy increases without model retraining. This is the learning loop's output.

**Independent Test**: Can be fully tested by correcting extraction errors for a specific layout, processing a new PDF with the same layout, and verifying that the LLM prompt contains the correction examples.

**Acceptance Scenarios**:

1. **Given** operator corrected 3 extraction errors for layout fingerprint `abc123`, **When** new PDF with same fingerprint is extracted, **Then** LLM prompt includes `hint_examples` array with 3 correction examples
2. **Given** no feedback exists for a layout, **When** PDF is extracted, **Then** LLM prompt has empty `hint_examples` (no injection)
3. **Given** 10 feedback events exist for a layout, **When** selecting examples, **Then** only the 3 most recent (by created_at DESC) are used
4. **Given** feedback example includes corrected line data, **When** injected into prompt, **Then** example contains `input_snippet` (first 1500 chars of PDF text) and `output` (corrected JSON)
5. **Given** examples are from different org, **When** selecting examples, **Then** only examples from same org_id are used (org isolation)

---

### User Story 4 - Mapping Feedback Loop (Priority: P2)

Confirmed SKU mappings must update the `sku_mapping` table with higher confidence and support_count, influencing future matching suggestions.

**Why this priority**: Mapping feedback directly improves matching quality over time. However, initial matching (P1) must exist first. This is an incremental improvement feature.

**Independent Test**: Can be fully tested by confirming a mapping, verifying that sku_mapping.status=CONFIRMED and support_count increments, then processing a new draft and verifying the mapping is auto-applied.

**Acceptance Scenarios**:

1. **Given** operator confirms mapping from customer_sku "ABC-123" to internal_sku "INT-999", **When** confirmation is saved, **Then** sku_mapping record is created/updated with `status=CONFIRMED`, `confidence=1.0`, `support_count += 1`
2. **Given** confirmed mapping exists, **When** new draft contains same customer_sku, **Then** matching engine auto-applies the confirmed mapping with `match_method=exact_mapping`
3. **Given** confirmed mapping is used in new draft, **When** matching completes, **Then** feedback_event is NOT created (only manual confirmations/corrections create feedback)
4. **Given** operator rejects a suggested mapping, **When** rejection is saved, **Then** sku_mapping status changes to REJECTED and confidence drops
5. **Given** multiple confirmed mappings for same customer_sku (different customers), **When** matching runs, **Then** customer-specific mapping is used (filtered by customer_id)

---

### User Story 5 - Learning Analytics Dashboard (Priority: P3)

Administrators need visibility into learning loop effectiveness: feedback event volumes, layout coverage, correction rates, and quality trends over time.

**Why this priority**: Analytics provide visibility into system improvement and highlight problem areas. However, data collection (P1) must happen first. This is a reporting/monitoring feature.

**Independent Test**: Can be fully tested by querying aggregated feedback_event data and displaying metrics in a UI dashboard (charts, tables).

**Acceptance Scenarios**:

1. **Given** admin opens learning analytics page, **When** page loads, **Then** charts show: feedback events per day (last 30 days), top corrected fields, layout coverage
2. **Given** 100 feedback events with `event_type=EXTRACTION_LINE_CORRECTED`, **When** aggregating by field, **Then** chart shows: qty corrected 40 times, sku corrected 30 times, uom corrected 20 times, price corrected 10 times
3. **Given** 10 unique layout fingerprints exist, **When** viewing layout coverage, **Then** table shows: fingerprint, seen_count, feedback_count, last_seen_at
4. **Given** extraction confidence trend data, **When** viewing chart, **Then** line graph shows average extraction_confidence over time (improving or degrading)
5. **Given** operator wants to see corrections for a specific layout, **When** filtering by fingerprint, **Then** table shows all feedback_events for that layout with before/after diffs

---

### Edge Cases

- What happens when feedback_event.before_json is very large (10MB)? (Store only relevant fields, not entire draft; truncate if needed)
- How does system handle feedback for deleted drafts? (Feedback persists for retention period; draft_order_id reference remains even if draft is soft-deleted)
- What if layout fingerprint collides (SHA256 collision)? (Astronomically unlikely; no special handling needed)
- What happens when operator corrects same field multiple times? (Each correction creates new feedback_event; few-shot uses most recent)
- How does system handle feedback from different users for same draft? (All feedback is captured with actor_user_id; last correction wins)
- What if layout fingerprint changes slightly (minor PDF update)? (New fingerprint is created; examples don't transfer; acceptable tradeoff)

## Requirements *(mandatory)*

### Technical Constraints

- **TC-006**: feedback_event.before_json and after_json MUST NOT exceed 10KB each. For large payloads, store only changed fields + context (e.g., line_id, field_name, old_value, new_value). Truncate descriptions to 500 chars if needed.

### Functional Requirements

- **FR-001**: System MUST implement `feedback_event` table per §5.5.5 schema
- **FR-002**: System MUST implement `doc_layout_profile` table per §5.5.3 schema
- **FR-003**: System MUST capture feedback_event for: MAPPING_CONFIRMED, MAPPING_REJECTED, EXTRACTION_LINE_CORRECTED, EXTRACTION_FIELD_CORRECTED, CUSTOMER_SELECTED
- **FR-004**: System MUST store before_json (original values) and after_json (corrected values) in feedback_event
- **FR-005**: System MUST generate layout_fingerprint for PDF documents as SHA256 hash of: page_count, page_dimensions, table_count, text_coverage_ratio
- **FR-006**: System MUST store layout_fingerprint in `document.layout_fingerprint` field
- **FR-007**: System MUST create or update `doc_layout_profile` when new layout fingerprint is encountered
- **FR-008**: System MUST increment `doc_layout_profile.seen_count` each time layout is processed
- **FR-009**: System MUST query last 3 feedback_events for a layout_fingerprint when preparing LLM prompt
- **FR-010**: System MUST filter feedback examples by org_id (org isolation)
- **FR-011**: System MUST inject examples into LLM prompt as `hint_examples` array in user context
- **FR-012**: System MUST format examples as: `[{"input_snippet": "...", "output": {...}}]` per §7.10.3
- **FR-013**: System MUST truncate input_snippet to first 1500 characters of PDF text
- **FR-014**: System MUST update sku_mapping on MAPPING_CONFIRMED: set status=CONFIRMED, confidence=1.0, support_count += 1
- **FR-015**: System MUST NOT create feedback_event when auto-applying confirmed mappings (only manual actions)
- **FR-016**: System MUST expose API: GET `/analytics/learning?start_date=X&end_date=Y` for admin dashboard
- **FR-017**: System MUST aggregate feedback_event by event_type, field_name, layout_fingerprint
- **FR-018**: System MUST calculate correction_rate = (corrected_extractions / total_extractions) per layout
- **FR-019**: System MUST retain feedback_events for 365 days (per §11.5 data retention)
- **FR-020**: System MUST restrict feedback analytics to ADMIN and INTEGRATOR roles

### Key Entities *(include if feature involves data)*

- **FeedbackEvent** (§5.5.5): Captures operator corrections and confirmations with before/after snapshots. Links to draft_order, actor_user, and optionally layout_fingerprint. Used for learning and quality monitoring.

- **DocLayoutProfile** (§5.5.3): Aggregates metadata for PDF layouts. Tracks seen_count, example_count (feedback events), and statistics. Used to select few-shot examples for extraction.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Feedback events are captured for 100% of manual corrections (mapping confirms, line edits, customer selections)
- **SC-002**: Layout fingerprints are generated for 100% of PDF documents processed
- **SC-003**: Few-shot examples are injected correctly in 100% of extractions where feedback exists (verified in component tests)
- **SC-004**: Confirmed mappings increase sku_mapping.support_count in 100% of cases
- **SC-005**: Few-shot injection improves extraction accuracy by 15%+ for layouts with 3+ feedback examples (measured in A/B test)
- **SC-006**: Learning analytics dashboard loads within 2 seconds with 90 days of data (performance test)
- **SC-007**: Feedback event capture adds < 50ms latency to operator actions (measured in E2E tests)

## Dependencies

- **Depends on**:
  - **001-database-setup**: Requires feedback_event and doc_layout_profile tables
  - **010-draft-orders**: Requires draft_order for linking feedback events
  - **013-pdf-extraction**: Requires document entity and PDF processing for layout fingerprinting
  - **012-matching**: Requires sku_mapping for mapping feedback loop
  - **002-auth**: Requires user context for actor_user_id tracking

- **Enables**:
  - **Continuous improvement**: System learns from corrections without model retraining
  - **Quality monitoring**: Operators and admins can track extraction accuracy trends

## Implementation Notes

**Few-Shot Injection Timing**: (1) Document received → (2) Layout fingerprint computed from first page → (3) Query feedback_events for matching fingerprint examples (<10ms SLA) → (4) Build LLM prompt with examples injected → (5) Call LLM. Example lookup MUST complete within 10ms; use indexed query on layout_fingerprint.

**Mapping Scope**: Confirmed SKU mappings are customer-specific and apply to ALL future extractions for that customer, regardless of document layout. Layout fingerprinting is separate optimization for few-shot LLM examples only. Both mechanisms work independently.

### Layout Fingerprint Generation

```python
import hashlib
import json

def generate_layout_fingerprint(document_metadata: dict) -> str:
    """Generate SHA256 fingerprint from PDF layout metadata."""
    fingerprint_data = {
        "page_count": document_metadata.get("page_count"),
        "page_dimensions": document_metadata.get("page_dimensions"),  # [(width, height), ...]
        "table_count": document_metadata.get("table_count"),
        "text_coverage_ratio": round(document_metadata.get("text_coverage_ratio", 0), 2)
    }

    # Normalize to JSON string for consistent hashing
    canonical_json = json.dumps(fingerprint_data, sort_keys=True)
    return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
```

### Feedback Event Capture (Mapping Confirm)

```python
@app.post("/sku-mappings/{id}/confirm")
@require_role(Role.OPERATOR)
def confirm_sku_mapping(id: UUID, current_user: User):
    mapping = get_sku_mapping(id, current_user.org_id)

    # Capture before state
    before_json = {
        "status": mapping.status,
        "confidence": mapping.confidence,
        "support_count": mapping.support_count
    }

    # Update mapping
    mapping.status = MappingStatus.CONFIRMED
    mapping.confidence = 1.0
    mapping.support_count += 1
    mapping.last_used_at = datetime.utcnow()

    # Create feedback event
    feedback_event = FeedbackEvent(
        org_id=current_user.org_id,
        actor_user_id=current_user.id,
        event_type="MAPPING_CONFIRMED",
        before_json=before_json,
        after_json={
            "status": mapping.status,
            "confidence": mapping.confidence,
            "internal_sku": mapping.internal_sku
        },
        entity_type="sku_mapping",
        entity_id=mapping.id
    )

    db.session.add(feedback_event)
    db.session.commit()

    return {"id": mapping.id, "status": mapping.status}
```

### Few-Shot Example Injection

```python
def get_few_shot_examples(layout_fingerprint: str, org_id: UUID, limit: int = 3) -> list:
    """Retrieve last N feedback examples for a layout."""
    feedback_events = db.session.query(FeedbackEvent).filter(
        FeedbackEvent.org_id == org_id,
        FeedbackEvent.layout_fingerprint == layout_fingerprint,
        FeedbackEvent.event_type.in_([
            "EXTRACTION_LINE_CORRECTED",
            "EXTRACTION_FIELD_CORRECTED"
        ])
    ).order_by(FeedbackEvent.created_at.desc()).limit(limit).all()

    examples = []
    for event in feedback_events:
        # Extract input snippet from meta_json
        input_snippet = event.meta_json.get("input_snippet", "")[:1500]

        examples.append({
            "input_snippet": input_snippet,
            "output": event.after_json  # Corrected extraction result
        })

    return examples

def prepare_llm_prompt(document: Document, context: dict) -> str:
    """Prepare LLM extraction prompt with few-shot examples if available."""
    few_shot_examples = []

    if document.layout_fingerprint:
        few_shot_examples = get_few_shot_examples(
            layout_fingerprint=document.layout_fingerprint,
            org_id=document.org_id,
            limit=3
        )

    context["hint_examples"] = json.dumps(few_shot_examples) if few_shot_examples else ""

    # Inject into prompt template (see §7.5.3 pdf_extract_text_v1)
    return render_template("pdf_extract_text_v1", context)
```

### Learning Analytics Query

```python
@app.get("/analytics/learning")
@require_role([Role.ADMIN, Role.INTEGRATOR])
def get_learning_analytics(
    start_date: date,
    end_date: date,
    current_user: User
):
    # Feedback events over time
    events_by_day = db.session.query(
        func.date(FeedbackEvent.created_at).label("date"),
        func.count(FeedbackEvent.id).label("count")
    ).filter(
        FeedbackEvent.org_id == current_user.org_id,
        FeedbackEvent.created_at >= start_date,
        FeedbackEvent.created_at <= end_date
    ).group_by(func.date(FeedbackEvent.created_at)).all()

    # Top corrected fields
    corrected_fields = db.session.query(
        FeedbackEvent.after_json.op("->>")("field").label("field"),
        func.count().label("count")
    ).filter(
        FeedbackEvent.org_id == current_user.org_id,
        FeedbackEvent.event_type == "EXTRACTION_FIELD_CORRECTED"
    ).group_by("field").order_by(func.count().desc()).limit(10).all()

    # Layout coverage
    layout_stats = db.session.query(
        DocLayoutProfile.layout_fingerprint,
        DocLayoutProfile.seen_count,
        DocLayoutProfile.example_count,
        DocLayoutProfile.last_seen_at
    ).filter(
        DocLayoutProfile.org_id == current_user.org_id
    ).order_by(DocLayoutProfile.seen_count.desc()).all()

    return {
        "events_by_day": [{"date": str(e.date), "count": e.count} for e in events_by_day],
        "corrected_fields": [{"field": f.field, "count": f.count} for f in corrected_fields],
        "layout_stats": [
            {
                "fingerprint": ls.layout_fingerprint[:8],  # Truncate for display
                "seen_count": ls.seen_count,
                "example_count": ls.example_count,
                "last_seen_at": ls.last_seen_at.isoformat()
            }
            for ls in layout_stats
        ]
    }
```

### Database Schema

```sql
CREATE TABLE feedback_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organization(id),
    actor_user_id UUID NULL REFERENCES user(id),
    event_type TEXT NOT NULL,  -- MAPPING_CONFIRMED, EXTRACTION_LINE_CORRECTED, etc.
    entity_type TEXT NULL,  -- sku_mapping, draft_order_line, etc.
    entity_id UUID NULL,
    draft_order_id UUID NULL REFERENCES draft_order(id),
    layout_fingerprint TEXT NULL,  -- Link to doc_layout_profile
    before_json JSONB NOT NULL DEFAULT '{}',
    after_json JSONB NOT NULL DEFAULT '{}',
    meta_json JSONB NOT NULL DEFAULT '{}',  -- For input_snippet, etc.
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_feedback_event_layout ON feedback_event(org_id, layout_fingerprint, created_at DESC);
CREATE INDEX idx_feedback_event_type ON feedback_event(org_id, event_type, created_at DESC);

CREATE TABLE doc_layout_profile (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organization(id),
    layout_fingerprint TEXT NOT NULL,
    seen_count INT DEFAULT 1,
    example_count INT DEFAULT 0,  -- Count of feedback_events for this layout
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    stats_json JSONB NOT NULL DEFAULT '{}',  -- Avg page_count, avg text_coverage, etc.
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_doc_layout_profile UNIQUE (org_id, layout_fingerprint)
);

CREATE INDEX idx_doc_layout_profile_seen ON doc_layout_profile(org_id, seen_count DESC);
```

## Testing Strategy

### Unit Tests
- Layout fingerprint generation with various PDF metadata
- Few-shot example selection: last 3, org filtering, ordering
- Feedback event JSON serialization/deserialization
- Mapping support_count increment logic

### Component Tests
- FeedbackService.capture_mapping_confirmed() creates feedback_event
- FeedbackService.get_few_shot_examples() returns correct examples
- LLM prompt builder with hint_examples injection
- DocLayoutProfile creation and seen_count increment

### Integration Tests
- End-to-end: Confirm mapping → feedback_event exists → sku_mapping updated
- End-to-end: Correct extraction → process PDF with same layout → examples injected in prompt
- Analytics API: query feedback events → aggregate by type/field → return JSON
- Layout profile: process 3 PDFs with same layout → seen_count = 3

### E2E Tests
- Operator confirms mapping in UI → feedback captured → next draft auto-applies mapping
- Operator corrects qty in draft line → feedback captured → analytics dashboard shows qty as top corrected field
- Admin opens learning analytics → charts render with real data

## SSOT Compliance Checklist

- [ ] `feedback_event` table schema matches §5.5.5
- [ ] `doc_layout_profile` table schema matches §5.5.3
- [ ] Feedback event types match §7.10 (MAPPING_CONFIRMED, EXTRACTION_LINE_CORRECTED, CUSTOMER_SELECTED, etc.)
- [ ] Layout fingerprint generation uses §7.10.3 algorithm (SHA256 of page_count, dimensions, table_count, text_coverage)
- [ ] Few-shot example format matches §7.10.3 (input_snippet, output JSON)
- [ ] Example selection: last 3 by created_at DESC, org-filtered per §7.10.3
- [ ] Input snippet truncated to 1500 chars per §7.10.3
- [ ] Mapping feedback updates sku_mapping per §7.10.1 (status=CONFIRMED, confidence=1.0, support_count += 1)
- [ ] Feedback events retained for 365 days per §11.5
- [ ] T-704 acceptance criteria met (mapping/extraction edits create feedback_event)
- [ ] T-705 acceptance criteria met (last 3 examples injected for same layout, org-filtered)

**SSOT Compliance - Few-Shot Schema**: Few-shot schema is self-defined in this spec (see Example Selection Algorithm and Few-Shot Example Injection section). SSOT §7.10 reference is for learning loop metrics, not schema definition. Schema: {example_id, layout_fingerprint, input_snippet, expected_output, confidence_improvement}.
