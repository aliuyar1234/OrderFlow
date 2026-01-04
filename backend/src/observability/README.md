# Observability Module

Production-grade observability infrastructure for OrderFlow.

## Features

- **Structured JSON Logging**: All logs in JSON format with request ID correlation
- **Prometheus Metrics**: Operational metrics for monitoring and alerting
- **Request ID Propagation**: Unique request IDs across async operations
- **Health Checks**: Liveness and readiness probes for Kubernetes
- **Distributed Tracing**: Optional OpenTelemetry integration

## Quick Start

### 1. Configure Logging

```python
from observability import configure_logging

configure_logging(level="INFO", json_format=True)
```

### 2. Add Middleware

```python
from fastapi import FastAPI
from observability import RequestIDMiddleware

app = FastAPI()
app.add_middleware(RequestIDMiddleware)
```

### 3. Include Router

```python
from observability.router import router as observability_router

app.include_router(observability_router)
```

### 4. Use in Code

```python
from observability import get_logger, ai_calls_total

logger = get_logger(__name__)

def process_document():
    logger.info("Processing document")
    ai_calls_total.labels(
        call_type="extraction",
        provider="openai",
        status="success"
    ).inc()
```

## Module Structure

```
observability/
├── __init__.py              # Public API exports
├── logging_config.py        # Structured JSON logging
├── request_id.py            # Request ID context management
├── middleware.py            # FastAPI middleware
├── metrics.py               # Prometheus metrics definitions
├── health.py                # Health check utilities
├── tracing.py               # OpenTelemetry integration (optional)
├── router.py                # FastAPI endpoints (/metrics, /health, /ready)
├── example_integration.py   # Full integration example
└── README.md                # This file
```

## Available Metrics

### AI Metrics
- `orderflow_ai_calls_total` - Total AI API calls
- `orderflow_ai_latency_ms` - AI call latency histogram
- `orderflow_ai_tokens_total` - Tokens consumed
- `orderflow_ai_cost_micros_total` - AI costs in micros

### Document Metrics
- `orderflow_documents_processed_total` - Documents processed
- `orderflow_extraction_duration_seconds` - Extraction time
- `orderflow_extraction_confidence` - Confidence scores

### Order Metrics
- `orderflow_orders_pushed_total` - Orders pushed to ERP
- `orderflow_orders_approval_rate` - Approval rate distribution

### Queue Metrics
- `orderflow_embedding_jobs_queue_depth` - Pending embedding jobs
- `orderflow_extraction_jobs_queue_depth` - Pending extraction jobs

### Validation Metrics
- `orderflow_validation_issues_total` - Validation issues detected
- `orderflow_matching_accuracy` - SKU matching accuracy

## Endpoints

- **GET /metrics** - Prometheus metrics (text/plain)
- **GET /health** - Component health checks (JSON)
- **GET /ready** - Readiness probe (JSON)

## Environment Variables

```bash
# Logging
LOG_LEVEL=INFO              # DEBUG, INFO, WARNING, ERROR
LOG_JSON=true               # true or false

# Tracing (optional)
OTEL_ENABLED=false          # Enable OpenTelemetry
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Infrastructure (for health checks)
DATABASE_URL=postgresql://...
REDIS_URL=redis://localhost:6379/0
S3_ENDPOINT_URL=http://localhost:9000
```

## Testing

```bash
# Test health endpoint
curl http://localhost:8000/health

# Test readiness endpoint
curl http://localhost:8000/ready

# Test metrics endpoint
curl http://localhost:8000/metrics

# Send request with custom request ID
curl -H "X-Request-ID: test-123" http://localhost:8000/api/v1/documents
```

## Dependencies

Required:
- `prometheus-client>=0.19.0`

Optional (for tracing):
- `opentelemetry-api>=1.22.0`
- `opentelemetry-sdk>=1.22.0`
- `opentelemetry-instrumentation-fastapi>=0.43b0`
- `opentelemetry-instrumentation-sqlalchemy>=0.43b0`
- `opentelemetry-exporter-otlp-proto-grpc>=1.22.0`

## Documentation

- **Full Guide**: [docs/observability.md](../../../docs/observability.md)
- **Quick Reference**: [docs/observability-quick-reference.md](../../../docs/observability-quick-reference.md)
- **Example Integration**: [example_integration.py](./example_integration.py)

## SSOT References

- §3.2 - Observability Architecture
- §8.10 - AI Observability
- FR-001 to FR-022 - Functional Requirements
