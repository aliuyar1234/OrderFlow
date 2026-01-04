# Research: Extraction Core

**Feature**: 009-extraction-core | **Date**: 2025-12-27

## Key Decisions

### 1. Canonical Output Schema (Pydantic)

**Decision**: Define canonical schema with Pydantic models for strict validation.

**Rationale**:
- Type safety (automatic validation)
- Clear contract for all extractors
- JSON serialization built-in
- Easy to extend (add fields without breaking)

**Schema**:
```python
class CanonicalExtractionOutput(BaseModel):
    order: ExtractionOrderHeader
    lines: List[ExtractionLineItem]
    metadata: dict = {}
```

### 2. ExtractorPort Interface

**Decision**: Define port interface all extractors must implement.

**Rationale**:
- Hexagonal architecture compliance
- Swappable extractors (rule-based ↔ LLM)
- Easy testing with mocks
- Clear version tracking (excel_v1, llm_v2)

**Methods**:
- `extract(document: Document) -> ExtractionResult`
- `supports(mime_type: str) -> bool`
- `version: str` property

### 3. Confidence Scoring Formula

**Decision**: Weighted average of header completeness (40%) and line completeness (60%).

**Rationale**:
- Lines are more important than header (can process order without full header)
- Simple, interpretable formula
- Deterministic (no ML black box)
- Can be tuned based on real-world data

**Formula**:
```
confidence = 0.4 * header_score + 0.6 * avg_line_score

header_score = (present_fields / required_fields)
line_score = (present_line_fields / required_line_fields)
```

### 4. Rule-Based Extraction (MVP)

**Decision**: Implement rule-based extraction for Excel/CSV/PDF (no LLM for MVP).

**Rationale**:
- Excel/CSV are structured (easy to parse)
- Text-based PDFs have extractable text (pdfplumber)
- No LLM costs for straightforward cases
- Fast, deterministic results

**LLM Future**: Add LLM extractor for scanned PDFs, complex layouts (spec 012)

### 5. Extractor Registry Pattern

**Decision**: Registry pattern for selecting extractor by MIME type.

**Rationale**:
- Decouples extraction logic from worker
- Easy to add new extractors
- Supports multiple extractors per MIME type (try rule-based, fallback to LLM)

## Best Practices

### Excel Extraction
- Use `openpyxl` with `read_only=True` (memory efficient)
- Detect header row (look for keywords: "SKU", "Qty", "Artikel", "Menge")
- Handle merged cells carefully
- Support both .xls (old format) and .xlsx (new format)

### CSV Extraction
- Auto-detect delimiter (comma vs semicolon)
- Handle European decimal format (comma → dot conversion)
- Parse with encoding detection (UTF-8, ISO-8859-1)
- Handle quoted values with commas inside

### PDF Text Extraction
- Use `pdfplumber` for table detection
- Check text_coverage_ratio first (>0.8 = text-based, <0.3 = scanned)
- Extract tables row-by-row
- Fallback to LLM if rule-based fails (future)

### Error Handling
- Store full error in extraction_run.error_json
- Include stack trace for debugging
- Don't fail silently (mark status=FAILED)
- Allow manual retry

## Integration Patterns

**Extraction Flow**:
1. Document uploaded/email received
2. Document status → PROCESSING
3. Extraction worker picks up job
4. Retrieve file from object storage
5. Select extractor by MIME type
6. Run extraction → canonical output
7. Calculate confidence score
8. Store extraction_run (output_json, metrics_json)
9. Update document status → EXTRACTED or FAILED
10. If successful: Enqueue draft order creation

**Retry Flow**:
1. User clicks "Retry Extraction"
2. API creates new extraction_run
3. Enqueues extraction worker
4. Worker processes with updated extractor version
5. Updates document status based on result
