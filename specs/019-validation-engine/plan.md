# Implementation Plan: Validation Engine

**Branch**: `019-validation-engine` | **Date**: 2025-12-27 | **Spec**: [specs/019-validation-engine/spec.md](./spec.md)

## Summary

The Validation Engine is the gatekeeper for order quality, implementing 14+ deterministic business rules that validate draft orders against catalog data, business constraints, and optionally customer prices. The engine automatically creates, updates, and resolves validation_issue records, computes ready_check_json to determine if a draft can be approved, and provides UI-friendly issue management (filtering, acknowledgement, navigation). Issues are classified by severity (INFO, WARNING, ERROR) with only ERROR-level issues blocking READY status. The system handles price validation with configurable tolerance, UoM compatibility checks, and quantity range validation.

**Technical Approach**: Port-based architecture with `ValidatorPort` interface allowing multiple rule set implementations. Rules are discrete functions returning ValidationIssue objects. Ready-Check is a pure function computing `{is_ready, blocking_reasons, checked_at}` from issue list. Price validation uses tier selection algorithm (max min_qty ≤ line.qty) with percentage-based tolerance comparison.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, Pydantic (validation schemas)
**Storage**: PostgreSQL (validation_issue table, draft_order.ready_check_json JSONB)
**Testing**: pytest (90%+ unit coverage for rules, component tests for engine, integration tests for API flow)
**Target Platform**: Linux server (containerized)
**Project Type**: Web application (backend/frontend split)
**Performance Goals**: Ready-Check <200ms for 100-line drafts, validation run <500ms
**Constraints**: Zero false positives (issues only for actual violations), auto-resolution when problem fixed
**Scale/Scope**: 10k products, 100-line orders, 20+ validation rule types

## Constitution Check

| Principle | Compliance | Notes |
|-----------|------------|-------|
| **I. SSOT-First** | ✅ Pass | All 14+ rule types from §7.3, severity/status enums from §5.2.6-5.2.7, ready-check logic from §6.3 |
| **II. Hexagonal Architecture** | ✅ Pass | ValidatorPort interface isolates rules from infrastructure. Domain logic doesn't import DB/API code. |
| **III. Multi-Tenant Isolation** | ✅ Pass | validation_issue table includes org_id. All queries filter by org. Customer price lookup scoped to org. |
| **IV. Idempotent Processing** | ✅ Pass | Re-running validation on same draft updates existing issues (by type+line_id), doesn't create duplicates. Auto-resolution is idempotent. |
| **V. AI-Layer Deterministic Control** | ✅ Pass | No AI involvement. All rules are deterministic (product exists, qty > 0, price tolerance, UoM compatibility). |
| **VI. Observability First-Class** | ✅ Pass | Validation logs each rule execution, issue creation/resolution. ready_check_json includes checked_at timestamp. |
| **VII. Test Pyramid Discipline** | ✅ Pass | Unit tests for each rule (14+), component tests for ValidationEngine, integration tests for API + auto-resolution. |

## Project Structure

### Documentation (this feature)

```text
specs/019-validation-engine/
├── plan.md              # This file
├── research.md          # Rule design patterns, auto-resolution strategies
├── data-model.md        # validation_issue schema, ready_check_json structure
├── quickstart.md        # Development setup for validation testing
└── contracts/
    └── openapi.yaml     # Validation issue APIs (GET issues, POST acknowledge)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── domain/
│   │   └── validation/
│   │       ├── __init__.py
│   │       ├── engine.py                  # ValidationEngine (orchestrator)
│   │       ├── port.py                    # ValidatorPort interface
│   │       ├── rules/
│   │       │   ├── __init__.py
│   │       │   ├── header_rules.py        # Customer, currency, date rules
│   │       │   ├── line_rules.py          # Product, qty, UoM rules
│   │       │   ├── price_rules.py         # Price mismatch, missing price
│   │       │   └── uom_rules.py           # UoM compatibility, conversions
│   │       ├── ready_check.py             # compute_ready_check() function
│   │       └── models.py                  # ValidationIssue, ReadyCheckResult dataclasses
│   ├── infrastructure/
│   │   └── repositories/
│   │       └── validation_repository.py   # DB access for issues
│   ├── api/
│   │   └── endpoints/
│   │       ├── draft_orders.py            # GET /draft-orders/{id} (includes issues)
│   │       └── validation.py              # POST /validation-issues/{id}/acknowledge
│   └── database/
│       └── models/
│           └── validation_issue.py        # SQLAlchemy model
└── tests/
    ├── unit/
    │   └── validation/
    │       ├── test_header_rules.py       # Customer, currency tests
    │       ├── test_line_rules.py         # Product, qty, UoM tests
    │       ├── test_price_rules.py        # Price validation tests
    │       └── test_ready_check.py        # Ready-Check logic tests
    ├── integration/
    │   └── validation/
    │       ├── test_validation_flow.py    # API → validate → issues created
    │       └── test_auto_resolution.py    # Fix data → issues resolved
    └── fixtures/
        └── validation_fixtures.py         # Test products, prices, drafts

frontend/
├── src/
│   ├── components/
│   │   └── draft-orders/
│   │       ├── ValidationIssuePanel.tsx   # Issue list with filters
│   │       └── ValidationIssueBadge.tsx   # Issue severity badge
│   └── services/
│       └── validationApi.ts               # API client for issue acknowledgement
└── tests/
    └── components/
        └── ValidationIssuePanel.test.tsx
```

**Structure Decision**: Web application structure for UI components (issue panel, filters, badges). Backend uses domain-driven design with rules as discrete functions in `rules/` directory. Port/Adapter pattern enables mocking for tests.

## Complexity Tracking

No Constitution violations. Complexity justified:
- 14+ rule types are business domain complexity, not accidental
- Auto-resolution logic is necessary to prevent stale issues
- Price tier selection is required for multi-tier pricing (business requirement)
