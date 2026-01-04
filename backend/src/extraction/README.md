# LLM Extraction Module

This module implements LLM-based extraction for unstructured and scanned PDFs as specified in SSOT §7.5.

## Architecture

The module follows Hexagonal Architecture (Ports & Adapters):

- **Ports**: `LLMProviderPort` - Abstract interface for LLM providers
- **Adapters**: `OpenAIProvider` - OpenAI implementation
- **Domain**: `LLMExtractor` - Core extraction logic

## Components

### 1. LLM Provider Port (`ai/ports.py`)

Abstract interface for LLM providers. Defines three methods:

- `extract_order_from_pdf_text()` - Extract from text-based PDFs
- `extract_order_from_pdf_images()` - Extract from scanned/image PDFs (vision LLM)
- `repair_invalid_json()` - Repair malformed JSON output

### 2. OpenAI Provider (`ai/providers/openai_provider.py`)

OpenAI implementation of LLMProviderPort:

- **Text model**: `gpt-4o-mini` (default, configurable)
- **Vision model**: `gpt-4o` (default, configurable)
- **Features**:
  - JSON mode enforcement
  - Cost calculation (micros)
  - Timeout handling
  - Rate limit detection

### 3. Prompt Templates (`extraction/prompts.py`)

SSOT-compliant prompt templates per §7.5.3:

- `pdf_extract_text_v1` - For text PDFs
- `pdf_extract_vision_v1` - For scanned/image PDFs
- `json_repair_v1` - For JSON repair

Templates support context variables:
- `{{from_email}}`, `{{subject}}`
- `{{default_currency}}`
- `{{known_customer_numbers_csv}}`
- `{{hint_examples}}` - Few-shot examples from feedback

### 4. LLM Extractor (`extraction/extractors/llm_extractor.py`)

Core extraction logic:

**Features**:
- Text and vision extraction
- JSON parsing with repair (1 retry per SSOT)
- Pydantic validation
- Hallucination guards
- Deduplication via input_hash

**Pipeline**:
1. Call LLM provider
2. Parse JSON (or repair if needed)
3. Validate against Pydantic schema
4. Apply hallucination guards
5. Re-validate and return

### 5. Hallucination Guards (`extraction/hallucination_guards.py`)

Per SSOT §7.5.4, implements three guards:

**Anchor Check**:
- Verifies extracted data appears in source text
- Checks: customer_sku_raw, description tokens (8+ chars), qty
- Penalty: Line confidence × 0.5 if failed
- Warning: `ANCHOR_CHECK_FAILED`

**Range Check**:
- Validates qty: 0 < qty <= max_qty (default 1,000,000)
- Sets qty=null if violated
- Warning: `QTY_RANGE_VIOLATION`

**Lines Count Check**:
- Flags suspicious line counts (e.g., >200 lines from <=2 pages)
- Penalty: Overall confidence × 0.7
- Warning: `LINES_COUNT_SUSPICIOUS`

If >30% of lines fail anchor check, overall confidence is reduced by 30%.

### 6. Extraction Schemas (`extraction/schemas/extraction_output.py`)

Pydantic models for validation (SSOT §7.5.3 schema):

- `OrderHeader` - Order header fields
- `OrderLine` - Line items (max 500 per SSOT)
- `ExtractionConfidence` - Per-field confidence scores
- `ExtractionOutput` - Complete output

**Validation**:
- Strict mode (no unknown keys)
- Type enforcement
- Auto-renumbering of line_no if gaps/duplicates
- ISO date/currency validation

### 7. Layout Fingerprinting (`extraction/layout_fingerprint.py`)

Per SSOT §7.10.3, calculates document structure fingerprint:

**Metadata**:
- Page count
- Average line length (bucketed)
- Table detection heuristics
- Text length bucket
- Numeric density

**Usage**: Enable few-shot learning by matching documents with same layout.

### 8. Decision Logic (`extraction/decision_logic.py`)

Implements extraction method selection per SSOT §7.2:

**Decision tree**:
1. If text_coverage_ratio < 0.15 → Vision LLM
2. Else run rule-based first
3. If rule_based confidence < 0.60 OR 0 lines → Text LLM fallback

**Budget gates**:
- Check daily budget before LLM calls
- Estimate costs based on text length / page count
- Block if budget exceeded

### 9. UoM Normalization (`extraction/uom_normalization.py`)

Maps UoM variations to canonical codes:

**Canonical UoMs** (SSOT §7.5.3):
`ST, M, CM, MM, KG, G, L, ML, KAR, PAL, SET`

**Compatibility checking**:
- Length units: M, CM, MM
- Weight units: KG, G
- Volume units: L, ML

### 10. AI Call Logger (`ai/call_logger.py`)

Logs all LLM calls for observability:

**Tracked data**:
- Call type (LLM_EXTRACT_PDF_TEXT, LLM_EXTRACT_PDF_VISION, LLM_REPAIR_JSON)
- Input hash (deduplication)
- Provider, model
- Tokens, latency, cost
- Status (SUCCEEDED/FAILED)
- Error details

## Usage Example

```python
from ai.providers.openai_provider import OpenAIProvider
from extraction.extractors.llm_extractor import LLMExtractor
from extraction.decision_logic import decide_extraction_method

# Initialize provider
provider = OpenAIProvider(
    api_key="sk-...",
    model_text="gpt-4o-mini",
    model_vision="gpt-4o",
    timeout_seconds=40,
)

# Initialize extractor
extractor = LLMExtractor(
    llm_provider=provider,
    max_lines=500,
    max_qty=1_000_000,
)

# Decide extraction method
method = decide_extraction_method(
    text_coverage_ratio=0.85,  # Good text coverage
    page_count=3,
    rule_based_confidence=0.45,  # Low confidence
    llm_trigger_confidence=0.60,
)
# → Returns "llm_text" (rule-based failed)

# Extract from text
context = {
    "from_email": "buyer@customer.de",
    "subject": "Order PO-12345",
    "default_currency": "EUR",
    "known_customer_numbers_csv": "4711,4712,4713",
    "hint_examples": "",  # Few-shot examples if available
}

result = extractor.extract_from_text(
    pdf_text=pdf_text,
    context=context,
    source_text=pdf_text,
    page_count=3,
)

if result["status"] == "SUCCEEDED":
    output = result["output"]  # ExtractionOutput model
    print(f"Extracted {len(output.lines)} lines")
    print(f"Confidence: {output.confidence.overall:.2f}")
else:
    error = result["error"]
    print(f"Extraction failed: {error['code']} - {error['message']}")
```

## Error Handling

Per SSOT §7.5.6, errors are handled gracefully:

**Error codes**:
- `LLM_TIMEOUT` - Request timed out
- `LLM_RATE_LIMIT` - Rate limit exceeded
- `LLM_INVALID_JSON` - JSON parsing failed (after repair)
- `LLM_SCHEMA_MISMATCH` - Schema validation failed
- `LLM_SUSPICIOUS_OUTPUT` - Sanity checks flagged issues

**Fallback chain** (§7.5.5):
1. Try rule-based (text PDFs)
2. If low confidence/0 lines → Try LLM
3. If LLM fails → Create Draft with 0 lines + issues
4. UI offers: "Manual entry" or "Retry with AI"

## Cost & Performance

**Target latencies** (SSOT §7.5.7):
- Text LLM: p95 < 12s
- Vision LLM: p95 < 25s

**Cost control**:
- Daily budget per organization (configurable)
- Max pages limit (default: 20)
- Max estimated tokens (default: 40,000)
- Deduplication via input_hash

**Budget gates enforced before calls**.

## Testing

**Unit tests**:
- Prompt template variable substitution
- JSON parsing and repair
- Anchor check (various scenarios)
- Range check (edge cases)
- Layout fingerprint calculation
- Confidence calculation with penalties

**Integration tests**:
- End-to-end: scanned PDF → vision LLM → Draft
- End-to-end: text PDF → rule fail → text LLM → Draft
- JSON repair flow
- Anchor check with real PDFs
- Fallback chain

**Mocking**:
- LLM responses mocked for deterministic tests
- VCR.py for API replay (optional)

## Future Enhancements

Per spec, these are out of scope for MVP but documented:

1. **Alternative providers**: Claude, local models
2. **Fine-tuning**: Custom models per organization
3. **Streaming**: Large PDF processing in chunks
4. **Multi-language**: Non-English orders
5. **Feedback loop**: Automatic model updates from corrections

## References

- SSOT §7.5: LLM-Based Extraction
- SSOT §7.5.3: Prompt Templates (exact text)
- SSOT §7.5.4: Structured Output Parsing
- SSOT §7.5.5: Fallback Chain
- SSOT §7.5.6: Error Handling
- SSOT §7.10.3: Layout-aware Few-Shot Learning
