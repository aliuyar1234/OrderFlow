# Implementation Plan: Customer Detection (Multi-Signal Detection & Disambiguation)

**Branch**: `018-customer-detection` | **Date**: 2025-12-27 | **Spec**: [specs/018-customer-detection/spec.md](./spec.md)

## Summary

Customer Detection implements a multi-signal, probabilistic approach to automatically identify the correct customer for incoming order documents. The system extracts signals from email metadata (sender address, domain) and document content (customer numbers via regex, company names via fuzzy matching), aggregates them using a probabilistic formula, and auto-selects customers when confidence thresholds are met. When ambiguity exists, operators receive ranked candidate lists with transparent signal badges for manual selection. The module includes confidence tracking, feedback logging for quality monitoring, and optional LLM customer hints as fallback signals.

**Technical Approach**: Service-based architecture with `CustomerDetectionService` orchestrating signal extraction (S1-S6), `SignalAggregator` implementing probabilistic combination (1 - Π(1-score_i)), and database-backed candidate storage for UI presentation. Integration points include InboundMessage for email signals, document extraction for text scanning, and ValidationService for CUSTOMER_AMBIGUOUS issue creation.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, PostgreSQL 16 with pg_trgm extension
**Storage**: PostgreSQL (customer_detection_candidate table, draft_order.customer_candidates_json JSONB)
**Testing**: pytest (unit tests for signal extraction/aggregation), integration tests with fixtures
**Target Platform**: Linux server (containerized)
**Project Type**: Web application (backend/frontend split)
**Performance Goals**: Detection completes in <100ms per inbound message, fuzzy name search <50ms for 1000 customers
**Constraints**: Auto-selection accuracy ≥97%, ambiguity rate <15%, manual override rate <5%
**Scale/Scope**: Handles 10k customers with multiple contacts, processes 1000s of inbound messages daily

## Constitution Check

| Principle | Compliance | Notes |
|-----------|------------|-------|
| **I. SSOT-First** | ✅ Pass | All signal scores, aggregation formula, confidence thresholds defined in SSOT §7.6, §7.8.2 |
| **II. Hexagonal Architecture** | ✅ Pass | CustomerDetectionService is domain logic, isolated from infrastructure. Signals extracted via ports (InboundMessagePort, DocumentPort). No direct database coupling in detection logic. |
| **III. Multi-Tenant Isolation** | ✅ Pass | All queries filter by org_id. customer_detection_candidate table includes org_id. Customer lookup scoped to org. |
| **IV. Idempotent Processing** | ✅ Pass | Detection can be re-run on same draft without creating duplicate candidates (upsert based on draft_order_id + customer_id). Feedback events are append-only. |
| **V. AI-Layer Deterministic Control** | ✅ Pass | LLM customer_hint (S6) is optional fallback, only used when extraction already occurred (no additional LLM call). Deterministic rules (S1-S5) take precedence. |
| **VI. Observability First-Class** | ✅ Pass | Detection logs signal extraction results, candidate scores, auto-selection decisions. Feedback events enable accuracy monitoring via analytics queries. |
| **VII. Test Pyramid Discipline** | ✅ Pass | Unit tests for signal extraction (regex, fuzzy), aggregation formula. Component tests for DetectionService. Integration tests for end-to-end detection + UI selection. |

## Project Structure

### Documentation (this feature)

```text
specs/018-customer-detection/
├── plan.md              # This file
├── research.md          # Signal weighting research, fuzzy matching best practices
├── data-model.md        # customer_detection_candidate schema, signal definitions
├── quickstart.md        # Development setup for detection testing
└── contracts/
    └── openapi.yaml     # Customer selection API (POST /draft-orders/{id}/select-customer)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── domain/
│   │   └── customer_detection/
│   │       ├── __init__.py
│   │       ├── service.py              # CustomerDetectionService (main orchestrator)
│   │       ├── signal_extractor.py     # Signal extraction logic (S1-S6)
│   │       ├── signal_aggregator.py    # Probabilistic aggregation (1 - Π(1-score_i))
│   │       └── models.py               # Candidate, DetectionResult dataclasses
│   ├── infrastructure/
│   │   └── repositories/
│   │       └── customer_detection_repository.py  # DB access for candidates
│   ├── api/
│   │   └── endpoints/
│   │       └── draft_orders.py         # POST /draft-orders/{id}/select-customer
│   └── database/
│       └── models/
│           └── customer_detection_candidate.py   # SQLAlchemy model
└── tests/
    ├── unit/
    │   └── customer_detection/
    │       ├── test_signal_extraction.py    # S1-S6 individual tests
    │       ├── test_aggregation.py          # Probabilistic formula tests
    │       └── test_auto_select.py          # Threshold/gap logic tests
    ├── integration/
    │   └── customer_detection/
    │       ├── test_detection_flow.py       # End-to-end: inbound → candidates → auto-select
    │       └── test_manual_selection.py     # UI selection → feedback event
    └── fixtures/
        └── customer_detection_fixtures.py   # Test customers, contacts, inbound messages

frontend/
├── src/
│   ├── components/
│   │   └── draft-orders/
│   │       └── CustomerDetectionPanel.tsx  # Candidate display, selection dropdown
│   └── services/
│       └── draftOrdersApi.ts               # API client for customer selection
└── tests/
    └── components/
        └── CustomerDetectionPanel.test.tsx
```

**Structure Decision**: Web application structure chosen due to frontend UI requirements (customer detection panel in draft detail view) and backend API endpoints for manual customer selection. Backend domain logic is cleanly separated from infrastructure (ports/adapters pattern for repositories and external integrations).

## Complexity Tracking

No Constitution violations. All complexity is justified within architectural principles:
- Multi-signal detection is core domain complexity, not accidental.
- Fuzzy matching via pg_trgm is standard PostgreSQL extension, not custom solution.
- Probabilistic aggregation is mathematically sound and testable.
