# Implementation Plan: Document Upload

**Branch**: `007-document-upload` | **Date**: 2025-12-27 | **Spec**: [spec.md](./spec.md)

## Summary

Implement manual document upload API for PDF/Excel/CSV files. Validates MIME types, calculates SHA256 for deduplication, stores files in object storage, creates document and inbound_message records, and triggers extraction. Supports batch upload and enforces role-based access control (OPS, ADMIN, INTEGRATOR only).

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, python-magic (MIME detection), Celery
**Storage**: PostgreSQL 16, S3-compatible object storage
**Testing**: pytest, pytest-asyncio
**Target Platform**: Linux server
**Project Type**: web
**Performance Goals**: <10s for 10MB uploads, <60s for 100MB uploads (P95)
**Constraints**: Streaming uploads (no memory buffering), zero file corruption
**Scale/Scope**: Support 100MB max file size, 10 files per batch

## Constitution Check

### I. SSOT-First
- **Status**: ✅ PASS
- **Evidence**: Upload API specified in SSOT §8.5, DocumentStatus in §5.2.3, document table in §5.4.6

### II. Hexagonal Architecture
- **Status**: ✅ PASS
- **Evidence**: Upload endpoint uses ObjectStoragePort interface. No direct storage implementation in API layer.

### III. Multi-Tenant Isolation
- **Status**: ✅ PASS
- **Evidence**: org_id extracted from JWT, enforced in all operations. Uploads scoped to authenticated user's org.

### IV. Idempotent Processing
- **Status**: ✅ PASS
- **Evidence**: SHA256 deduplication prevents duplicate storage. Same file uploaded twice → reuses storage_key.

### V. AI-Layer Deterministic Control
- **Status**: N/A

### VI. Observability First-Class
- **Status**: ✅ PASS
- **Evidence**: Upload metrics logged (file size, SHA256, org_id, upload duration). Errors logged with context.

### VII. Test Pyramid Discipline
- **Status**: ✅ PASS
- **Evidence**: Unit tests for MIME validation, status transitions. Integration tests for upload API. E2E tests for batch upload.

## Project Structure

### Documentation (this feature)

```text
specs/007-document-upload/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    └── openapi.yaml
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/
│   │   └── v1/
│   │       └── uploads.py          # POST /uploads endpoint
│   ├── domain/
│   │   └── documents/
│   │       ├── document_status.py  # DocumentStatus enum
│   │       └── validation.py       # MIME type validation
│   ├── workers/
│   │   └── extraction_worker.py    # Trigger extraction
│   └── config/
│       └── settings.py             # MAX_FILE_SIZE
└── tests/
    ├── unit/
    │   └── uploads/
    │       ├── test_mime_validation.py
    │       ├── test_status_transitions.py
    │       └── test_file_size_validation.py
    ├── integration/
    │   └── uploads/
    │       ├── test_upload_api.py
    │       ├── test_batch_upload.py
    │       └── test_deduplication.py
    └── e2e/
        └── test_upload_to_draft_flow.py
```

**Structure Decision**: Web application structure. Upload API is part of backend/api/v1. Reuses ObjectStoragePort from spec 005 and document model. Workers trigger extraction pipeline.

## Complexity Tracking

> **No violations identified. All constitution checks pass.**
