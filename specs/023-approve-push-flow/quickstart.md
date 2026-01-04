# Quickstart: Approve & Push Flow

## Prerequisites

- Python 3.12+
- PostgreSQL 16 running locally
- Redis server running
- Celery worker configured
- OrderFlow backend installed (see main README)

## Development Setup

### 1. Database Migration

Apply the approve/push schema:

```bash
cd backend
alembic upgrade head
```

Verify tables created:

```sql
\d draft_order    -- Should have approved_by_user_id, approved_at columns
\d erp_export     -- New table
\d audit_log      -- Existing table
```

### 2. Redis Configuration

Start Redis locally:

```bash
# macOS/Linux
redis-server

# Docker
docker run -d -p 6379:6379 redis:7-alpine
```

Verify connection:

```bash
redis-cli ping
# Expected: PONG
```

### 3. Environment Variables

Add to `.env`:

```bash
# Redis
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Idempotency
IDEMPOTENCY_TTL_HOURS=24
```

### 4. Start Celery Worker

In separate terminal:

```bash
cd backend
celery -A orderflow.workers worker --loglevel=info --concurrency=4
```

Expected output:
```
[tasks]
  . orderflow.workers.export_worker.process_export_job

[2025-12-27 10:00:00,000: INFO/MainProcess] Connected to redis://localhost:6379/0
[2025-12-27 10:00:00,100: INFO/MainProcess] celery@hostname ready.
```

### 5. Run Backend Server

```bash
cd backend
uvicorn orderflow.main:app --reload --port 8000
```

Verify endpoints:

```bash
curl http://localhost:8000/docs
# Should show:
# - POST /draft-orders/{id}/approve
# - POST /draft-orders/{id}/push
# - POST /draft-orders/{id}/retry-push
```

## Testing

### Unit Tests

```bash
cd backend
pytest tests/unit/test_approve_service.py -v
pytest tests/unit/test_push_service.py -v
pytest tests/unit/test_state_machine.py -v
```

### Integration Tests

```bash
# Requires PostgreSQL + Redis running
pytest tests/integration/test_approve_push_flow.py -v
pytest tests/integration/test_idempotency.py -v
```

### E2E Tests

```bash
# Requires full stack (API + worker + Redis)
pytest tests/e2e/test_full_workflow.py -v
```

## Manual Testing

### 1. Create READY Draft

```bash
# Create draft via API or seed script
curl -X POST http://localhost:8000/draft-orders \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "...",
    "lines": [...]
  }'

# Run validation to set status=READY
curl -X POST http://localhost:8000/draft-orders/{id}/validate \
  -H "Authorization: Bearer $JWT_TOKEN"
```

### 2. Approve Draft

```bash
curl -X POST http://localhost:8000/draft-orders/{id}/approve \
  -H "Authorization: Bearer $JWT_TOKEN"

# Expected response:
{
  "id": "...",
  "status": "APPROVED",
  "approved_at": "2025-12-27T10:30:00Z"
}
```

Verify in database:

```sql
SELECT id, status, approved_by_user_id, approved_at FROM draft_order WHERE id = '...';
```

### 3. Push Draft (with Idempotency)

```bash
# Generate idempotency key
IDEMPOTENCY_KEY=$(uuidgen)

# First push
curl -X POST http://localhost:8000/draft-orders/{id}/push \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Idempotency-Key: $IDEMPOTENCY_KEY"

# Expected response:
{
  "erp_export_id": "...",
  "status": "PUSHING"
}

# Second push with same key (should return same export_id)
curl -X POST http://localhost:8000/draft-orders/{id}/push \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Idempotency-Key: $IDEMPOTENCY_KEY"

# Expected response:
{
  "erp_export_id": "...",  # Same ID
  "status": "in_progress"  # or "SENT" if completed
}
```

Verify idempotency cache:

```bash
redis-cli GET "idempotency:{draft_id}:{idempotency_key}"
# Expected: {export_id}
```

### 4. Monitor Export Job

Watch Celery worker logs:

```
[2025-12-27 10:35:00,000: INFO/MainProcess] Task process_export_job[...] received
[2025-12-27 10:35:05,000: INFO/ForkPoolWorker-1] Export completed: {export_id}
[2025-12-27 10:35:05,100: INFO/ForkPoolWorker-1] Task process_export_job[...] succeeded
```

Verify in database:

```sql
SELECT id, status, export_storage_key, sent_at FROM erp_export WHERE draft_order_id = '...';
-- Expected: status=SENT, sent_at=<timestamp>

SELECT id, status FROM draft_order WHERE id = '...';
-- Expected: status=PUSHED
```

### 5. Check Audit Log

```bash
curl -X GET "http://localhost:8000/audit-log?entity_id={draft_id}" \
  -H "Authorization: Bearer $JWT_TOKEN"

# Expected response:
[
  {
    "action": "DRAFT_APPROVED",
    "actor_user_id": "...",
    "created_at": "2025-12-27T10:30:00Z"
  },
  {
    "action": "DRAFT_PUSHED",
    "actor_user_id": "...",
    "created_at": "2025-12-27T10:35:00Z"
  }
]
```

### 6. Test Retry Flow

Simulate failure:

```bash
# Manually set export to FAILED
UPDATE erp_export SET status = 'FAILED', error_json = '{"error": "SFTP unreachable"}' WHERE id = '...';
UPDATE draft_order SET status = 'ERROR' WHERE id = '...';
```

Retry push:

```bash
curl -X POST http://localhost:8000/draft-orders/{id}/retry-push \
  -H "Authorization: Bearer $JWT_TOKEN"

# Expected response:
{
  "erp_export_id": "...",  # New export ID
  "status": "PUSHING"
}
```

Verify new export created:

```sql
SELECT id, status, created_at FROM erp_export WHERE draft_order_id = '...' ORDER BY created_at DESC;
-- Expected: 2 rows (failed + retry)
```

## Troubleshooting

### Approve Returns 409 "Draft must be READY"

Check draft status:

```sql
SELECT id, status FROM draft_order WHERE id = '...';
```

If status is not READY, run validation:

```bash
curl -X POST http://localhost:8000/draft-orders/{id}/validate \
  -H "Authorization: Bearer $JWT_TOKEN"
```

### Push Returns 400 "No active ERP connector"

Verify connector exists:

```sql
SELECT id, connector_type, is_active FROM erp_connection WHERE org_id = '...';
```

Create connector if missing (see spec 022-dropzone-connector).

### Export Job Hangs

Check Celery worker is running:

```bash
ps aux | grep celery
```

Check Redis connection:

```bash
redis-cli ping
```

View Celery logs:

```bash
tail -f celery.log
```

### Idempotency Not Working

Check Redis:

```bash
redis-cli GET "idempotency:{draft_id}:{key}"
```

If empty, check TTL configuration:

```bash
echo $IDEMPOTENCY_TTL_HOURS
# Expected: 24
```

Verify Redis client in code:

```python
import redis
redis_client = redis.Redis.from_url(os.getenv("REDIS_URL"))
redis_client.ping()  # Should not raise
```

## Next Steps

- Implement frontend approve/push buttons (see `specs/023-approve-push-flow/contracts/openapi.yaml`)
- Configure ERP connector (spec 022-dropzone-connector)
- Set up monitoring for export worker (Prometheus metrics)
- Configure audit log retention policy (spec 026-data-retention)
