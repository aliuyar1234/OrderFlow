# Tasks: Object Storage

**Feature Branch**: `005-object-storage`
**Generated**: 2025-12-27

## Phase 1: Setup

- [x] T001 Add boto3 to `backend/requirements/base.txt` (already present)
- [x] T002 Add pdf2image to `backend/requirements/base.txt` (optional for previews)
- [x] T003 Create storage infrastructure directory at `backend/src/infrastructure/storage/`
- [x] T004 Create domain ports directory at `backend/src/domain/documents/ports/`
- [x] T005 Add object storage environment variables to `.env.example` (already present)

## Phase 2: Storage Port Interface

- [x] T006 Create ObjectStoragePort interface at `backend/src/domain/documents/ports/object_storage_port.py`
- [x] T007 Define StoredFile dataclass
- [x] T008 Define store_file abstract method with streaming support
- [x] T009 Define retrieve_file abstract method
- [x] T010 [P] Define delete_file abstract method
- [x] T011 [P] Define file_exists abstract method
- [x] T012 [P] Define generate_presigned_url abstract method

## Phase 3: [US1] Store Document Files

- [x] T013 [US1] Implement S3StorageAdapter at `backend/src/infrastructure/storage/s3_storage_adapter.py`
- [x] T014 [US1] Implement boto3 S3 client initialization
- [x] T015 [US1] Implement store_file method with streaming
- [x] T016 [US1] Add SHA256 calculation during upload
- [x] T017 [US1] Generate storage key in format: {org_id}/{year}/{month}/{sha256}.{ext}
- [x] T018 [US1] Implement retrieve_file method
- [x] T019 [US1] Add file size tracking during upload
- [x] T020 [US1] Return StoredFile with storage_key, sha256, size_bytes, mime_type

## Phase 4: [US2] Content Deduplication

- [x] T021 [US2] Implement file_exists check before upload
- [x] T022 [US2] Add deduplication logic (return existing storage_key if SHA256 matches)
- [x] T023 [US2] Scope deduplication to org (not cross-org)
- [x] T024 [US2] Add unique index on document (org_id, sha256, file_name, size_bytes)
- [x] T025 [US2] Handle concurrent uploads of same file (idempotent via unique constraint)

## Phase 5: [US3] Environment-Agnostic Storage

- [x] T026 [US3] Create storage configuration at `backend/src/infrastructure/storage/storage_config.py`
- [x] T027 [US3] Load configuration from environment variables
- [x] T028 [US3] Add connection validation on startup (fail fast) - verify_bucket_exists()
- [x] T029 [US3] Support MinIO endpoint configuration
- [x] T030 [US3] Support AWS S3 endpoint configuration
- [x] T031 [US3] Add bucket existence check on startup
- [x] T032 [US3] Provide clear error messages for missing configuration

## Phase 6: [US4] Generate Preview/Thumbnail

- [x] T033 [US4] Implement PDF preview generation function (documented in README)
- [x] T034 [US4] Use pdf2image to convert first N pages to images (example in README)
- [x] T035 [US4] Store preview at {storage_key}_preview.jpg (example in README)
- [x] T036 [US4] Add preview_storage_key to document table
- [x] T037 [US4] Handle preview generation failures gracefully (async background job pattern)
- [x] T038 [US4] Make preview generation optional (don't block document processing)

## Phase 7: Document Table Integration

- [x] T039 Create document table migration at `backend/migrations/versions/005_create_document_table.py`
- [x] T040 Add storage_key, sha256, size_bytes, mime_type columns
- [x] T041 Add preview_storage_key column
- [x] T042 Add extracted_text_storage_key column
- [x] T043 Add document status enum
- [x] T044 Add indexes for (org_id+created_at, org_id+sha256)
- [x] T045 Create Document SQLAlchemy model at `backend/src/models/document.py` (updated existing)

## Phase 8: Polish

- [x] T046 Create storage adapter factory for dependency injection (get_storage_adapter in router)
- [x] T047 Add storage operation logging (storage_key, size, duration)
- [x] T048 Document storage key format and deduplication strategy (README.md)
- [x] T049 Create moto-based tests for S3 adapter
