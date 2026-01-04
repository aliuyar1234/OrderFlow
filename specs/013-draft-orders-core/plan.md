# Implementation Plan: Draft Orders Core (Entity & State Machine)

**Branch**: `013-draft-orders-core` | **Date**: 2025-12-27 | **Spec**: [specs/013-draft-orders-core/spec.md](./spec.md)

## Summary

Implement the DraftOrder and DraftOrderLine entities with state machine, ready-check logic, confidence scoring, and line CRUD operations. This is the central entity for the order processing workflow. Every extracted document creates a Draft with header data, lines, confidence scores, and validation status. The state machine enforces transitions (NEW → EXTRACTED → NEEDS_REVIEW → READY → APPROVED → PUSHING → PUSHED) with clear blocking conditions. Ready-check validates customer assignment, line completeness, and absence of ERROR-level issues. Confidence scoring combines extraction, customer detection, and matching quality into a single score for review prioritization.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, SQLAlchemy, Pydantic, enum (state machine)
**Storage**: PostgreSQL 16 (draft_order, draft_order_line, validation_issue, audit_log)
**Testing**: pytest, fixtures for various draft states, state transition tests
**Target Platform**: Linux server (API + workers)
**Project Type**: Web application (backend entity + API, frontend consumes)
**Performance Goals**: Ready-check <100ms, confidence calc <10ms, API queries <500ms (10k drafts)
**Constraints**: Support 500-line orders, prevent invalid state transitions, ensure 0% false positives on ready-check
**Scale/Scope**: 10k+ drafts per org, sub-second query performance

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. SSOT-First** | ✅ PASS | Implements §5.4.8 (draft_order), §5.4.9 (draft_order_line), §5.2.5 (State Machine), §6.3 (Ready-Check), §7.8 (Confidence). |
| **II. Hexagonal Architecture** | ✅ PASS | Draft entity is domain model. Services orchestrate use cases. Adapters handle persistence. |
| **III. Multi-Tenant Isolation** | ✅ PASS | All tables include org_id. Queries filtered by org_id. FK constraints enforce isolation. |
| **IV. Idempotent Processing** | ✅ PASS | State transitions atomic. Ready-check can run multiple times safely. |
| **V. AI-Layer Deterministic Control** | ✅ PASS | Confidence formulas per §7.8 exactly. No AI in this spec (uses results from 010/012). |
| **VI. Observability First-Class** | ✅ PASS | State transitions logged to audit_log. Confidence scores tracked. |
| **VII. Test Pyramid Discipline** | ✅ PASS | Unit tests for state machine, ready-check, confidence calc. Integration tests for full workflow. |

## Project Structure

```text
specs/013-draft-orders-core/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    └── openapi.yaml

backend/
├── src/
│   ├── domain/
│   │   └── draft_orders/
│   │       ├── models.py              # DraftOrder, DraftOrderLine entities
│   │       ├── state_machine.py       # State transition logic
│   │       ├── ready_check.py         # Ready-check validation
│   │       └── confidence.py          # Confidence scoring (§7.8)
│   ├── services/
│   │   └── draft_order_service.py     # CRUD operations, orchestration
│   ├── api/
│   │   └── routes/
│   │       └── draft_orders.py        # API endpoints
│   └── db/
│       └── models/
│           ├── draft_order.py         # SQLAlchemy models
│           └── draft_order_line.py
└── tests/
    ├── unit/
    │   ├── test_state_machine.py
    │   ├── test_ready_check.py
    │   └── test_confidence.py
    └── integration/
        └── test_draft_workflow.py    # Extract → Draft → Review → Approve
```

**Structure Decision**: Web application backend. Draft entities are central domain models. API layer exposes CRUD + state transitions. Frontend (spec 014) consumes API.

## Complexity Tracking

No violations detected.
