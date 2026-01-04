# Feature Specification: Approve & Push Flow

**Feature Branch**: `023-approve-push-flow`
**Created**: 2025-12-27
**Status**: Draft
**Module**: draft_orders, connectors
**SSOT References**: §6.4-6.5 (Approve/Push Rules), §8.6 (approve/push Endpoints), §11.4 (Audit Logging), T-601, T-605

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Approve Ready Draft (Priority: P1)

As an operator, I need to approve a READY draft order to confirm that all data is correct and the order is authorized for ERP export.

**Why this priority**: Approve is the final human checkpoint before order data leaves OrderFlow. It represents operator confirmation that the order is complete and accurate. This is a critical audit point.

**Independent Test**: Can be fully tested by creating a READY draft, calling POST `/draft-orders/{id}/approve`, and verifying that status changes to APPROVED and audit log entry is created.

**Acceptance Scenarios**:

1. **Given** a draft with `status=READY`, **When** POST `/draft-orders/{id}/approve`, **Then** status changes to APPROVED, `approved_by_user_id` is set, and `approved_at` timestamp is recorded
2. **Given** a draft with `status=NEEDS_REVIEW` (not READY), **When** POST approve, **Then** API returns 409 Conflict with message "Draft must be READY to approve"
3. **Given** a draft is already APPROVED, **When** POST approve again, **Then** API returns 409 Conflict with message "Draft already approved"
4. **Given** approval succeeds, **When** querying audit_log, **Then** entry exists with `action=DRAFT_APPROVED`, `actor_user_id=<approver>`, `entity_id=<draft_id>`
5. **Given** user lacks OPERATOR role, **When** POST approve, **Then** API returns 403 Forbidden

---

### User Story 2 - Push Approved Draft to ERP (Priority: P1)

After approving a draft, operators must be able to push it to ERP, triggering export JSON generation and dropzone delivery.

**Why this priority**: Push is the culmination of the entire OrderFlow workflow. It delivers validated order data to ERP for fulfillment. Without push, the system has no output.

**Independent Test**: Can be fully tested by approving a draft, calling POST `/draft-orders/{id}/push`, and verifying that erp_export record is created and export JSON appears in dropzone.

**Acceptance Scenarios**:

1. **Given** a draft with `status=APPROVED`, **When** POST `/draft-orders/{id}/push`, **Then** status changes to PUSHING, erp_export job is created with status PENDING
2. **Given** export worker processes job successfully, **When** export completes, **Then** draft status changes to PUSHED, erp_export status changes to SENT
3. **Given** export worker fails (SFTP unreachable), **When** job completes, **Then** draft status changes to ERROR, erp_export status changes to FAILED with error_json
4. **Given** draft status is NEEDS_REVIEW (not APPROVED), **When** POST push, **Then** API returns 409 Conflict with message "Draft must be APPROVED to push"
5. **Given** push succeeds, **When** querying audit_log, **Then** entries exist for DRAFT_APPROVED and DRAFT_PUSHED

---

### User Story 3 - Idempotent Push with Idempotency-Key (Priority: P1)

To prevent duplicate exports during retries, the push endpoint must support idempotency via `Idempotency-Key` header, returning the same export result for duplicate requests.

**Why this priority**: Network retries and double-clicks can cause duplicate push requests. Without idempotency, the same order could be exported multiple times, causing duplicate orders in ERP.

**Independent Test**: Can be fully tested by calling POST push twice with the same Idempotency-Key and verifying that only one erp_export record is created.

**Acceptance Scenarios**:

1. **Given** first push request with `Idempotency-Key: abc-123`, **When** POST push, **Then** new erp_export is created and export_id is returned
2. **Given** second push request with same `Idempotency-Key: abc-123` within 24 hours, **When** POST push, **Then** same export_id is returned without creating new export
3. **Given** first push is still PENDING, **When** second push with same key is called, **Then** API returns 202 Accepted with same export_id and message "Export in progress"
4. **Given** first push FAILED, **When** second push with same key is called, **Then** API returns 200 with failed export_id (allowing operator to retry with new key)
5. **Given** push request without Idempotency-Key header, **When** called twice, **Then** second call returns 409 Conflict "Export already in progress or completed". Fallback idempotency: Check draft.status and erp_export table for existing PUSHING/PUSHED status. If found, return existing export_id with 200 OK. If not found and draft is APPROVED, proceed with push.

---

### User Story 4 - Audit Trail for Approve & Push (Priority: P1)

Every approve and push action must be logged to the audit_log with actor, timestamp, and entity references for compliance and debugging.

**Why this priority**: Audit logging is required for compliance (SOC2, GDPR), fraud prevention, and debugging. "Who approved what and when" is a fundamental business requirement.

**Independent Test**: Can be fully tested by approving and pushing a draft, querying audit_log, and verifying that entries contain correct action, actor_user_id, and timestamps.

**Acceptance Scenarios**:

1. **Given** draft is approved by user "alice@example.com", **When** querying audit_log, **Then** entry exists with `action=DRAFT_APPROVED`, `actor_user_id=<alice-id>`, `entity_type=draft_order`
2. **Given** draft is pushed by user "bob@example.com", **When** querying audit_log, **Then** entry exists with `action=DRAFT_PUSHED`, `actor_user_id=<bob-id>`, `created_at=<push-timestamp>`
3. **Given** push fails, **When** querying audit_log, **Then** entry exists with `action=DRAFT_PUSH_FAILED`, `details_json` contains error message
4. **Given** audit log entries, **When** filtering by draft_order_id, **Then** chronological sequence shows: APPROVED → PUSHED (or PUSH_FAILED)
5. **Given** system action (background worker), **When** export status changes to ACKED, **Then** audit_log entry has `actor_user_id=NULL` and `action=EXPORT_ACKED`

---

### User Story 5 - Retry Failed Push (Priority: P2)

Operators must be able to retry a failed push (e.g., after fixing SFTP credentials) without re-approving the draft.

**Why this priority**: Retry reduces manual work during transient failures. However, initial push (P1) must work first. Retry is a convenience feature that improves operator experience.

**Independent Test**: Can be fully tested by creating a failed export, calling POST `/draft-orders/{id}/retry-push`, and verifying that a new export is created.

**Acceptance Scenarios**:

1. **Given** draft has status ERROR (push failed), **When** POST `/draft-orders/{id}/retry-push`, **Then** new erp_export is created, status changes to PUSHING
2. **Given** draft has status PUSHED (already succeeded), **When** POST retry-push, **Then** API returns 409 Conflict "Export already succeeded"
3. **Given** retry succeeds, **When** querying draft, **Then** status changes to PUSHED and latest erp_export has status SENT
4. **Given** retry fails again, **When** querying draft, **Then** status remains ERROR and latest erp_export has status FAILED
5. **Given** retry is triggered, **When** querying audit_log, **Then** entry exists with `action=DRAFT_PUSH_RETRIED`

---

### Edge Cases

- What happens if operator approves draft, then another operator pushes it? (Allowed; both actions are audited separately)
- How does system handle approve request while validation is still running? (Approve checks ready_check_json; if not READY, returns 409)
- What if SFTP credentials are changed between approve and push? (Push uses current connector config; may fail if invalid; operator must update config and retry)
- What happens if draft is edited after approval but before push? (Status reverts to NEEDS_REVIEW; must re-approve before push)
- How does system handle concurrent push requests (race condition)? (Database transaction + status check prevents double-push; second request gets 409)
- What if Idempotency-Key is reused across different drafts? (Idempotency-Key is scoped to draft_order_id; same key for different drafts creates separate exports)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose API endpoint: POST `/draft-orders/{id}/approve`
- **FR-002**: System MUST validate draft status is READY before allowing approve (else return 409)
- **FR-003**: System MUST set `draft_order.status=APPROVED`, `approved_by_user_id=<user-id>`, `approved_at=<timestamp>` on approve
- **FR-004**: System MUST create audit_log entry with `action=DRAFT_APPROVED` on approve
- **FR-005**: System MUST expose API endpoint: POST `/draft-orders/{id}/push`
- **FR-006**: System MUST validate draft status is APPROVED before allowing push (else return 409)
- **FR-007**: System MUST support optional header `Idempotency-Key: <uuid>` on push endpoint
- **FR-008**: System MUST store idempotency key mapping: (draft_order_id, idempotency_key) → erp_export_id for 24 hours
- **FR-009**: System MUST return same erp_export_id for duplicate push requests with same Idempotency-Key
- **FR-010**: System MUST set `draft_order.status=PUSHING` immediately on push, then PUSHED on success or ERROR on failure
- **FR-011**: System MUST create `erp_export` record with status PENDING when push is initiated
- **FR-012**: System MUST enqueue export job to background worker (async processing)
- **FR-013**: System MUST invoke ERPConnectorPort.export() via ConnectorRegistry in background worker
- **FR-014**: System MUST update `erp_export.status=SENT` on successful export, FAILED on error
- **FR-015**: System MUST create audit_log entry with `action=DRAFT_PUSHED` on successful push
- **FR-016**: System MUST create audit_log entry with `action=DRAFT_PUSH_FAILED` on failed push, including error details
- **FR-017**: System MUST expose API endpoint: POST `/draft-orders/{id}/retry-push` for failed exports
- **FR-018**: System MUST validate draft status is ERROR before allowing retry (else return 409 if already PUSHED)
- **FR-019**: System MUST create new erp_export record on retry (not update existing)
- **FR-020**: System MUST restrict approve and push endpoints to OPERATOR role (and above)
- **FR-021**: System MUST revert APPROVED draft to NEEDS_REVIEW when edited (line added/modified/deleted, customer changed, header updated). Clear approved_at and approved_by_user_id. User must re-approve after changes. Audit log captures 'approval_reverted' event.

### Key Entities *(include if feature involves data)*

- **DraftOrder**: Status transitions: READY → APPROVED → PUSHING → PUSHED (or ERROR). Tracks approved_by_user_id and approved_at.

- **ERPExport**: Represents a single export attempt. Links to draft_order and erp_connection. Tracks status progression: PENDING → SENT (or FAILED).

- **AuditLog** (§5.4.16): Records all approve and push actions with actor, timestamp, and entity references.

- **IdempotencyCache**: In-memory or Redis cache mapping (draft_order_id, idempotency_key) → erp_export_id with 24-hour TTL.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Approve endpoint correctly blocks non-READY drafts in 100% of test cases
- **SC-002**: Push endpoint creates erp_export record in 100% of successful pushes
- **SC-003**: Idempotency-Key prevents duplicate exports in 100% of retry scenarios (integration tests)
- **SC-004**: Audit log entries are created for 100% of approve and push actions
- **SC-005**: Push workflow completes end-to-end (APPROVED → PUSHED) within 10 seconds for typical drafts
- **SC-006**: Retry logic creates new export in 100% of ERROR status cases
- **SC-007**: Status transitions follow state machine rules in 100% of cases (no invalid transitions)

## Dependencies

- **Depends on**:
  - **019-validation-engine**: Requires ready_check_json to determine READY status
  - **021-erp-connector-framework**: Requires ERPConnectorPort and ConnectorRegistry
  - **022-dropzone-connector**: Requires DropzoneJsonV1Connector implementation
  - **001-database-setup**: Requires draft_order, erp_export, audit_log tables
  - **002-auth**: Requires OPERATOR role enforcement

- **Enables**:
  - **End-to-end order processing**: Completes the intake → extraction → validation → approve → push pipeline

## Implementation Notes

### Approve Endpoint Implementation

```python
@app.post("/draft-orders/{id}/approve")
@require_role(Role.OPERATOR)
def approve_draft_order(id: UUID, current_user: User):
    draft = get_draft_order(id, current_user.org_id)

    # Validate state
    if draft.status != DraftOrderStatus.READY:
        raise HTTPException(
            status_code=409,
            detail=f"Draft must be READY to approve (current: {draft.status})"
        )

    # Update draft
    draft.status = DraftOrderStatus.APPROVED
    draft.approved_by_user_id = current_user.id
    draft.approved_at = datetime.utcnow()

    db.session.commit()

    # Audit log
    create_audit_log(
        org_id=draft.org_id,
        actor_user_id=current_user.id,
        action="DRAFT_APPROVED",
        entity_type="draft_order",
        entity_id=draft.id
    )

    return {"id": draft.id, "status": draft.status, "approved_at": draft.approved_at}
```

### Push Endpoint with Idempotency

```python
@app.post("/draft-orders/{id}/push")
@require_role(Role.OPERATOR)
def push_draft_order(
    id: UUID,
    current_user: User,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key")
):
    draft = get_draft_order(id, current_user.org_id)

    # Validate state
    if draft.status != DraftOrderStatus.APPROVED:
        raise HTTPException(
            status_code=409,
            detail=f"Draft must be APPROVED to push (current: {draft.status})"
        )

    # Check idempotency
    if idempotency_key:
        existing_export_id = get_idempotent_export(draft.id, idempotency_key)
        if existing_export_id:
            export = get_erp_export(existing_export_id)
            if export.status == ERPExportStatus.PENDING:
                return JSONResponse(
                    status_code=202,
                    content={"erp_export_id": str(export.id), "status": "in_progress"}
                )
            else:
                return {"erp_export_id": str(export.id), "status": export.status}

    # Check for existing export (no idempotency key provided)
    if draft.status in [DraftOrderStatus.PUSHING, DraftOrderStatus.PUSHED]:
        raise HTTPException(status_code=409, detail="Export already in progress or completed")

    # Get active connector
    connector = get_active_connector(draft.org_id)
    if not connector:
        raise HTTPException(status_code=400, detail="No active ERP connector configured")

    # Create export record
    export = ERPExport(
        org_id=draft.org_id,
        erp_connection_id=connector.id,
        draft_order_id=draft.id,
        export_format_version="orderflow_export_json_v1",
        status=ERPExportStatus.PENDING
    )
    db.session.add(export)

    # Update draft status
    draft.status = DraftOrderStatus.PUSHING

    db.session.commit()

    # Store idempotency mapping
    if idempotency_key:
        set_idempotent_export(draft.id, idempotency_key, export.id, ttl_hours=24)

    # Enqueue export job
    enqueue_export_job(export.id)

    # Audit log
    create_audit_log(
        org_id=draft.org_id,
        actor_user_id=current_user.id,
        action="DRAFT_PUSHED",
        entity_type="draft_order",
        entity_id=draft.id,
        details_json={"erp_export_id": str(export.id)}
    )

    return {"erp_export_id": str(export.id), "status": "PUSHING"}
```

### Background Export Worker

```python
def process_export_job(export_id: UUID):
    """Background worker to process export."""
    export = get_erp_export(export_id)
    draft = export.draft_order

    try:
        # Get connector
        connector_type = export.erp_connection.connector_type
        connector_impl = ConnectorRegistry.get(connector_type)
        config = decrypt_config(export.erp_connection.config_encrypted)

        # Generate and write export
        result = connector_impl.export(draft, config)

        if result.success:
            export.status = ERPExportStatus.SENT
            export.export_storage_key = result.storage_key
            export.dropzone_path = result.dropzone_path
            draft.status = DraftOrderStatus.PUSHED
        else:
            raise Exception(result.error_message)

    except Exception as e:
        export.status = ERPExportStatus.FAILED
        export.error_json = {
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
            "traceback": traceback.format_exc()
        }
        draft.status = DraftOrderStatus.ERROR

        # Audit log for failure
        create_audit_log(
            org_id=draft.org_id,
            actor_user_id=None,  # System action
            action="DRAFT_PUSH_FAILED",
            entity_type="draft_order",
            entity_id=draft.id,
            details_json={"error": str(e)}
        )

    finally:
        db.session.commit()
```

### Idempotency Cache (Redis)

```python
def set_idempotent_export(draft_id: UUID, idempotency_key: str, export_id: UUID, ttl_hours: int):
    """Store idempotency mapping in Redis."""
    key = f"idempotency:{draft_id}:{idempotency_key}"
    redis_client.setex(key, ttl_hours * 3600, str(export_id))

def get_idempotent_export(draft_id: UUID, idempotency_key: str) -> UUID | None:
    """Retrieve export_id from idempotency cache."""
    key = f"idempotency:{draft_id}:{idempotency_key}"
    export_id = redis_client.get(key)
    return UUID(export_id) if export_id else None
```

**Idempotency-Key Scoping**: Cache key format is `(org_id, draft_id, idempotency_key)` to prevent cross-org key collision. Even if attacker guesses key, org_id isolation prevents replay attacks across tenants. In production, update the cache key to include org_id:

```python
key = f"idempotency:{org_id}:{draft_id}:{idempotency_key}"
```

### State Machine Validation

```python
ALLOWED_TRANSITIONS = {
    (DraftOrderStatus.READY, DraftOrderStatus.APPROVED),
    (DraftOrderStatus.APPROVED, DraftOrderStatus.PUSHING),
    (DraftOrderStatus.PUSHING, DraftOrderStatus.PUSHED),
    (DraftOrderStatus.PUSHING, DraftOrderStatus.ERROR),
    (DraftOrderStatus.ERROR, DraftOrderStatus.PUSHING),  # Retry
}

def validate_status_transition(from_status: str, to_status: str):
    if (from_status, to_status) not in ALLOWED_TRANSITIONS:
        raise ValueError(f"Invalid status transition: {from_status} → {to_status}")
```

## Testing Strategy

### Unit Tests
- Approve logic: READY → APPROVED (success), NEEDS_REVIEW → error
- Push logic: APPROVED → PUSHING (success), NEEDS_REVIEW → error
- Idempotency cache: set/get with TTL
- State machine validation: allowed vs disallowed transitions

### Component Tests
- PushService with mocked ERPConnectorPort
- Export worker with mocked connector (success and failure scenarios)
- Audit log creation for all actions

### Integration Tests
- End-to-end: approve → push → export worker → status PUSHED
- Idempotency: push twice with same key → one export created
- Retry: failed export → retry-push → new export created
- Audit log query: filter by draft_order_id → chronological actions

### E2E Tests
- Full workflow: READY draft → Approve button → Push button → Export appears in SFTP dropzone
- Failure scenario: SFTP unreachable → Push fails → UI shows ERROR → Operator retries → Success
- Idempotency UI: Click "Push" twice rapidly → only one export shown

## SSOT Compliance Checklist

- [ ] Approve rules match §6.4 (only READY allowed, sets approved_by_user_id and approved_at)
- [ ] Push rules match §6.5 (only APPROVED allowed, idempotent per draft)
- [ ] API endpoints match §8.6 (POST approve, POST push)
- [ ] Audit logging matches §11.4 (DRAFT_APPROVED, DRAFT_PUSHED actions)
- [ ] Idempotency-Key header supported per §8.1
- [ ] Status transitions follow state machine: READY → APPROVED → PUSHING → PUSHED | ERROR
- [ ] erp_export.status follows §5.2.9 (PENDING, SENT, ACKED, FAILED)
- [ ] T-601 acceptance criteria met (only READY allowed, audit log entry created, NEEDS_REVIEW → 409)
- [ ] T-605 acceptance criteria met (repeated call with same Idempotency-Key returns same export_id, only one export created)
