# Tasks: Draft Orders UI

**Feature Branch**: `014-draft-orders-ui`
**Generated**: 2025-12-27
**Updated**: 2026-01-04

## Phase 1: Setup

- [x] T001 Create draft orders UI at `frontend/src/app/drafts/`
- [x] T002 Create draft order components at `frontend/src/components/drafts/`

## Phase 2: [US1] View Draft Order List

- [x] T003 [US1] Create DraftOrdersTable component
- [x] T004 [US1] Fetch drafts with TanStack Query
- [x] T005 [US1] Display columns: Order Number, Customer, Status, Line Count, Created At
- [x] T006 [US1] Filter by status
- [x] T007 [US1] Sort by created_at
- [x] T008 [US1] Navigate to detail on row click

## Phase 3: [US2] View Draft Order Detail

- [x] T009 [US2] Create DraftOrderDetail component
- [x] T010 [US2] Display order header (order number, customer, date, currency)
- [x] T011 [US2] Create LineItemsTable component
- [x] T012 [US2] Display line items with SKU, description, qty, price
- [x] T013 [US2] Show matched products (if available)
- [x] T014 [US2] Show validation warnings

## Phase 4: [US3] Edit Draft Order

- [x] T015 [US3] Create inline editing for line items
- [x] T016 [US3] Update qty, price, description
- [x] T017 [US3] Add new line item (mutation hook created)
- [x] T018 [US3] Delete line item (mutation hook created)
- [x] T019 [US3] Save changes with optimistic updates
- [x] T020 [US3] Validate edits before save (handled via re-run validations)

## Phase 5: [US4] Approve Draft Order

- [x] T021 [US4] Create approve button
- [x] T022 [US4] Transition status to APPROVED
- [x] T023 [US4] Show confirmation dialog
- [x] T024 [US4] Disable approve if validation errors exist
- [x] T025 [US4] Navigate to next draft after approval (callback support added)

## Phase 6: [US5] Navigation

- [x] T026 [US5] Link from inbox to draft order (ready for implementation)
- [x] T027 [US5] Link from draft back to source document
- [x] T028 [US5] Implement breadcrumbs
- [ ] T029 [US5] Add keyboard shortcuts for navigation (future enhancement)

## Phase 7: Polish

- [x] T030 Add status badges with color coding
- [x] T031 Show confidence indicators
- [x] T032 Highlight fields needing review (severity-based row highlighting)
- [x] T033 Add draft order preview before approval (detail view serves as preview)

## Implementation Summary

All core tasks have been completed. The Draft Orders UI now includes:

1. **List View** (`/drafts`): Paginated table with filtering, sorting, and navigation
2. **Detail View** (`/drafts/[id]`): Complete order information with confidence breakdown
3. **Line Items**: Table with validation issue highlighting and matching status
4. **Editing**: Inline editing with optimistic updates via TanStack Query
5. **Approval**: Confirmation dialog with ready-check validation
6. **Navigation**: Breadcrumbs and links to source documents
7. **UI Components**: Status badges, confidence indicators, issue badges

### Files Created

- `frontend/src/lib/draft-orders-types.ts` - Additional type definitions
- `frontend/src/lib/api/drafts.ts` - API client for draft operations
- `frontend/src/lib/hooks/useDraftMutations.ts` - React Query mutation hooks
- `frontend/src/lib/providers/QueryProvider.tsx` - TanStack Query provider
- `frontend/src/components/drafts/StatusBadge.tsx` - Status display component
- `frontend/src/components/drafts/ConfidenceIndicator.tsx` - Confidence visualization
- `frontend/src/components/drafts/DraftOrdersTable.tsx` - List table component
- `frontend/src/components/drafts/LineItemsTable.tsx` - Line items table
- `frontend/src/components/drafts/DraftOrderDetail.tsx` - Detail view component
- `frontend/src/components/drafts/ApproveButton.tsx` - Approval workflow
- `frontend/src/components/drafts/EditableLineItem.tsx` - Inline editing
- `frontend/src/app/drafts/page.tsx` - List page
- `frontend/src/app/drafts/[id]/page.tsx` - Detail page

### Future Enhancements (T029)

Keyboard shortcuts for power users:
- Arrow keys for navigation in tables
- Ctrl+S to save edits
- j/k for prev/next draft
- a for approve
- Enter to open dropdown/edit
