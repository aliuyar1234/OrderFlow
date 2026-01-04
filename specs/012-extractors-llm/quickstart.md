# Quickstart: LLM-Based Extractors

**Feature**: 012-extractors-llm
**Date**: 2025-12-27

## Prerequisites

- Completed setup from specs 010 (rule-based extractors) and 011 (LLM provider layer)
- OpenAI API key configured
- Sample scanned PDF for testing

## Step 1: Database Migration

```bash
cd backend
alembic revision --autogenerate -m "Add feedback_event and doc_layout_profile tables"
alembic upgrade head
```

## Step 2: Test Vision LLM Extraction

```python
# test_vision_extraction.py
from src.adapters.extraction.llm_vision_extractor import LLMVisionExtractor
from pathlib import Path

extractor = LLMVisionExtractor()

# Upload scanned PDF
scanned_pdf = Path("tests/fixtures/scanned_order.pdf")
result = extractor.extract(
    document_path=scanned_pdf,
    org_id=your_org_id,
    context={}
)

print(f"Lines extracted: {len(result['lines'])}")
print(f"Confidence: {result['confidence']['overall']}")
print(f"Cost: {result['metadata']['cost_micros']} micros")
```

## Step 3: Test Anchor Check

```python
from src.adapters.extraction.anchor_check import anchor_check

source_text = "Order PO-123: Widget ABC-1 qty 10, Gadget XYZ-2 qty 5"

line = {
    "customer_sku_raw": "ABC-1",
    "product_description": "Widget",
    "qty": 10
}

passed = anchor_check(line, source_text)
print(f"Anchor check: {'PASS' if passed else 'FAIL'}")
# Expected: PASS (all values found in source)

hallucinated_line = {
    "customer_sku_raw": "FAKE-999",
    "qty": 100
}

passed = anchor_check(hallucinated_line, source_text)
print(f"Hallucinated line check: {'PASS' if passed else 'FAIL'}")
# Expected: FAIL (FAKE-999 not in source)
```

## Step 4: Test Fallback Chain

Upload text PDF with irregular layout:

1. Rule-based extraction runs → low confidence (0.45)
2. Decision logic triggers LLM extraction
3. Text LLM improves confidence to 0.75
4. Draft created with LLM results

```bash
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@tests/fixtures/irregular_layout.pdf" \
  -H "Authorization: Bearer $TOKEN"

# Monitor extraction logs
tail -f logs/celery_worker.log

# Expected log sequence:
# INFO: Rule-based extraction: confidence=0.45
# INFO: Triggering LLM extraction (low confidence)
# INFO: LLM extraction: confidence=0.75
# INFO: Draft created with LLM results
```

## Step 5: Monitor AI Call Costs

```sql
-- LLM extraction costs by type
SELECT
    call_type,
    COUNT(*) AS calls,
    SUM(cost_micros) / 1000000.0 AS total_cost_eur,
    AVG(latency_ms) / 1000.0 AS avg_latency_sec
FROM ai_call_log
WHERE org_id = 'your-org-id'
  AND call_type LIKE 'LLM_EXTRACT%'
  AND created_at >= NOW() - INTERVAL '7 days'
GROUP BY call_type;
```

## Common Issues

### Issue 1: Vision LLM Returns 0 Lines

**Solution**: Check if PDF pages were converted to images correctly. Verify image quality (300 DPI recommended).

### Issue 2: Anchor Check Too Strict

**Symptom**: Many valid lines fail anchor check.

**Solution**: Adjust normalization (case-insensitive, whitespace-insensitive). Consider fuzzy matching.

### Issue 3: Layout Fingerprint Collisions

**Symptom**: Unrelated PDFs get same fingerprint.

**Solution**: Include more structural features in fingerprint calculation (font names, table structure, not just page count).
