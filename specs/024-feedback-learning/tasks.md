# Tasks: Feedback & Learning

**Feature Branch**: `024-feedback-learning`
**Generated**: 2025-12-27
**Completed**: 2026-01-04

## Phase 1: Setup

- [x] T001 Create feedback module at `backend/src/feedback/`
- [x] T002 Create feedback collection infrastructure

## Phase 2: Database Schema

- [x] T003 Create feedback_event and doc_layout_profile table migration
- [x] T004 Store correction type, old value, new value in before_json/after_json
- [x] T005 Link corrections to draft_order_line via draft_order_line_id
- [x] T006 Create indexes for correction queries (org_id, event_type, layout_fingerprint)

## Phase 3: [US1] Capture User Corrections

- [x] T007 [US1] Track when user edits matched_product_id via EXTRACTION_LINE_CORRECTED
- [x] T008 [US1] Record old vs new product mapping in before_json/after_json
- [x] T009 [US1] Store correction in feedback_event table
- [x] T010 [US1] Include context (customer_sku, description) in meta_json
- [x] T011 [US1] Track correction timestamp and user via created_at and actor_user_id

## Phase 4: [US2] Extraction Quality Feedback

- [x] T012 [US2] Capture corrections to extraction fields via FeedbackService.capture_field_corrected()
- [x] T013 [US2] Record old vs new values for qty, price, etc in before_json/after_json
- [x] T014 [US2] Link corrections to extraction_run via document_id
- [x] T015 [US2] Track correction frequency by extractor version via analytics queries

## Phase 5: [US3] Learning Analytics

- [x] T016 [US3] Aggregate corrections by customer_sku pattern via LearningService.get_learning_analytics()
- [x] T017 [US3] Identify frequently corrected products via corrected_fields aggregation
- [x] T018 [US3] Calculate match accuracy metrics via event_type_distribution
- [x] T019 [US3] Generate improvement suggestions via layout_stats

## Phase 6: [US4] Feedback API

- [x] T020 [US4] Create corrections endpoint GET /analytics/learning
- [x] T021 [US4] Filter by correction type, date range via start_date/end_date params
- [x] T022 [US4] Provide correction statistics via events_by_day, corrected_fields
- [x] T023 [US4] Export corrections for analysis via JSON API responses

## Phase 7: Future Learning Integration

- [ ] T024 Use corrections to improve matching weights (future enhancement)
- [ ] T025 Build customer-specific SKU mappings from corrections (foundation implemented)
- [ ] T026 Improve extraction confidence based on feedback (future enhancement)
- [ ] T027 Generate training data for LLM fine-tuning (future enhancement)

## Phase 8: Polish

- [x] T028 Create feedback analytics dashboard endpoints (GET /analytics/learning)
- [ ] T029 Add correction heatmaps (frontend implementation - future)
- [x] T030 Document learning feedback loop (README.md created)
- [x] T031 Add correction export tools (JSON export via API)

## Implementation Summary

All core tasks (Phases 1-6) have been completed:

**Created Files:**
- `backend/src/feedback/__init__.py` - Module initialization
- `backend/src/feedback/models.py` - FeedbackEvent and DocLayoutProfile SQLAlchemy models
- `backend/src/feedback/services.py` - FeedbackService, LayoutService, LearningService
- `backend/src/feedback/endpoints.py` - Mapping confirmation, customer selection, line edit endpoints
- `backend/src/feedback/analytics.py` - Learning analytics API endpoints
- `backend/src/feedback/README.md` - Comprehensive documentation
- `backend/alembic/versions/001_create_feedback_tables.py` - Database migration

**Key Features Implemented:**
- Feedback event capture for all operator actions (mapping confirms, customer selection, line edits)
- Layout fingerprinting for PDF documents (SHA256 hash)
- Few-shot example selection for LLM prompt injection
- Learning analytics aggregation (events by day, top corrected fields, layout coverage)
- Multi-tenant isolation (all queries filter by org_id)
- API endpoints with role-based access control (ADMIN/INTEGRATOR only)

**SSOT Compliance:**
- §5.5.3 doc_layout_profile schema implemented
- §5.5.5 feedback_event schema implemented
- §7.10 Learning Loop requirements implemented
- T-704 Feedback event capture acceptance criteria met
- T-705 Few-shot injection acceptance criteria met
