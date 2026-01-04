# Quickstart: Data Retention & Cleanup

## Prerequisites

- Python 3.12+
- PostgreSQL 16
- Celery + Redis
- S3/MinIO

## Development Setup

### 1. Configure Retention Settings

Update org settings:
```sql
UPDATE organization
SET settings_json = jsonb_set(
  settings_json,
  '{raw_document_retention_days}',
  '365'
);
```

### 2. Start Celery Beat

```bash
# Terminal 1: Worker
celery -A orderflow.workers worker --loglevel=info

# Terminal 2: Beat scheduler
celery -A orderflow.workers beat --loglevel=info
```

### 3. Manually Trigger Retention Job (Testing)

```bash
celery -A orderflow.workers call tasks.retention_cleanup_job
```

Check logs:
```
INFO: Retention cleanup job completed
INFO: Stats: {"documents_soft_deleted": 42, "documents_hard_deleted": 10, "ai_logs_deleted": 5000}
```

## Testing

### Create Old Test Data

```sql
-- Old document (370 days ago)
INSERT INTO document (id, org_id, created_at, status)
VALUES (gen_random_uuid(), '...', NOW() - INTERVAL '370 days', 'ACTIVE');

-- Old AI log (95 days ago)
INSERT INTO ai_call_log (id, org_id, created_at, call_type, provider, model, status)
VALUES (gen_random_uuid(), '...', NOW() - INTERVAL '95 days', 'extraction', 'openai', 'gpt-4o', 'success');
```

### Run Retention Job

```bash
python -c "from orderflow.workers.retention_job import retention_cleanup_job; import asyncio; asyncio.run(retention_cleanup_job())"
```

### Verify Deletion

```sql
-- Document should be soft-deleted
SELECT id, status FROM document WHERE created_at < NOW() - INTERVAL '365 days';
-- Expected: status=DELETED

-- AI log should be hard-deleted
SELECT COUNT(*) FROM ai_call_log WHERE created_at < NOW() - INTERVAL '90 days';
-- Expected: 0
```

## Manual Deletion (Admin)

### Delete Specific Document

```bash
curl -X DELETE http://localhost:8000/documents/{id} \
  -H "Authorization: Bearer $ADMIN_JWT"
```

Verify audit log:
```sql
SELECT action, entity_id, actor_user_id FROM audit_log WHERE action = 'MANUAL_DELETE';
```

## Next Steps

- Configure Celery Beat schedule for production (02:00 UTC daily)
- Set up monitoring for retention job failures
- Test GDPR deletion workflow
