# Tasks: ERP Connector Framework

**Feature Branch**: `021-erp-connector-framework`
**Generated**: 2025-12-27

## Phase 1: Setup

- [x] T001 Create connectors module at `backend/src/connectors/`
- [x] T002 Create connector domain ports

## Phase 2: ERPConnectorPort Interface

- [x] T003 Create ERPConnectorPort abstract class
- [x] T004 Define export method signature
- [x] T005 Define test_connection method
- [x] T006 Create ExportResult dataclass
- [x] T007 Create TestResult dataclass

## Phase 3: Database Schema

- [x] T008 Create erp_connection table migration
- [x] T009 Store connector settings per org with AES-GCM encryption (BYTEA)
- [x] T010 Create erp_push_log table for push history
- [x] T011 Track push status (SUCCESS, FAILED, PENDING, RETRYING)

## Phase 4: [US1] Connector Registry

- [x] T012 [US1] Create ConnectorRegistry class
- [x] T013 [US1] Register available connectors
- [x] T014 [US1] Select connector based on org configuration
- [x] T015 [US1] Support connector type resolution

## Phase 5: [US2] Push Order Interface

- [x] T016 [US2] Create PushOrchestrator service
- [x] T017 [US2] Implement connector.export() method
- [x] T018 [US2] Handle push responses (success/error)
- [x] T019 [US2] Store push logs with full request/response
- [x] T020 [US2] Implement idempotency key generation

## Phase 6: [US3] Connector Configuration

- [x] T021 [US3] Implement AES-256-GCM encryption service
- [x] T022 [US3] Create ERPConnection SQLAlchemy model
- [x] T023 [US3] Support config encryption/decryption
- [x] T024 [US3] Implement test_connection flow
- [x] T025 [US3] Store encrypted credentials in config_encrypted field

## Phase 7: [US4] Error Handling

- [x] T026 [US4] Implement retry logic with exponential backoff
- [x] T027 [US4] Store error details in erp_push_log
- [x] T028 [US4] Generate user-friendly error messages via ConnectorError
- [x] T029 [US4] Support retry via attempt_number in idempotency key

## Phase 8: Polish

- [x] T030 Add BaseConnector with common functionality
- [x] T031 Document connector implementation guide (README.md)
- [x] T032 Create MockConnector for testing
- [ ] T033 Add push metrics and analytics (deferred - post-MVP)
