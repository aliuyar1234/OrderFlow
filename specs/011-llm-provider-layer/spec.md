# Feature Specification: LLM Provider Layer

**Feature Branch**: `011-llm-provider-layer`
**Created**: 2025-12-27
**Status**: Draft
**Module**: ai
**SSOT Refs**: §3.5 (LLMProviderPort), §5.5.1 (ai_call_log), §7.5.1-7.5.2 (Provider Interface & Model Selection), §10.1 (AI Settings), T-307

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Transparent LLM Cost and Usage Tracking (Priority: P1)

An Admin user views AI usage metrics for their organization to understand costs and optimize LLM usage. All LLM calls are logged with provider, model, tokens, latency, and cost in micros.

**Why this priority**: AI costs can escalate quickly. Transparent tracking enables budget control and optimization decisions. This is foundational for all LLM features.

**Independent Test**: Trigger any LLM extraction → verify `ai_call_log` entry is created with provider, model, tokens_in, tokens_out, cost_micros, latency_ms.

**Acceptance Scenarios**:

1. **Given** an LLM extraction call completes successfully, **When** querying ai_call_log, **Then** entry contains provider="openai", model="gpt-4o-mini", tokens_in, tokens_out, cost_micros (calculated), status="SUCCEEDED"
2. **Given** an LLM call fails with timeout, **When** logging, **Then** entry has status="FAILED", error_json contains timeout details, cost_micros=0
3. **Given** multiple LLM calls in one day, **When** Admin views usage dashboard, **Then** total cost and call count are aggregated correctly per org

---

### User Story 2 - Budget Gate Protection (Priority: P1)

An organization configures a daily LLM budget limit. When the limit is reached, further LLM calls are blocked, preventing cost overruns while still allowing manual processing.

**Why this priority**: Critical for cost control. Organizations must be able to cap AI spending per day.

**Independent Test**: Set org daily_budget_micros=10000 (0.01 EUR) → trigger LLM calls until budget exceeded → verify next call is blocked with budget gate error.

**Acceptance Scenarios**:

1. **Given** org settings ai.llm.daily_budget_micros=50000, **When** LLM calls totaling 50000 micros complete, **Then** next LLM call is blocked with error "Daily LLM budget exceeded"
2. **Given** daily budget exceeded, **When** processing a new order, **Then** rule-based extraction runs, LLM is skipped, Draft is created with status NEEDS_REVIEW
3. **Given** a new day starts (UTC midnight), **When** checking budget, **Then** budget counter resets to 0

---

### User Story 3 - Provider Abstraction and Failover (Priority: P2)

The system uses a provider-agnostic interface for LLM calls. If the configured provider fails, the system logs the error gracefully without crashing the extraction pipeline.

**Why this priority**: Decouples business logic from specific LLM vendors, enabling future provider switches and resilience.

**Independent Test**: Mock OpenAI API failure → verify extraction job logs error, sets document status appropriately, does not crash worker.

**Acceptance Scenarios**:

1. **Given** LLMProviderPort configured with OpenAI adapter, **When** calling extract_order_from_pdf_text(), **Then** adapter transforms request to OpenAI API format and parses response
2. **Given** OpenAI API returns 429 rate limit error, **When** extraction runs, **Then** ai_call_log records status=FAILED, error_json contains "rate_limit", extraction falls back per §7.5.5
3. **Given** org configures alternative provider (e.g., "anthropic"), **When** LLM call is made, **Then** system uses corresponding adapter (future extensibility)

---

### User Story 4 - Token and Page Limits for Cost Control (Priority: P1)

The system enforces per-document limits (max_pages_for_llm, max_estimated_tokens) to prevent expensive LLM calls on unusually large documents.

**Why this priority**: Prevents single-document cost spikes (e.g., 100-page PDF triggering $10 LLM call).

**Independent Test**: Upload 25-page PDF with max_pages_for_llm=20 → verify LLM call is blocked, extraction falls back to manual entry.

**Acceptance Scenarios**:

1. **Given** PDF with page_count=25 and org.settings.ai.pdf.max_pages_for_llm=20, **When** decision logic evaluates, **Then** LLM call is aborted, Draft is created with 0 lines and NEEDS_REVIEW status
2. **Given** text extraction yields estimated_tokens=50000 and max_estimated_tokens=40000, **When** gate check runs, **Then** LLM call is blocked, error logged
3. **Given** LLM call blocked by gate, **When** Ops views Draft, **Then** UI shows warning "Document too large for AI processing - manual entry required"

---

### User Story 5 - Deduplication of Identical LLM Calls (Priority: P3)

When the same document (identified by sha256) is processed multiple times, the system reuses previous LLM extraction results instead of making redundant API calls.

**Why this priority**: Reduces costs and latency for duplicate uploads (e.g., same order forwarded twice).

**Independent Test**: Upload same PDF twice → verify second extraction reuses first result, no second LLM call logged.

**Acceptance Scenarios**:

1. **Given** document with sha256=X previously extracted via LLM, **When** same document uploaded again, **Then** system retrieves cached extraction result, no new ai_call_log entry
2. **Given** cached extraction result exists, **When** creating Draft, **Then** extraction completes in <1 second (cache hit)
3. **Given** user explicitly clicks "Retry with AI", **When** processing, **Then** cache is bypassed, new LLM call is made

---

### Edge Cases

- What happens when OpenAI API returns malformed JSON despite schema enforcement?
- How does system handle token estimation errors (actual tokens >> estimated)?
- What happens when budget is exceeded mid-call (call started before limit, finishes after)?
- How does system handle provider API credential expiration/rotation?
- What happens when ai_call_log grows very large (millions of entries) - query performance?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST define LLMProviderPort interface with methods:
  - `extract_order_from_pdf_text(text: str, context: dict) -> LLMExtractionResult`
  - `extract_order_from_pdf_images(images: list[bytes], context: dict) -> LLMExtractionResult`
  - `repair_invalid_json(previous_output: str, error: str, context: dict) -> str`
- **FR-002**: System MUST implement OpenAI adapter for LLMProviderPort supporting:
  - Text extraction via gpt-4o-mini
  - Vision extraction via gpt-4o
  - JSON repair via gpt-4o-mini
- **FR-003**: System MUST log every LLM API call to `ai_call_log` table with:
  - `org_id`, `call_type` (enum per §5.2.10), `document_id` (if applicable)
  - `provider`, `model`, `tokens_in`, `tokens_out`, `latency_ms`, `cost_micros`
  - `status` (SUCCEEDED/FAILED), `error_json`, `created_at`
- **FR-004**: System MUST calculate `cost_micros` based on provider pricing:
  - OpenAI gpt-4o-mini: input=$0.150/1M tokens, output=$0.600/1M tokens
  - OpenAI gpt-4o: input=$2.50/1M tokens, output=$10.00/1M tokens
  - Store pricing in configuration, update when provider changes rates
- **FR-005**: System MUST enforce daily budget gate per org:
  - Query sum(cost_micros) from ai_call_log WHERE org_id=X AND created_at >= today_utc
  - If total >= org.settings.ai.llm.daily_budget_micros AND budget > 0, block call
  - Return error: "Daily LLM budget exceeded" with current usage and limit
- **FR-015**: Budget check and debit MUST be atomic. Implementation: Use SELECT FOR UPDATE on org.settings_json OR implement atomic compare-and-decrement pattern. Budget gate check and cost deduction MUST occur in single database transaction with SERIALIZABLE isolation level to prevent race conditions.
- **FR-006**: System MUST enforce per-document limits before LLM call:
  - `page_count > max_pages_for_llm` → block
  - `estimated_tokens > max_estimated_tokens` → block
  - Estimation: text LLM = ceil(len(text)/4), vision LLM = 1500 * page_count
- **FR-007**: System MUST deduplicate LLM calls:
  - Before extraction, check if ai_call_log contains successful call for same document sha256 + org_id + call_type
  - If found and <7 days old, reuse result (retrieve from extraction_run.metrics_json or document metadata)
  - Implement cache bypass flag for explicit "Retry with AI"
- **FR-008**: System MUST transform context parameters into provider-specific API calls:
  - Populate prompt templates per §7.5.3
  - Enforce structured output (JSON mode) for OpenAI
  - Parse provider response into LLMExtractionResult
- **FR-009**: System MUST handle provider errors gracefully:
  - Timeout → status=FAILED, error_json=timeout details
  - Rate limit (429) → status=FAILED, error_json=rate_limit, retry after delay (worker retry)
  - Invalid API key (401) → status=FAILED, error_json=auth_error, alert admin
  - Model unavailable (503) → status=FAILED, error_json=service_unavailable
- **FR-010**: System MUST support configurable provider/model per org via settings_json:
  - `ai.llm.provider` (default: "openai")
  - `ai.llm.model_text` (default: "gpt-4o-mini")
  - `ai.llm.model_vision` (default: "gpt-4o")
  - `ai.llm.daily_budget_micros` (default: 0 = unlimited)
  - `ai.llm.max_estimated_tokens` (default: 40000)
  - `ai.pdf.max_pages_for_llm` (default: 20)
- **FR-011**: LLMExtractionResult MUST contain:
  - `raw_output` (string from LLM)
  - `parsed_json` (dict or null if parsing failed)
  - `provider`, `model`, `tokens_in`, `tokens_out`, `latency_ms`, `cost_micros`
  - `warnings` (list of strings for non-critical issues)

### Key Entities

- **ai_call_log** (§5.5.1): Immutable log of all LLM/embedding calls with cost tracking
- **LLMProviderPort**: Abstract interface for LLM providers
- **OpenAIAdapter**: Concrete implementation of LLMProviderPort
- **LLMExtractionResult**: Data class for extraction call results
- **BudgetGate**: Service component enforcing daily budget limits
- **TokenEstimator**: Utility for estimating token usage before calls

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of LLM calls are logged in ai_call_log with complete metadata
- **SC-002**: Budget gate prevents spending beyond configured limit in ≥99.9% of cases
- **SC-003**: Token estimation accuracy within ±20% for text calls, ±30% for vision calls
- **SC-004**: LLM call deduplication reduces redundant calls by ≥80% for duplicate uploads
- **SC-005**: Provider errors are handled without crashing workers in 100% of cases
- **SC-006**: Admin can view aggregated cost metrics (daily/weekly/monthly) via API/UI
- **SC-007**: Page/token limits prevent cost spikes >2x expected per-document cost
- **SC-008**: Latency overhead of logging/budget checks <50ms per LLM call

## Dependencies

- **Depends on**:
  - PostgreSQL database (ai_call_log table)
  - Organization settings (org.settings_json)
  - Redis/Celery worker infrastructure
  - OpenAI API credentials (env vars: OPENAI_API_KEY)

- **Blocks**:
  - 012-extractors-llm (requires LLMProviderPort to make extraction calls)
  - 016-embedding-layer (EmbeddingProviderPort follows same pattern)
  - 018-customer-detection (uses LLM customer hint if needed)

## Technical Notes

### Implementation Guidance

**LLMProviderPort Interface:**
```python
from abc import ABC, abstractmethod
from typing import Protocol
from dataclasses import dataclass

@dataclass
class LLMExtractionResult:
    raw_output: str
    parsed_json: dict | None
    provider: str
    model: str
    tokens_in: int | None
    tokens_out: int | None
    latency_ms: int
    cost_micros: int
    warnings: list[str]

class LLMProviderPort(ABC):
    @abstractmethod
    def extract_order_from_pdf_text(self, text: str, context: dict) -> LLMExtractionResult:
        pass

    @abstractmethod
    def extract_order_from_pdf_images(self, images: list[bytes], context: dict) -> LLMExtractionResult:
        pass

    @abstractmethod
    def repair_invalid_json(self, previous_output: str, error: str, context: dict) -> str:
        pass
```

**OpenAI Adapter:**
- Use `openai` Python SDK (v1.x+)
- Implement structured output via `response_format={"type": "json_object"}`
- Parse usage from `response.usage.prompt_tokens`, `completion_tokens`
- Calculate cost: `(tokens_in * input_rate + tokens_out * output_rate) * 1_000_000` (micros)
- Track latency via `time.perf_counter()` before/after call

**Budget Gate Service:**
```python
def check_budget_gate(org_id: UUID) -> tuple[bool, int, int]:
    """Returns (allowed, current_usage_micros, budget_micros)"""
    budget = get_org_setting(org_id, "ai.llm.daily_budget_micros", default=0)
    if budget == 0:  # unlimited
        return True, 0, 0

    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0)
    usage = db.query(func.sum(AICallLog.cost_micros)).filter(
        AICallLog.org_id == org_id,
        AICallLog.created_at >= today_start
    ).scalar() or 0

    return usage < budget, usage, budget
```

**Token Estimator:**
- Text: `ceil(len(text) / 4)` (conservative, accounts for tokenizer overhead)
- Vision: `base_tokens + (page_count * 1500)` where base_tokens=500
- Add 20% buffer for prompt template overhead

**Cache Validity Rules:**
- AI call cache is valid if ALL conditions met:
  1. ai_call_log.created_at >= NOW() - INTERVAL 7 days
  2. document.sha256 unchanged since cache entry
  3. org.settings.ai.llm.model_text unchanged
- 'Retry with AI' button (FR-007) bypasses cache entirely

**Token Estimation Justification:**
- Token Estimation: Text tokens ≈ len(text)/4 (conservative, assumes 25% overhead). Vision tokens ≈ 1500 * page_count + 500 base. These are CONSERVATIVE estimates. Success criterion SC-003 requires ±20% accuracy. Adjust factors based on actual OpenAI response comparison in production.

**Deduplication:**
- Unique index on ai_call_log: `(org_id, call_type, document_id, status)` WHERE status='SUCCEEDED'
- Before call, query for existing successful call
- Cache extraction result in document metadata or extraction_run table
- TTL: 7 days (configurable)

**Error Handling:**
- Wrap all provider calls in try/except
- Map provider errors to ai_call_log status codes
- Log stack trace in error_json for debugging
- Return graceful fallback (null result + warnings)

### Testing Strategy

**Unit Tests:**
- LLMProviderPort interface compliance (OpenAI adapter)
- Budget gate logic (various budget/usage scenarios)
- Token estimation accuracy (sample texts/images)
- Cost calculation (various token counts)
- Error handling (mock provider failures)

**Integration Tests:**
- End-to-end: LLM call → ai_call_log entry created
- Budget enforcement: exceed limit → call blocked
- Deduplication: same doc uploaded twice → one LLM call
- Provider failover: OpenAI down → graceful degradation

**Test Data:**
- Mock OpenAI API responses (success, errors)
- Sample documents of varying sizes (1-page, 10-page, 25-page PDFs)
- Budget scenarios (0/unlimited, low, high)

## SSOT References

- **§3.5**: Hexagonal Architecture - LLMProviderPort definition
- **§5.2.10**: AICallType enumeration
- **§5.5.1**: ai_call_log table schema
- **§7.2.3**: Cost/Latency Gates (budget enforcement)
- **§7.5.1**: Provider Interface specification
- **§7.5.2**: Model Selection (gpt-4o-mini, gpt-4o)
- **§7.5.7**: Cost/Latency Considerations
- **§10.1**: AI Settings in org.settings_json
- **T-307**: LLM Provider Port task
