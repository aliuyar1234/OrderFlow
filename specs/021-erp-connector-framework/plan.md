# Implementation Plan: ERP Connector Framework

**Branch**: `021-erp-connector-framework` | **Date**: 2025-12-27 | **Spec**: [specs/021-erp-connector-framework/spec.md](./spec.md)

## Summary

ERP Connector Framework provides a plugin architecture for integrating with diverse ERP systems through a standard Port interface (ERPConnectorPort). The framework handles secure credential storage via AES-256-GCM encryption, connection testing without live exports, and connector registration/resolution through ConnectorRegistry. Each organization can configure one active connector (MVP constraint) with encrypted credentials stored in erp_connection table. The framework isolates domain logic from specific connector implementations, enabling mocking in tests and future connector additions (SAP, EDI, REST APIs) without changing core Push workflow.

**Technical Approach**: Port/Adapter pattern with ERPConnectorPort interface defining export() and test_connection() methods. ConnectorRegistry maps connector_type strings to implementation classes. Encryption uses AES-GCM with random IV per record, ENCRYPTION_MASTER_KEY from environment. API endpoints for config CRUD, test execution, and metadata queries.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, cryptography (AES-GCM), paramiko (SFTP - optional per connector)
**Storage**: PostgreSQL (erp_connection table with config_encrypted BYTEA)
**Testing**: pytest (encryption round-trip tests, mock connector tests, API integration tests)
**Target Platform**: Linux server (containerized)
**Project Type**: Web application (backend API + minimal frontend for config UI)
**Performance Goals**: Connector resolution <10ms, encryption/decryption <5ms, connection test <2s
**Constraints**: ENCRYPTION_MASTER_KEY must be 32-byte hex, UNIQUE active connector per org
**Scale/Scope**: 100 orgs, 1 connector per org (MVP), 5+ connector types (future)

## Constitution Check

| Principle | Compliance | Notes |
|-----------|------------|-------|
| **I. SSOT-First** | ✅ Pass | Schema from §5.4.14, ERPConnectorPort from §3.5, encryption from §11.3 |
| **II. Hexagonal Architecture** | ✅ Pass | ERPConnectorPort is the Port. Concrete implementations (DropzoneJsonV1, SAP, etc.) are Adapters. Domain (PushService) depends only on Port. |
| **III. Multi-Tenant Isolation** | ✅ Pass | erp_connection.org_id enforced. UNIQUE constraint scoped to org_id. |
| **IV. Idempotent Processing** | ✅ Pass | Config updates are idempotent. Test connection is read-only (no side effects). |
| **V. AI-Layer Deterministic Control** | ✅ Pass | No AI involvement. All connector logic is deterministic. |
| **VI. Observability First-Class** | ✅ Pass | Connection test logs success/failure, latency. Encryption failures logged with request_id. |
| **VII. Test Pyramid Discipline** | ✅ Pass | Unit tests for encryption, ConnectorRegistry. Component tests for MockConnector. Integration tests for API + database. |

## Project Structure

```text
backend/
├── src/
│   ├── domain/
│   │   └── connectors/
│   │       ├── port.py                    # ERPConnectorPort interface
│   │       ├── registry.py                # ConnectorRegistry (type → impl mapping)
│   │       ├── models.py                  # ExportResult, TestResult dataclasses
│   │       └── implementations/
│   │           └── mock_connector.py      # MockConnector for tests
│   ├── infrastructure/
│   │   ├── encryption/
│   │   │   └── aes_gcm.py                 # encrypt_config(), decrypt_config()
│   │   └── repositories/
│   │       └── erp_connection_repository.py
│   ├── api/
│   │   └── endpoints/
│   │       └── connectors.py              # POST/GET/TEST connector endpoints
│   └── database/
│       └── models/
│           └── erp_connection.py          # SQLAlchemy model
└── tests/
    ├── unit/
    │   └── connectors/
    │       ├── test_encryption.py         # AES-GCM round-trip tests
    │       └── test_registry.py           # ConnectorRegistry tests
    ├── integration/
    │   └── connectors/
    │       ├── test_api.py                # POST /connectors, test endpoint
    │       └── test_unique_constraint.py  # Duplicate ACTIVE connector blocked
    └── fixtures/
        └── connector_fixtures.py          # Test configs, encrypted data

frontend/
├── src/
│   └── pages/
│       └── ConnectorConfigPage.tsx        # Connector configuration UI
```

## Complexity Tracking

No violations. Encryption is security requirement (non-negotiable). Port/Adapter pattern is justified by extensibility requirement (multiple ERP systems).
