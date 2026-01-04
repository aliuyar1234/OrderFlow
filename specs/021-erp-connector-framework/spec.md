# Feature Specification: ERP Connector Framework

**Feature Branch**: `021-erp-connector-framework`
**Created**: 2025-12-27
**Status**: Draft
**Module**: connectors
**SSOT References**: §3.5 (ERPConnectorPort), §5.4.14 (erp_connection), §8.9 (Connectors API), §11.3 (Encryption), T-602

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Configure ERP Connection (Priority: P1)

As an administrator, I need to configure how OrderFlow connects to our ERP system by providing connection details (SFTP host, credentials, paths) that are securely stored and testable.

**Why this priority**: ERP connection configuration is the foundation for all export functionality. Without it, no orders can be pushed to ERP. This is the first step in the Approve & Push workflow.

**Independent Test**: Can be fully tested by POSTing connector configuration via API, verifying that config is encrypted in database, and testing that connection works via test endpoint.

**Acceptance Scenarios**:

1. **Given** admin provides SFTP credentials (host, port, username, password, export_path), **When** POST `/connectors/dropzone-json-v1`, **Then** `erp_connection` record is created with `config_encrypted` (AES-GCM) and `status=ACTIVE`
2. **Given** an existing `erp_connection`, **When** admin updates credentials, **Then** `config_encrypted` is re-encrypted with new IV and updated_at timestamp changes
3. **Given** admin provides local filesystem path (for testing), **When** POST `/connectors/dropzone-json-v1`, **Then** connector config stores `mode=filesystem` and `export_path`
4. **Given** invalid credentials (wrong password), **When** POST with `test_on_save=true`, **Then** API returns 400 with connection test failure message
5. **Given** valid credentials, **When** POST with `test_on_save=true`, **Then** API returns 200 and `last_test_at` timestamp is recorded

---

### User Story 2 - Test ERP Connection (Priority: P1)

Administrators must be able to test the ERP connection without pushing a real order, to verify credentials and network connectivity before going live.

**Why this priority**: Connection testing prevents runtime failures during critical push operations. Testing before production use reduces downtime and support burden.

**Independent Test**: Can be fully tested by calling POST `/connectors/dropzone-json-v1/test`, verifying that a test file is written to the dropzone and then cleaned up.

**Acceptance Scenarios**:

1. **Given** a valid SFTP connection configured, **When** POST `/connectors/dropzone-json-v1/test`, **Then** a test file is written to `export_path/test_connection_<timestamp>.json` and then deleted
2. **Given** invalid SFTP credentials, **When** POST test endpoint, **Then** API returns 400 with error "Authentication failed"
3. **Given** SFTP server is unreachable, **When** POST test endpoint, **Then** API returns 400 with error "Connection timeout"
4. **Given** export_path has no write permissions, **When** POST test endpoint, **Then** API returns 400 with error "Permission denied"
5. **Given** filesystem mode (local path), **When** POST test endpoint, **Then** test file is created and deleted from local filesystem

---

### User Story 3 - Connector Registry & Abstraction (Priority: P1)

The system must support multiple connector implementations (DROPZONE_JSON_V1 in MVP, later SAP, EDI, etc.) through a plugin architecture without changing core domain logic.

**Why this priority**: Connector abstraction is required for extensibility and testability. Domain logic must not depend on specific connector implementations. This enables mocking in tests and future connector additions.

**Independent Test**: Can be fully tested by mocking ERPConnectorPort interface, verifying that domain service (PushService) calls connector methods without knowing implementation details.

**Acceptance Scenarios**:

1. **Given** `ERPConnectorPort` interface defines `export(draft_order) -> ExportResult`, **When** PushService calls export, **Then** concrete connector (DROPZONE_JSON_V1) is invoked via registry
2. **Given** multiple connector types (DROPZONE_JSON_V1, MOCK), **When** org selects connector_type, **Then** registry returns correct implementation
3. **Given** connector raises `ConnectorError`, **When** export is called, **Then** domain service catches error and sets `erp_export.status=FAILED` with error_json
4. **Given** connector interface is mocked in tests, **When** running unit tests for PushService, **Then** tests pass without real SFTP connection
5. **Given** new connector type is added (e.g., REST_API), **When** registered in ConnectorRegistry, **Then** existing domain code works without changes

---

### User Story 4 - Secure Credential Storage (Priority: P1)

All ERP connection credentials (passwords, API keys, SSH keys) must be encrypted at rest using AES-GCM with organization-specific encryption keys.

**Why this priority**: Security compliance (GDPR, SOC2) requires encrypted credential storage. Plaintext passwords are a critical vulnerability. This is non-negotiable for production deployment.

**Independent Test**: Can be fully tested by storing credentials, querying database directly to verify `config_encrypted` is not plaintext, decrypting via application and verifying original values match.

**Acceptance Scenarios**:

1. **Given** admin saves SFTP password "secret123", **When** querying database, **Then** `config_encrypted` contains random IV + ciphertext + auth tag (not "secret123")
2. **Given** encrypted config with IV, **When** application decrypts using ENCRYPTION_MASTER_KEY, **Then** original JSON config is recovered
3. **Given** attacker has database read access but not ENCRYPTION_MASTER_KEY, **When** attempting to decrypt config, **Then** decryption fails (auth tag mismatch)
4. **Given** ENCRYPTION_MASTER_KEY is rotated, **When** re-encrypting all configs, **Then** all connections continue to work with new key
5. **Given** config_encrypted is tampered with (bit flip), **When** decryption is attempted, **Then** auth tag validation fails and error is raised

---

### User Story 5 - Single Active Connection per Org (MVP) (Priority: P2)

In MVP, each organization can have only one active ERP connection at a time. Multi-connector support is deferred to post-MVP.

**Why this priority**: Simplifies MVP implementation and UI. Most customers have one ERP system. Multi-connector support adds complexity (routing logic, UI selection) that is not immediately needed.

**Independent Test**: Can be fully tested by creating a second `erp_connection` for the same org and verifying that database UNIQUE constraint fails.

**Acceptance Scenarios**:

1. **Given** org already has an ACTIVE connector, **When** admin creates a second ACTIVE connector, **Then** API returns 409 Conflict "Only one active connector per org"
2. **Given** org has an ACTIVE connector, **When** admin disables it (`status=DISABLED`), **Then** a new ACTIVE connector can be created
3. **Given** org has DISABLED connector, **When** admin re-enables it, **Then** connector becomes ACTIVE (assuming no other ACTIVE exists)
4. **Given** UNIQUE constraint on (org_id, connector_type) WHERE status=ACTIVE, **When** attempting duplicate ACTIVE, **Then** database constraint prevents insertion

---

### Edge Cases

- What happens if ENCRYPTION_MASTER_KEY is lost? (Credentials are unrecoverable; must re-enter all connection configs)
- How does system handle partial decryption failure (corrupted IV)? (Return error, log incident, block connector usage)
- What if SFTP server changes hostname/port mid-flight? (Admin must update connector config; existing exports may fail until updated)
- What if export_path is changed after exports already exist? (Old exports remain in old path; new exports go to new path; path is stored per export in `dropzone_path`)
- What happens when testing connection during high SFTP server load? (Test may timeout; configurable timeout in connector config)
- How does system handle connector config with 10,000+ character export_path? (Database column TEXT supports it; application validates max path length)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST implement `ERPConnectorPort` interface with methods: `export(draft_order) -> ExportResult`, `test_connection() -> TestResult`
- **FR-002**: System MUST implement `ConnectorRegistry` to map `connector_type` string to concrete implementation
- **FR-003**: System MUST support `connector_type = DROPZONE_JSON_V1` in MVP
- **FR-004**: System MUST implement `erp_connection` table per §5.4.14 schema
- **FR-005**: System MUST encrypt `config_encrypted` field using AES-256-GCM with random 96-bit IV per record
- **FR-006**: System MUST store IV and authentication tag alongside ciphertext in `config_encrypted` BYTEA field
- **FR-007**: System MUST use `ENCRYPTION_MASTER_KEY` environment variable (32-byte hex string) for encryption/decryption
- **FR-008**: System MUST validate `ENCRYPTION_MASTER_KEY` is set and correct length on application startup
- **FR-009**: System MUST expose API: POST `/connectors/dropzone-json-v1` with body `{mode, host, port, username, password, export_path, ack_path, ...}`
- **FR-010**: System MUST expose API: GET `/connectors` returning list of org's connectors with `id, connector_type, status, last_test_at` (excluding config_encrypted)
- **FR-011**: System MUST expose API: POST `/connectors/dropzone-json-v1/test` to test connection without creating export
- **FR-012**: System MUST enforce UNIQUE constraint on (org_id, connector_type) WHERE status='ACTIVE' in database
- **FR-013**: System MUST return 409 Conflict when attempting to create second ACTIVE connector for same org
- **FR-014**: System MUST allow multiple DISABLED connectors per org (for historical record)
- **FR-015**: System MUST validate connector config fields: `mode` (sftp|filesystem), `host` (required if sftp), `export_path` (required)
- **FR-016**: System MUST set `last_test_at` timestamp when test endpoint succeeds
- **FR-017**: System MUST log connector errors (connection failures, encryption errors) with request_id for debugging
- **FR-018**: System MUST support `test_on_save` parameter in POST `/connectors/...` to test before saving
- **FR-019**: System MUST provide decryption utility for admin CLI: `decrypt_connector_config <connection_id>`
- **FR-020**: System MUST restrict connector APIs to ADMIN and INTEGRATOR roles only

### Key Entities *(include if feature involves data)*

- **ERPConnection** (§5.4.14): Represents a configured ERP connector with encrypted credentials. Links org to connector_type and stores encrypted config JSON. Tracks status (ACTIVE/DISABLED) and last_test_at timestamp.

- **ERPConnectorPort** (§3.5): Interface defining contract for ERP connectors. Methods: export(draft_order), test_connection(). Implementations: DropzoneJsonV1Connector, MockConnector (for tests).

- **ExportResult Interface**: Standard return structure for all ERPConnectorPort implementations: {success: bool, export_id: UUID, error_message: str|null, storage_key: str|null, connector_metadata: dict}. All ERPConnectorPort implementations MUST return this exact structure. Connector-specific fields go in connector_metadata.

- **ConnectorRegistry**: Service that maintains mapping of connector_type → implementation class. Used by PushService to resolve connector at runtime.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Connector configuration is encrypted with 100% success rate (verified in integration tests)
- **SC-002**: Decryption of encrypted config yields original plaintext in 100% of cases (unit tests)
- **SC-003**: Connection test correctly identifies failures (wrong credentials, unreachable host) in 100% of test cases
- **SC-004**: UNIQUE constraint prevents duplicate ACTIVE connectors in 100% of attempts (integration tests)
- **SC-005**: ConnectorRegistry resolves correct implementation in < 10ms (performance test)
- **SC-006**: ERPConnectorPort interface allows full mocking in unit tests without real SFTP connections
- **SC-007**: Zero plaintext credentials are logged or returned in API responses (security audit)

## Dependencies

- **Depends on**:
  - **001-database-setup**: Requires `erp_connection` table (§5.4.14)
  - **002-auth**: Requires ADMIN/INTEGRATOR roles for access control
  - **003-organization**: Requires org_id for multi-tenancy

- **Enables**:
  - **022-dropzone-connector**: Provides framework for DROPZONE_JSON_V1 implementation
  - **023-approve-push-flow**: Provides connector interface for push operation

## Implementation Notes

### ERPConnectorPort Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ExportResult:
    success: bool
    export_id: UUID
    error_message: str | None
    storage_key: str | None  # Object storage key for export file
    connector_metadata: dict  # Connector-specific fields (e.g., dropzone_path)

@dataclass
class TestResult:
    success: bool
    error_message: str | None
    latency_ms: int

class ERPConnectorPort(ABC):
    @abstractmethod
    def export(self, draft_order: DraftOrder, config: dict) -> ExportResult:
        """Export draft order to ERP system. Raises ConnectorError on failure."""
        pass

    @abstractmethod
    def test_connection(self, config: dict) -> TestResult:
        """Test connection without exporting. Returns success/failure."""
        pass
```

### ConnectorRegistry Implementation

```python
class ConnectorRegistry:
    _connectors: dict[str, type[ERPConnectorPort]] = {}

    @classmethod
    def register(cls, connector_type: str, implementation: type[ERPConnectorPort]):
        cls._connectors[connector_type] = implementation

    @classmethod
    def get(cls, connector_type: str) -> ERPConnectorPort:
        if connector_type not in cls._connectors:
            raise ValueError(f"Unknown connector type: {connector_type}")
        return cls._connectors[connector_type]()

# Register implementations
ConnectorRegistry.register("DROPZONE_JSON_V1", DropzoneJsonV1Connector)
ConnectorRegistry.register("MOCK", MockConnector)  # For tests
```

### Encryption Key Rotation

Procedure for rotating encryption keys:
1. Store key version in encrypted config prefix (e.g., 'v2:encrypted_data')
2. Support decryption with previous key versions during migration window
3. Re-encrypt all configs with new key via admin migration job
4. Remove old key support after migration confirmed

Document rotation procedure in ops runbook.

### Encryption Implementation (AES-GCM)

```python
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import json

ENCRYPTION_KEY = bytes.fromhex(os.environ["ENCRYPTION_MASTER_KEY"])  # 32 bytes

def encrypt_config(config: dict) -> bytes:
    """Encrypt config JSON and return IV + ciphertext + tag."""
    aesgcm = AESGCM(ENCRYPTION_KEY)
    iv = os.urandom(12)  # 96-bit IV
    plaintext = json.dumps(config).encode('utf-8')
    ciphertext = aesgcm.encrypt(iv, plaintext, None)  # Returns ciphertext + tag
    return iv + ciphertext  # Store IV + ciphertext+tag

def decrypt_config(encrypted: bytes) -> dict:
    """Decrypt config from IV + ciphertext + tag."""
    aesgcm = AESGCM(ENCRYPTION_KEY)
    iv = encrypted[:12]
    ciphertext = encrypted[12:]
    plaintext = aesgcm.decrypt(iv, ciphertext, None)  # Raises on auth failure
    return json.loads(plaintext.decode('utf-8'))
```

### Database Schema

```sql
CREATE TABLE erp_connection (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organization(id),
    connector_type TEXT NOT NULL,  -- 'DROPZONE_JSON_V1'
    config_encrypted BYTEA NOT NULL,  -- IV (12 bytes) + ciphertext + tag (16 bytes)
    status TEXT NOT NULL DEFAULT 'ACTIVE',  -- 'ACTIVE' | 'DISABLED'
    last_test_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_active_connector UNIQUE (org_id, connector_type) WHERE (status = 'ACTIVE')
);

CREATE INDEX idx_erp_connection_org ON erp_connection(org_id, status);
```

### API Examples

**Create Connector**
```http
POST /api/v1/connectors/dropzone-json-v1
Authorization: Bearer <admin-jwt>

{
  "mode": "sftp",
  "host": "sftp.example.com",
  "port": 22,
  "username": "orderflow",
  "password": "secret123",
  "export_path": "/import/orders",
  "ack_path": "/import/acks",
  "atomic_write": true,
  "test_on_save": true
}
```

Response:
```json
{
  "id": "uuid",
  "connector_type": "DROPZONE_JSON_V1",
  "status": "ACTIVE",
  "last_test_at": "2025-12-27T10:00:00Z",
  "test_result": {
    "success": true,
    "latency_ms": 234
  }
}
```

**Test Connector**
```http
POST /api/v1/connectors/dropzone-json-v1/test
Authorization: Bearer <admin-jwt>
```

Response:
```json
{
  "success": true,
  "message": "Test file written and cleaned up successfully",
  "latency_ms": 198
}
```

## Testing Strategy

### Unit Tests
- Encryption/decryption round-trip with various config payloads
- ConnectorRegistry registration and retrieval
- ERPConnectorPort interface mocking for domain services
- Config validation (missing required fields)

### Component Tests
- DropzoneJsonV1Connector.test_connection() with mock SFTP server
- DropzoneJsonV1Connector.export() with mock SFTP server
- Encryption key rotation scenario

### Integration Tests
- POST /connectors/dropzone-json-v1 → encrypted config stored → GET /connectors returns metadata (not plaintext)
- UNIQUE constraint enforcement: create second ACTIVE connector → 409 Conflict
- Test endpoint with invalid credentials → 400 error with message
- Decrypt config via admin CLI → verify original values

### E2E Tests
- Admin configures SFTP connector in UI → tests connection → saves → later push uses this connector
- Admin disables connector → push fails with "No active connector" → re-enable → push works

## SSOT Compliance Checklist

- [ ] `erp_connection` table schema matches §5.4.14
- [ ] `config_encrypted` uses AES-GCM encryption per §11.3
- [ ] ENCRYPTION_MASTER_KEY is random per record (IV) and environment-based (key)
- [ ] ERPConnectorPort interface matches §3.5 design
- [ ] Connector is abstracted from domain logic (Port/Adapter pattern)
- [ ] UNIQUE constraint on (org_id, connector_type) WHERE status='ACTIVE'
- [ ] API endpoints match §8.9 specification
- [ ] Test endpoint simulates write without creating real export
- [ ] T-602 acceptance criteria met (connector is austauschbar, domain unchanged)
