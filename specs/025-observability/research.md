# Research: Observability & AI Monitoring

## Key Decisions

### 1. Request ID Propagation via ContextVars

**Decision**: Use Python's contextvars for async-safe request ID storage.

**Rationale**:
- Thread-local storage is unsafe with async frameworks (FastAPI, asyncio)
- ContextVars are async-safe and propagate across await boundaries
- Celery tasks inherit context from parent request

**Implementation**:
```python
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default=None)

# Middleware sets context
request_id_var.set(str(uuid.uuid4()))

# Logger reads context
logger.info("Processing", extra={"request_id": request_id_var.get()})
```

---

### 2. Structured Logging Format

**Decision**: JSON format with standardized fields.

**Format**:
```json
{
  "timestamp": "2025-12-27T10:30:00Z",
  "level": "INFO",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "module": "orderflow.api.draft_orders",
  "function": "approve_draft_order",
  "message": "Draft approved",
  "org_id": "...",
  "user_id": "..."
}
```

**Benefits**: Easy parsing, supports log aggregation (ELK, Datadog), filterable by request_id.

---

### 3. Prometheus Metrics Design

**Metrics**:
- `orderflow_ai_calls_total{type,status}` - Counter
- `orderflow_ai_latency_ms{type}` - Histogram with buckets
- `orderflow_extraction_confidence` - Histogram
- `orderflow_embedding_jobs_queue_depth` - Gauge

**Why Histogram for Latency**: Enables percentile queries (p95, p99) in Prometheus.

---

## Best Practices

### Cost Tracking Accuracy

**Challenge**: AI provider billing may differ from token counts.

**Solution**:
1. Log exact token counts from API response
2. Calculate cost using known pricing table
3. Monthly reconciliation: compare calculated vs invoiced
4. Adjust pricing table if drift > 5%

---

### Log Volume Management

**Challenge**: High-traffic applications generate 100k+ log lines/hour.

**Solution**:
1. Use INFO level in production (DEBUG only for troubleshooting)
2. Sample verbose logs (log 1 in 100 for routine operations)
3. Structured format enables efficient compression (JSON gzip)
4. Rotate logs daily, retain 30 days

---

## Open Questions

1. **Should OpenTelemetry be mandatory or optional?**
   - Answer: Optional. Structured logs + Prometheus cover 90% of use cases. OTel adds complexity.

2. **How to handle AI cost spikes?**
   - Answer: Daily budget limits enforced at API wrapper level. Alert if daily spend > threshold.
