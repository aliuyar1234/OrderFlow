# Research: Approve & Push Flow

## Key Decisions

### 1. State Machine Enforcement

**Decision**: Implement explicit state machine validation for draft status transitions.

**Rationale**:
- Prevents invalid state transitions (e.g., NEEDS_REVIEW → PUSHED)
- Makes allowed transitions explicit and testable
- Provides clear error messages for operators
- Enables state visualization in UI

**Implementation**:
```python
ALLOWED_TRANSITIONS = {
    (DraftOrderStatus.READY, DraftOrderStatus.APPROVED),
    (DraftOrderStatus.APPROVED, DraftOrderStatus.PUSHING),
    (DraftOrderStatus.PUSHING, DraftOrderStatus.PUSHED),
    (DraftOrderStatus.PUSHING, DraftOrderStatus.ERROR),
    (DraftOrderStatus.ERROR, DraftOrderStatus.PUSHING),  # Retry
}
```

**Alternatives Rejected**:
- Allow any transition (rejected: too error-prone, no validation)
- Database constraints only (rejected: error messages less clear, harder to test)

---

### 2. Idempotency via Redis Cache

**Decision**: Store idempotency key mappings in Redis with 24-hour TTL.

**Rationale**:
- Network retries typically happen within seconds/minutes, not days
- Redis provides fast lookups (< 1ms) without database load
- TTL prevents unbounded cache growth
- In-memory cache survives across API restarts (unlike process-level cache)

**Implementation**:
```python
key = f"idempotency:{draft_id}:{idempotency_key}"
redis_client.setex(key, 24 * 3600, str(export_id))
```

**Alternatives Rejected**:
- Database table (rejected: slower, adds DB load for temporary data)
- In-memory dict (rejected: lost on restart, no TTL, memory leak risk)
- No idempotency (rejected: duplicate exports on retry)

**Edge Cases**:
- Same key for different drafts → scoped by draft_id, allowed
- Key reused after 24h → treated as new request, acceptable
- Redis down → idempotency disabled, fall back to status check (409 if already pushing)

---

### 3. Two-Phase Push: PUSHING → PUSHED

**Decision**: Set status to PUSHING immediately, then PUSHED on background worker success.

**Rationale**:
- API responds quickly (< 200ms) without waiting for export
- Operator sees immediate feedback (export started)
- Background worker handles slow operations (S3 upload, SFTP transfer)
- Status tracks progress: PUSHING = in-flight, PUSHED = completed

**Implementation**:
```python
# API endpoint
draft.status = DraftOrderStatus.PUSHING
enqueue_export_job(export.id)
return {"status": "PUSHING"}

# Background worker
export.status = ERPExportStatus.SENT
draft.status = DraftOrderStatus.PUSHED
```

**Alternatives Rejected**:
- Synchronous push (rejected: slow API response, timeout risk)
- Set PUSHED immediately (rejected: inaccurate, no in-flight indicator)

---

### 4. Audit Logging Strategy

**Decision**: Create separate audit_log entries for DRAFT_APPROVED, DRAFT_PUSHED, DRAFT_PUSH_FAILED.

**Rationale**:
- Separate entries enable filtering by action type
- Each entry has accurate timestamp (not aggregated)
- Failed pushes are distinct events (not updates)
- Actor tracking: manual actions have user_id, system actions are NULL

**Implementation**:
```python
create_audit_log(
    org_id=draft.org_id,
    actor_user_id=current_user.id,  # NULL for system
    action="DRAFT_APPROVED",
    entity_type="draft_order",
    entity_id=draft.id
)
```

**Alternatives Rejected**:
- Update existing audit entry (rejected: loses event history)
- Single "DRAFT_EXPORTED" action (rejected: can't distinguish approve vs push)

---

### 5. Retry Logic: New Export Record

**Decision**: Retry creates new erp_export record, not update existing.

**Rationale**:
- Preserves failure history (why first export failed)
- Each export has unique ID for tracking
- Idempotent: same retry logic as initial push
- Simplifies querying (latest export = most recent created_at)

**Implementation**:
```python
# Retry creates new export
export = ERPExport(
    org_id=draft.org_id,
    erp_connection_id=connector.id,
    draft_order_id=draft.id,
    status=ERPExportStatus.PENDING
)
```

**Alternatives Rejected**:
- Reset existing export to PENDING (rejected: loses failure context)
- Separate retry_count field (rejected: complicates logic, history unclear)

---

## Best Practices

### Idempotency Key Format

**Recommendation**: Use UUID v4 generated client-side.

**Example**:
```javascript
const idempotencyKey = crypto.randomUUID();
fetch(`/draft-orders/${id}/push`, {
  headers: { 'Idempotency-Key': idempotencyKey }
});
```

**Why**: Client controls uniqueness, prevents accidental reuse, no coordination needed.

---

### Error Handling in Export Worker

**Recommendation**: Catch all exceptions, log to error_json, set status FAILED.

**Example**:
```python
try:
    result = connector_impl.export(draft, config)
except Exception as e:
    export.error_json = {
        "error": str(e),
        "timestamp": datetime.utcnow().isoformat(),
        "traceback": traceback.format_exc()
    }
    export.status = ERPExportStatus.FAILED
    draft.status = DraftOrderStatus.ERROR
```

**Why**: Worker failures don't crash job queue, operators see error details, retry is possible.

---

### Role Enforcement

**Recommendation**: Restrict approve/push to OPERATOR role and above.

**Rationale**:
- Approve/push are high-privilege actions (trigger ERP export)
- VIEWER role is read-only
- ADMIN/INTEGRATOR inherit OPERATOR permissions

**Implementation**:
```python
@app.post("/draft-orders/{id}/approve")
@require_role(Role.OPERATOR)
def approve_draft_order(id: UUID, current_user: User):
    ...
```

---

## Performance Considerations

### Export Worker Concurrency

**Recommendation**: Run 4-8 worker processes with concurrency tuning based on connector type.

**SFTP/FTP connectors**: Low concurrency (2-4 workers) to avoid connection pool exhaustion.
**S3/Dropzone connectors**: Higher concurrency (8-16 workers) for parallel uploads.

**Configuration**:
```bash
celery -A orderflow.workers worker --concurrency=4 --max-tasks-per-child=100
```

---

### Database Transaction Isolation

**Recommendation**: Use `READ COMMITTED` isolation for approve/push endpoints to prevent phantom reads.

**Why**: Status checks (READY → APPROVED) must see committed data only. Higher isolation (SERIALIZABLE) unnecessary, causes contention.

---

## GDPR / Compliance Notes

### Audit Trail Retention

**Requirement**: Audit logs must be retained for minimum 365 days per §11.5.

**Implementation**: Retention job skips audit_log table, enforced via database constraint.

---

### Actor Attribution

**Requirement**: Every approve/push action must record actor_user_id for compliance.

**Implementation**: JWT provides user context, stored in audit_log. System actions (background worker) have NULL actor_user_id with distinguishing action type.

---

## Testing Strategy

### Component Test Example: Idempotency

```python
def test_idempotency_prevents_duplicate_exports():
    draft = create_approved_draft()
    key = "test-key-123"

    # First push
    response1 = client.post(
        f"/draft-orders/{draft.id}/push",
        headers={"Idempotency-Key": key}
    )
    export_id_1 = response1.json()["erp_export_id"]

    # Second push with same key
    response2 = client.post(
        f"/draft-orders/{draft.id}/push",
        headers={"Idempotency-Key": key}
    )
    export_id_2 = response2.json()["erp_export_id"]

    # Assert same export ID returned
    assert export_id_1 == export_id_2

    # Assert only one export record created
    exports = db.query(ERPExport).filter_by(draft_order_id=draft.id).all()
    assert len(exports) == 1
```

---

### Integration Test Example: Full Workflow

```python
def test_approve_push_workflow():
    # Create READY draft
    draft = create_ready_draft()

    # Approve
    response = client.post(f"/draft-orders/{draft.id}/approve")
    assert response.status_code == 200
    assert draft.status == DraftOrderStatus.APPROVED
    assert draft.approved_by_user_id is not None

    # Push
    response = client.post(f"/draft-orders/{draft.id}/push")
    assert response.status_code == 200
    assert draft.status == DraftOrderStatus.PUSHING

    # Process export job
    process_export_job(export_id)

    # Verify final state
    db.session.refresh(draft)
    assert draft.status == DraftOrderStatus.PUSHED
    assert draft.erp_exports[0].status == ERPExportStatus.SENT

    # Verify audit log
    audit_entries = db.query(AuditLog).filter_by(entity_id=draft.id).all()
    assert len(audit_entries) == 2  # APPROVED + PUSHED
```

---

## Open Questions

1. **What happens if operator approves then edits draft before push?**
   - Answer: Status reverts to NEEDS_REVIEW on edit, must re-approve. Implemented via draft update trigger.

2. **Should retry increment attempt counter?**
   - Answer: No. Each export is independent record. Query latest by created_at DESC.

3. **How long should idempotency cache persist?**
   - Answer: 24 hours (configurable). Covers retry window, prevents unbounded growth.

4. **Should push endpoint validate connector config before enqueueing?**
   - Answer: Yes. Check connector exists and is active. Detailed validation happens in worker (credentials, connectivity).
