# Integration Note: Existing Connector Framework

## Discovery

During implementation of the Dropzone connector, we discovered that OrderFlow already has an established ERP connector framework at `backend/src/connectors/`. This framework includes:

1. **ERPConnectorPort** interface (`connectors/ports.py`)
2. **BaseConnector** base class (`connectors/base_connector.py`)
3. **ConnectorRegistry** for managing implementations (`connectors/registry.py`)
4. **Push Service** for orchestrating exports (`connectors/push_service.py`)
5. **Encryption utilities** for config storage (`connectors/encryption.py`)

## Implementation Created

We created a parallel implementation at `backend/src/domain/connectors/` with:

1. Our own ERPConnectorPort interface (slightly different structure)
2. DropzoneJsonV1Connector implementation
3. SFTP client infrastructure
4. Ack poller worker
5. Database models (ERPConnection, ERPExport)

## Differences Between Implementations

### Existing Framework (connectors/ports.py)

```python
@dataclass
class ExportResult:
    success: bool
    export_id: UUID  # ← Includes export_id
    error_message: Optional[str] = None
    storage_key: Optional[str] = None
    connector_metadata: dict[str, Any] = None

class ERPConnectorPort(ABC):
    def export(self, draft_order: Any, config: dict) -> ExportResult:
        # Takes only draft_order and config
        pass

    def test_connection(self, config: dict) -> TestResult:
        # Includes connection testing
        pass

    def get_connector_type(self) -> str:
        pass
```

### Our Implementation (domain/connectors/ports/erp_connector_port.py)

```python
@dataclass
class ExportResult:
    success: bool
    export_storage_key: str  # ← Different field name
    connector_metadata: ConnectorMetadata  # ← Typed metadata
    error_message: Optional[str] = None
    error_details: Optional[dict] = None

class ERPConnectorPort(ABC):
    async def export(self, draft_order: Any, org: Any, config: dict) -> ExportResult:
        # Async method, takes org parameter
        pass

    @property
    @abstractmethod
    def connector_type(self) -> str:  # ← Property instead of method
        pass

    @property
    @abstractmethod
    def export_format_version(self) -> str:  # ← Additional property
        pass
```

## Recommendation: Consolidate

**Option 1: Adapt Our Code to Existing Framework (Recommended)**

1. **Migrate DropzoneJsonV1Connector** to use existing `connectors/ports.py` interface
2. **Keep SFTP client** as infrastructure (already good)
3. **Keep database models** (ERPConnection, ERPExport) as-is
4. **Keep ack poller** worker as-is
5. **Delete** `domain/connectors/` duplicate implementation
6. **Register** DropzoneJsonV1Connector in existing ConnectorRegistry

Benefits:
- Leverage existing push_service.py orchestration
- Leverage existing config encryption utilities
- Consistent with codebase architecture
- No duplicate port interfaces

**Option 2: Use Our Implementation**

1. **Delete** existing `connectors/` framework
2. **Migrate** any existing connector implementations to our interface
3. Update PushService to use our port interface

This is riskier if other code depends on the existing framework.

## Migration Steps (Option 1)

### Step 1: Update DropzoneJsonV1Connector

File: `backend/src/connectors/implementations/dropzone_json_v1.py` (NEW location)

```python
from connectors.ports import ERPConnectorPort, ExportResult, TestResult, ConnectorError
from connectors.base_connector import BaseConnector
from infrastructure.sftp import SFTPClient, SFTPConfig

class DropzoneJsonV1Connector(BaseConnector):
    """Dropzone JSON V1 connector implementation."""

    def __init__(self, storage_port):
        self.storage = storage_port

    def export(self, draft_order, config: dict) -> ExportResult:
        """Export draft order to JSON dropzone."""
        try:
            # Validate config
            self.validate_required_fields(config, ['mode', 'export_path'])

            # Generate JSON (same logic)
            export_data = self._generate_export_json(draft_order)
            export_json = json.dumps(export_data, indent=2)

            # Store in object storage
            filename = self._generate_filename(draft_order)
            storage_key = f"exports/{draft_order.org_id}/{filename}"

            # ... rest of implementation ...

            return ExportResult(
                success=True,
                export_id=export_record.id,  # ← Created by caller
                storage_key=storage_key,
                connector_metadata={
                    'dropzone_path': dropzone_path,
                    'filename': filename
                }
            )
        except Exception as e:
            raise ConnectorError(f"Export failed: {e}")

    def test_connection(self, config: dict) -> TestResult:
        """Test SFTP/filesystem connection."""
        start = time.time()
        try:
            mode = config.get('mode')
            if mode == 'sftp':
                # Test SFTP connection
                sftp_config = SFTPConfig(...)
                with SFTPClient(sftp_config) as client:
                    # Write and delete test file
                    client.write_file('test.txt', 'test')
                    client.delete_file(f"{config['export_path']}/test.txt")

            latency_ms = int((time.time() - start) * 1000)
            return TestResult(success=True, latency_ms=latency_ms)

        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            return TestResult(
                success=False,
                error_message=str(e),
                latency_ms=latency_ms
            )

    def get_connector_type(self) -> str:
        return "DROPZONE_JSON_V1"
```

### Step 2: Register in ConnectorRegistry

File: `backend/src/connectors/registry.py`

```python
from connectors.implementations.dropzone_json_v1 import DropzoneJsonV1Connector

registry = ConnectorRegistry()
registry.register("DROPZONE_JSON_V1", DropzoneJsonV1Connector)
```

### Step 3: Use Existing Push Service

The existing `connectors/push_service.py` already handles:
- Creating ERPExport records
- Calling connector.export()
- Updating status (PENDING → SENT/FAILED)
- Error handling and logging

No need to reimplement this logic.

### Step 4: Cleanup

Delete duplicate files:
- `backend/src/domain/connectors/ports/erp_connector_port.py`
- `backend/src/domain/connectors/implementations/dropzone_json_v1.py`
- `backend/src/domain/connectors/` (entire directory)

## Files to Keep

✅ **Keep (Core Implementation)**:
- `backend/src/infrastructure/sftp/client.py` - SFTP client
- `backend/src/models/erp_connection.py` - Database model
- `backend/src/models/erp_export.py` - Database model
- `backend/src/workers/connectors/ack_poller.py` - Ack poller
- `backend/tests/unit/connectors/test_ack_poller.py` - Tests

✅ **Keep (Move to connectors/implementations/)**:
- Core logic from `domain/connectors/implementations/dropzone_json_v1.py`
  → Migrate to `connectors/implementations/dropzone_json_v1.py`

❌ **Delete (Duplicate)**:
- `backend/src/domain/connectors/ports/erp_connector_port.py` (use existing)
- `backend/src/domain/connectors/` directory

## Updated Test Structure

Update tests to use existing port interface:

```python
from connectors.ports import ERPConnectorPort, ExportResult
from connectors.implementations.dropzone_json_v1 import DropzoneJsonV1Connector

def test_export_generates_json(mock_storage):
    connector = DropzoneJsonV1Connector(mock_storage)
    result = connector.export(draft_order, config)

    assert result.success
    assert result.export_id is not None  # ← Updated assertion
    assert result.storage_key.startswith('exports/')
```

## Summary

The existing connector framework at `backend/src/connectors/` is well-designed and should be used. Our implementation created valuable components (SFTP client, ack poller, database models) but duplicated the port interface unnecessarily.

**Next Action**: Migrate DropzoneJsonV1Connector to use existing ERPConnectorPort interface and delete duplicate port definition.
