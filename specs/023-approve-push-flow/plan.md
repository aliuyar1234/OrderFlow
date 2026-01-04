# Implementation Plan: Approve & Push Flow

**Branch**: `023-approve-push-flow` | **Date**: 2025-12-27 | **Spec**: [spec.md](./spec.md)

## Summary

This feature implements the final human checkpoint and ERP export workflow. Operators approve READY drafts to confirm data accuracy, then push approved drafts to trigger export JSON generation and dropzone delivery. The push endpoint supports idempotent retries via `Idempotency-Key` header to prevent duplicate exports during network failures or double-clicks. All approve and push actions are logged to audit trail for compliance and debugging.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, Celery, Redis
**Storage**: PostgreSQL 16 (draft_order, erp_export, audit_log tables), Redis (idempotency cache)
**Testing**: pytest (unit, component, integration, E2E)
**Target Platform**: Linux server
**Project Type**: web (backend API + background worker)
**Performance Goals**: Approve/push API responds < 200ms, export worker completes < 10s for typical drafts
**Constraints**: Idempotency must prevent duplicate exports 100% of time, audit logs required for all actions
**Scale/Scope**: 10k orders/month, 1k concurrent users

## Constitution Check

| Principle | Status | Compliance Notes |
|-----------|--------|------------------|
| **I. SSOT-First** | ✅ PASS | All approve/push rules match §6.4-6.5, status transitions per §5.2.5, API endpoints per §8.6 |
| **II. Hexagonal Architecture** | ✅ PASS | ERPConnectorPort used for export, ConnectorRegistry provides adapter selection, no direct coupling to SFTP/dropzone |
| **III. Multi-Tenant Isolation** | ✅ PASS | All queries filter by org_id from JWT, no cross-tenant data access, 404 on unauthorized access |
| **IV. Idempotent Processing** | ✅ PASS | Idempotency-Key prevents duplicate exports, retry-push creates new export (no mutation), status transitions enforce state machine |
| **V. AI-Layer Deterministic Control** | N/A | No AI components in approve/push flow |
| **VI. Observability First-Class** | ✅ PASS | All actions logged to audit_log with request_id, Prometheus metrics for export success/failure, structured JSON logs |
| **VII. Test Pyramid Discipline** | ✅ PASS | Unit tests for state machine, component tests for PushService, integration tests for idempotency, E2E tests for full workflow |

**GATE STATUS**: ✅ APPROVED - All applicable principles satisfied

## Project Structure

### Documentation (this feature)

```text
specs/023-approve-push-flow/
├── plan.md              # This file
├── research.md          # Technical decisions and best practices
├── data-model.md        # DraftOrder, ERPExport, AuditLog schemas
├── quickstart.md        # Development setup
└── contracts/           # API contracts
    └── openapi.yaml
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   ├── draft_order.py       # DraftOrder entity with status transitions
│   │   ├── erp_export.py        # ERPExport entity
│   │   └── audit_log.py         # AuditLog entity
│   ├── services/
│   │   ├── approve_service.py   # Approve logic
│   │   ├── push_service.py      # Push logic with idempotency
│   │   └── audit_service.py     # Audit logging
│   ├── api/
│   │   └── draft_orders.py      # POST /draft-orders/{id}/approve, /push, /retry-push
│   ├── workers/
│   │   └── export_worker.py     # Background export job
│   └── ports/
│       └── erp_connector.py     # ERPConnectorPort interface
└── tests/
    ├── unit/
    │   ├── test_approve_service.py
    │   ├── test_push_service.py
    │   └── test_state_machine.py
    ├── integration/
    │   ├── test_approve_push_flow.py
    │   └── test_idempotency.py
    └── e2e/
        └── test_full_workflow.py

frontend/
├── src/
│   ├── components/
│   │   └── DraftActions.tsx     # Approve/Push buttons
│   └── pages/
│       └── DraftDetail.tsx      # Draft detail page with actions
└── tests/
```

**Structure Decision**: Web application structure selected due to backend API + frontend UI requirements. Backend handles approve/push logic and background export worker. Frontend provides operator interface for triggering actions.

## Complexity Tracking

*No violations - all constitution principles satisfied.*
