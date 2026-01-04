# Feature Specification: LLM-Based Extractors (Text + Vision)

**Feature Branch**: `012-extractors-llm`
**Created**: 2025-12-27
**Status**: Draft
**Module**: extraction, ai
**SSOT Refs**: §7.5 (LLM Extraction), §7.5.3 (Prompt Templates), §7.5.4 (Parsing), §7.5.5 (Fallback), §7.5.6 (Error Handling), T-308, T-309

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Scanned PDF Order Extraction via Vision LLM (Priority: P1)

An Ops user receives a scanned/image-based PDF purchase order. The system detects low text coverage and automatically uses vision LLM to extract order data, creating a reviewable Draft.

**Why this priority**: Many B2B customers still send scanned orders. Vision LLM enables extraction where OCR or rule-based methods fail.

**Independent Test**: Upload scanned PDF (text_coverage_ratio <0.15) → vision LLM extracts order header + lines → Draft created with extraction_confidence ≥0.70.

**Acceptance Scenarios**:

1. **Given** PDF with text_coverage_ratio=0.08, **When** decision logic evaluates, **Then** system triggers LLM_EXTRACT_PDF_VISION call
2. **Given** vision LLM processes 3-page scanned order, **When** extraction completes, **Then** Draft contains header (order_number, date, currency) and ≥90% of visible line items
3. **Given** vision LLM returns structured JSON, **When** parsing, **Then** system validates against schema, normalizes UoM, assigns line_no

---

### User Story 2 - Unstructured Text PDF Extraction via Text LLM (Priority: P1)

An Ops user receives a text-based PDF with poor/irregular table structure. Rule-based extraction yields confidence <0.60, triggering text LLM extraction that successfully extracts order data.

**Why this priority**: Many customer orders are "PDF exports" with inconsistent formatting. Text LLM handles variability rule-based parsers can't.

**Independent Test**: Upload text PDF with irregular layout → rule-based confidence=0.45 → text LLM extraction triggered → extraction_confidence improves to ≥0.75.

**Acceptance Scenarios**:

1. **Given** rule-based extraction yields extraction_confidence=0.50, **When** decision logic evaluates per §7.2.2.B, **Then** LLM_EXTRACT_PDF_TEXT is triggered
2. **Given** text LLM processes order with embedded notes and signatures, **When** extracting, **Then** system extracts clean order data, ignores irrelevant text, sets customer_hint from letterhead
3. **Given** LLM output includes per-field confidence scores, **When** storing extraction, **Then** confidence values are preserved in extraction result JSON

---

### User Story 3 - JSON Repair for Malformed LLM Output (Priority: P2)

LLM returns invalid JSON (e.g., trailing comma, unquoted keys). The system automatically calls json_repair_v1 prompt to fix the output without failing the extraction.

**Why this priority**: LLMs occasionally produce invalid JSON despite schema instructions. Automatic repair reduces manual intervention.

**Independent Test**: Mock LLM returns malformed JSON → system calls repair prompt → valid JSON returned → extraction succeeds.

**Acceptance Scenarios**:

1. **Given** LLM returns JSON with syntax error (e.g., trailing comma in array), **When** parsing fails, **Then** system calls repair_invalid_json() with error message
2. **Given** repair call returns valid JSON, **When** re-parsing, **Then** extraction succeeds, ai_call_log shows two entries (extract + repair)
3. **Given** repair call also fails, **When** extraction finalizes, **Then** Draft is created with 0 lines, status=NEEDS_REVIEW, issue=LLM_OUTPUT_INVALID

---

### User Story 4 - Hallucination Detection and Confidence Penalties (Priority: P1)

The system validates LLM output against source document using anchor checks. If extracted data doesn't appear in source text, confidence is penalized and warnings are generated.

**Why this priority**: LLMs can hallucinate data. Anchor checks prevent accepting fabricated order lines.

**Independent Test**: Mock LLM returns line with customer_sku="FAKE-123" not in source → anchor check fails → line confidence reduced by 50%, warning logged.

**Acceptance Scenarios**:

1. **Given** LLM extracts line with customer_sku_raw="ABC-999", **When** anchor check scans source text, **Then** if "ABC-999" not found (case-insensitive), line confidence *= 0.5 and warning added
2. **Given** LLM extracts qty=500 for a line, **When** anchor check runs, **Then** if "500" appears in source near SKU/description, no penalty
3. **Given** >30% of lines fail anchor check, **When** calculating extraction_confidence, **Then** overall confidence *= 0.7 per §7.8.1

---

### User Story 5 - Fallback Chain and Manual Entry (Priority: P2)

LLM extraction fails (timeout, budget gate, invalid output after repair). The system creates a Draft with 0 lines, allowing manual entry, and offers "Retry with AI" button.

**Why this priority**: Ensures orders are never lost due to extraction failures. Manual entry is ultimate fallback.

**Independent Test**: Trigger LLM timeout → extraction fails → Draft created with 0 lines, status=NEEDS_REVIEW, UI shows "Add lines manually" and "Retry with AI" button.

**Acceptance Scenarios**:

1. **Given** LLM call times out after 60s, **When** extraction job completes, **Then** Draft is created with lines=[], issues=[LLM_OUTPUT_INVALID], status=NEEDS_REVIEW
2. **Given** budget gate blocks LLM call, **When** extraction completes, **Then** Draft uses rule-based result if available, else 0 lines, UI shows budget exceeded message
3. **Given** Draft with extraction failure, **When** Ops clicks "Retry with AI", **Then** new extraction_run is created, LLM is called again (bypass cache, respect budget)

---

### User Story 6 - Layout Fingerprinting and Few-Shot Learning (Priority: P3)

The system calculates a layout fingerprint for each PDF. When Ops corrects extraction errors, corrections are stored and injected as few-shot examples for future PDFs with the same layout.

**Why this priority**: Enables learning from corrections without fine-tuning. Improves accuracy over time for recurring order formats.

**Independent Test**: Process PDF with layout_fingerprint=X → Ops corrects extraction → next PDF with same fingerprint uses correction as example → extraction accuracy improves.

**Acceptance Scenarios**:

1. **Given** PDF processed, **When** extraction completes, **Then** system calculates layout_fingerprint (sha256 of structural metadata)
2. **Given** Ops corrects line qty from 10 to 100, **When** saving, **Then** feedback_event is created with before/after, layout_fingerprint
3. **Given** new PDF with same layout_fingerprint, **When** LLM prompt is built, **Then** last 3 corrections for this fingerprint are included as hint_examples per §7.10.3

---

### Edge Cases

- What happens when vision LLM returns 0 lines despite visible table in image?
- How does system handle extremely long order text (>100k characters, exceeds token limit)?
- What happens when LLM returns lines_count=500 (exceeds max_lines=500 limit)?
- How does system handle PDFs with mixed scanned and text pages?
- What happens when json_repair fails to produce valid JSON?
- How does system handle non-English orders (Chinese, Arabic characters)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST implement extractor_version=`llm_v1` supporting:
  - Text-based PDF extraction via LLM_EXTRACT_PDF_TEXT
  - Image-based PDF extraction via LLM_EXTRACT_PDF_VISION
  - JSON repair via LLM_REPAIR_JSON
- **FR-002**: System MUST use exact prompt templates from §7.5.3:
  - `pdf_extract_text_v1` with context variables substitution
  - `pdf_extract_vision_v1` with page images
  - `json_repair_v1` with schema and error message
- **FR-003**: System MUST populate prompt context with:
  - `from_email`, `subject` from inbound_message
  - `default_currency` from org.settings
  - `canonical_uoms` list (ST,M,CM,MM,KG,G,L,ML,KAR,PAL,SET)
  - `known_customer_numbers_csv` from customer.erp_customer_number
  - `hint_examples` from feedback_events for matching layout_fingerprint (Top 3)
- **FR-004**: System MUST parse LLM output per §7.5.4:
  - Strip whitespace, reject if doesn't start with `{`
  - json.loads → if fail → call LLM_REPAIR_JSON once
  - Validate against Pydantic schema (strict mode: no unknown keys, correct types)
  - Enforce max_lines limit (default 500)
- **FR-005**: System MUST normalize LLM output:
  - Map UoM strings to canonical codes (case-insensitive)
  - Normalize currency to ISO 4217 (EUR, CHF, USD)
  - Re-number line_no sequentially 1..n if gaps/duplicates detected
  - Convert dates to YYYY-MM-DD
- **FR-006**: System MUST implement sanity checks per §7.5.4 item 6:
  - **Anchor Check**: For each line, verify at least one of (customer_sku_raw, 8+ char token from description, qty as string) appears in source text (case-insensitive, whitespace-normalized). If fail → line confidence *= 0.5, warning added
  - **Range Check**: qty must be 0 < qty <= max_qty (default 1,000,000). If exceeded → qty=null, warning added
  - **Lines Count Check**: If lines_count >200 and page_count <=2 → overall confidence *= 0.7, warning added
- **FR-007**: System MUST calculate extraction_confidence per §7.8.1 including sanity penalties
- **FR-008**: System MUST handle LLM errors per §7.5.6:
  - Timeout → status=FAILED, error_json=timeout, fallback
  - Rate limit → status=FAILED, error_json=rate_limit, fallback
  - Invalid JSON (after repair) → status=FAILED, error_json=invalid_json, fallback
  - Schema mismatch → status=FAILED, error_json=schema_mismatch, fallback
  - Suspicious output (sanity checks) → status=SUCCEEDED, confidence capped at 0.55, issue=LLM_SUSPICIOUS_OUTPUT
- **FR-009**: System MUST implement fallback chain per §7.5.5:
  - Rule-based (rule_v1) always runs first for text PDFs
  - If confidence <0.60 OR lines_count==0 → trigger LLM
  - If LLM fails → create Draft with rule-based lines (if any) else 0 lines
  - Set status=NEEDS_REVIEW, add issues: LOW_CONFIDENCE_EXTRACTION, LLM_OUTPUT_INVALID
- **FR-010**: System MUST calculate layout_fingerprint for PDFs:
  - Extract structural metadata: page_count, median line length, table detection heuristics, font info (if available)
  - Calculate sha256(structural_metadata_json)
  - Store in document.layout_fingerprint
- **FR-011**: System MUST store extraction results in canonical JSON per §7.1 including:
  - order header fields
  - lines array
  - confidence object (per-field + overall)
  - warnings array
  - extractor_version="llm_v1"
- **FR-012**: Vision LLM multi-page handling:
  1. Estimate tokens per page ≈ 1500
  2. Max pages per batch = floor(max_tokens / 1500)
  3. No page overlap between batches
  4. Merge batch results by line_no (append lines from subsequent batches)
  5. Log batch_count and pages_per_batch in extraction_run.metrics_json
- **FR-013**: System MUST create validation issues:
  - `LOW_CONFIDENCE_EXTRACTION` (WARNING) if extraction_confidence <0.60
  - `LLM_OUTPUT_INVALID` (WARNING/ERROR) if LLM failed or suspicious
  - `MISSING_PRICE` (WARNING) if unit_price is null for lines
- **FR-014**: System MUST support "Retry with AI" action:
  - Available when draft.status=NEEDS_REVIEW and extraction failed/low confidence
  - Creates new extraction_run with extractor_version=llm_v1
  - Bypasses deduplication cache
  - Respects budget/page/token gates

### Key Entities

- **ExtractionRun**: Links to document, stores extractor_version=llm_v1, metrics_json (tokens, latency, cost)
- **Document**: Contains layout_fingerprint, extracted_text_storage_key
- **AICallLog**: Records LLM_EXTRACT_PDF_TEXT, LLM_EXTRACT_PDF_VISION, LLM_REPAIR_JSON calls
- **FeedbackEvent**: Stores extraction corrections with layout_fingerprint for few-shot learning
- **DocLayoutProfile** (§5.5.3): Aggregates feedback for layout fingerprints

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Vision LLM extracts ≥85% of lines from scanned PDFs with clear table structure
- **SC-002**: Text LLM improves extraction_confidence by ≥0.20 on average when rule-based <0.60
- **SC-003**: JSON repair succeeds in ≥90% of invalid JSON cases
- **SC-004**: Anchor checks reduce hallucinated lines by ≥80% (false positive rate <5%)
- **SC-005**: LLM extraction p95 latency <12s for text mode, <25s for vision mode
- **SC-006**: Fallback chain ensures 100% of orders create Draft (even if 0 lines)
- **SC-007**: Layout fingerprinting + few-shot examples improve repeat-format accuracy by ≥15% after 5+ corrections
- **SC-008**: LLM errors are handled gracefully in 100% of cases (no worker crashes)

## Dependencies

- **Depends on**:
  - 010-extractors-rule-based (rule-based extraction runs first)
  - 011-llm-provider-layer (LLMProviderPort for API calls)
  - Document storage (extracted_text_storage_key, page images)
  - Organization settings (AI config)

- **Blocks**:
  - 013-draft-orders-core (needs extraction results)
  - 018-customer-detection (uses customer_hint from LLM extraction)

## Technical Notes

### Implementation Guidance

**Prompt Building:**
- Load templates from §7.5.3 (store in Python string constants or config files)
- Substitute variables: `{{from_email}}`, `{{subject}}`, `{{pdf_text}}`, etc.
- For few-shot examples:
  - Query feedback_events WHERE layout_fingerprint=X AND event_type='EXTRACTION_LINE_CORRECTED' ORDER BY created_at DESC LIMIT 3
  - Format as JSON array: `[{"input_snippet":"...","output":{...}}]`
  - Inject into prompt context

**Vision LLM:**
- Convert PDF pages to PNG images (300 DPI)
- Base64 encode images
- Send via OpenAI vision API with `gpt-4o` model
- Handle multi-page: combine all pages in single API call if total tokens < limit, else batch

**Anchor Check Algorithm:**
- normalize(text) = UPPER(text) with whitespace collapsed to single space
- For SKU anchor: exact substring match required
- For description anchor: match any 8+ character token
- For qty anchor: extract digits only, match as substring
- Example: 'ABC-999' anchors if 'ABC-999' or 'ABC 999' found in normalized source

**Anchor Check Implementation:**
```python
def anchor_check(line: dict, source_text: str) -> bool:
    source_norm = source_text.lower().replace(" ", "")

    # Check SKU
    if line.get("customer_sku_raw"):
        sku_norm = line["customer_sku_raw"].lower().replace(" ", "")
        if sku_norm in source_norm:
            return True

    # Check description tokens
    if line.get("product_description"):
        tokens = line["product_description"].split()
        for token in tokens:
            if len(token) >= 8 and token.lower() in source_text.lower():
                return True

    # Check qty
    if line.get("qty"):
        qty_str = str(line["qty"])
        if qty_str in source_text:
            return True

    return False
```

**Layout Fingerprint:**
```python
def calculate_layout_fingerprint(doc: Document) -> str:
    # Extract structural metadata
    metadata = {
        "page_count": doc.page_count,
        "avg_line_length": calculate_avg_line_length(doc),
        "has_tables": detect_tables(doc),  # heuristic: count "|" or tab chars
        "font_info": extract_font_metadata(doc),  # if available via pdfplumber
    }
    return hashlib.sha256(json.dumps(metadata, sort_keys=True).encode()).hexdigest()
```

**Error Handling:**
- Wrap all LLM calls in try/except with timeout (60s)
- Catch provider exceptions: `openai.APIError`, `openai.Timeout`, `openai.RateLimitError`
- Log to ai_call_log with status=FAILED, error_json
- Return fallback result (empty or rule-based)

**Pydantic Schema Validation:**
```python
from pydantic import BaseModel, Field

class OrderLine(BaseModel):
    line_no: int = Field(ge=1)
    customer_sku_raw: str | None
    product_description: str | None
    qty: float | None = Field(gt=0, le=1_000_000)
    uom: str | None
    unit_price: float | None
    currency: str | None
    requested_delivery_date: str | None  # ISO date

class ExtractionOutput(BaseModel):
    order: OrderHeader
    lines: list[OrderLine] = Field(max_length=500)
    confidence: ConfidenceScores
    warnings: list[Warning]
    extractor_version: str
```

### Testing Strategy

**Unit Tests:**
- Prompt template variable substitution
- JSON parsing and repair logic
- Anchor check (various line/text combinations)
- Range check (qty limits)
- Layout fingerprint calculation
- Confidence calculation with sanity penalties

**Integration Tests:**
- End-to-end: scanned PDF → vision LLM → Draft with lines
- End-to-end: text PDF → rule-based fail → text LLM → Draft
- JSON repair: invalid output → repair → success
- Anchor check: hallucinated line → confidence penalty
- Fallback: LLM fail → rule-based lines used
- Few-shot: feedback exists → examples in prompt

**Test Data:**
- Scanned PDFs with varying quality (clear, blurry, rotated)
- Text PDFs with irregular layouts (orders, quotes, invoices)
- Mock LLM responses (valid, invalid JSON, timeouts)
- Documents with known layout fingerprints for few-shot testing

## SSOT References

- **§7.5**: LLM-Based Extraction (full section)
- **§7.5.1**: Provider Interface (LLMProviderPort)
- **§7.5.2**: Model Selection (gpt-4o-mini, gpt-4o)
- **§7.5.3**: Prompt Templates (EXACT text to use)
- **§7.5.4**: Structured Output Parsing (validation pipeline)
- **§7.5.5**: Fallback Chain (rule → LLM → manual)
- **§7.5.6**: Error Handling (error classes and reactions)
- **§7.5.7**: Cost/Latency Considerations
- **§7.8.1**: Extraction Confidence calculation
- **§7.10.3**: Layout-aware few-shot learning
- **§5.2.10**: AICallType enumeration
- **§5.4.7**: extraction_run schema
- **§5.5.3**: doc_layout_profile schema
- **T-308**: LLM Text Extractor task
- **T-309**: LLM Vision Extractor task
