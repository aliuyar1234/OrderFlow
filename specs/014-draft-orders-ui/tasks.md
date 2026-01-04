# Tasks: Draft Orders UI

**Feature Branch**: `014-draft-orders-ui`
**Generated**: 2025-12-27

## Phase 1: Setup

- [ ] T001 Create draft orders UI at `frontend/src/app/drafts/`
- [ ] T002 Create draft order components at `frontend/src/components/drafts/`

## Phase 2: [US1] View Draft Order List

- [ ] T003 [US1] Create DraftOrdersTable component
- [ ] T004 [US1] Fetch drafts with TanStack Query
- [ ] T005 [US1] Display columns: Order Number, Customer, Status, Line Count, Created At
- [ ] T006 [US1] Filter by status
- [ ] T007 [US1] Sort by created_at
- [ ] T008 [US1] Navigate to detail on row click

## Phase 3: [US2] View Draft Order Detail

- [ ] T009 [US2] Create DraftOrderDetail component
- [ ] T010 [US2] Display order header (order number, customer, date, currency)
- [ ] T011 [US2] Create LineItemsTable component
- [ ] T012 [US2] Display line items with SKU, description, qty, price
- [ ] T013 [US2] Show matched products (if available)
- [ ] T014 [US2] Show validation warnings

## Phase 4: [US3] Edit Draft Order

- [ ] T015 [US3] Create inline editing for line items
- [ ] T016 [US3] Update qty, price, description
- [ ] T017 [US3] Add new line item
- [ ] T018 [US3] Delete line item
- [ ] T019 [US3] Save changes with optimistic updates
- [ ] T020 [US3] Validate edits before save

## Phase 5: [US4] Approve Draft Order

- [ ] T021 [US4] Create approve button
- [ ] T022 [US4] Transition status to APPROVED
- [ ] T023 [US4] Show confirmation dialog
- [ ] T024 [US4] Disable approve if validation errors exist
- [ ] T025 [US4] Navigate to next draft after approval

## Phase 6: [US5] Navigation

- [ ] T026 [US5] Link from inbox to draft order
- [ ] T027 [US5] Link from draft back to source document
- [ ] T028 [US5] Implement breadcrumbs
- [ ] T029 [US5] Add keyboard shortcuts for navigation

## Phase 7: Polish

- [ ] T030 Add status badges with color coding
- [ ] T031 Show confidence indicators
- [ ] T032 Highlight fields needing review
- [ ] T033 Add draft order preview before approval
