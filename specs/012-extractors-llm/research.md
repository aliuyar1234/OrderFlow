# Research: LLM-Based Extractors

**Feature**: 012-extractors-llm
**Date**: 2025-12-27

## Key Decisions

### Decision 1: Vision vs Text LLM Trigger

**Choice**: Use text_coverage_ratio <0.15 as threshold for vision LLM, else text LLM.

**Rationale**: Scanned PDFs have low extractable text. Vision LLM required for image-based content. Text LLM cheaper and faster for text-based PDFs.

### Decision 2: Anchor Check Implementation

**Choice**: Verify extracted data appears in source text. Reduce confidence by 50% for hallucinated fields.

**Rationale**: LLMs can fabricate SKUs or quantities. Anchor check detects when extracted value doesn't exist in source, preventing incorrect orders.

### Decision 3: Layout Fingerprinting

**Choice**: SHA256 hash of structural metadata (page count, table patterns, font info).

**Rationale**: Enables few-shot learning. PDFs from same supplier have same layout. Feedback from previous corrections improves future extractions.

### Decision 4: JSON Repair Strategy

**Choice**: One repair attempt via LLM with schema + error message. Fail gracefully if repair fails.

**Rationale**: LLMs occasionally produce invalid JSON. Repair prompt fixes most syntax errors. Limit to 1 attempt to control costs.

## Best Practices

### Prompt Engineering
- Use exact templates from §7.5.3
- Include few-shot examples from feedback_event for matching layout_fingerprint
- Structured output mode enforced (JSON schema)
- Temperature=0 for determinism

### Hallucination Prevention
- Anchor check: verify extracted values appear in source
- Range check: reject unrealistic quantities (>1M units)
- Lines count check: flag if >200 lines extracted from 2-page PDF

### Cost Optimization
- Rule-based extraction first (free, fast)
- LLM only when necessary (confidence <0.60)
- Cache results via deduplication (7-day TTL)
- Use mini model for text, full model only for vision

## Testing Strategy

### Mock LLM Responses
```python
MOCK_EXTRACTION_SUCCESS = {
    "order": {"external_order_number": "PO-123", ...},
    "lines": [{"line_no": 1, "customer_sku_raw": "ABC-1", ...}],
    "confidence": {...}
}

MOCK_EXTRACTION_INVALID_JSON = '{"order": {"external_order_number": "PO-123",}}'  # Trailing comma
```

### Test Cases
- Scanned PDF → vision LLM → successful extraction
- Text PDF → text LLM → successful extraction
- Invalid JSON → repair → success
- Hallucinated SKU → anchor check → confidence penalty
- Budget gate triggered → LLM skipped → fallback to rule-based
