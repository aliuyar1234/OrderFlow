# Tasks: Tenancy Isolation

**Feature Branch**: `003-tenancy-isolation`
**Generated**: 2025-12-27

## Phase 1: Setup

- [X] T001 Create tenancy module structure at `backend/src/tenancy/`
- [X] T002 Add org settings Pydantic schemas to project structure

## Phase 2: Org Settings Schema

- [X] T003 Create OrgSettings Pydantic model at `backend/src/tenancy/schemas.py`
- [X] T004 Create MatchingSettings sub-schema
- [X] T005 [P] Create CustomerDetectionSettings sub-schema
- [X] T006 [P] Create AISettings sub-schema
- [X] T007 [P] Create ExtractionSettings sub-schema
- [X] T008 Add validation for default_currency (ISO 4217)
- [X] T009 Add validation for price_tolerance_percent (>= 0)
- [X] T010 Add validation for threshold values (0.0-1.0 range)

## Phase 3: [US1] Automatic Tenant Scoping

- [X] T011 [US1] Create scoped session factory at `backend/src/database.py`
- [X] T012 [US1] Implement get_org_id dependency at `backend/src/dependencies.py`
- [X] T013 [US1] Create automatic org_id filter for SQLAlchemy queries
- [X] T014 [US1] Implement 404 (not 403) response for cross-org resource access
- [X] T015 [US1] Create middleware to extract org_id from JWT at `backend/src/tenancy/middleware.py`
- [X] T016 [US1] Implement automatic org_id injection for INSERT operations
- [X] T017 [US1] Add org_id validation (ensure org exists in database)

## Phase 4: [US2] Org Settings Management

- [X] T018 [US2] Create org settings router at `backend/src/tenancy/router.py`
- [X] T019 [US2] Implement GET /org/settings endpoint
- [X] T020 [US2] Implement PATCH /org/settings endpoint (ADMIN only)
- [X] T021 [US2] Add settings validation before persisting to settings_json
- [X] T022 [US2] Implement partial settings update (merge logic)
- [X] T023 [US2] Add default settings initialization for new orgs
- [X] T024 [US2] Ensure settings changes take effect immediately (<1 second)

## Phase 5: [US3] Org Isolation in Background Jobs

- [X] T025 [US3] Update Celery task signatures to require org_id parameter
- [X] T026 [US3] Create org_id validation utility for background jobs
- [X] T027 [US3] Implement scoped session creation in Celery tasks
- [X] T028 [US3] Add org_id to all job enqueue calls
- [X] T029 [US3] Implement job failure on missing/invalid org_id
- [X] T030 [US3] Document org_id passing pattern for background jobs

## Phase 6: Polish

- [X] T031 Create multi-org test fixtures for pytest
- [X] T032 Create SQL query logging utility to verify org_id filters
- [X] T033 Add database constraint verification script (org_id NOT NULL, foreign keys)
- [X] T034 Document tenant scoping patterns for developers
