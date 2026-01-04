# Research: LLM Provider Layer

**Feature**: 011-llm-provider-layer
**Date**: 2025-12-27

## Key Decisions and Rationale

### Decision 1: Provider Interface Design (Port Pattern)

**Choice**: Define abstract `LLMProviderPort` protocol with OpenAI as first concrete adapter.

**Rationale**:
- Decouples business logic from specific LLM vendor API
- Enables future provider switches (Anthropic Claude, local LLaMA, Azure OpenAI) without code changes
- Simplifies testing (mock provider for deterministic tests)
- Follows hexagonal architecture principle

**Interface Methods**:
```python
class LLMProviderPort(Protocol):
    def extract_order_from_pdf_text(self, text: str, context: dict) -> LLMExtractionResult: ...
    def extract_order_from_pdf_images(self, images: list[bytes], context: dict) -> LLMExtractionResult: ...
    def repair_invalid_json(self, previous_output: str, error: str, context: dict) -> str: ...
```

**Alternatives Rejected**:
- Direct OpenAI SDK usage throughout codebase: Tight coupling, hard to test
- Generic "LLM call" method: Loses type safety, unclear contracts

### Decision 2: Cost Tracking Granularity

**Choice**: Log every LLM API call individually with full metadata (tokens, cost, latency).

**Rationale**:
- Enables precise cost attribution per document, per org, per call type
- Debugging: trace expensive calls, identify cost spikes
- Analytics: aggregate by day/week/month, forecast costs
- Compliance: audit trail for AI usage

**Cost Calculation**:
```python
# OpenAI pricing (as of 2024, in USD per 1M tokens)
PRICING = {
    "gpt-4o-mini": {"input": 0.150, "output": 0.600},
    "gpt-4o": {"input": 2.50, "output": 10.00},
}

cost_micros = (
    (tokens_in * pricing["input"] / 1_000_000) +
    (tokens_out * pricing["output"] / 1_000_000)
) * 1_000_000  # Convert to micros (1 EUR = 1,000,000 micros)
```

**Alternatives Rejected**:
- Batch/aggregate logging: Loses per-call granularity, harder to debug
- Cost estimation only: Inaccurate, can't track actual spending

### Decision 3: Budget Gate Implementation

**Choice**: Pre-flight budget check with Redis-cached daily totals, fail-fast if exceeded.

**Rationale**:
- Prevents runaway costs from automated processing
- Org-level control: different orgs can have different budgets
- Graceful degradation: extraction falls back to rule-based or manual entry
- Performance: Redis cache avoids hitting DB on every LLM call

**Implementation**:
```python
def check_budget_gate(org_id: UUID) -> tuple[bool, int, int]:
    # Check cache first
    cache_key = f"llm_budget:{org_id}:{date.today().isoformat()}"
    cached_usage = redis.get(cache_key)

    if cached_usage is None:
        # Cache miss: query DB
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0)
        usage = db.query(func.sum(AICallLog.cost_micros)).filter(
            AICallLog.org_id == org_id,
            AICallLog.created_at >= today_start
        ).scalar() or 0
        redis.setex(cache_key, ttl=300, value=usage)  # 5min TTL
    else:
        usage = int(cached_usage)

    budget = get_org_setting(org_id, "ai.llm.daily_budget_micros", default=0)
    allowed = budget == 0 or usage < budget  # 0 = unlimited
    return allowed, usage, budget
```

**Edge Cases**:
- Budget exceeded mid-call (call started before limit): Allow to complete, log warning
- Budget reset timing (UTC midnight): Clear cache at midnight, re-query DB

### Decision 4: Token Estimation Strategy

**Choice**: Conservative estimation with 20% buffer for text, fixed estimate for vision.

**Rationale**:
- Text: ~4 chars per token (conservative for GPT-4 tokenizer)
- Vision: ~1500 tokens per page (based on OpenAI vision API documentation)
- Buffer accounts for prompt template overhead (system message, examples)

**Implementation**:
```python
def estimate_tokens_text(text: str) -> int:
    base = ceil(len(text) / 4)
    prompt_overhead = 500  # System message, schema definition
    return int(base * 1.2 + prompt_overhead)  # 20% buffer

def estimate_tokens_vision(page_count: int) -> int:
    base_per_page = 1500
    prompt_overhead = 500
    return page_count * base_per_page + prompt_overhead
```

**Validation**: Compare estimates vs actual tokens from API response, log discrepancies >30%.

### Decision 5: Deduplication Strategy

**Choice**: Hash-based deduplication with 7-day TTL, bypass flag for explicit retry.

**Rationale**:
- Duplicate uploads common (forwarded email chains, re-submissions)
- Hash input: (org_id, document.sha256, call_type, extractor_version)
- 7-day TTL balances cost savings vs freshness (orders rarely change after 1 week)
- Bypass flag: user can force re-extraction if needed

**Implementation**:
```python
def get_cached_extraction(org_id: UUID, doc_sha256: str, call_type: str) -> Optional[LLMExtractionResult]:
    # Query for successful call within 7 days
    cutoff = datetime.now(UTC) - timedelta(days=7)
    cached = db.query(AICallLog).filter(
        AICallLog.org_id == org_id,
        AICallLog.document_sha256 == doc_sha256,
        AICallLog.call_type == call_type,
        AICallLog.status == "SUCCEEDED",
        AICallLog.created_at >= cutoff
    ).order_by(AICallLog.created_at.desc()).first()

    if cached:
        # Retrieve extraction result from storage
        return load_extraction_result(cached.result_storage_key)
    return None
```

**Cache Invalidation**: Automatic after 7 days. Manual invalidation via "Retry with AI" button.

### Decision 6: Error Handling and Retry Strategy

**Choice**: Categorize errors, log all, retry only transient failures (rate limit, timeout).

**Rationale**:
- **Rate Limit (429)**: Retry with exponential backoff (handled by Celery)
- **Timeout (504)**: Retry once with increased timeout
- **Auth Error (401)**: Alert admin, no retry
- **Service Unavailable (503)**: Retry with backoff
- **Invalid API Key**: Fail immediately, alert admin
- **Client Errors (400)**: Log, do not retry (bad request)

**Error Categories**:
```python
class LLMErrorType(str, Enum):
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    AUTH_ERROR = "auth_error"
    SERVICE_UNAVAILABLE = "service_unavailable"
    INVALID_REQUEST = "invalid_request"
    UNKNOWN = "unknown"
```

**Graceful Degradation**:
- LLM failure → fallback to rule-based result (if available)
- If no fallback → create Draft with 0 lines, status=NEEDS_REVIEW
- UI shows error message: "AI extraction failed, manual entry required"

### Decision 7: Structured Output Enforcement

**Choice**: Use OpenAI JSON mode with strict Pydantic validation.

**Rationale**:
- JSON mode (`response_format={"type": "json_object"}`) forces valid JSON
- Pydantic schema validates structure, types, constraints
- One repair attempt for malformed JSON, then fail gracefully

**Implementation**:
```python
# OpenAI API call
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}],
    response_format={"type": "json_object"},  # Enforce JSON
    temperature=0,  # Deterministic
)

raw_output = response.choices[0].message.content

# Parse and validate
try:
    parsed = json.loads(raw_output)
    validated = CanonicalExtractionOutput.model_validate(parsed)
except (json.JSONDecodeError, ValidationError) as e:
    # One repair attempt
    repaired = repair_invalid_json(raw_output, str(e), context)
    validated = CanonicalExtractionOutput.model_validate(json.loads(repaired))
```

## Best Practices for LLM Provider Abstraction

### Provider Interface Design
- Keep interface minimal (3-5 methods max)
- All methods return rich result objects (not just strings)
- Include metadata in results (tokens, cost, latency)
- Design for async/await (future-proofing)

### Cost Control
- Enforce gates at multiple levels: daily budget, per-document token limit, page count limit
- Cache aggressively: deduplication, Redis budget totals
- Monitor cost trends: alert if daily cost >2x average
- Fallback to cheaper options: rule-based → mini model → full model

### Observability
- Log 100% of calls (no sampling)
- Include context: org_id, document_id, call_type
- Track latency percentiles (p50, p95, p99)
- Alert on errors >5% rate

### Testing
- Mock provider for unit tests (deterministic)
- Use VCR.py to record/replay real API calls in integration tests
- Test error scenarios: timeout, rate limit, invalid output
- Validate cost calculations against known token counts

## Performance Considerations

- **Logging Overhead**: Async logging to avoid blocking LLM call
- **Budget Check**: Redis cache with 5min TTL (trade-off: stale data vs DB load)
- **Token Estimation**: O(n) string length calculation, negligible overhead
- **Concurrent Calls**: Use asyncio for parallel LLM calls when processing multi-page PDFs

## Security Considerations

- **API Key Storage**: Environment variables, never in code/DB
- **Key Rotation**: Support multiple keys, rotate without downtime
- **Rate Limit**: Org-level rate limiting (prevent abuse)
- **PII in Prompts**: Minimal, use customer hint (name) only, no addresses/emails in prompts

## Monitoring and Alerts

### Key Metrics
- `llm_calls_total{org_id, provider, model, status}` (counter)
- `llm_cost_micros{org_id, provider, model}` (counter)
- `llm_latency_seconds{provider, model, call_type}` (histogram)
- `llm_budget_usage_ratio{org_id}` (gauge, 0.0-1.0)

### Alerts
- Daily cost >80% of budget → warning email to admin
- Error rate >10% → page on-call
- Latency p95 >30s → investigate provider issues
- Auth errors → immediate alert (API key problem)
