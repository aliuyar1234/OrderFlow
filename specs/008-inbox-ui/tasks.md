# Tasks: Inbox UI

**Feature Branch**: `008-inbox-ui`
**Generated**: 2025-12-27

## Phase 1: Setup

- [ ] T001 Create inbox UI directory at `frontend/src/app/inbox/`
- [ ] T002 Create inbox components at `frontend/src/components/inbox/`
- [ ] T003 Add TanStack Query for data fetching
- [ ] T004 Add react-pdf for PDF preview

## Phase 2: Backend API Endpoints

- [x] T005 Create inbox router at `backend/src/inbox/router.py`
- [x] T006 Implement GET /inbox endpoint with filters
- [x] T007 Add cursor-based pagination
- [x] T008 Implement GET /inbox/{id} endpoint for detail
- [ ] T009 Create document download endpoint GET /documents/{id}/download
- [ ] T010 Create document preview endpoint GET /documents/{id}/preview
- [x] T011 Add org_id scoping to all endpoints

## Phase 3: [US1] View Inbox List

- [ ] T012 [US1] Create InboxTable component
- [ ] T013 [US1] Implement data fetching with TanStack Query
- [ ] T014 [US1] Display columns: Received, From, Subject, Attachments, Status, Draft
- [ ] T015 [US1] Sort by received_at DESC
- [ ] T016 [US1] Show attachment count badge
- [ ] T017 [US1] Show draft order link if exists
- [ ] T018 [US1] Navigate to detail on row click

## Phase 4: [US2] Filter and Search Inbox

- [ ] T019 [US2] Create InboxFilters component
- [ ] T020 [US2] Add status filter dropdown
- [ ] T021 [US2] Add sender email search input
- [ ] T022 [US2] Add date range picker
- [ ] T023 [US2] Update query parameters on filter change
- [ ] T024 [US2] Clear all filters button

## Phase 5: [US3] View Message Details

- [ ] T025 [US3] Create MessageDetail component
- [ ] T026 [US3] Display full metadata (From, To, Subject, Received At)
- [ ] T027 [US3] Create AttachmentList component
- [ ] T028 [US3] Show attachment metadata (name, size, type, status)
- [ ] T029 [US3] Link to associated draft orders
- [ ] T030 [US3] Show processing status with badges

## Phase 6: [US4] View and Download Attachments

- [ ] T031 [US4] Implement download attachment button
- [ ] T032 [US4] Create AttachmentPreview component
- [ ] T033 [US4] Integrate react-pdf for PDF preview
- [ ] T034 [US4] Add page navigation for multi-page PDFs
- [ ] T035 [US4] Show thumbnail previews if available
- [ ] T036 [US4] Handle preview errors gracefully

## Phase 7: [US5] Navigate to Draft Orders

- [ ] T037 [US5] Create DraftOrderLink component
- [ ] T038 [US5] Navigate to draft detail on click
- [ ] T039 [US5] Show "Processing..." for pending extractions
- [ ] T040 [US5] Show error message with retry option for failures
- [ ] T041 [US5] Display multiple draft links if applicable

## Phase 8: Polish

- [ ] T042 Create StatusBadge component with color coding
- [ ] T043 Implement text truncation with tooltips
- [ ] T044 Add loading states (spinners)
- [ ] T045 Add empty state ("No messages yet")
- [ ] T046 Implement error handling with retry
- [ ] T047 Add real-time updates (polling every 10s)
- [ ] T048 Make table responsive for tablet
