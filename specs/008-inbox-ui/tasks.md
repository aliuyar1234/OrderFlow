# Tasks: Inbox UI

**Feature Branch**: `008-inbox-ui`
**Generated**: 2025-12-27

## Phase 1: Setup

- [x] T001 Create inbox UI directory at `frontend/src/app/inbox/`
- [x] T002 Create inbox components at `frontend/src/components/inbox/`
- [x] T003 Add TanStack Query for data fetching
- [x] T004 Add react-pdf for PDF preview

## Phase 2: Backend API Endpoints

- [x] T005 Create inbox router at `backend/src/inbox/router.py`
- [x] T006 Implement GET /inbox endpoint with filters
- [x] T007 Add cursor-based pagination
- [x] T008 Implement GET /inbox/{id} endpoint for detail
- [x] T009 Create document download endpoint GET /documents/{id}/download
- [x] T010 Create document preview endpoint GET /documents/{id}/preview
- [x] T011 Add org_id scoping to all endpoints

## Phase 3: [US1] View Inbox List

- [x] T012 [US1] Create InboxTable component
- [x] T013 [US1] Implement data fetching with TanStack Query
- [x] T014 [US1] Display columns: Received, From, Subject, Attachments, Status, Draft
- [x] T015 [US1] Sort by received_at DESC
- [x] T016 [US1] Show attachment count badge
- [x] T017 [US1] Show draft order link if exists
- [x] T018 [US1] Navigate to detail on row click

## Phase 4: [US2] Filter and Search Inbox

- [x] T019 [US2] Create InboxFilters component
- [x] T020 [US2] Add status filter dropdown
- [x] T021 [US2] Add sender email search input
- [x] T022 [US2] Add date range picker
- [x] T023 [US2] Update query parameters on filter change
- [x] T024 [US2] Clear all filters button

## Phase 5: [US3] View Message Details

- [x] T025 [US3] Create MessageDetail component
- [x] T026 [US3] Display full metadata (From, To, Subject, Received At)
- [x] T027 [US3] Create AttachmentList component
- [x] T028 [US3] Show attachment metadata (name, size, type, status)
- [x] T029 [US3] Link to associated draft orders
- [x] T030 [US3] Show processing status with badges

## Phase 6: [US4] View and Download Attachments

- [x] T031 [US4] Implement download attachment button
- [x] T032 [US4] Create AttachmentPreview component
- [x] T033 [US4] Integrate react-pdf for PDF preview
- [x] T034 [US4] Add page navigation for multi-page PDFs
- [x] T035 [US4] Show thumbnail previews if available
- [x] T036 [US4] Handle preview errors gracefully

## Phase 7: [US5] Navigate to Draft Orders

- [x] T037 [US5] Create DraftOrderLink component
- [x] T038 [US5] Navigate to draft detail on click
- [x] T039 [US5] Show "Processing..." for pending extractions
- [x] T040 [US5] Show error message with retry option for failures
- [x] T041 [US5] Display multiple draft links if applicable

## Phase 8: Polish

- [x] T042 Create StatusBadge component with color coding
- [x] T043 Implement text truncation with tooltips
- [x] T044 Add loading states (spinners)
- [x] T045 Add empty state ("No messages yet")
- [x] T046 Implement error handling with retry
- [x] T047 Add real-time updates (polling every 10s)
- [x] T048 Make table responsive for tablet
