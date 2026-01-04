# Tasks: Approve & Push Flow

**Feature Branch**: `023-approve-push-flow`
**Generated**: 2025-12-27

## Phase 1: Setup

- [x] T001 Create approval workflow at `backend/src/draft_orders/approval.py`
- [x] T002 Add workflow state management (status transitions in approval.py)

## Phase 2: [US1] Approve Draft Order

- [x] T003 [US1] Create approve endpoint POST /draft-orders/{id}/approve
- [x] T004 [US1] Validate no validation errors exist (ready_check validation)
- [x] T005 [US1] Require all lines have matched products (in ready_check)
- [x] T006 [US1] Require customer is set
- [x] T007 [US1] Transition status to APPROVED
- [x] T008 [US1] Audit approval action (DRAFT_APPROVED event)
- [x] T009 [US1] Restrict to OPS, ADMIN roles (via require_role(UserRole.OPS))

## Phase 3: [US2] Push to ERP

- [x] T010 [US2] Create push endpoint POST /draft-orders/{id}/push
- [x] T011 [US2] Check status is APPROVED
- [x] T012 [US2] Load org connector configuration
- [x] T013 [US2] Call connector.export() via worker (process_erp_export)
- [x] T014 [US2] Update status to PUSHED on success
- [x] T015 [US2] Store ERP order ID (export_storage_key + dropzone_path)
- [x] T016 [US2] Create erp_export entry (ERPExport model)
- [x] T017 [US2] Handle push errors (worker error handling + retry logic)

## Phase 4: [US3] Idempotency & Retry

- [x] T018 [US3] Implement idempotency via Idempotency-Key header
- [x] T019 [US3] Cache idempotent export mappings in Redis (24h TTL)
- [x] T020 [US3] Return existing export for duplicate keys
- [x] T021 [US3] Create retry-push endpoint POST /draft-orders/{id}/retry-push
- [x] T022 [US3] Create new ERPExport on retry (not mutate failed)

## Phase 5: [US4] Audit & Logging

- [x] T023 [US4] Log DRAFT_APPROVED events
- [x] T024 [US4] Log DRAFT_PUSHED events
- [x] T025 [US4] Log DRAFT_PUSH_RETRIED events
- [x] T026 [US4] Log DRAFT_PUSH_FAILED events (system actor)
- [x] T027 [US4] Log DRAFT_APPROVAL_REVOKED events

## Phase 6: UI Integration (Future)

- [ ] T028 Add approve button to draft detail page
- [ ] T029 Add push button to draft detail page
- [ ] T030 Show push status indicators
- [ ] T031 Display export_id and dropzone_path after push
- [ ] T032 Handle push errors in UI with retry option
- [ ] T033 Show approval metadata (approved_by, approved_at)

## Phase 7: Polish (Future)

- [ ] T034 Add bulk approve & push
- [ ] T035 Add push preview (dry run)
- [ ] T036 Create push analytics dashboard
- [ ] T037 Document approval workflow

---

## Implementation Summary

**Core Backend Implementation Complete** (Phases 1-5):

1. **Approval Service** (`backend/src/draft_orders/approval.py`):
   - `approve_draft_order()`: Validates READY status, transitions to APPROVED
   - `revoke_approval()`: Reverts APPROVED → NEEDS_REVIEW on edits
   - Validates ready_check_json, customer_id, state transitions

2. **Push Service** (`backend/src/draft_orders/push.py`):
   - `push_draft_order()`: Creates ERPExport, transitions to PUSHING
   - `retry_push()`: Creates new export for ERROR status drafts
   - Idempotency support via Redis cache (24h TTL)
   - Fallback idempotency via database status checks

3. **Export Worker** (`backend/src/workers/export_worker.py`):
   - `process_erp_export()`: Celery task for background export
   - Connector registry for pluggable ERP adapters
   - Retry logic with exponential backoff
   - Status updates: PENDING → SENT/FAILED
   - Draft status: PUSHING → PUSHED/ERROR

4. **API Router** (`backend/src/draft_orders/router.py`):
   - `POST /draft-orders/{id}/approve`: Approve endpoint
   - `POST /draft-orders/{id}/push`: Push endpoint with idempotency
   - `POST /draft-orders/{id}/retry-push`: Retry failed push
   - `DELETE /draft-orders/{id}/approval`: Revoke approval
   - All endpoints require OPS role or higher

5. **Audit Logging**:
   - DRAFT_APPROVED, DRAFT_PUSHED, DRAFT_PUSH_RETRIED
   - DRAFT_PUSH_FAILED (system actor), DRAFT_APPROVAL_REVOKED
   - IP address + User-Agent tracking

**Models** (already existed):
- `DraftOrder`: Status state machine, approval fields
- `ERPExport`: Export tracking, status lifecycle
- `ERPConnection`: Connector configuration

**Port Interface** (already existed):
- `ERPConnectorPort`: Abstract interface for ERP connectors
- `ExportResult`: Standard return type for export operations

**Next Steps** (UI + Polish):
- Frontend integration (Phase 6)
- Bulk operations and analytics (Phase 7)
