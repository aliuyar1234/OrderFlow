# Observability Guide

This guide covers OrderFlow's observability infrastructure including structured logging, metrics, tracing, and health checks.

**SSOT Reference**: §3.2 (Observability), §8.10 (AI Observability)

## Overview

OrderFlow implements production-grade observability:

- **Structured JSON Logging**: All logs in JSON format with request ID correlation
- **Prometheus Metrics**: Operational metrics for monitoring and alerting
- **Health Checks**: Endpoints for liveness and readiness probes
- **Distributed Tracing**: Optional OpenTelemetry integration for advanced debugging

## Request ID Correlation

Every API request receives a unique `request_id` (UUID v4) that is propagated through:

- All log entries during request processing
- Background jobs triggered by the request
- HTTP response headers (`X-Request-ID`)

### Usage in Code

```python
from observability import get_request_id, get_logger

logger = get_logger(__name__)

def process_document(doc_id: str):
    logger.info(f"Processing document {doc_id}")
    # request_id is automatically included in log output
```

### Client Usage

Clients can pass their own request ID for correlation:

```bash
curl -H "X-Request-ID: my-custom-id-123" http://localhost:8000/api/v1/documents
```

## Structured Logging

All logs are output in JSON format with the following fields:

```json
{
  "timestamp": "2025-01-04T12:34:56.789Z",
  "level": "INFO",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "module": "extraction.service",
  "function": "extract_document",
  "message": "Document extraction completed",
  "org_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

### Configuration

Configure logging in your application startup:

```python
from observability import configure_logging

# JSON format (production)
configure_logging(level="INFO", json_format=True)

# Human-readable format (development)
configure_logging(level="DEBUG", json_format=False)
```

### Environment Variables

- `LOG_LEVEL`: Log level (DEBUG, INFO, WARNING, ERROR) - default: INFO
- `LOG_JSON`: Enable JSON format (true/false) - default: true

### Adding Context to Logs

```python
from observability import get_logger

logger = get_logger(__name__)

# Log with extra context
logger.info(
    "Order pushed to ERP",
    extra={
        "org_id": str(org_id),
        "order_id": str(order_id),
        "erp_type": "sap",
    }
)

# Log errors with traceback
try:
    process_order()
except Exception as e:
    logger.error(
        f"Failed to process order: {e}",
        exc_info=True  # Include full traceback
    )
```

## Prometheus Metrics

Metrics are exposed at the `/metrics` endpoint in Prometheus exposition format.

### Available Metrics

#### Document Processing

```
orderflow_documents_processed_total{org_id, source, status}
```
Counter: Total documents processed
- `source`: email | upload
- `status`: success | error

#### Extraction

```
orderflow_extraction_duration_seconds{extraction_type}
orderflow_extraction_confidence{bucket}
```
- `extraction_duration_seconds`: Histogram of extraction time
- `extraction_confidence`: Histogram of confidence scores (0.0-1.0)

#### AI Calls

```
orderflow_ai_calls_total{call_type, provider, status}
orderflow_ai_latency_ms{call_type, provider}
orderflow_ai_tokens_total{call_type, provider, direction}
orderflow_ai_cost_micros_total{call_type, provider}
```
- `call_type`: extraction | embedding
- `provider`: openai | anthropic
- `direction`: input | output
- Cost in micros: 1 micro = $0.000001 USD

#### Orders

```
orderflow_orders_pushed_total{org_id, erp_type, status}
orderflow_orders_approval_rate{bucket}
```

#### Queue Depths

```
orderflow_embedding_jobs_queue_depth
orderflow_extraction_jobs_queue_depth
```
Gauges showing pending background jobs.

### Recording Metrics

```python
from observability import ai_calls_total, ai_latency_ms
import time

def call_llm_api():
    start = time.time()
    try:
        result = llm_provider.extract(prompt)
        latency_ms = (time.time() - start) * 1000

        ai_calls_total.labels(
            call_type="extraction",
            provider="openai",
            status="success"
        ).inc()

        ai_latency_ms.labels(
            call_type="extraction",
            provider="openai"
        ).observe(latency_ms)

        return result

    except Exception as e:
        ai_calls_total.labels(
            call_type="extraction",
            provider="openai",
            status="error"
        ).inc()
        raise
```

### Prometheus Configuration

Add OrderFlow to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'orderflow'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

### Example PromQL Queries

```promql
# AI call error rate
rate(orderflow_ai_calls_total{status="error"}[5m]) /
rate(orderflow_ai_calls_total[5m])

# p95 extraction latency
histogram_quantile(0.95,
  rate(orderflow_extraction_duration_seconds_bucket[5m])
)

# Daily AI cost (in USD)
sum(rate(orderflow_ai_cost_micros_total[1d])) / 1000000
```

## Health Checks

### Health Endpoint: `/health`

Returns health status of all system components.

**Response (200 OK - All healthy)**:
```json
{
  "status": "healthy",
  "components": {
    "database": {
      "status": "healthy",
      "message": "Database connection OK",
      "latency_ms": 5.2
    },
    "redis": {
      "status": "healthy",
      "message": "Redis connection OK",
      "latency_ms": 1.8
    },
    "object_storage": {
      "status": "healthy",
      "message": "Object storage connection OK",
      "latency_ms": 12.3
    }
  }
}
```

**Response (503 Service Unavailable - Component unhealthy)**:
```json
{
  "status": "unhealthy",
  "components": {
    "database": {
      "status": "unhealthy",
      "message": "Database error: connection refused",
      "latency_ms": null
    },
    ...
  }
}
```

### Readiness Endpoint: `/ready`

Lightweight check for Kubernetes readiness probes.

**Response (200 OK)**:
```json
{
  "status": "ready",
  "message": "Application is ready to serve traffic"
}
```

**Response (503 Service Unavailable)**:
```json
{
  "status": "not_ready",
  "message": "Database connection failed"
}
```

### Kubernetes Integration

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: orderflow-api
spec:
  containers:
  - name: api
    image: orderflow:latest
    livenessProbe:
      httpGet:
        path: /health
        port: 8000
      initialDelaySeconds: 30
      periodSeconds: 10
    readinessProbe:
      httpGet:
        path: /ready
        port: 8000
      initialDelaySeconds: 5
      periodSeconds: 5
```

## Distributed Tracing (Optional)

OpenTelemetry tracing is optional and disabled by default.

### Enable Tracing

1. Set environment variables:
   ```bash
   export OTEL_ENABLED=true
   export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
   ```

2. Start a tracing backend (Jaeger example):
   ```bash
   docker run -d --name jaeger \
     -e COLLECTOR_OTLP_ENABLED=true \
     -p 16686:16686 \
     -p 4317:4317 \
     jaegertracing/all-in-one:latest
   ```

3. Tracing will automatically instrument:
   - FastAPI endpoints
   - SQLAlchemy database queries
   - Redis operations

### Manual Instrumentation

```python
from observability.tracing import get_tracer

tracer = get_tracer(__name__)

def process_export_job(export_id: str):
    with tracer.start_as_current_span("export_job") as span:
        span.set_attribute("export_id", export_id)
        span.set_attribute("org_id", str(org_id))

        # Business logic here
        result = generate_export()

        span.set_attribute("result_size_bytes", len(result))
        return result
```

### Viewing Traces

Open Jaeger UI: http://localhost:16686

Filter by:
- Service: `orderflow`
- Operation: API endpoint or function name
- Tags: `org_id`, `user_id`, `request_id`

## Log Aggregation

For production deployments, aggregate logs to a centralized service:

### ELK Stack (Elasticsearch, Logstash, Kibana)

**Logstash configuration**:
```ruby
input {
  file {
    path => "/var/log/orderflow/*.log"
    codec => json
  }
}

filter {
  # Logs are already JSON, no parsing needed
}

output {
  elasticsearch {
    hosts => ["localhost:9200"]
    index => "orderflow-logs-%{+YYYY.MM.dd}"
  }
}
```

### Datadog

```bash
# Install Datadog agent
DD_API_KEY=<your-key> DD_SITE="datadoghq.com" bash -c "$(curl -L https://s3.amazonaws.com/dd-agent/scripts/install_script.sh)"

# Configure log collection
echo "logs_enabled: true" >> /etc/datadog-agent/datadog.yaml

# Add OrderFlow log config
cat > /etc/datadog-agent/conf.d/orderflow.d/conf.yaml <<EOF
logs:
  - type: file
    path: /var/log/orderflow/*.log
    service: orderflow
    source: python
    sourcecategory: orderflow
EOF

# Restart agent
systemctl restart datadog-agent
```

### Querying Logs by Request ID

**Elasticsearch**:
```json
GET orderflow-logs-*/_search
{
  "query": {
    "term": {
      "request_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  },
  "sort": [{ "timestamp": "asc" }]
}
```

**Datadog**:
```
request_id:550e8400-e29b-41d4-a716-446655440000
```

## Monitoring Best Practices

### Alerts

Configure alerts for critical conditions:

1. **High error rate**:
   ```promql
   rate(orderflow_ai_calls_total{status="error"}[5m]) > 0.1
   ```

2. **Slow extraction**:
   ```promql
   histogram_quantile(0.95,
     rate(orderflow_extraction_duration_seconds_bucket[5m])
   ) > 30
   ```

3. **Queue backlog**:
   ```promql
   orderflow_extraction_jobs_queue_depth > 100
   ```

4. **Component unhealthy**:
   Monitor `/health` endpoint returns 503

### Dashboards

Create Grafana dashboards for:

- **API Performance**: Request rate, latency percentiles, error rate
- **Extraction Pipeline**: Success rate, confidence scores, processing time
- **AI Costs**: Daily spend, tokens consumed, cost per model
- **Order Push**: Success rate, ERP latency, failures by type

### Retention

- **Logs**: 7 days local, 90 days in aggregation service
- **Metrics**: 15 days high-resolution, 1 year downsampled
- **Traces**: 7 days (sampling: 10% in production)

## Troubleshooting

### Request ID not appearing in logs

Ensure middleware is registered:
```python
from observability.middleware import RequestIDMiddleware

app.add_middleware(RequestIDMiddleware)
```

### Metrics endpoint returns 404

Ensure observability router is included:
```python
from observability.router import router as observability_router

app.include_router(observability_router)
```

### Tracing not working

1. Verify OpenTelemetry installed: `pip list | grep opentelemetry`
2. Check environment: `echo $OTEL_ENABLED`
3. Verify backend reachable: `curl http://localhost:4317`
4. Check logs for tracing errors

### High log volume

1. Increase log level to WARNING in production
2. Exclude health check endpoints from logging
3. Enable sampling for high-traffic endpoints:
   ```python
   LOG_SAMPLE_RATE=0.1  # Log 10% of requests
   ```

## Integration Examples

### Background Jobs (Celery)

Propagate request ID to background jobs:

```python
from observability import get_request_id, set_request_id

@celery_app.task
def process_extraction(document_id: str, request_id: str):
    # Restore request ID context
    set_request_id(request_id)

    # All logs will include this request_id
    logger.info(f"Processing document {document_id}")

# When enqueuing task
process_extraction.delay(
    document_id=str(doc.id),
    request_id=get_request_id()
)
```

### Custom Metrics

```python
from prometheus_client import Histogram

custom_metric = Histogram(
    "orderflow_custom_operation_duration",
    "Custom operation duration",
    ["operation_type"]
)

with custom_metric.labels(operation_type="import").time():
    # Operation is automatically timed
    perform_import()
```

## References

- Prometheus: https://prometheus.io/docs/
- OpenTelemetry: https://opentelemetry.io/docs/
- Grafana: https://grafana.com/docs/
- Jaeger: https://www.jaegertracing.io/docs/
