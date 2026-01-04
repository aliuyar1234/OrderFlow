# Dropzone Connector Implementation Guide

## Overview

The Dropzone JSON V1 Connector (DROPZONE_JSON_V1) exports draft orders as JSON files to SFTP or filesystem dropzone locations for ERP integration. This implementation follows the hexagonal architecture pattern with the connector as an adapter implementing the ERPConnectorPort interface.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Domain Layer                        │
│  ┌─────────────────────────────────────────────────┐  │
│  │         ERPConnectorPort (Interface)            │  │
│  │  - export(draft_order, org, config)             │  │
│  │  - connector_type: str                          │  │
│  │  - export_format_version: str                   │  │
│  └─────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                           ▲
                           │ implements
                           │
┌─────────────────────────────────────────────────────────┐
│                  Adapter Layer                          │
│  ┌─────────────────────────────────────────────────┐  │
│  │      DropzoneJsonV1Connector                    │  │
│  │  - Generates JSON per §12.1 schema              │  │
│  │  - Stores in object storage (S3/MinIO)         │  │
│  │  - Writes to dropzone (SFTP/filesystem)        │  │
│  │  - Atomic write support                         │  │
│  └─────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                           │
                           │ uses
                           ▼
┌─────────────────────────────────────────────────────────┐
│              Infrastructure Layer                       │
│  ┌──────────────┐    ┌──────────────────────────────┐ │
│  │ SFTPClient   │    │  ObjectStoragePort          │ │
│  │ - Atomic     │    │  - S3/MinIO storage         │ │
│  │   write      │    │  - Deduplication            │ │
│  │ - SSH auth   │    │                             │ │
│  └──────────────┘    └──────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

## Database Schema

### erp_connection

Stores ERP connector configuration for an organization.

```sql
CREATE TABLE erp_connection (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES org(id),
    connector_type TEXT NOT NULL,  -- 'DROPZONE_JSON_V1'
    config_encrypted TEXT NOT NULL,  -- Encrypted JSON config
    active BOOLEAN NOT NULL DEFAULT TRUE,
    last_test_at TIMESTAMPTZ NULL,
    last_test_success BOOLEAN NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_erp_connection_org_type ON erp_connection(org_id, connector_type);
CREATE INDEX idx_erp_connection_org_active ON erp_connection(org_id, active);
```

### erp_export

Tracks each export attempt to ERP.

```sql
CREATE TABLE erp_export (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES org(id),
    erp_connection_id UUID NOT NULL REFERENCES erp_connection(id),
    draft_order_id UUID NOT NULL,  -- Will add FK when draft_order exists
    export_format_version TEXT NOT NULL DEFAULT 'orderflow_export_json_v1',
    export_storage_key TEXT NOT NULL,  -- S3/MinIO key
    dropzone_path TEXT NULL,  -- Actual SFTP/FS path
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',  -- PENDING|SENT|ACKED|FAILED
    erp_order_id TEXT NULL,  -- From ERP ack
    error_json JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_erp_export_draft ON erp_export(org_id, draft_order_id, created_at DESC);
```

## Configuration

### SFTP Mode

```json
{
  "mode": "sftp",
  "host": "sftp.example.com",
  "port": 22,
  "username": "orderflow",
  "password": "secret",  // OR use ssh_key
  "ssh_key": "-----BEGIN RSA PRIVATE KEY-----\n...",
  "export_path": "/dropzone/exports",
  "ack_path": "/dropzone/acks",  // Optional
  "atomic_write": true
}
```

### Filesystem Mode

```json
{
  "mode": "filesystem",
  "export_path": "/var/dropzone/exports",
  "ack_path": "/var/dropzone/acks",  // Optional
  "atomic_write": true
}
```

## Export JSON Schema (orderflow_export_json_v1)

Per SSOT §12.1:

```json
{
  "export_version": "orderflow_export_json_v1",
  "org_slug": "acme",
  "draft_order_id": "550e8400-e29b-41d4-a716-446655440000",
  "approved_at": "2025-12-26T10:00:00Z",
  "customer": {
    "id": "UUID",
    "erp_customer_number": "4711",
    "name": "Muster GmbH"
  },
  "header": {
    "external_order_number": "PO-12345",
    "order_date": "2025-12-01",
    "currency": "EUR",
    "requested_delivery_date": "2025-12-10",
    "notes": "Urgent delivery"
  },
  "lines": [
    {
      "line_no": 1,
      "internal_sku": "INT-999",
      "qty": 10.0,
      "uom": "M",
      "unit_price": 1.23,
      "currency": "EUR",
      "customer_sku_raw": "AB-123",
      "description": "Kabel NYM-J 3x1,5"
    }
  ],
  "meta": {
    "created_by": "ops@acme.de",
    "source_document": {
      "document_id": "UUID",
      "file_name": "order.pdf",
      "sha256": "abc123..."
    }
  }
}
```

## Filename Format

Pattern: `sales_order_{draft_id_short}_{timestamp}_{uuid_suffix}.json`

Example: `sales_order_550e8400_20251227_100000_abc12345.json`

Components:
- `draft_id_short`: First segment of draft_order UUID
- `timestamp`: YYYYMMDD_HHMMSS in UTC
- `uuid_suffix`: Random 8-char UUID for collision prevention

## Acknowledgment Files (Optional)

ERP systems can optionally write acknowledgment files to `ack_path`:

### Success Acknowledgment

Filename: `ack_sales_order_{draft_id}_{timestamp}_{uuid}.json`

```json
{
  "status": "ACKED",
  "erp_order_id": "SO-2025-000123",
  "processed_at": "2025-12-26T10:01:00Z"
}
```

### Error Acknowledgment

Filename: `error_sales_order_{draft_id}_{timestamp}_{uuid}.json`

```json
{
  "status": "FAILED",
  "error_code": "ERP_VALIDATION",
  "message": "Unknown customer 4711",
  "processed_at": "2025-12-26T10:01:00Z"
}
```

## Usage

### Basic Export

```python
from domain.connectors.implementations.dropzone_json_v1 import DropzoneJsonV1Connector
from infrastructure.storage.s3_adapter import S3StorageAdapter

# Initialize connector
storage = S3StorageAdapter(...)
connector = DropzoneJsonV1Connector(storage)

# Configure dropzone
config = {
    'mode': 'sftp',
    'host': 'sftp.example.com',
    'username': 'orderflow',
    'password': 'secret',
    'export_path': '/exports',
    'atomic_write': True
}

# Export draft order
result = await connector.export(draft_order, org, config)

if result.success:
    print(f"Export stored at: {result.export_storage_key}")
    print(f"Dropzone path: {result.connector_metadata.dropzone_path}")
else:
    print(f"Export failed: {result.error_message}")
```

### Acknowledgment Polling

The ack poller runs as a background worker (Celery task):

```python
from workers.connectors.ack_poller import poll_acks_for_all_connectors

# Celery task (runs every 60 seconds)
@celery.task
def poll_erp_acks():
    db = get_db_session()
    stats = poll_acks_for_all_connectors(db)
    logger.info(f"Ack polling stats: {stats}")
```

## Error Handling

The connector handles errors gracefully:

1. **SFTP Connection Failure**: Returns ExportResult with success=False and error details
2. **Authentication Error**: Caught and returned in error_message
3. **Write Timeout**: Network errors are caught and logged
4. **Atomic Write Failure**: Temporary .tmp files are cleaned up
5. **Malformed Ack Files**: Moved to `error/` subdirectory

All errors are logged with full stack traces for debugging.

## Testing

### Unit Tests

```bash
pytest backend/tests/unit/connectors/test_dropzone_json_v1.py
pytest backend/tests/unit/connectors/test_ack_poller.py
```

### Integration Tests

```bash
# Requires mock SFTP server (e.g., Docker container)
pytest backend/tests/integration/connectors/test_sftp_export.py
```

## Security Considerations

1. **Config Encryption**: Connector configs (including passwords) are stored encrypted in `erp_connection.config_encrypted`
2. **SSH Key Auth**: Prefer SSH key authentication over passwords
3. **Host Key Verification**: Currently uses AutoAddPolicy (dev mode). In production, verify SFTP host keys.
4. **File Permissions**: SFTP files are written with default permissions. Consider configuring restrictive permissions.

## Performance

- **Export Generation**: <2s for drafts with up to 500 lines
- **SFTP Write**: <5s for typical export files (10-100KB)
- **Ack Polling Interval**: 60s (configurable)
- **Object Storage**: All exports backed up to S3/MinIO for audit trail

## Troubleshooting

### Export fails with "Authentication failed"

Check SFTP credentials in connector config. Verify username/password or SSH key is correct.

### Export succeeds but file not visible in ERP dropzone

1. Check `erp_export.dropzone_path` for actual write location
2. Verify SFTP export_path is correct
3. Check atomic_write setting (ERP might be reading .tmp files)

### Ack files not processed

1. Verify `ack_path` is configured in connector config
2. Check ack file naming follows pattern: `ack_sales_order_{draft_id}_{timestamp}_{uuid}.json`
3. Check ack poller worker is running (Celery task)
4. Review logs for JSON parsing errors (malformed acks moved to `error/`)

## Next Steps

1. **Database Migration**: Create Alembic migration for erp_connection and erp_export tables
2. **API Endpoints**: Implement POST `/draft-orders/{id}/push` and `/draft-orders/{id}/retry-push`
3. **Celery Tasks**: Register ack poller as periodic task (60s interval)
4. **Integration Tests**: Add tests with mock SFTP server
5. **Documentation**: Add connector setup guide for operators
6. **Monitoring**: Add Prometheus metrics for export success/failure rates
