# Tasks: SMTP Ingest

**Feature Branch**: `006-smtp-ingest`
**Generated**: 2025-12-27
**Implemented**: 2026-01-04

## Phase 1: Setup

- [x] T001 Add aiosmtpd to `backend/requirements/base.txt`
- [x] T002 Create inbox domain ports at `backend/src/domain/inbox/ports/` (Created inbox module structure)
- [x] T003 Create SMTP infrastructure at `backend/src/infrastructure/ingest/`
- [x] T004 Add SMTP configuration to `.env.example`

## Phase 2: Database Schema

- [x] T005 Create inbound_message table migration
- [x] T006 Add unique constraint on (org_id, source, source_message_id)
- [x] T007 Create indexes for inbound_message (org_id+received_at, org_id+status)
- [x] T008 Create InboundMessage SQLAlchemy model at `backend/src/models/inbound_message.py`
- [x] T009 Create InboundMessageStatus enum

## Phase 3: [US1] Receive Orders via Email

- [x] T010 [US1] Create SMTP handler at `backend/src/infrastructure/ingest/smtp_handler.py`
- [x] T011 [US1] Implement handle_DATA method for email receipt
- [x] T012 [US1] Store raw MIME message in object storage
- [x] T013 [US1] Create inbound_message record with status=RECEIVED
- [x] T014 [US1] Add SMTP health checks (Implemented in Dockerfile)
- [x] T015 [US1] Handle emails with no attachments (log warning)

## Phase 4: [US2] Plus-Addressing for Org Routing

- [x] T016 [US2] Implement plus-addressing parser (extract org_slug from email)
- [x] T017 [US2] Validate org exists from org_slug
- [x] T018 [US2] Reject emails for unknown org (SMTP 550 error)
- [x] T019 [US2] Associate inbound_message with correct org_id

## Phase 5: [US3] MIME Parsing and Attachment Extraction

- [x] T020 [US3] Create MIME parser at `backend/src/infrastructure/ingest/mime_parser.py`
- [x] T021 [US3] Implement attachment extraction worker at `backend/src/workers/attachment_extraction_worker.py`
- [x] T022 [US3] Extract all file attachments (skip inline images)
- [x] T023 [US3] Store each attachment in object storage
- [x] T024 [US3] Create document record for each attachment
- [x] T025 [US3] Update inbound_message status to PARSED after extraction
- [x] T026 [US3] Handle multipart/mixed MIME messages
- [x] T027 [US3] Decode RFC 2047 encoded filenames (Handled by Python email library)

## Phase 6: [US4] Deduplication of Identical Messages

- [x] T028 [US4] Implement Message-ID extraction from email headers
- [x] T029 [US4] Handle IntegrityError for duplicate Message-ID
- [x] T030 [US4] Generate synthetic Message-ID for emails missing header
- [x] T031 [US4] Log warning for duplicate messages
- [x] T032 [US4] Ensure deduplication is org-scoped

## Phase 7: Infrastructure

- [x] T033 Create SMTP server Dockerfile at `smtp_ingest.Dockerfile`
- [x] T034 Add SMTP service to docker-compose.yml
- [x] T035 Configure SMTP port binding (25:25)
- [x] T036 Add SMTP server startup script
- [x] T037 Configure SMTP restart policy (always)

## Phase 8: Polish

- [x] T038 Add SMTP server logging configuration (Implemented in start_smtp_server.py)
- [ ] T039 Implement SMTP connection limits (Deferred - can be added via aiosmtpd parameters)
- [x] T040 Document supported MIME types (Documented in spec.md and mime_parser.py)
- [ ] T041 Create test email generator script (Deferred - can use standard email clients for testing)

## Implementation Summary

All core tasks have been completed. The SMTP ingest feature is fully implemented with:

- Database schema with deduplication and multi-tenant isolation
- SMTP server with plus-addressing for org routing
- MIME parsing and attachment extraction
- Background worker for async processing
- Docker containerization with health checks
- Comprehensive error handling and logging

Optional tasks (T039, T041) are deferred as they are not critical for MVP functionality.
