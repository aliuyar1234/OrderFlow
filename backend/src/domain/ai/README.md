# AI Domain Layer - LLM Provider Interface

This module implements the LLM provider abstraction layer for OrderFlow.

## Architecture

Following Hexagonal Architecture (Ports & Adapters):

- **Domain Port**: `LLMProviderPort` - Abstract interface that business logic depends on
- **Infrastructure Adapters**: `OpenAIProvider`, `AnthropicProvider` - Concrete implementations
- **Domain Services**: `BudgetGate`, `AICallLogger` - Budget enforcement and logging

## SSOT References

- **§3.5**: Hexagonal Architecture - LLMProviderPort definition
- **§5.5.1**: ai_call_log table schema
- **§7.2.3**: Cost/Latency Gates (budget enforcement)
- **§7.5.1-7.5.2**: Provider Interface & Model Selection
- **§7.5.7**: Cost/Latency Considerations
- **§10.1**: AI Settings in org.settings_json

## Components

### 1. LLMProviderPort (ports.py)

Abstract interface for LLM providers. Business logic depends on this port, not concrete implementations.

**Methods:**
- `extract_order_from_pdf_text(text, context)` - Extract from PDF text using text LLM
- `extract_order_from_pdf_images(images, context)` - Extract from PDF images using vision LLM
- `repair_invalid_json(previous_output, error, context)` - Repair malformed JSON (1 attempt)

**Data Classes:**
- `LLMExtractionResult` - Result containing raw output, parsed JSON, tokens, cost, latency
- `LLMMessage` - Message format for LLM conversations

### 2. OpenAI Provider (infrastructure/ai/openai_provider.py)

Concrete implementation using OpenAI's GPT models.

**Supported Models:**
- `gpt-4o-mini` - Default for text extraction (cost-effective)
- `gpt-4o` - Default for vision extraction (image support)

**Features:**
- JSON mode for structured output
- Token/cost tracking from API usage
- Error handling (timeout, rate limit, auth, service errors)
- Temperature=0.0 for deterministic extraction

### 3. Budget Gate (budget_gate.py)

Enforces daily LLM spending limits per organization.

**Features:**
- Query daily usage from ai_call_log
- Block calls if `org.settings.ai.llm.daily_budget_micros` exceeded
- Budget = 0 means unlimited
- Returns (allowed, current_usage, budget) for UI display

### 4. AI Call Logger (ai_call_logger.py)

Logs all AI calls to database with deduplication.

**Features:**
- Compute SHA256 input_hash for deduplication
- Find cached results (<7 days old)
- Log success/failure with tokens, cost, latency
- Support for document/draft references

### 5. Cost Calculator (infrastructure/ai/cost_calculator.py)

Calculate LLM costs from token usage.

**Pricing (as of 2026-01-04):**
- OpenAI gpt-4o-mini: $0.150/$0.600 per 1M tokens (input/output)
- OpenAI gpt-4o: $2.50/$10.00 per 1M tokens
- Anthropic claude-3-haiku: $0.25/$1.25 per 1M tokens
- Anthropic claude-3-sonnet: $3.00/$15.00 per 1M tokens

**Output:** Cost in micro-USD (1/1,000,000 USD) for precision

### 6. Token Estimator (infrastructure/ai/token_estimator.py)

Conservative token usage estimation for budget gates.

**Estimation Rules:**
- Text LLM: `ceil(len(text)/4) * 1.2` (20% buffer)
- Vision LLM: `(500 + 1500*page_count) * 1.2`
- Repair: `(100 + tokens(prev_output) + tokens(error)) * 1.2`

## Usage Example

```python
from domain.ai import (
    LLMProviderPort,
    BudgetGate,
    AICallLogger,
    AICallType
)
from infrastructure.ai import OpenAIProvider
from models import AICallStatus

# Initialize provider
provider = OpenAIProvider()  # Uses OPENAI_API_KEY env var

# Check budget gate
org_id = UUID("...")
settings_json = org.settings_json

allowed, usage, budget = BudgetGate.check_budget_gate(
    db=db,
    org_id=org_id,
    settings_json=settings_json
)

if not allowed:
    print(f"Budget exceeded: {usage}/{budget} micros used today")
    return

# Compute input hash for deduplication
input_hash = AICallLogger.compute_input_hash(
    call_type=AICallType.LLM_EXTRACT_PDF_TEXT.value,
    input_text=pdf_text,
    org_id=org_id
)

# Check cache
cached_call = AICallLogger.find_cached_result(
    db=db,
    input_hash=input_hash,
    org_id=org_id,
    max_age_days=7
)

if cached_call:
    print(f"Cache hit! Reusing result from {cached_call.created_at}")
    # Use cached result
else:
    # Make LLM call
    result = provider.extract_order_from_pdf_text(
        text=pdf_text,
        context={
            "org_id": str(org_id),
            "document_id": str(document_id)
        }
    )

    # Log the call
    AICallLogger.log_success(
        db=db,
        org_id=org_id,
        call_type=AICallType.LLM_EXTRACT_PDF_TEXT,
        provider=result.provider,
        model=result.model,
        prompt_tokens=result.tokens_in,
        completion_tokens=result.tokens_out,
        cost_usd=result.cost_micros,
        latency_ms=result.latency_ms,
        input_hash=input_hash,
        document_id=document_id
    )
```

## Error Handling

All providers raise standard exceptions:

- `LLMTimeoutError` - Request timed out
- `LLMRateLimitError` - Rate limit exceeded (429)
- `LLMAuthError` - Authentication failed (401)
- `LLMServiceError` - Service unavailable or other API error
- `LLMInvalidResponseError` - Unexpected response format

Business logic should catch these and handle gracefully (fall back to manual entry, retry, etc).

## Configuration

### Environment Variables

```bash
# Required
OPENAI_API_KEY=sk-...

# Optional (future)
ANTHROPIC_API_KEY=sk-ant-...
```

### Organization Settings (org.settings_json)

```json
{
  "ai": {
    "llm": {
      "provider": "openai",
      "model_text": "gpt-4o-mini",
      "model_vision": "gpt-4o",
      "daily_budget_micros": 50000,  // $0.05 per day, 0 = unlimited
      "max_estimated_tokens": 40000
    },
    "pdf": {
      "max_pages_for_llm": 20
    }
  }
}
```

## Testing

### Unit Tests

- Test token estimation accuracy (±20% target)
- Test cost calculation for various models
- Test budget gate logic (allow/block scenarios)
- Test input hash determinism
- Test cache lookup logic

### Integration Tests

- Mock OpenAI API responses
- Test full extraction flow with logging
- Test budget enforcement blocks call
- Test deduplication reuses cached result
- Test error handling (timeout, rate limit, etc)

## Future Enhancements

1. **Anthropic Provider** - Full implementation of Claude models
2. **Provider Registry** - Dynamic provider selection from org settings
3. **Few-Shot Learning** - Inject examples by layout fingerprint
4. **Prompt Templates** - Externalize prompts for A/B testing
5. **Streaming** - Support streaming responses for large outputs
6. **Batch API** - Use OpenAI batch API for cost savings
