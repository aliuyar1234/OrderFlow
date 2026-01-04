# Feature Specification: Data Retention & Cleanup

**Feature Branch**: `026-data-retention`
**Created**: 2025-12-27
**Status**: Draft
**Module**: audit, documents, ai
**SSOT References**: §11.5 (Data Retention), T-703

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automatic Cleanup of Raw Documents (Priority: P1)

Raw MIME messages and document files older than the configured retention period (default 365 days) must be automatically deleted from object storage to comply with data retention policies and reduce storage costs.

**Why this priority**: Data retention compliance is mandatory for GDPR and storage cost management. Without automatic cleanup, storage costs grow indefinitely and compliance violations accumulate. This is a production-critical operational requirement.

**Independent Test**: Can be fully tested by seeding old documents, running the retention job, and verifying that documents older than retention period are deleted while newer documents remain.

**Acceptance Scenarios**:

1. **Given** org has `raw_document_retention_days=365` setting, **When** retention job runs, **Then** documents older than 365 days are soft-deleted (status set to DELETED)
2. **Given** document has `created_at = 370 days ago`, **When** retention job runs, **Then** document status changes to DELETED and raw file is removed from object storage
3. **Given** document has `created_at = 300 days ago`, **When** retention job runs, **Then** document remains unchanged (not yet expired)
4. **Given** soft-deleted document exists for 90 days, **When** hard-delete job runs, **Then** document record is permanently deleted from database
5. **Given** document is linked to an active draft order, **When** retention job runs, **Then** document is NOT deleted (preservation rule for active data)

---

### User Story 2 - Cleanup of AI Call Logs (Priority: P1)

AI call logs older than the configured retention period (default 90 days) must be automatically deleted to reduce database size while preserving recent logs for debugging and cost tracking.

**Why this priority**: AI call logs grow rapidly (potentially 100k+ rows/month). Without cleanup, database performance degrades and costs increase. 90-day retention provides sufficient debugging window while managing growth.

**Independent Test**: Can be fully tested by seeding old ai_call_log records, running the retention job, and verifying that records older than 90 days are deleted.

**Acceptance Scenarios**:

1. **Given** org has `ai_log_retention_days=90` setting, **When** retention job runs, **Then** ai_call_log records older than 90 days are hard-deleted
2. **Given** ai_call_log record has `created_at = 95 days ago`, **When** retention job runs, **Then** record is permanently deleted
3. **Given** ai_call_log record has `created_at = 30 days ago`, **When** retention job runs, **Then** record remains unchanged
4. **Given** 1 million old ai_call_log records exist, **When** retention job runs in batches, **Then** all records are deleted over multiple iterations without blocking database
5. **Given** org has custom retention period (180 days), **When** retention job runs, **Then** only records older than 180 days are deleted (org-specific setting respected)

---

### User Story 3 - Soft-Delete vs Hard-Delete Strategy (Priority: P1)

The system must implement a two-phase deletion strategy: soft-delete for user-facing data (documents, drafts) with grace period, hard-delete for system logs (ai_call_log) with immediate removal.

**Why this priority**: Soft-delete allows recovery from accidental deletions and provides audit trail. Hard-delete is appropriate for logs where recovery is not needed. This balances compliance, usability, and storage efficiency.

**Independent Test**: Can be fully tested by soft-deleting a document, verifying it's hidden from UI but still in database, waiting for grace period, and verifying hard-delete removes it permanently.

**Acceptance Scenarios**:

1. **Given** document is soft-deleted (status=DELETED), **When** querying via API, **Then** document is excluded from results (WHERE status != DELETED)
2. **Given** soft-deleted document has been DELETED for 90 days, **When** hard-delete job runs, **Then** document record and file are permanently removed
3. **Given** ai_call_log retention expires, **When** cleanup runs, **Then** records are hard-deleted immediately (no soft-delete phase)
4. **Given** admin wants to manually recover soft-deleted document, **When** admin runs recovery command, **Then** document status changes back to ACTIVE (if within grace period)
5. **Given** feedback_event has retention period 365 days, **When** retention job runs, **Then** old events are hard-deleted (no soft-delete for system events)

---

### User Story 4 - Manual Deletion by Admin (Priority: P2)

Administrators must be able to manually delete specific documents, drafts, or AI logs (e.g., for GDPR data subject requests) outside of automatic retention schedules.

**Why this priority**: GDPR requires ability to delete personal data on request. Automatic retention covers most cases, but manual deletion handles exceptions (right to be forgotten, sensitive data removal).

**Independent Test**: Can be fully tested by admin calling DELETE `/documents/{id}`, verifying immediate soft-delete, and confirming file is removed from object storage.

**Acceptance Scenarios**:

1. **Given** admin calls DELETE `/documents/{id}`, **When** request completes, **Then** document status changes to DELETED and raw file is removed from object storage
2. **Given** admin calls DELETE `/draft-orders/{id}`, **When** request completes, **Then** draft status changes to DELETED and all linked documents are soft-deleted
3. **Given** admin requests deletion of all data for customer "Acme GmbH", **When** bulk delete is triggered, **Then** all drafts, documents, and feedback events for that customer are soft-deleted
4. **Given** manual deletion is performed, **When** querying audit_log, **Then** entry exists with `action=MANUAL_DELETE`, `actor_user_id=<admin>`, `entity_id=<deleted-id>`
5. **Given** deleted document is linked to audit log, **When** viewing audit log, **Then** reference to deleted document shows "DELETED" status but preserves log entry

---

### User Story 5 - Retention Job Monitoring & Alerting (Priority: P3)

Retention jobs must log execution statistics (records deleted, errors, duration) and alert operators if jobs fail or if retention thresholds are exceeded.

**Why this priority**: Monitoring ensures retention jobs are running correctly. However, the jobs themselves (P1) must exist first. This is an operational monitoring feature.

**Independent Test**: Can be fully tested by running retention job, checking logs for execution summary, and simulating failure to verify alert is triggered.

**Acceptance Scenarios**:

1. **Given** retention job completes, **When** checking logs, **Then** log entry contains: `{"job": "retention_cleanup", "documents_deleted": 150, "ai_logs_deleted": 5000, "duration_ms": 12000, "status": "success"}`
2. **Given** retention job fails (database error), **When** error occurs, **Then** alert is sent to ops team and error is logged with traceback
3. **Given** retention job deletes 50k+ documents in one run, **When** job completes, **Then** warning alert is sent (unexpected high volume)
4. **Given** retention job hasn't run in 48 hours, **When** monitoring check runs, **Then** alert is triggered (job missed schedule)
5. **Given** admin wants to verify retention settings, **When** viewing settings page, **Then** current retention periods are displayed: documents (365d), ai_logs (90d), feedback_events (365d), audit_logs (365d minimum)

---

### Edge Cases

- What happens if document is deleted during active draft editing? (Optimistic locking prevents; delete fails if draft is in use)
- How does system handle retention job running during high load? (Job runs during low-traffic window; configurable schedule; batched deletes to avoid blocking)
- What if object storage deletion fails (S3 unreachable)? (Database record remains DELETED; retry deletion in next job run; log error)
- What happens to foreign key references when document is hard-deleted? (Cascading deletes remove dependent records; draft_order.document_id set to NULL)
- How does system handle timezone differences in retention calculation? (All timestamps are UTC; retention period calculated from UTC created_at)
- What if org changes retention period mid-flight? (Next job run uses new setting; previously deleted data is not recovered)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST implement background job `retention_cleanup_job` running daily at 02:00 UTC (configurable)
- **FR-002**: System MUST support org-level retention settings in `org.settings_json`: `raw_document_retention_days` (default 365), `ai_log_retention_days` (default 90), `feedback_event_retention_days` (default 365)
- **FR-003**: System MUST soft-delete documents older than `raw_document_retention_days` by setting `status=DELETED`
- **FR-004**: System MUST hard-delete soft-deleted documents after 90-day grace period
- **FR-005**: System MUST delete raw document files from object storage when soft-deleting document
- **FR-006**: System MUST hard-delete ai_call_log records older than `ai_log_retention_days` (no soft-delete)
- **FR-007**: System MUST hard-delete feedback_event records older than `feedback_event_retention_days`
- **FR-008**: System MUST preserve audit_log records for minimum 365 days (regardless of org setting)
- **FR-009**: System MUST skip deletion of documents linked to active draft_orders (status != DELETED)
- **FR-010**: System MUST execute deletions in batches of 1000 records to avoid long-running transactions
- **FR-011**: System MUST expose API: DELETE `/documents/{id}` for manual admin deletion
- **FR-012**: Soft-deleted documents (deleted_at IS NOT NULL) MUST be excluded from all API queries. Draft queries: If draft.document_id references soft-deleted document, document field returns null with warning 'Source document deleted'. Prevent cascade issues by validating document exists before draft operations.
- **FR-013**: Object storage deletion error handling: (1) 404 Not Found is non-fatal (file already gone, idempotent), log at DEBUG, (2) 403 Forbidden or 500 errors: mark job for retry on next run, log at ERROR, (3) Maximum 3 retry attempts per file before alerting, (4) Never fail entire retention job due to single file error.
- **FR-014**: System MUST expose API: DELETE `/draft-orders/{id}` for manual admin deletion
- **FR-015**: System MUST create audit_log entry for all manual deletions with `action=MANUAL_DELETE`
- **FR-016**: System MUST restrict manual deletion APIs to ADMIN role only
- **FR-017**: System MUST log retention job execution with: records_deleted, errors, duration_ms, status
- **FR-018**: System MUST send alert if retention job fails 2+ consecutive times
- **FR-019**: System MUST send warning if retention job deletes > 10k records in one run (anomaly detection)
- **FR-020**: System MUST expose API: GET `/admin/retention-settings` to view current retention periods
- **FR-021**: System MUST expose API: PATCH `/admin/retention-settings` to update retention periods (ADMIN only)
- **FR-022**: System MUST validate retention periods: min 30 days, max 3650 days (10 years)

### Key Entities *(include if feature involves data)*

- **Document**: Soft-deleted via status=DELETED when retention expires. Hard-deleted after 90-day grace period.

- **AICallLog**: Hard-deleted immediately when retention expires (no grace period).

- **FeedbackEvent**: Hard-deleted when retention expires.

- **AuditLog**: Never auto-deleted; min 365 days retention enforced.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Retention job correctly deletes documents older than configured period in 100% of test runs
- **SC-002**: Soft-deleted documents are hidden from API responses in 100% of queries
- **SC-003**: Hard-delete removes database records and object storage files in 100% of cases
- **SC-004**: Retention job completes within 5 minutes for 100k documents (performance test). 5-minute SLA assumes batch_size=1000 and parallel processing (4 workers). For >100k documents, either increase batch_size to 5000 or extend SLA to 15 minutes. Add performance test with realistic data volumes.
- **SC-005**: Manual deletion by admin creates audit_log entry in 100% of cases
- **SC-006**: Retention job alerts trigger when job fails in 100% of failure scenarios (integration test)
- **SC-007**: Storage costs reduce by 80%+ after retention cleanup runs on production data

## Dependencies

- **Depends on**:
  - **001-database-setup**: Requires document, ai_call_log, feedback_event, audit_log tables
  - **003-object-storage**: Requires S3/MinIO for document file deletion
  - **002-auth**: Requires ADMIN role for manual deletion APIs
  - **025-observability**: Requires structured logging for job monitoring

- **Enables**:
  - **Compliance**: GDPR data retention requirements met
  - **Cost management**: Storage and database costs controlled

## Implementation Notes

### Retention Job Implementation

```python
import asyncio
from datetime import datetime, timedelta

async def retention_cleanup_job():
    """Daily job to clean up expired data."""
    logger.info("Starting retention cleanup job")
    start_time = datetime.utcnow()

    stats = {
        "documents_soft_deleted": 0,
        "documents_hard_deleted": 0,
        "ai_logs_deleted": 0,
        "feedback_events_deleted": 0,
        "errors": []
    }

    orgs = get_all_orgs()

    for org in orgs:
        try:
            # Get org retention settings
            settings = org.settings_json
            raw_doc_retention_days = settings.get("raw_document_retention_days", 365)
            ai_log_retention_days = settings.get("ai_log_retention_days", 90)
            feedback_retention_days = settings.get("feedback_event_retention_days", 365)

            # Soft-delete old documents
            doc_cutoff = datetime.utcnow() - timedelta(days=raw_doc_retention_days)
            stats["documents_soft_deleted"] += soft_delete_documents(org.id, doc_cutoff)

            # Hard-delete soft-deleted documents older than grace period
            grace_cutoff = datetime.utcnow() - timedelta(days=90)
            stats["documents_hard_deleted"] += hard_delete_documents(org.id, grace_cutoff)

            # Hard-delete old AI logs (no soft-delete)
            ai_cutoff = datetime.utcnow() - timedelta(days=ai_log_retention_days)
            stats["ai_logs_deleted"] += hard_delete_ai_logs(org.id, ai_cutoff)

            # Hard-delete old feedback events
            feedback_cutoff = datetime.utcnow() - timedelta(days=feedback_retention_days)
            stats["feedback_events_deleted"] += hard_delete_feedback_events(org.id, feedback_cutoff)

        except Exception as e:
            logger.error(f"Retention cleanup failed for org {org.id}: {e}", exc_info=True)
            stats["errors"].append({"org_id": str(org.id), "error": str(e)})

    duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

    logger.info("Retention cleanup job completed", extra={
        "stats": stats,
        "duration_ms": duration_ms
    })

    # Alert on anomalies
    total_deleted = sum([stats["documents_soft_deleted"], stats["documents_hard_deleted"],
                         stats["ai_logs_deleted"], stats["feedback_events_deleted"]])
    if total_deleted > 10000:
        send_alert("Retention job deleted unusually high number of records", stats)

    if len(stats["errors"]) > 0:
        send_alert("Retention job encountered errors", stats["errors"])
```

### Soft-Delete Documents

```python
def soft_delete_documents(org_id: UUID, cutoff_date: datetime) -> int:
    """Soft-delete documents older than cutoff."""
    # Find documents to delete (excluding those linked to active drafts)
    documents = db.session.query(Document).filter(
        Document.org_id == org_id,
        Document.created_at < cutoff_date,
        Document.status != DocumentStatus.DELETED,
        ~Document.draft_orders.any(DraftOrder.status.notin_([DraftOrderStatus.DELETED]))
    ).limit(1000).all()  # Batch limit

    deleted_count = 0

    for doc in documents:
        try:
            # Delete from object storage
            if doc.raw_storage_key:
                delete_object_storage_file(doc.raw_storage_key)

            # Soft-delete in database
            doc.status = DocumentStatus.DELETED
            deleted_count += 1

        except Exception as e:
            logger.error(f"Failed to delete document {doc.id}: {e}")

    db.session.commit()
    return deleted_count
```

### Hard-Delete Documents

```python
def hard_delete_documents(org_id: UUID, grace_cutoff: datetime) -> int:
    """Hard-delete documents that have been soft-deleted for > grace period."""
    documents = db.session.query(Document).filter(
        Document.org_id == org_id,
        Document.status == DocumentStatus.DELETED,
        Document.updated_at < grace_cutoff  # Using updated_at as soft-delete timestamp
    ).limit(1000).all()

    deleted_count = 0

    for doc in documents:
        try:
            # Remove any remaining files (double-check)
            if doc.raw_storage_key:
                delete_object_storage_file(doc.raw_storage_key)

            # Hard-delete from database (cascading deletes will handle dependencies)
            db.session.delete(doc)
            deleted_count += 1

        except Exception as e:
            logger.error(f"Failed to hard-delete document {doc.id}: {e}")

    db.session.commit()
    return deleted_count
```

### Hard-Delete AI Logs

```python
def hard_delete_ai_logs(org_id: UUID, cutoff_date: datetime) -> int:
    """Hard-delete AI call logs older than cutoff."""
    result = db.session.query(AICallLog).filter(
        AICallLog.org_id == org_id,
        AICallLog.created_at < cutoff_date
    ).delete(synchronize_session=False)

    db.session.commit()
    return result
```

### Manual Deletion API

```python
@app.delete("/documents/{id}")
@require_role(Role.ADMIN)
def delete_document(id: UUID, current_user: User):
    doc = get_document(id, current_user.org_id)

    # Delete from object storage
    if doc.raw_storage_key:
        delete_object_storage_file(doc.raw_storage_key)

    # Soft-delete
    doc.status = DocumentStatus.DELETED
    db.session.commit()

    # Audit log
    create_audit_log(
        org_id=current_user.org_id,
        actor_user_id=current_user.id,
        action="MANUAL_DELETE",
        entity_type="document",
        entity_id=doc.id
    )

    return {"id": doc.id, "status": "DELETED"}
```

### Retention Settings API

```python
@app.get("/admin/retention-settings")
@require_role(Role.ADMIN)
def get_retention_settings(current_user: User):
    org = get_org(current_user.org_id)
    return {
        "raw_document_retention_days": org.settings_json.get("raw_document_retention_days", 365),
        "ai_log_retention_days": org.settings_json.get("ai_log_retention_days", 90),
        "feedback_event_retention_days": org.settings_json.get("feedback_event_retention_days", 365),
        "audit_log_retention_days": 365  # Minimum, not configurable
    }

@app.patch("/admin/retention-settings")
@require_role(Role.ADMIN)
def update_retention_settings(settings: dict, current_user: User):
    org = get_org(current_user.org_id)

    # Validate
    for key, value in settings.items():
        if key.endswith("_retention_days"):
            if not (30 <= value <= 3650):
                raise HTTPException(status_code=400, detail=f"{key} must be between 30 and 3650 days")

    # Update
    org.settings_json.update(settings)
    db.session.commit()

    # Audit log
    create_audit_log(
        org_id=current_user.org_id,
        actor_user_id=current_user.id,
        action="RETENTION_SETTINGS_UPDATED",
        entity_type="organization",
        entity_id=org.id,
        details_json=settings
    )

    return {"status": "updated", "settings": settings}
```

### Job Scheduling (Celery/APScheduler)

```python
from celery import Celery
from celery.schedules import crontab

celery = Celery("orderflow")

celery.conf.beat_schedule = {
    "retention-cleanup": {
        "task": "tasks.retention_cleanup_job",
        "schedule": crontab(hour=2, minute=0)  # Daily at 02:00 UTC
    }
}
```

## Testing Strategy

### Unit Tests
- Retention period calculation with various cutoff dates
- Soft-delete vs hard-delete logic
- Batch deletion limit (1000 records)
- Validation of retention period constraints (30-3650 days)

### Component Tests
- Soft-delete: document status changes to DELETED, file removed from storage
- Hard-delete: document record removed from database
- Grace period: documents soft-deleted < 90 days ago are not hard-deleted
- Active draft exclusion: documents linked to active drafts are not deleted

### Integration Tests
- End-to-end: seed old documents → run retention job → verify documents deleted
- Manual deletion: admin calls DELETE → document soft-deleted → audit log entry created
- Retention settings: PATCH settings → next job run uses new settings
- Alert triggering: retention job fails → alert sent to ops team

### E2E Tests
- Admin views retention settings → updates periods → runs manual cleanup → verifies logs show deletion stats
- Retention job runs on schedule → documents older than retention period are removed → storage costs decrease

## SSOT Compliance Checklist

- [ ] Retention periods match §11.5 defaults (documents 365d, ai_logs 90d, feedback_events 365d, audit_logs 365d minimum)
- [ ] Soft-delete strategy implemented for user-facing data (documents, drafts)
- [ ] Hard-delete strategy implemented for system logs (ai_call_log, feedback_event)
- [ ] Grace period (90 days) for hard-delete of soft-deleted documents
- [ ] Retention job runs daily per §11.5
- [ ] Manual deletion creates audit_log entry per §11.4
- [ ] Audit logs retained for minimum 365 days (not configurable)
- [ ] Org-level retention settings stored in org.settings_json
- [ ] Retention job logs execution statistics (records_deleted, duration, errors)
- [ ] T-703 acceptance criteria met (raw docs/AI logs older than retention are deleted/anonymized, integration test seeds old docs → cleanup removes them)
