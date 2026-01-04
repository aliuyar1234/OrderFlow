# Implementation Plan: Object Storage

**Branch**: `005-object-storage` | **Date**: 2025-12-27 | **Spec**: [spec.md](./spec.md)

## Summary

Implement S3-compatible object storage layer for document persistence with MinIO (dev) and AWS S3 (prod) support. Provides storage adapter interface, SHA256-based deduplication, streaming uploads, and optional preview generation for PDFs. Storage keys include org_id for multi-tenant isolation and SHA256 for content-addressed storage.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, boto3, SQLAlchemy 2.x, pdf2image (optional for previews)
**Storage**: PostgreSQL 16, MinIO (dev), AWS S3 (prod)
**Testing**: pytest, moto (S3 mocking)
**Target Platform**: Linux server (Docker containers)
**Project Type**: web
**Performance Goals**: <60s for 100MB uploads, <500ms for file retrieval (P95)
**Constraints**: <10% overhead for SHA256 calculation, zero file corruption
**Scale/Scope**: Support files up to 100MB, handle 1000+ documents per org

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. SSOT-First
- **Status**: ✅ PASS
- **Evidence**: Object storage is specified in SSOT §3.2, §5.4.6, §10.2. Storage key format, deduplication logic, and environment configuration are fully defined.

### II. Hexagonal Architecture
- **Status**: ✅ PASS
- **Evidence**: ObjectStoragePort interface defined with S3StorageAdapter as implementation. Domain code will not import boto3 directly. Adapter is swappable (MinIO ↔ S3).

### III. Multi-Tenant Isolation
- **Status**: ✅ PASS
- **Evidence**: Storage keys include org_id prefix: `{org_id}/{year}/{month}/{sha256}.{ext}`. Per-org deduplication (not cross-org).

### IV. Idempotent Processing
- **Status**: ✅ PASS
- **Evidence**: `store_file()` checks if SHA256 exists before upload; returns existing storage_key if duplicate. Same file uploaded multiple times produces same result.

### V. AI-Layer Deterministic Control
- **Status**: N/A
- **Evidence**: No AI components in this feature.

### VI. Observability First-Class
- **Status**: ✅ PASS
- **Evidence**: Storage operations will log storage_key, size_bytes, SHA256, and errors. Integration with structured logging and OpenTelemetry spans.

### VII. Test Pyramid Discipline
- **Status**: ✅ PASS
- **Evidence**: Unit tests for SHA256 calculation, storage key generation, deduplication logic. Integration tests for MinIO/S3 round-trips. Component tests for adapter interface.

## Project Structure

### Documentation (this feature)

```text
specs/005-object-storage/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── contracts/           # Phase 1 output
    └── openapi.yaml     # API schemas (if applicable)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── domain/
│   │   └── documents/
│   │       └── ports/
│   │           └── object_storage_port.py    # Port interface
│   ├── infrastructure/
│   │   └── storage/
│   │       ├── s3_storage_adapter.py         # S3 adapter implementation
│   │       └── storage_config.py             # Environment-based config
│   ├── api/
│   │   └── v1/
│   │       └── documents/
│   │           └── download.py               # Download endpoints (future)
│   └── config/
│       └── settings.py                       # Environment variables
└── tests/
    ├── unit/
    │   └── storage/
    │       ├── test_storage_key_generation.py
    │       ├── test_sha256_calculation.py
    │       └── test_deduplication.py
    ├── integration/
    │   └── storage/
    │       ├── test_s3_adapter_minio.py
    │       └── test_s3_adapter_s3.py
    └── component/
        └── test_object_storage_port.py
```

**Structure Decision**: Web application structure with backend containing domain (ports) and infrastructure (adapters). Storage adapter is pure infrastructure, isolated from domain logic. Tests organized by type (unit, integration, component) per Test Pyramid.

## Complexity Tracking

> **No violations identified. All constitution checks pass.**
