# Quickstart: Observability & AI Monitoring

## Prerequisites

- Python 3.12+
- PostgreSQL 16
- Prometheus server (optional)

## Development Setup

### 1. Database Migration

```bash
cd backend
alembic upgrade head
```

### 2. Configure Structured Logging

Add to `backend/logging.conf`:
```json
{
  "version": 1,
  "formatters": {
    "json": {
      "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
      "format": "%(timestamp)s %(level)s %(request_id)s %(module)s %(message)s"
    }
  },
  "handlers": {
    "console": {
      "class": "logging.StreamHandler",
      "formatter": "json"
    }
  },
  "root": {
    "level": "INFO",
    "handlers": ["console"]
  }
}
```

### 3. Run Backend

```bash
uvicorn orderflow.main:app --reload
```

### 4. Verify Metrics Endpoint

```bash
curl http://localhost:8000/metrics
```

Expected output (Prometheus format):
```
# HELP orderflow_ai_calls_total Total AI API calls
# TYPE orderflow_ai_calls_total counter
orderflow_ai_calls_total{type="extraction",status="success"} 42
...
```

## Testing

### Trigger AI Call and Check Logs

```bash
# Trigger extraction
curl -X POST http://localhost:8000/documents/{id}/extract \
  -H "Authorization: Bearer $JWT_TOKEN"

# Check ai_call_log
SELECT provider, model, tokens_in, tokens_out, cost_micros, latency_ms
FROM ai_call_log
ORDER BY created_at DESC LIMIT 1;
```

### View AI Monitor Dashboard

Open browser: `http://localhost:3000/admin/ai-monitor`

Expected charts:
- Cost per day (line chart)
- Calls by model (pie chart)
- Error rate (gauge)
- Latency percentiles (table)

## Prometheus Integration (Optional)

### 1. Install Prometheus

```bash
# macOS
brew install prometheus

# Docker
docker run -d -p 9090:9090 prom/prometheus
```

### 2. Configure Scrape Target

Add to `prometheus.yml`:
```yaml
scrape_configs:
  - job_name: 'orderflow'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:8000']
```

### 3. Query Metrics

Open `http://localhost:9090` and query:
```promql
rate(orderflow_ai_calls_total[5m])
histogram_quantile(0.95, orderflow_ai_latency_ms_bucket)
```
