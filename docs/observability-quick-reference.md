# Observability Quick Reference

Quick reference for OrderFlow observability features.

## Logging

```python
from observability import get_logger

logger = get_logger(__name__)

# Basic logging
logger.info("Processing started")
logger.warning("Low confidence score")
logger.error("Failed to connect", exc_info=True)

# With context
logger.info("Order processed", extra={
    "org_id": str(org_id),
    "order_id": str(order_id),
    "amount": 1250.50
})
```

## Request ID

```python
from observability import get_request_id, set_request_id

# Get current request ID
request_id = get_request_id()

# Pass to background job
task.delay(doc_id=doc_id, request_id=request_id)

# In the background job
set_request_id(request_id)  # Restore context
```

## Metrics

```python
from observability import (
    ai_calls_total,
    ai_latency_ms,
    extraction_confidence_histogram,
    documents_processed_total
)
import time

# Counter
ai_calls_total.labels(
    call_type="extraction",
    provider="openai",
    status="success"
).inc()

# Histogram
start = time.time()
# ... do work ...
latency_ms = (time.time() - start) * 1000
ai_latency_ms.labels(
    call_type="extraction",
    provider="openai"
).observe(latency_ms)

# Record confidence score
extraction_confidence_histogram.observe(0.85)

# Record document processing
documents_processed_total.labels(
    org_id=str(org_id),
    source="email",
    status="success"
).inc()
```

## Application Setup

```python
from fastapi import FastAPI
from observability import configure_logging, RequestIDMiddleware
from observability.router import router as observability_router

# Configure logging
configure_logging(level="INFO", json_format=True)

# Create app
app = FastAPI()

# Add middleware
app.add_middleware(RequestIDMiddleware)

# Include observability endpoints
app.include_router(observability_router)
```

## Endpoints

- **GET /metrics** - Prometheus metrics
- **GET /health** - Component health checks
- **GET /ready** - Readiness probe

## Environment Variables

```bash
# Logging
LOG_LEVEL=INFO              # DEBUG|INFO|WARNING|ERROR
LOG_JSON=true               # true|false

# Tracing (optional)
OTEL_ENABLED=false          # true|false
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Infrastructure
DATABASE_URL=postgresql://...
REDIS_URL=redis://localhost:6379/0
S3_ENDPOINT_URL=http://localhost:9000
```

## Common Patterns

### Timed Operation

```python
from observability import ai_latency_ms
import time

def call_ai_api():
    start = time.time()
    try:
        result = provider.call_api()
        return result
    finally:
        latency_ms = (time.time() - start) * 1000
        ai_latency_ms.labels(
            call_type="extraction",
            provider="openai"
        ).observe(latency_ms)
```

### Error Tracking

```python
from observability import get_logger, ai_calls_total

logger = get_logger(__name__)

try:
    result = call_api()
    ai_calls_total.labels(
        call_type="extraction",
        provider="openai",
        status="success"
    ).inc()
except Exception as e:
    logger.error(f"API call failed: {e}", exc_info=True)
    ai_calls_total.labels(
        call_type="extraction",
        provider="openai",
        status="error"
    ).inc()
    raise
```

### Background Job with Request ID

```python
from observability import get_request_id, set_request_id, get_logger

logger = get_logger(__name__)

# In API endpoint
@app.post("/extract")
def trigger_extraction():
    request_id = get_request_id()
    extract_task.delay(doc_id="...", request_id=request_id)

# In Celery task
@celery_app.task
def extract_task(doc_id: str, request_id: str):
    set_request_id(request_id)  # Restore context
    logger.info(f"Extracting document {doc_id}")
    # All logs will have the same request_id
```

## Prometheus Queries

```promql
# Error rate (last 5 minutes)
rate(orderflow_ai_calls_total{status="error"}[5m]) /
rate(orderflow_ai_calls_total[5m])

# p95 latency
histogram_quantile(0.95,
  rate(orderflow_ai_latency_ms_bucket[5m])
)

# Total AI cost today (USD)
sum(increase(orderflow_ai_cost_micros_total[24h])) / 1000000

# Queue depth
orderflow_extraction_jobs_queue_depth
```

## Alert Examples

```yaml
# Prometheus alerts.yml
groups:
  - name: orderflow
    interval: 1m
    rules:
      - alert: HighErrorRate
        expr: rate(orderflow_ai_calls_total{status="error"}[5m]) > 0.1
        for: 5m
        annotations:
          summary: "High AI error rate"

      - alert: SlowExtraction
        expr: histogram_quantile(0.95, rate(orderflow_extraction_duration_seconds_bucket[5m])) > 30
        for: 5m
        annotations:
          summary: "Extraction taking too long"

      - alert: HighQueueDepth
        expr: orderflow_extraction_jobs_queue_depth > 100
        for: 5m
        annotations:
          summary: "Extraction queue backing up"
```

## Troubleshooting

**No request_id in logs?**
- Ensure `RequestIDMiddleware` is added to app
- Check middleware is registered before routes

**Metrics endpoint 404?**
- Include observability router: `app.include_router(observability_router)`

**Health check fails?**
- Check database: `psql -U orderflow -d orderflow -c "SELECT 1"`
- Check Redis: `redis-cli ping`
- Check MinIO: `curl http://localhost:9000/minio/health/live`

**Tracing not working?**
- Verify `OTEL_ENABLED=true`
- Install dependencies: `pip install opentelemetry-*`
- Check backend: `curl http://localhost:4317`
