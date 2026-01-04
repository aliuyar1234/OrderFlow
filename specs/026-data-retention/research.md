# Research: Data Retention & Cleanup

## Key Decisions

### 1. Two-Phase Deletion Strategy

**Decision**: Soft-delete user data with 90-day grace period, hard-delete system logs immediately.

**Rationale**:
- User-facing data (documents, drafts) needs recovery window
- System logs (AI calls, feedback) no recovery needed
- Grace period allows "oops" recovery without backup restore

**Implementation**:
```python
# Phase 1: Soft-delete (status=DELETED, file removed)
document.status = DocumentStatus.DELETED
delete_s3_file(document.raw_storage_key)

# Phase 2: Hard-delete (90 days later, DB record removed)
db.session.delete(document)
```

---

### 2. Batched Deletion

**Decision**: Delete in batches of 1000 records to avoid long-running transactions.

**Rationale**:
- Large deletes lock tables, block other queries
- Batching allows incremental progress
- Job can resume if interrupted

**Implementation**:
```python
while True:
    batch = db.query(Document).filter(...).limit(1000).all()
    if not batch:
        break

    for doc in batch:
        db.session.delete(doc)
    db.session.commit()
```

---

### 3. Active Draft Preservation

**Decision**: Skip deletion for documents linked to active draft orders.

**Rationale**:
- Deleting documents while draft is in use breaks workflow
- Operators may need to re-extract after retention period
- Active drafts are by definition recent (< retention period)

**Implementation**:
```python
documents = db.query(Document).filter(
    Document.created_at < cutoff,
    ~Document.draft_orders.any(DraftOrder.status != DraftOrderStatus.DELETED)
).all()
```

---

## Best Practices

### Retention Period Validation

**Constraints**:
- Minimum: 30 days (GDPR allows short retention with justification)
- Maximum: 3650 days (10 years, exceeds typical compliance needs)
- Audit logs: Minimum 365 days (not user-configurable)

**Validation**:
```python
if not (30 <= retention_days <= 3650):
    raise ValueError("Retention must be between 30 and 3650 days")
```

---

### Job Scheduling

**Recommendation**: Run daily at 02:00 UTC (low-traffic window).

**Celery Beat Configuration**:
```python
celery.conf.beat_schedule = {
    "retention-cleanup": {
        "task": "tasks.retention_cleanup_job",
        "schedule": crontab(hour=2, minute=0)
    }
}
```

---

### Monitoring and Alerting

**Alerts**:
1. Job failed 2+ consecutive times → critical alert
2. Job deleted > 10k records → warning (anomaly)
3. Job hasn't run in 48 hours → critical alert

**Metrics**:
- Documents deleted/day (track storage savings)
- Job duration (detect performance degradation)
- Errors per run (track reliability)

---

## GDPR Compliance

### Right to Erasure (RTBF)

**Requirement**: Delete all personal data on user request.

**Implementation**:
```python
@app.delete("/customers/{id}/gdpr-delete")
@require_role(Role.ADMIN)
def gdpr_delete_customer(id: UUID):
    # Soft-delete all drafts for customer
    drafts = db.query(DraftOrder).filter_by(customer_id=id).all()
    for draft in drafts:
        draft.status = DraftOrderStatus.DELETED

    # Soft-delete all documents
    documents = db.query(Document).join(DraftOrder).filter_by(customer_id=id).all()
    for doc in documents:
        doc.status = DocumentStatus.DELETED
        delete_s3_file(doc.raw_storage_key)

    # Soft-delete customer
    customer.status = CustomerStatus.DELETED

    # Audit log
    create_audit_log(action="GDPR_DELETE", entity_id=id)
```

---

## Testing Strategy

### Integration Test: Retention Job

```python
def test_retention_deletes_old_documents():
    # Create old document
    old_doc = create_document(created_at=datetime.utcnow() - timedelta(days=400))

    # Run retention job
    retention_cleanup_job()

    # Verify soft-deleted
    db.refresh(old_doc)
    assert old_doc.status == DocumentStatus.DELETED

    # Wait grace period and run again
    old_doc.updated_at = datetime.utcnow() - timedelta(days=100)
    db.commit()
    retention_cleanup_job()

    # Verify hard-deleted
    assert db.query(Document).filter_by(id=old_doc.id).first() is None
```

---

## Open Questions

1. **Should retention be configurable per customer?**
   - Answer: No. Org-level setting is sufficient. Per-customer adds complexity without clear benefit.

2. **What happens to soft-deleted documents during grace period?**
   - Answer: Hidden from API (WHERE status != DELETED). Admin can manually recover if needed.

3. **Should retention job send summary email to admins?**
   - Answer: Yes. Weekly summary (total deleted, storage saved, errors). Helps track compliance.
