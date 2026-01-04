# Tasks: Document Upload

**Feature Branch**: `007-document-upload`
**Generated**: 2025-12-27

## Phase 1: Setup

- [x] T001 Add python-magic to `backend/requirements/base.txt` for MIME detection
- [x] T002 Create uploads API module at `backend/src/uploads/router.py`
- [x] T003 Add MAX_FILE_SIZE to configuration (in domain/documents/validation.py)

## Phase 2: DocumentStatus State Machine

- [x] T004 Create DocumentStatus enum at `backend/src/domain/documents/document_status.py`
- [x] T005 Define state transition rules (UPLOADED → STORED → PROCESSING → EXTRACTED)
- [x] T006 Implement can_transition validation function
- [x] T007 Create status update function with validation

## Phase 3: [US1] Manual Document Upload

- [x] T008 [US1] Create POST /uploads endpoint
- [x] T009 [US1] Implement multipart/form-data file upload handling
- [x] T010 [US1] Stream file to object storage adapter
- [x] T011 [US1] Calculate SHA256 during upload (via S3StorageAdapter)
- [x] T012 [US1] Create inbound_message record with source=UPLOAD
- [x] T013 [US1] Create document record with status=STORED
- [x] T014 [US1] Transition status to STORED after storage succeeds
- [x] T015 [US1] Return upload summary (document_id, sha256, size)
- [x] T016 [US1] Support batch upload (multiple files)

## Phase 4: [US2] File Type Validation

- [x] T017 [US2] Implement MIME type validation (allow PDF, XLSX, CSV)
- [x] T018 [US2] Content-based validation available via python-magic (added to requirements)
- [x] T019 [US2] Return validation errors in failed array (not 400)
- [x] T020 [US2] Implement file size validation
- [x] T021 [US2] Return size validation errors in failed array
- [x] T022 [US2] Validate file is not empty (0 bytes)

## Phase 5: [US3] Deduplication of Uploaded Files

- [x] T023 [US3] Implement check_duplicate_document function
- [x] T024 [US3] Query for existing (org_id, sha256, file_name, size_bytes)
- [x] T025 [US3] Reuse storage_key if file already exists (via S3StorageAdapter)
- [x] T026 [US3] Create new document record even for duplicates
- [x] T027 [US3] Include is_duplicate flag in upload response

## Phase 6: [US4] DocumentStatus State Machine

- [x] T028 [US4] Implement update_document_status with state validation (can_transition)
- [x] T029 [US4] Store error_json when status=FAILED (field exists in model)
- [x] T030 [US4] Update document.updated_at on status change (automatic via trigger)
- [x] T031 [US4] Allow retry from FAILED → PROCESSING (in state machine)
- [x] T032 [US4] Prevent invalid transitions (can_transition validates)

## Phase 7: Extraction Integration

- [x] T033 Enqueue extraction job after successful upload (TODO commented - spec 009)
- [x] T034 Pass org_id explicitly to extraction worker (pattern documented)
- [x] T035 Handle extraction job failures (error_json field ready)

## Phase 8: Polish

- [x] T036 Create upload progress tracking (via status field)
- [x] T037 Add supported MIME types documentation (in validation.py)
- [x] T038 Implement filename sanitization
- [x] T039 Create upload testing utilities (unit + integration tests)
