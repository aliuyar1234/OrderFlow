# Implementation Plan: SMTP Ingest

**Branch**: `006-smtp-ingest` | **Date**: 2025-12-27 | **Spec**: [spec.md](./spec.md)

## Summary

Implement SMTP server for receiving order emails with plus-addressing for multi-tenant routing (orders+{org_slug}@domain). Parses MIME messages, extracts attachments, stores raw email in object storage, creates inbound_message records, and enqueues extraction jobs. Supports deduplication based on Message-ID to prevent duplicate processing.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: aiosmtpd, FastAPI, SQLAlchemy 2.x, Celery, Redis
**Storage**: PostgreSQL 16, S3-compatible object storage
**Testing**: pytest, pytest-asyncio, smtplib (for sending test emails)
**Target Platform**: Linux server (Docker containers)
**Project Type**: web
**Performance Goals**: <5s email processing (P95), 100 concurrent connections
**Constraints**: Zero data loss, all emails stored before ACK
**Scale/Scope**: Handle 1000+ emails per day per org

## Constitution Check

### I. SSOT-First
- **Status**: ✅ PASS
- **Evidence**: SMTP ingest specified in SSOT §3.3-3.4, §5.2.2 (InboundMessageStatus), §5.4.5 (inbound_message table)

### II. Hexagonal Architecture
- **Status**: ✅ PASS
- **Evidence**: InboundChannelPort interface with SMTPChannelAdapter implementation. Domain does not import aiosmtpd directly.

### III. Multi-Tenant Isolation
- **Status**: ✅ PASS
- **Evidence**: Plus-addressing extracts org_slug (orders+acme@...), validates org exists, routes to correct org_id. Deduplication constraint includes org_id.

### IV. Idempotent Processing
- **Status**: ✅ PASS
- **Evidence**: Unique constraint on (org_id, source='EMAIL', source_message_id). Same email sent twice → second INSERT fails, skipped.

### V. AI-Layer Deterministic Control
- **Status**: N/A
- **Evidence**: No AI components in email ingestion.

### VI. Observability First-Class
- **Status**: ✅ PASS
- **Evidence**: Structured logging for all received emails (Message-ID, org_id, attachment count, processing time). OpenTelemetry spans for email processing pipeline.

### VII. Test Pyramid Discipline
- **Status**: ✅ PASS
- **Evidence**: Unit tests for plus-addressing parser, MIME parsing, Message-ID extraction. Integration tests for end-to-end email receipt. Contract tests for InboundChannelPort interface.

## Project Structure

### Documentation (this feature)

```text
specs/006-smtp-ingest/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    └── inbound-channel-port.yaml
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── domain/
│   │   └── inbox/
│   │       └── ports/
│   │           └── inbound_channel_port.py
│   ├── infrastructure/
│   │   └── ingest/
│   │       ├── smtp_channel_adapter.py
│   │       ├── smtp_handler.py
│   │       └── mime_parser.py
│   ├── workers/
│   │   └── attachment_extraction_worker.py
│   └── config/
│       └── settings.py
└── tests/
    ├── unit/
    │   └── ingest/
    │       ├── test_plus_addressing.py
    │       ├── test_mime_parsing.py
    │       └── test_message_id_extraction.py
    ├── integration/
    │   └── ingest/
    │       ├── test_smtp_server.py
    │       └── test_email_processing_e2e.py
    └── component/
        └── test_inbound_channel_port.py

smtp_ingest.Dockerfile    # Dedicated SMTP server container
docker-compose.yml         # Add smtp_ingest service
```

**Structure Decision**: Web application with dedicated SMTP ingest service. SMTP handler is infrastructure adapter implementing InboundChannelPort. Worker processes attachments asynchronously.

## Complexity Tracking

> **No violations identified. All constitution checks pass.**
