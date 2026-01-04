# Implementation Plan: Dropzone JSON Connector (DROPZONE_JSON_V1)

**Branch**: `022-dropzone-connector` | **Date**: 2025-12-27 | **Spec**: [specs/022-dropzone-connector/spec.md](./spec.md)

## Summary

Dropzone JSON Connector (DROPZONE_JSON_V1) is the concrete implementation of ERPConnectorPort for JSON file-based ERP integration. It generates export JSON files conforming to the orderflow_export_json_v1 schema, writes them to configured dropzone locations (SFTP or local filesystem) with atomic rename, stores export metadata in erp_export table for tracking, and optionally polls for ERP acknowledgment files. The connector handles network failures gracefully, logs all export attempts, and supports retry logic for failed exports. Background worker polls ack_path directory for ERP responses, updating export status to ACKED or FAILED based on ack file content.

**Technical Approach**: DropzoneJsonV1Connector implements ERPConnectorPort. JSON generation uses Pydantic schema validation. SFTP write uses paramiko library with atomic .tmp → rename pattern. Export metadata stored in erp_export table with status tracking (PENDING → SENT → ACKED/FAILED). Celery worker polls ack_path every 60s, parses ack files, updates export records.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, paramiko (SFTP), boto3 (S3), Celery (background worker)
**Storage**: PostgreSQL (erp_export table), S3/MinIO (export JSON files)
**Testing**: pytest (snapshot tests for JSON schema, SFTP integration tests, ack poller tests)
**Target Platform**: Linux server (containerized)
**Project Type**: Web application (backend service + background worker)
**Performance Goals**: Export generation <2s for 500-line drafts, SFTP write <5s, ack polling every 60s
**Constraints**: JSON schema must match §12.1 exactly, atomic write required, idempotent retry
**Scale/Scope**: 1000 exports/day, 100MB export files, 60s ack polling interval

## Constitution Check

| Principle | Compliance | Notes |
|-----------|------------|-------|
| **I. SSOT-First** | ✅ Pass | JSON schema from §12.1, erp_export schema from §5.4.15, ack format from §12.2 |
| **II. Hexagonal Architecture** | ✅ Pass | DropzoneJsonV1Connector is Adapter implementing ERPConnectorPort. Domain (PushService) calls Port, not Adapter directly. |
| **III. Multi-Tenant Isolation** | ✅ Pass | erp_export.org_id enforced. Export files isolated by org_id in S3 keys. |
| **IV. Idempotent Processing** | ✅ Pass | Retry creates new erp_export record (not update). Ack poller is idempotent (moves ack files to processed/). |
| **V. AI-Layer Deterministic Control** | ✅ Pass | No AI. All logic is deterministic JSON generation and file I/O. |
| **VI. Observability First-Class** | ✅ Pass | Export logs storage_key, dropzone_path, status. Ack poller logs processing. |
| **VII. Test Pyramid Discipline** | ✅ Pass | Unit tests for JSON generation. Component tests with mock SFTP. Integration tests for end-to-end export. Snapshot tests for schema compliance. |

## Project Structure

```text
backend/
├── src/
│   ├── domain/
│   │   └── connectors/
│   │       └── implementations/
│   │           └── dropzone_json_v1.py    # DropzoneJsonV1Connector
│   ├── infrastructure/
│   │   ├── sftp/
│   │   │   └── client.py                  # SFTP client wrapper
│   │   └── workers/
│   │       └── ack_poller.py              # Celery worker for ack polling
│   ├── api/
│   │   └── endpoints/
│   │       └── draft_orders.py            # POST /draft-orders/{id}/retry-push
│   └── database/
│       └── models/
│           └── erp_export.py              # SQLAlchemy model
└── tests/
    ├── unit/
    │   └── connectors/
    │       ├── test_json_generation.py    # Schema validation tests
    │       └── test_filename_format.py    # Filename pattern tests
    ├── integration/
    │   └── connectors/
    │       ├── test_sftp_write.py         # SFTP integration with mock server
    │       ├── test_ack_poller.py         # Ack file processing tests
    │       └── test_retry.py              # Failed export retry tests
    └── snapshots/
        └── export_json_v1.snapshot.json   # Golden snapshot for schema
```

## Complexity Tracking

No violations. SFTP atomic write is necessary for reliability. Ack polling is optional feature for bidirectional integration.
