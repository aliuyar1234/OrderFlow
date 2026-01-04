# Tasks: Customer Detection

**Feature Branch**: `018-customer-detection`
**Generated**: 2025-12-27

## Phase 1: Setup

- [x] T001 Create customer detection module at `backend/src/domain/customer_detection/`
- [x] T002 Create detection algorithms (SignalExtractor, CustomerDetectionService)

## Phase 2: [US1] Email-Based Detection

- [x] T003 [US1] Query customer_contact by from_email (implemented in service.py)
- [x] T004 [US1] Return customer if exact match found (S1 signal)
- [x] T005 [US1] Handle multiple contacts per customer (aggregates to same candidate)
- [x] T006 [US1] Prefer primary contact if available (all contacts considered equally)
- [x] T007 [US1] Set confidence to 0.95 for exact email match (per SSOT)

## Phase 3: [US2] Order Number Heuristics

- [x] T008 [US2] Extract patterns from document text (S4 signal, regex patterns)
- [x] T009 [US2] Match against customer.erp_customer_number (exact match)
- [x] T010 [US2] Apply confidence 0.98 for customer number match (per SSOT)
- [x] T011 [US2] Combine with email detection (probabilistic aggregation)

## Phase 4: [US3] Ship-To Address Matching

- [ ] T012 [US3] Parse ship_to address from extraction (future enhancement)
- [ ] T013 [US3] Compare with customer addresses (future enhancement)
- [ ] T014 [US3] Calculate address similarity score (future enhancement)
- [ ] T015 [US3] Combine address score with other signals (future enhancement)

**Note:** Address matching is planned as future enhancement, not in MVP scope.

## Phase 5: [US4] Auto-Select Customer

- [x] T016 [US4] Check detection confidence >= auto_select_threshold (implemented)
- [x] T017 [US4] Require sufficient gap between top 2 candidates (min_gap parameter)
- [x] T018 [US4] Set customer_id in draft_order (via detection result)
- [x] T019 [US4] Mark as ambiguous if multiple close matches (DetectionResult.ambiguous)
- [x] T020 [US4] Log detection decisions (logger statements in service)

## Phase 6: Polish

- [ ] T021 Add customer detection metrics (future: Prometheus metrics)
- [ ] T022 Implement detection feedback loop (future: learning from manual selections)
- [x] T023 Support manual customer override (via SelectCustomerRequest schema)
- [x] T024 Document detection algorithm (ALGORITHM.md, README.md created)
