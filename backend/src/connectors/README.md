# ERP Connector Framework

The ERP Connector Framework provides a plugin architecture for integrating OrderFlow with diverse ERP systems through a standard Port interface (ERPConnectorPort).

## Architecture

The framework follows **Hexagonal Architecture (Ports & Adapters)**:

- **Port**: `ERPConnectorPort` - Abstract interface defining the contract
- **Adapters**: Concrete implementations (e.g., `DropzoneJsonV1Connector`, `MockConnector`)
- **Domain Logic**: Uses only the Port, never depends on specific Adapters

```
┌─────────────────────────────────────────┐
│         Domain Logic (PushService)       │
│              depends on ↓                │
│         ERPConnectorPort (Port)          │
└─────────────────────────────────────────┘
                    ↑
        ┌───────────┴───────────┐
        │                       │
┌───────────────┐    ┌─────────────────┐
│DropzoneJSON   │    │  MockConnector  │
│   Connector   │    │   (for tests)   │
│  (Adapter)    │    │    (Adapter)    │
└───────────────┘    └─────────────────┘
```

## Core Components

### 1. ERPConnectorPort (`ports.py`)

Abstract interface that all connectors must implement:

```python
class ERPConnectorPort(ABC):
    @abstractmethod
    def export(self, draft_order, config) -> ExportResult:
        """Export a draft order to ERP"""
        pass

    @abstractmethod
    def test_connection(self, config) -> TestResult:
        """Test connection without exporting"""
        pass
```

### 2. ConnectorRegistry (`registry.py`)

Central registry for connector implementations:

```python
# Register a connector (at startup)
ConnectorRegistry.register("DROPZONE_JSON_V1", DropzoneJsonV1Connector)

# Resolve connector at runtime
connector = ConnectorRegistry.get("DROPZONE_JSON_V1")
result = connector.export(draft_order, config)
```

### 3. EncryptionService (`encryption.py`)

AES-256-GCM encryption for secure credential storage:

```python
# Encrypt configuration
config = {"host": "sftp.example.com", "password": "secret"}
encrypted = EncryptionService.encrypt_config(config)

# Decrypt configuration
config = EncryptionService.decrypt_config(encrypted)
```

### 4. PushOrchestrator (`push_service.py`)

Orchestrates push operations with idempotency and retry logic:

```python
orchestrator = PushOrchestrator(db_session)
result = orchestrator.push_order(
    org_id=org.id,
    draft_order=draft_order,
    max_retries=3
)
```

### 5. BaseConnector (`base_connector.py`)

Common functionality for connector implementations:

- Config validation helpers
- Latency measurement
- Standard error handling
- Logging utilities

## Database Schema

### `erp_connection` - Connector Configuration

Stores encrypted connector configurations per organization:

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `org_id` | UUID | Organization (multi-tenant isolation) |
| `connector_type` | TEXT | Connector type (DROPZONE_JSON_V1, MOCK, etc.) |
| `config_encrypted` | BYTEA | AES-GCM encrypted config (IV + ciphertext + tag) |
| `status` | TEXT | ACTIVE or DISABLED |
| `last_test_at` | TIMESTAMPTZ | Last successful test timestamp |
| `created_at` | TIMESTAMPTZ | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | Last update timestamp |

**Constraints**:
- UNIQUE(org_id, connector_type) WHERE status='ACTIVE' (MVP: one active connector per org)

### `erp_push_log` - Push History

Tracks every push attempt with full request/response for debugging:

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `org_id` | UUID | Organization |
| `draft_order_id` | UUID | Draft order being pushed |
| `connector_type` | TEXT | Connector type used |
| `status` | TEXT | SUCCESS, FAILED, PENDING, RETRYING |
| `request_json` | JSONB | Request payload |
| `response_json` | JSONB | Response metadata |
| `error_message` | TEXT | Error message if failed |
| `idempotency_key` | TEXT | Unique key (prevents duplicates) |
| `retry_count` | INTEGER | Number of retry attempts |
| `latency_ms` | INTEGER | Total latency in milliseconds |
| `created_at` | TIMESTAMPTZ | Creation timestamp |

**Constraints**:
- UNIQUE(idempotency_key) (prevents duplicate processing)

## Implementing a New Connector

### Step 1: Create Implementation

Create a new file `backend/src/connectors/implementations/my_connector.py`:

```python
from typing import Any, Dict
from ..ports import ExportResult, TestResult, ConnectorError
from ..base_connector import BaseConnector

class MyConnector(BaseConnector):
    """
    My ERP Connector - Integrates with MyERP system.

    Configuration:
        - api_url: MyERP API endpoint
        - api_key: Authentication key
        - company_id: Company identifier
    """

    def export(self, draft_order: Any, config: Dict[str, Any]) -> ExportResult:
        """Export draft order to MyERP."""
        # Validate config
        self.validate_required_fields(
            config,
            ["api_url", "api_key", "company_id"]
        )

        # Transform draft_order to MyERP format
        payload = self._transform_order(draft_order, config)

        # Send to MyERP API
        try:
            response = self._send_to_erp(payload, config)

            return ExportResult(
                success=True,
                export_id=draft_order.id,
                storage_key=f"myerp/exports/{draft_order.id}.json",
                connector_metadata={
                    "erp_order_id": response["order_id"],
                    "erp_order_number": response["order_number"]
                }
            )
        except Exception as e:
            raise ConnectorError(f"MyERP export failed: {e}")

    def test_connection(self, config: Dict[str, Any]) -> TestResult:
        """Test connection to MyERP API."""
        with self.measure_latency("myerp_connection_test") as timer:
            try:
                self.validate_required_fields(
                    config,
                    ["api_url", "api_key", "company_id"]
                )

                # Attempt simple API call
                self._test_api_connection(config)

                return self.build_test_result(
                    success=True,
                    latency_ms=timer.latency_ms
                )
            except Exception as e:
                return self.build_test_result(
                    success=False,
                    error_message=str(e),
                    latency_ms=timer.latency_ms
                )

    def _transform_order(self, draft_order, config):
        """Transform draft order to MyERP format."""
        # Implementation here
        pass

    def _send_to_erp(self, payload, config):
        """Send payload to MyERP API."""
        # Implementation here
        pass

    def _test_api_connection(self, config):
        """Test API connection."""
        # Implementation here
        pass
```

### Step 2: Register Connector

Register at application startup (e.g., in `backend/src/app.py`):

```python
from connectors.implementations.my_connector import MyConnector
from connectors.registry import ConnectorRegistry

# Register connector
ConnectorRegistry.register("MY_ERP", MyConnector)
```

### Step 3: Update Model Validation

Add the new connector type to `backend/src/models/erp_connection.py`:

```python
@validates('connector_type')
def validate_connector_type(self, key, value):
    valid_types = ['DROPZONE_JSON_V1', 'MOCK', 'SAP', 'EDI', 'MY_ERP']
    if value not in valid_types:
        raise ValueError(f"Invalid connector_type: {value}")
    return value
```

### Step 4: Write Tests

Create tests in `backend/tests/unit/connectors/test_my_connector.py`:

```python
import pytest
from connectors.implementations.my_connector import MyConnector
from connectors.ports import ConnectorError

def test_my_connector_export_success(mock_draft_order):
    connector = MyConnector()
    config = {
        "api_url": "https://myerp.example.com/api",
        "api_key": "test-key",
        "company_id": "ACME"
    }

    result = connector.export(mock_draft_order, config)

    assert result.success is True
    assert result.export_id == mock_draft_order.id

def test_my_connector_missing_config():
    connector = MyConnector()
    config = {"api_url": "https://example.com"}  # Missing api_key

    with pytest.raises(ConnectorError):
        connector.export(mock_draft_order, config)

def test_my_connector_test_connection():
    connector = MyConnector()
    config = {
        "api_url": "https://myerp.example.com/api",
        "api_key": "test-key",
        "company_id": "ACME"
    }

    result = connector.test_connection(config)

    assert result.success is True
    assert result.latency_ms > 0
```

## Security Best Practices

### 1. Encryption

All connector credentials MUST be encrypted at rest:

```python
from connectors.encryption import EncryptionService

# Before storing in database
config = {"api_key": "secret123"}
encrypted = EncryptionService.encrypt_config(config)

# Store encrypted bytes in erp_connection.config_encrypted
connection.config_encrypted = encrypted
```

### 2. Environment Variables

Master encryption key must be set via environment variable:

```bash
# Generate a key (32 bytes = 64 hex chars)
python -c 'import os; print(os.urandom(32).hex())'

# Set in environment
export ENCRYPTION_MASTER_KEY="abc123..."
```

### 3. Never Log Credentials

Never log plaintext credentials or decrypted configs:

```python
# BAD
logger.info(f"Config: {config}")  # Logs password!

# GOOD
logger.info(f"Connector type: {connector_type}")
logger.debug(f"Config has {len(config)} fields")  # No sensitive data
```

## Idempotency

All push operations are idempotent via `idempotency_key`:

```python
# Same org_id + draft_order_id + attempt always generates same key
key = orchestrator.generate_idempotency_key(org_id, order_id, attempt=0)

# Check if already processed
existing = orchestrator.check_idempotency(key)
if existing:
    return existing  # Skip duplicate processing
```

## Retry Logic

Push operations retry with exponential backoff:

```python
orchestrator.push_order(
    org_id=org.id,
    draft_order=draft_order,
    max_retries=3,          # Total of 4 attempts (initial + 3 retries)
    retry_delay_base=1.0    # Delays: 1s, 2s, 4s
)
```

**Retry delays**: `base * (2 ^ attempt)`
- Attempt 1: 1s
- Attempt 2: 2s
- Attempt 3: 4s

## Testing

### Unit Tests

Test connector implementations in isolation:

```python
# backend/tests/unit/connectors/test_mock_connector.py
def test_mock_connector_success():
    connector = MockConnector()
    config = {"mode": "success"}

    result = connector.export(draft_order, config)

    assert result.success is True
```

### Integration Tests

Test with database and encryption:

```python
# backend/tests/integration/connectors/test_push_service.py
def test_push_order_with_mock_connector(db_session, test_org):
    # Create encrypted connection
    config = {"mode": "success"}
    encrypted = EncryptionService.encrypt_config(config)

    connection = ERPConnection(
        org_id=test_org.id,
        connector_type="MOCK",
        config_encrypted=encrypted,
        status="ACTIVE"
    )
    db_session.add(connection)
    db_session.commit()

    # Push order
    orchestrator = PushOrchestrator(db_session)
    result = orchestrator.push_order(test_org.id, draft_order)

    assert result.status == "SUCCESS"
```

## Troubleshooting

### Connector Not Found

```
ValueError: Unknown connector type: 'MY_ERP'
```

**Solution**: Ensure connector is registered at startup:
```python
ConnectorRegistry.register("MY_ERP", MyConnector)
```

### Decryption Failed

```
EncryptionError: authentication tag verification failed
```

**Causes**:
1. ENCRYPTION_MASTER_KEY changed after encryption
2. Database data corrupted
3. Wrong key being used

**Solution**: Check environment variable matches original encryption key.

### Idempotency Key Conflict

```
IntegrityError: duplicate key value violates unique constraint "idx_erp_push_log_idempotency"
```

**Cause**: Attempting to push same order with same attempt number twice.

**Solution**: This is expected behavior (idempotency working). Check existing push log to get result.

## SSOT References

- §3.5: ERPConnectorPort interface
- §5.4.14: erp_connection table schema
- §8.9: Connectors API specification
- §11.3: Encryption requirements
- T-602: Connector austauschbar requirement

## Performance Considerations

### Connector Resolution

ConnectorRegistry.get() is fast (< 10ms) - simple dictionary lookup.

### Encryption/Decryption

AES-GCM operations typically complete in < 5ms per operation.

### Connection Testing

Set reasonable timeouts in connector implementations:

```python
def test_connection(self, config):
    # Set 5-second timeout for external calls
    with timeout(5):
        # Test connection
        pass
```

## Future Enhancements

Planned for post-MVP:

1. **Multiple Connectors**: Support multiple active connectors per org with routing logic
2. **Connector Health Monitoring**: Track success rates, average latency, error patterns
3. **Connector SDK**: Template project for third-party connector development
4. **Async Push**: Queue-based push operations for better scalability
5. **Push Scheduling**: Delayed/scheduled push operations
6. **Rollback Support**: Connector interface for reversing pushed orders

## License

Internal OrderFlow project - proprietary.
