# Implementation Plan: Feedback & Learning Loop

**Branch**: `024-feedback-learning` | **Date**: 2025-12-27 | **Spec**: [spec.md](./spec.md)

## Summary

This feature implements continuous improvement through feedback capture and few-shot learning. Every operator correction (SKU mapping confirms, line edits, customer selections) is captured as a feedback_event. PDF documents are fingerprinted by layout structure to group similar documents. When extracting PDFs with known layouts, the system injects the last 3 corrected examples into the LLM prompt to improve accuracy without model retraining. Confirmed SKU mappings update the matching engine to auto-apply in future drafts. An optional analytics dashboard provides visibility into learning effectiveness and quality trends.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, hashlib (SHA256), OpenAI/Anthropic SDK
**Storage**: PostgreSQL 16 (feedback_event, doc_layout_profile tables)
**Testing**: pytest (unit, component, integration, E2E)
**Target Platform**: Linux server
**Project Type**: web (backend API + frontend UI + background workers)
**Performance Goals**: Feedback capture < 50ms latency, few-shot lookup < 10ms, analytics dashboard loads < 2s
**Constraints**: Org isolation for examples, 1500 char input snippet limit, 365-day retention
**Scale/Scope**: 100k feedback events/month, 1k unique layouts, 3-example injection per extraction

## Constitution Check

| Principle | Status | Compliance Notes |
|-----------|--------|------------------|
| **I. SSOT-First** | ✅ PASS | Feedback event schema per §5.5.5, layout profile per §5.5.3, few-shot injection per §7.10 |
| **II. Hexagonal Architecture** | ✅ PASS | FeedbackService abstracts capture logic, LLMProviderPort receives examples via context, no direct coupling |
| **III. Multi-Tenant Isolation** | ✅ PASS | All feedback events filtered by org_id, examples injected only from same org, no cross-tenant leakage |
| **IV. Idempotent Processing** | ✅ PASS | Feedback capture is additive (insert-only), layout profile increment is idempotent, no duplicate prevention needed |
| **V. AI-Layer Deterministic Control** | ✅ PASS | Few-shot examples are deterministic (last 3 by created_at DESC), no hallucination risk, examples are validated corrections |
| **VI. Observability First-Class** | ✅ PASS | Feedback events logged with request_id, analytics dashboard exposes metrics, correction rates tracked |
| **VII. Test Pyramid Discipline** | ✅ PASS | Unit tests for fingerprinting, component tests for example injection, integration tests for E2E capture, A/B test for accuracy improvement |

**GATE STATUS**: ✅ APPROVED - All principles satisfied

## Project Structure

### Documentation (this feature)

```text
specs/024-feedback-learning/
├── plan.md              # This file
├── research.md          # Learning loop best practices
├── data-model.md        # FeedbackEvent, DocLayoutProfile schemas
├── quickstart.md        # Development setup
└── contracts/           # API contracts
    └── openapi.yaml
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   ├── feedback_event.py       # FeedbackEvent entity
│   │   └── doc_layout_profile.py   # DocLayoutProfile entity
│   ├── services/
│   │   ├── feedback_service.py     # Feedback capture logic
│   │   ├── layout_service.py       # Fingerprinting and profile management
│   │   └── learning_service.py     # Few-shot example selection
│   ├── api/
│   │   ├── sku_mappings.py         # POST /sku-mappings/{id}/confirm
│   │   ├── draft_lines.py          # PATCH /draft-lines/{id} (capture edits)
│   │   └── analytics.py            # GET /analytics/learning
│   └── lib/
│       └── fingerprint.py          # Layout fingerprint generation
└── tests/
    ├── unit/
    │   ├── test_fingerprint.py
    │   ├── test_example_selection.py
    │   └── test_mapping_feedback.py
    ├── integration/
    │   ├── test_feedback_capture.py
    │   └── test_few_shot_injection.py
    └── e2e/
        └── test_learning_loop.py

frontend/
├── src/
│   ├── components/
│   │   └── LearningAnalytics.tsx   # Analytics dashboard
│   └── pages/
│       └── AdminAnalytics.tsx      # Admin page for learning metrics
└── tests/
```

**Structure Decision**: Web application structure selected due to backend API + frontend analytics UI requirements. Backend handles feedback capture, fingerprinting, and example injection. Frontend provides analytics visualization for admins.

## Complexity Tracking

*No violations - all constitution principles satisfied.*
