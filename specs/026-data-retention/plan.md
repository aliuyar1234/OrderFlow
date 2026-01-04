# Implementation Plan: Data Retention & Cleanup

**Branch**: `026-data-retention` | **Date**: 2025-12-27 | **Spec**: [spec.md](./spec.md)

## Summary

This feature implements GDPR-compliant data retention and automatic cleanup. Raw MIME messages and document files older than configured retention period (default 365 days) are automatically soft-deleted from database and removed from object storage. AI call logs older than 90 days are hard-deleted to manage database growth. The system implements a two-phase deletion strategy: soft-delete with 90-day grace period for user-facing data (documents, drafts), hard-delete for system logs. Administrators can manually delete specific documents or drafts for GDPR data subject requests. Retention jobs log execution statistics and alert on failures or anomalies.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: Celery, SQLAlchemy 2.x, S3 SDK
**Storage**: PostgreSQL 16, S3/MinIO
**Testing**: pytest
**Target Platform**: Linux server
**Project Type**: web (backend cron job + admin API)
**Performance Goals**: Retention job completes < 5min for 100k documents, batched deletes (1000/batch)
**Constraints**: Min 30 days retention, max 3650 days (10 years), audit logs min 365 days
**Scale/Scope**: 100k documents/month, 1M AI logs/month

## Constitution Check

| Principle | Status | Compliance Notes |
|-----------|--------|------------------|
| **I. SSOT-First** | ✅ PASS | Retention periods per §11.5, soft/hard delete strategy per spec |
| **II. Hexagonal Architecture** | ✅ PASS | Object storage access via port, retention logic independent of storage implementation |
| **III. Multi-Tenant Isolation** | ✅ PASS | All deletion scoped by org_id, no cross-tenant data deletion |
| **IV. Idempotent Processing** | ✅ PASS | Retention job is idempotent (running twice has same effect), batched deletes |
| **V. AI-Layer Deterministic Control** | N/A | No AI components |
| **VI. Observability First-Class** | ✅ PASS | Retention job logs execution stats, alerts on failure/anomalies |
| **VII. Test Pyramid Discipline** | ✅ PASS | Unit tests for date calculations, integration tests for deletion, E2E for retention job |

**GATE STATUS**: ✅ APPROVED

## Project Structure

```text
specs/026-data-retention/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    └── openapi.yaml

backend/
├── src/
│   ├── workers/
│   │   └── retention_job.py        # Daily cleanup job
│   ├── services/
│   │   └── retention_service.py    # Soft/hard delete logic
│   └── api/
│       └── admin_retention.py      # Manual deletion, settings
└── tests/
```

**Structure Decision**: Web application for admin API + background job.
