# Feature Specification: Observability & AI Monitoring

**Feature Branch**: `025-observability`
**Created**: 2025-12-27
**Status**: Draft
**Module**: audit, notifications, ai
**SSOT References**: §3.2 (Observability), §5.4.16 (audit_log), §8.10 (AI Observability), §9.7 (AI Monitor UI), T-701, T-702, T-706

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Structured JSON Logging with Request IDs (Priority: P1)

Every API request must be logged in structured JSON format with a unique request_id for tracing requests across services and debugging production issues.

**Why this priority**: Structured logging is the foundation for debugging, monitoring, and compliance. Without request IDs, troubleshooting multi-step workflows (intake → extraction → matching → push) is nearly impossible. This is production-critical infrastructure.

**Independent Test**: Can be fully tested by making an API request, checking logs, and verifying that all log entries for that request share the same request_id and are in JSON format.

**Acceptance Scenarios**:

1. **Given** API request is received, **When** processing starts, **Then** a unique request_id is generated (UUID v4) and attached to logging context
2. **Given** request_id is generated, **When** any log is written during request processing, **Then** log entry contains `{"request_id": "...", "timestamp": "...", "level": "INFO", "message": "...", ...}`
3. **Given** request triggers background jobs (extraction, matching), **When** jobs are processed, **Then** job logs inherit request_id from original request
4. **Given** request fails with error, **When** exception is logged, **Then** log entry includes `{"level": "ERROR", "request_id": "...", "error": "...", "traceback": "..."}`
5. **Given** operator searches logs by request_id, **When** querying log aggregation system, **Then** all logs for that request are returned in chronological order

---

### User Story 2 - Prometheus Metrics Endpoint (Priority: P1)

The system must expose a `/metrics` endpoint in Prometheus format, providing key operational metrics for monitoring dashboards and alerting.

**Why this priority**: Metrics enable proactive monitoring and alerting. Without metrics, operators cannot detect issues (high error rates, slow processing) until users complain. This is essential for production operations.

**Independent Test**: Can be fully tested by calling GET `/metrics`, verifying Prometheus format, and checking that expected metrics (ai_calls_total, extraction_confidence_histogram) are present.

**Acceptance Scenarios**:

1. **Given** `/metrics` endpoint is called, **When** response is received, **Then** content-type is `text/plain` and format matches Prometheus exposition format
2. **Given** metrics are exposed, **When** querying `/metrics`, **Then** metrics include: `orderflow_ai_calls_total{type,status}`, `orderflow_ai_latency_ms_bucket{type}`, `orderflow_extraction_confidence_histogram`
3. **Given** AI call completes, **When** metrics are updated, **Then** `orderflow_ai_calls_total{type="extraction",status="success"}` increments by 1
4. **Given** extraction completes with confidence 0.85, **When** metrics are updated, **Then** `orderflow_extraction_confidence_histogram` records value in 0.8-0.9 bucket
5. **Given** Prometheus server scrapes `/metrics`, **When** scrape completes, **Then** metrics appear in Prometheus UI and can be queried with PromQL

---

### User Story 3 - AI Call Logging for Cost & Quality Tracking (Priority: P1)

Every LLM and embedding API call must be logged to `ai_call_log` table with provider, model, tokens, cost, latency, and status for cost tracking and quality monitoring.

**Why this priority**: AI costs can spiral out of control without tracking. Latency and error rates directly impact user experience. This logging is the data source for cost optimization and quality assurance.

**Independent Test**: Can be fully tested by triggering an LLM extraction, querying ai_call_log, and verifying that record contains provider, model, tokens_in/out, cost_micros, latency_ms.

**Acceptance Scenarios**:

1. **Given** LLM extraction is called with gpt-4o-mini, **When** call completes, **Then** ai_call_log entry is created with `provider=openai`, `model=gpt-4o-mini`, `call_type=extraction`, `status=success`
2. **Given** LLM call consumes 1200 input tokens and 800 output tokens, **When** logged, **Then** `tokens_in=1200`, `tokens_out=800`, `cost_micros` calculated based on model pricing
3. **Given** LLM call takes 3.5 seconds, **When** logged, **Then** `latency_ms=3500`
4. **Given** LLM call fails with rate limit error, **When** logged, **Then** `status=error`, `error_type=rate_limit`, `error_message` contains API error
5. **Given** embedding API call is made, **When** logged, **Then** ai_call_log entry has `call_type=embedding`, `model=text-embedding-ada-002`, `tokens_in=500`, `tokens_out=0`

---

### User Story 4 - AI Monitor UI for Cost & Performance Analysis (Priority: P2)

Administrators and integrators need a UI dashboard to view AI call statistics: cost per day, error rates, p95 latency, model usage distribution.

**Why this priority**: UI makes AI metrics accessible to non-technical stakeholders. However, underlying logging (P1) must exist first. This is a visualization layer for decision-making.

**Independent Test**: Can be fully tested by opening AI Monitor page, verifying that charts render with aggregated data from ai_call_log (cost/day, errors, latency percentiles).

**Acceptance Scenarios**:

1. **Given** admin opens AI Monitor page, **When** page loads, **Then** charts display: total cost (last 30 days), cost per day (line chart), calls by model (pie chart), error rate (%)
2. **Given** date range filter "Last 7 days" is selected, **When** chart updates, **Then** only data from last 7 days is displayed
3. **Given** admin filters by call_type "extraction", **When** filter is applied, **Then** charts show only extraction calls
4. **Given** latency percentiles are calculated, **When** viewing metrics, **Then** table shows: p50, p95, p99 latency in milliseconds
5. **Given** cost breakdown by model, **When** viewing chart, **Then** stacked bar chart shows: gpt-4o ($120), gpt-4o-mini ($15), embeddings ($5)

---

### User Story 5 - OpenTelemetry Tracing (Priority: P3)

For advanced debugging, the system should support distributed tracing via OpenTelemetry, allowing operators to trace requests across services (API → worker → AI provider).

**Why this priority**: Distributed tracing is valuable for complex debugging but not critical for MVP. Structured logs (P1) cover most troubleshooting needs. This is an advanced observability feature.

**Independent Test**: Can be fully tested by enabling OpenTelemetry, triggering a request, and verifying that trace spans appear in a tracing backend (Jaeger, Zipkin).

**Acceptance Scenarios**:

1. **Given** OpenTelemetry is enabled, **When** API request is received, **Then** a root trace span is created with trace_id and span_id
2. **Given** request triggers background job, **When** job is processed, **Then** child span is created linked to parent trace_id
3. **Given** LLM API call is made, **When** call completes, **Then** span is created with attributes: `ai.provider=openai`, `ai.model=gpt-4o-mini`, `ai.tokens_in=1200`
4. **Given** trace is completed, **When** viewing in Jaeger UI, **Then** full trace shows: API request → extraction job → LLM call (with timing for each span)
5. **Given** error occurs, **When** viewing trace, **Then** span is marked with error status and exception details

---

### Edge Cases

- What happens when log volume is very high (100k req/sec)? (Structured logs enable sampling; configure log level to WARN in production to reduce volume)
- How does system handle metrics endpoint being scraped during high load? (Metrics are in-memory; scrape is fast; no DB queries)
- What if ai_call_log table grows to millions of rows? (Retention job deletes old logs per §11.5; partition by month for performance)
- What happens when AI provider returns unexpected token counts? (Log as-is; flag for manual review; cost calculation may be inaccurate)
- How does system handle timezone differences in logs? (All timestamps are UTC per SSOT; conversion to local time happens in UI)
- What if OpenTelemetry backend is unreachable? (Traces are dropped; system continues; logging is fallback)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST generate unique request_id (UUID v4) for every API request
- **FR-002**: System MUST attach request_id to all logs within request context (using thread-local storage or async context)
- **FR-003**: System MUST log all messages in structured JSON format with fields: `timestamp`, `level`, `request_id`, `message`, `module`, `function`
- **FR-004**: System MUST propagate request_id to background jobs (extraction, matching, push) via job metadata
- **FR-005**: System MUST expose `/metrics` endpoint in Prometheus exposition format
- **FR-006**: System MUST implement metrics: `orderflow_ai_calls_total{type,status}`, `orderflow_ai_latency_ms_bucket{type}`, `orderflow_embedding_jobs_queue_depth`, `orderflow_extraction_confidence_histogram`
- **FR-007**: System MUST implement `ai_call_log` table per §5.4.16 schema
- **FR-008**: System MUST log every LLM and embedding API call with: provider, model, call_type, tokens_in, tokens_out, cost_micros, latency_ms, status
- **FR-009**: System MUST calculate cost_micros based on model pricing (configurable per provider+model)
- **FR-010**: System MUST log errors with: error_type, error_message, traceback (if available)
- **FR-011**: System MUST expose API: GET `/ai/calls?start_date=X&end_date=Y&call_type=Z` for querying ai_call_log
- **FR-012**: System MUST restrict ai_call_log API to ADMIN and INTEGRATOR roles
- **FR-013**: System MUST implement UI page: AI Monitor with charts for cost, errors, latency, model usage
- **FR-014**: System MUST aggregate ai_call_log by day for cost/day chart
- **FR-015**: AI call logging MUST include input_hash = SHA256(template_name + truncated_prompt_first_1000_chars) instead of full prompt for privacy compliance. Full prompt stored only if org.settings.ai.log_full_prompts=true (default false). Enables deduplication without PII exposure.
- **FR-016**: Log rotation: Daily rotation, retain 7 days locally. For log aggregation (ELK/Datadog), sample high-volume endpoints at 10% (configurable via LOG_SAMPLE_RATE). Health check endpoints excluded from logging. Disk usage alert at 80% capacity.
- **FR-017**: System MUST calculate p50, p95, p99 latency percentiles from ai_call_log
- **FR-018**: System MUST support OpenTelemetry tracing (optional, configurable via env var OTEL_ENABLED=true)
- **FR-019**: System MUST create trace spans for: API requests, background jobs, AI calls
- **FR-020**: System MUST export traces to OTLP endpoint (configurable via OTEL_EXPORTER_OTLP_ENDPOINT)
- **FR-021**: System MUST include trace_id in structured logs when tracing is enabled
- **FR-022**: System MUST retain ai_call_logs for 90 days (org-configurable) per §11.5

### Key Entities *(include if feature involves data)*

- **AuditLog** (§5.4.16): General-purpose audit trail for user actions (approve, push, mapping confirm). Separate from ai_call_log.

- **AICallLog** (separate table): Tracks AI provider API calls with cost, latency, and error details. Used for cost tracking and quality monitoring.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Request_id is present in 100% of API request logs (verified in integration tests)
- **SC-002**: Prometheus metrics endpoint responds within 100ms under normal load (performance test)
- **SC-003**: AI call logs capture 100% of LLM and embedding calls with accurate token counts (integration tests)
- **SC-004**: AI Monitor UI loads within 2 seconds with 90 days of data (performance test)
- **SC-005**: Cost calculations match actual AI provider invoices within 5% margin (manual verification)
- **SC-006**: OpenTelemetry traces capture full request flow (API → worker → AI) in 100% of traced requests
- **SC-007**: Log volume is < 10GB/day for 10k daily orders (production monitoring)

## Dependencies

- **Depends on**:
  - **001-database-setup**: Requires audit_log table (§5.4.16) and ai_call_log table
  - **002-auth**: Requires ADMIN/INTEGRATOR roles for AI Monitor access
  - **013-pdf-extraction**: Requires LLM calls to generate ai_call_log data

- **Enables**:
  - **Production operations**: Monitoring, alerting, debugging, cost control
  - **Compliance**: Audit trail for GDPR, SOC2 requirements

## Implementation Notes

**Log Format - module field**: Use Python __name__ convention (e.g., 'orderflow.domain.validation', 'orderflow.adapters.llm.openai'). Enables filtering by component in log aggregation tools.

### Structured Logging with Request ID

```python
import logging
import uuid
from contextvars import ContextVar

# Context variable for request_id (async-safe)
request_id_var: ContextVar[str] = ContextVar("request_id", default=None)

class RequestIDFilter(logging.Filter):
    """Add request_id to all log records."""
    def filter(self, record):
        record.request_id = request_id_var.get() or "no-request-id"
        return True

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "request_id": "%(request_id)s", "module": "%(module)s", "message": "%(message)s"}',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)
logger.addFilter(RequestIDFilter())

# Middleware to generate request_id
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request_id_var.set(request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
```

### Prometheus Metrics

```python
from prometheus_client import Counter, Histogram, Gauge, generate_latest

# Define metrics
ai_calls_total = Counter(
    "orderflow_ai_calls_total",
    "Total AI API calls",
    ["type", "status"]  # type: extraction|embedding, status: success|error
)

ai_latency_ms = Histogram(
    "orderflow_ai_latency_ms",
    "AI API call latency in milliseconds",
    ["type"],
    buckets=[50, 100, 250, 500, 1000, 2500, 5000, 10000]
)

extraction_confidence = Histogram(
    "orderflow_extraction_confidence",
    "Extraction confidence score",
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

embedding_queue_depth = Gauge(
    "orderflow_embedding_jobs_queue_depth",
    "Number of pending embedding jobs"
)

# Metrics endpoint
@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type="text/plain")

# Usage in AI call
def call_llm(prompt: str):
    start = time.time()
    try:
        result = llm_provider.extract(prompt)
        latency_ms = (time.time() - start) * 1000

        ai_calls_total.labels(type="extraction", status="success").inc()
        ai_latency_ms.labels(type="extraction").observe(latency_ms)

        return result
    except Exception as e:
        ai_calls_total.labels(type="extraction", status="error").inc()
        raise
```

### AI Call Logging

```python
def log_ai_call(
    org_id: UUID,
    call_type: str,  # extraction | embedding
    provider: str,  # openai | anthropic
    model: str,
    tokens_in: int,
    tokens_out: int,
    latency_ms: int,
    status: str,
    error_type: str = None,
    error_message: str = None
):
    """Log AI call to database."""
    # Calculate cost based on model pricing
    cost_micros = calculate_cost(provider, model, tokens_in, tokens_out)

    ai_log = AICallLog(
        org_id=org_id,
        call_type=call_type,
        provider=provider,
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_micros=cost_micros,
        latency_ms=latency_ms,
        status=status,
        error_type=error_type,
        error_message=error_message,
        request_id=request_id_var.get()
    )

    db.session.add(ai_log)
    db.session.commit()

def calculate_cost(provider: str, model: str, tokens_in: int, tokens_out: int) -> int:
    """Calculate cost in micros (1 micro = 0.000001 USD)."""
    pricing = {
        ("openai", "gpt-4o"): {"input": 2.5, "output": 10.0},  # per 1M tokens
        ("openai", "gpt-4o-mini"): {"input": 0.15, "output": 0.60},
        ("openai", "text-embedding-ada-002"): {"input": 0.10, "output": 0.0}
    }

    rates = pricing.get((provider, model), {"input": 0, "output": 0})
    cost_usd = (tokens_in * rates["input"] + tokens_out * rates["output"]) / 1_000_000
    return int(cost_usd * 1_000_000)  # Convert to micros
```

### AI Monitor API

```python
@app.get("/ai/calls")
@require_role([Role.ADMIN, Role.INTEGRATOR])
def get_ai_calls(
    start_date: date,
    end_date: date,
    call_type: str = None,
    current_user: User = Depends(get_current_user)
):
    query = db.session.query(AICallLog).filter(
        AICallLog.org_id == current_user.org_id,
        AICallLog.created_at >= start_date,
        AICallLog.created_at <= end_date
    )

    if call_type:
        query = query.filter(AICallLog.call_type == call_type)

    logs = query.all()

    # Aggregate metrics
    total_cost = sum(log.cost_micros for log in logs) / 1_000_000  # USD
    total_calls = len(logs)
    error_rate = sum(1 for log in logs if log.status == "error") / total_calls if total_calls > 0 else 0

    # Latency percentiles
    latencies = sorted([log.latency_ms for log in logs if log.latency_ms])
    p50 = latencies[len(latencies) // 2] if latencies else 0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0

    return {
        "total_cost_usd": total_cost,
        "total_calls": total_calls,
        "error_rate": error_rate,
        "latency_percentiles": {"p50": p50, "p95": p95, "p99": p99},
        "calls": [
            {
                "id": str(log.id),
                "call_type": log.call_type,
                "provider": log.provider,
                "model": log.model,
                "tokens_in": log.tokens_in,
                "tokens_out": log.tokens_out,
                "cost_micros": log.cost_micros,
                "latency_ms": log.latency_ms,
                "status": log.status,
                "created_at": log.created_at.isoformat()
            }
            for log in logs
        ]
    }
```

### OpenTelemetry Integration (Optional)

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# Initialize tracer (if enabled)
if os.getenv("OTEL_ENABLED") == "true":
    trace.set_tracer_provider(TracerProvider())
    otlp_exporter = OTLPSpanExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))
    trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))

tracer = trace.get_tracer(__name__)

# Usage in API endpoint
@app.post("/draft-orders/{id}/push")
def push_draft_order(id: UUID):
    with tracer.start_as_current_span("push_draft_order") as span:
        span.set_attribute("draft_order_id", str(id))
        # ... business logic
        return {"status": "success"}

# Usage in background job
def process_export_job(export_id: UUID):
    with tracer.start_as_current_span("export_job") as span:
        span.set_attribute("export_id", str(export_id))
        # ... export logic
```

### Database Schema

```sql
CREATE TABLE ai_call_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organization(id),
    call_type TEXT NOT NULL,  -- extraction | embedding
    provider TEXT NOT NULL,  -- openai | anthropic
    model TEXT NOT NULL,
    tokens_in INT NULL,
    tokens_out INT NULL,
    cost_micros BIGINT NULL,  -- Cost in micros (1 micro = 0.000001 USD)
    latency_ms INT NULL,
    status TEXT NOT NULL,  -- success | error
    error_type TEXT NULL,
    error_message TEXT NULL,
    request_id TEXT NULL,
    trace_id TEXT NULL,  -- OpenTelemetry trace_id
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ai_call_log_org_date ON ai_call_log(org_id, created_at DESC);
CREATE INDEX idx_ai_call_log_type ON ai_call_log(org_id, call_type, created_at DESC);
```

## Testing Strategy

### Unit Tests
- Request ID generation and propagation
- Cost calculation for various models and token counts
- Latency percentile calculation
- Prometheus metric increment

### Component Tests
- Structured logging: verify JSON format and request_id presence
- Metrics endpoint: verify Prometheus format and metric values
- AI call logging: verify database record created with correct fields

### Integration Tests
- End-to-end: API request → background job → both logs have same request_id
- Metrics scrape: Prometheus server scrapes `/metrics` → metrics appear in Prometheus UI
- AI Monitor API: query ai_call_log → aggregated metrics returned

### E2E Tests
- Admin opens AI Monitor UI → charts render with data from ai_call_log
- High load test: 1000 concurrent requests → all have unique request_ids, no log loss
- OpenTelemetry: trace API request → view full trace in Jaeger UI

## SSOT Compliance Checklist

- [ ] Request IDs are UUID v4 and attached to all logs per §3.2
- [ ] Logs are structured JSON with timestamp, level, request_id, message per §3.2
- [ ] Prometheus metrics match §3.2 list (ai_calls_total, ai_latency_ms_bucket, embedding_queue_depth, extraction_confidence_histogram)
- [ ] ai_call_log table schema matches §5.4.16 design (provider, model, tokens, cost, latency, status)
- [ ] AI Monitor UI matches §9.7 requirements (cost/day, errors, p95 latency, filter by call_type/date range)
- [ ] AI call logging captures template_name + input_hash (not full prompt) per §11.3
- [ ] AI logs retained for 90 days (org-configurable) per §11.5
- [ ] OpenTelemetry support is optional per §3.2
- [ ] T-701 acceptance criteria met (every API call has request_id, logs are JSON)
- [ ] T-702 acceptance criteria met (Prometheus scrape works, includes required metrics)
- [ ] T-706 acceptance criteria met (AI Monitor UI shows rows, filterable by call_type and date range)
