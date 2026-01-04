# Quickstart: LLM Provider Layer

**Feature**: 011-llm-provider-layer
**Date**: 2025-12-27

## Prerequisites

- Completed setup from spec 010 (extractors-rule-based)
- OpenAI API key (sign up at platform.openai.com)
- PostgreSQL, Redis, MinIO running

## Step 1: Install Additional Dependencies

```bash
cd backend
pip install openai  # OpenAI Python SDK v1.x+
```

## Step 2: Configure OpenAI API Key

Add to `backend/.env`:
```env
# OpenAI Configuration
OPENAI_API_KEY=sk-proj-...your-key-here...
OPENAI_ORG_ID=org-...optional...

# LLM Settings (defaults)
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL_TEXT=gpt-4o-mini
DEFAULT_LLM_MODEL_VISION=gpt-4o
DEFAULT_DAILY_BUDGET_MICROS=0  # 0 = unlimited (be careful!)
```

**Security**: Never commit API keys. Use environment variables or secret management.

## Step 3: Run Database Migration

```bash
cd backend
alembic revision --autogenerate -m "Add ai_call_log table"
alembic upgrade head

# Verify table created
psql -h localhost -U orderflow -d orderflow_dev -c "\d ai_call_log"
```

## Step 4: Test OpenAI Adapter

```bash
# Run unit tests
pytest tests/unit/ai/test_openai_adapter.py -v

# Expected output:
# test_openai_adapter::test_extract_order_from_text PASSED
# test_openai_adapter::test_cost_calculation PASSED
# test_openai_adapter::test_error_handling PASSED
```

## Step 5: Test Budget Gate

```python
# Interactive test (Python REPL)
from src.domain.ai.budget import check_budget_gate
from uuid import UUID

org_id = UUID("your-test-org-id")
allowed, usage, budget = check_budget_gate(org_id)

print(f"Allowed: {allowed}, Usage: {usage} micros, Budget: {budget} micros")
# Expected: Allowed: True, Usage: 0 micros, Budget: 0 micros (unlimited)
```

## Step 6: Set Org Budget (Optional)

```sql
-- Set daily budget to 50,000 micros (0.05 EUR)
UPDATE organization
SET settings_json = jsonb_set(
    COALESCE(settings_json, '{}'),
    '{ai,llm,daily_budget_micros}',
    '50000'
)
WHERE id = 'your-org-id';
```

## Step 7: Test End-to-End LLM Call

```python
# Test script: test_llm_e2e.py
from src.services.llm_service import LLMService
from src.adapters.ai.openai_adapter import OpenAIAdapter

# Initialize
adapter = OpenAIAdapter()
service = LLMService(adapter)

# Test text extraction
sample_text = """
Purchase Order: PO-2024-12345
Date: 2024-12-20
Customer: Acme GmbH

Line Items:
1. Widget Pro - Qty: 10 - Price: €45.50
2. Gadget Plus - Qty: 5 - Price: €120.00
"""

result = service.extract_order_from_text(
    text=sample_text,
    org_id=your_org_id,
    document_id=your_doc_id,
    context={}
)

print(f"Extraction confidence: {result.confidence['overall']}")
print(f"Lines extracted: {len(result.lines)}")
print(f"Cost: {result.cost_micros} micros")

# Check ai_call_log
# SELECT * FROM ai_call_log WHERE document_id = 'your_doc_id';
```

## Step 8: Monitor AI Usage

```sql
-- Daily cost aggregation
SELECT
    DATE(created_at) AS date,
    provider,
    model,
    COUNT(*) AS calls,
    SUM(tokens_in) AS total_tokens_in,
    SUM(tokens_out) AS total_tokens_out,
    SUM(cost_micros) AS total_cost_micros,
    AVG(latency_ms) AS avg_latency_ms
FROM ai_call_log
WHERE org_id = 'your-org-id'
  AND created_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at), provider, model
ORDER BY date DESC;
```

## Common Issues

### Issue 1: "OpenAI API key not found"

**Solution**:
```bash
# Verify .env file loaded
echo $OPENAI_API_KEY

# If empty, source .env:
export $(cat backend/.env | xargs)
```

### Issue 2: Budget Gate Always Blocks

**Symptom**: All LLM calls fail with "Daily budget exceeded" even with 0 usage.

**Solution**:
```sql
-- Check org budget setting
SELECT settings_json->'ai'->'llm'->'daily_budget_micros'
FROM organization
WHERE id = 'your-org-id';

-- Set to 0 (unlimited) for testing
UPDATE organization
SET settings_json = jsonb_set(
    COALESCE(settings_json, '{}'),
    '{ai,llm,daily_budget_micros}',
    '0'
)
WHERE id = 'your-org-id';

-- Clear Redis cache
redis-cli DEL "llm_budget:your-org-id:2025-12-27"
```

### Issue 3: High Token Estimation Errors

**Symptom**: Estimated tokens differ from actual by >50%.

**Solution**:
- Review estimation logic in `token_estimator.py`
- Log discrepancies: `WARNING: Estimated 1000 tokens, actual 1450 (+45%)`
- Adjust estimation formula if consistent over/under estimation

### Issue 4: Cost Calculation Mismatch

**Symptom**: `cost_micros` doesn't match manual calculation.

**Solution**:
```python
# Verify pricing constants
from src.adapters.ai.cost_calculator import PRICING

print(PRICING["gpt-4o-mini"])
# Expected: {"input": 0.150, "output": 0.600}

# Manual calculation
tokens_in = 1000
tokens_out = 500
cost = (1000 * 0.150 / 1_000_000 + 500 * 0.600 / 1_000_000) * 1_000_000
print(f"Expected cost: {cost} micros")
# Expected: 450 micros
```

## Testing Checklist

- [ ] OpenAI adapter unit tests pass
- [ ] Budget gate unit tests pass
- [ ] Token estimator accuracy within ±20%
- [ ] Cost calculator matches manual calculation
- [ ] ai_call_log entry created for every LLM call
- [ ] Budget gate blocks calls when limit exceeded
- [ ] Deduplication prevents duplicate calls
- [ ] Error handling graceful for API failures
- [ ] Redis cache reduces DB queries for budget checks

## Next Steps

1. Integrate with extraction pipeline (Spec 012)
2. Test with real PDFs (scanned + text-based)
3. Monitor cost trends over 1 week
4. Tune budget limits based on actual usage
5. Set up alerts for cost >80% of budget
