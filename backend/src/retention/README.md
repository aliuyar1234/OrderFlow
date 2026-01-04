# Data Retention Module

This module implements GDPR-compliant data retention and automatic cleanup for OrderFlow.

## Overview

The retention module provides:
- **Configurable retention periods** per organization for different data types
- **Automatic soft-delete** for expired user-facing data (documents, drafts, messages)
- **Automatic hard-delete** after grace period for permanently removing data
- **Immediate hard-delete** for system logs (AI calls, feedback events) without grace period
- **Manual deletion APIs** for admins to handle GDPR data subject requests
- **Audit logging** for all deletion operations
- **Retention reports** to preview eligible records before cleanup

## Architecture

### Components

1. **Schemas** (`schemas.py`)
   - `RetentionSettings`: Configuration for retention periods (stored in org.settings_json)
   - `RetentionStatistics`: Statistics from cleanup job execution
   - `RetentionReport`: Preview of records eligible for deletion
   - `RetentionSettingsUpdate`: Schema for partial updates

2. **Service** (`service.py`)
   - `RetentionService`: Core business logic for cleanup operations
   - `run_global_retention_cleanup()`: Main entry point for scheduled task

3. **Tasks** (`tasks.py`)
   - `retention_cleanup_task`: Daily scheduled Celery task (02:00 UTC)
   - `retention_cleanup_org_task`: Manual cleanup for specific organization

4. **Router** (`router.py`)
   - `GET /retention/settings`: View retention configuration
   - `PATCH /retention/settings`: Update retention periods (ADMIN only)
   - `GET /retention/report`: Preview eligible records
   - `POST /retention/cleanup`: Manually trigger cleanup (ADMIN only)
   - `GET /retention/statistics`: View cleanup statistics

### Two-Phase Deletion Strategy

#### Soft-Delete (Phase 1)
- Applied to user-facing data: documents, draft orders, inbound messages
- Sets `status=DELETED` or `deleted_at` field
- Removes files from object storage immediately
- Keeps database record for grace period (default 90 days)
- Allows recovery if needed

#### Hard-Delete (Phase 2)
- Applied after grace period expires for soft-deleted records
- Applied immediately to system logs (AI calls, feedback events)
- Permanently removes database records
- Cascades to related records via foreign keys
- Double-checks object storage cleanup

## Configuration

### Default Retention Periods (SSOT §11.5)

```python
RetentionSettings(
    document_retention_days=365,           # 1 year
    ai_log_retention_days=90,              # 3 months
    feedback_event_retention_days=365,     # 1 year
    draft_order_retention_days=730,        # 2 years
    inbound_message_retention_days=90,     # 3 months
    soft_delete_grace_period_days=90,      # 3 months
)
```

### Validation Rules
- All retention periods: 30-3650 days (min 30 days, max 10 years)
- Grace period: 1-365 days
- Audit logs: Minimum 365 days (non-configurable, enforced by system)

### Organization-Level Settings

Retention settings are stored in `org.settings_json`:

```json
{
  "retention": {
    "document_retention_days": 365,
    "ai_log_retention_days": 90,
    "feedback_event_retention_days": 365,
    "draft_order_retention_days": 730,
    "inbound_message_retention_days": 90,
    "soft_delete_grace_period_days": 90
  }
}
```

## Usage

### Scheduled Cleanup (Automatic)

Celery Beat runs the cleanup task daily at 02:00 UTC:

```python
# celeryconfig.py
from celery.schedules import crontab

beat_schedule = {
    'retention-cleanup-daily': {
        'task': 'retention.cleanup',
        'schedule': crontab(hour=2, minute=0),
    },
}
```

The task processes all organizations sequentially and logs statistics.

### Manual Cleanup (Admin API)

Admins can trigger cleanup for their organization:

```bash
# Trigger cleanup
curl -X POST https://api.orderflow.com/retention/cleanup \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Response
{
  "status": "enqueued",
  "task_id": "abc123...",
  "org_id": "org-uuid"
}
```

### Preview Eligible Records

Before running cleanup, admins can preview what would be deleted:

```bash
curl https://api.orderflow.com/retention/report \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Response
{
  "org_id": "org-uuid",
  "org_name": "Acme GmbH",
  "retention_settings": {...},
  "documents_eligible_for_soft_delete": 150,
  "documents_eligible_for_hard_delete": 50,
  "ai_logs_eligible_for_delete": 5000,
  "total_eligible_for_deletion": 5200
}
```

### Update Retention Settings

Admins can customize retention periods:

```bash
curl -X PATCH https://api.orderflow.com/retention/settings \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "document_retention_days": 180,
    "ai_log_retention_days": 60
  }'
```

## Implementation Status

### Current Status (Spec 026)
- ✅ Module structure created
- ✅ Schemas defined and validated
- ✅ Service logic implemented (placeholder for models)
- ✅ Celery tasks created
- ✅ Admin APIs implemented
- ✅ Audit logging integrated
- ✅ Unit tests written

### Pending (Future Specs)
- ⏳ Document model with `status` or `deleted_at` field
- ⏳ Draft order model with soft-delete support
- ⏳ Inbound message model with soft-delete support
- ⏳ AI call log model (hard-delete only)
- ⏳ Feedback event model (hard-delete only)
- ⏳ Object storage integration for file deletion
- ⏳ Integration tests with real database
- ⏳ Retention job history table for statistics

## Error Handling

### Object Storage Errors (FR-013)

The service implements robust error handling for object storage operations:

1. **404 Not Found**: Non-fatal (idempotent) - file already deleted
   - Logged at DEBUG level
   - Deletion proceeds normally

2. **403 Forbidden / 500 Server Error**: Retry required
   - Logged at ERROR level
   - Deletion marked for retry on next run
   - Maximum 3 retry attempts per file

3. **Unknown errors**: Retry with caution
   - Logged at ERROR level with full traceback
   - Never fail entire job due to single file error

### Database Errors

- Each organization's cleanup is isolated in its own transaction
- Errors in one org do not block processing of others
- Failed operations are rolled back per org
- Errors are logged with org_id context

## Monitoring & Alerts

### Success Conditions
- Job completes within expected time (< 5 minutes for 100k documents)
- All records deleted successfully
- No storage or database errors

### Warning Conditions (FR-019)
- **Anomaly detection**: > 10,000 records deleted in one run
  - Indicates potential misconfiguration or bulk data issue
  - Triggers warning alert to ops team

### Error Conditions (FR-018)
- Storage deletion failures (403/500 errors)
- Database errors during deletion
- 2+ consecutive job failures triggers alert

### Logged Metrics
```python
{
  "job": "retention_cleanup",
  "duration_seconds": 120.5,
  "orgs_processed": 15,
  "documents_soft_deleted": 150,
  "documents_hard_deleted": 75,
  "ai_logs_deleted": 5000,
  "feedback_events_deleted": 200,
  "storage_errors": 0,
  "database_errors": 0,
  "total_deleted": 5425,
  "status": "success"
}
```

## Security

### Access Control
- All retention APIs require ADMIN role
- Manual cleanup can only be triggered for user's own organization
- Retention settings are scoped per organization (multi-tenant isolation)

### Audit Trail
Every retention operation is logged:
- `RETENTION_SETTINGS_UPDATED`: Settings changed by admin
- `RETENTION_CLEANUP_TRIGGERED`: Manual cleanup initiated
- Automatic cleanups logged via structured logging (not audit_log)

Future enhancement: Manual deletions will log `MANUAL_DELETE` action.

## Testing

### Unit Tests
```bash
pytest tests/unit/test_retention.py -v
```

Tests cover:
- Schema validation (min/max retention periods)
- Default values per SSOT
- Statistics calculation
- Error detection

### Integration Tests (Future)
When models are implemented, integration tests will cover:
- End-to-end cleanup flow
- Soft-delete → grace period → hard-delete
- Active draft preservation rule
- Object storage cleanup
- Cross-org isolation

## SSOT Compliance

This implementation aligns with:
- **§11.5**: Data Retention periods and cleanup strategy
- **FR-001 to FR-022**: All functional requirements from spec 026
- **T-703**: Acceptance criteria for raw document and AI log cleanup

## Future Enhancements

1. **Retention job history table**: Store execution statistics for trend analysis
2. **Legal hold**: Prevent deletion of records under legal hold
3. **Archive storage**: Move old records to cold storage before deletion
4. **Restore from archive**: Recover archived records on demand
5. **Retention dashboard**: UI for visualizing retention metrics
6. **Per-customer retention**: Different retention for different customers
7. **Selective retention**: Tag records for longer/shorter retention

## References

- **SSOT**: §11.5 (Data Retention)
- **Spec**: [specs/026-data-retention/spec.md](../../../specs/026-data-retention/spec.md)
- **Plan**: [specs/026-data-retention/plan.md](../../../specs/026-data-retention/plan.md)
- **Tasks**: [specs/026-data-retention/tasks.md](../../../specs/026-data-retention/tasks.md)
