# Research: Dropzone JSON Connector

**Date**: 2025-12-27

## Key Decisions

### Decision 1: Atomic Write with .tmp Suffix
**Selected**: Write to `<filename>.tmp`, then rename to `<filename>`

**Rationale**:
- Prevents ERP from reading partial files
- SFTP rename is atomic on most SFTP servers
- Standard pattern for reliable file delivery

**Implementation**:
```python
# Write to .tmp
sftp.open(f"{path}.tmp", 'w').write(content)

# Atomic rename
sftp.rename(f"{path}.tmp", path)
```

### Decision 2: Filename Pattern
**Selected**: `sales_order_<draft_order_id>_<timestamp>.json` where timestamp is `YYYYMMDDTHHMMSSZ`

**Rationale**:
- Sortable by timestamp
- Includes draft_order_id for correlation
- Minimizes collisions (timestamp precision to second)

**Example**: `sales_order_abc-123_20251227T100530Z.json`

### Decision 3: Ack File Matching Pattern
**Selected**: `ack_<export_filename>.json` or `error_<export_filename>.json`

**Rationale**:
- Clear mapping to original export file
- Prefix indicates success (ack_) or failure (error_)
- JSON format allows structured response (erp_order_id, error details)

**Example Ack**:
```json
{
  "status": "ACKED",
  "erp_order_id": "SO-2025-000123",
  "processed_at": "2025-12-27T10:10:00Z"
}
```

**Example Error**:
```json
{
  "status": "FAILED",
  "error_code": "INVALID_CUSTOMER",
  "message": "Customer 4711 not found in ERP",
  "processed_at": "2025-12-27T10:10:00Z"
}
```

### Decision 4: Export Metadata Storage
**Selected**: Store export JSON in object storage (S3) + metadata in erp_export table

**Rationale**:
- Object storage is cheap, scalable, durable
- Database stores metadata (status, timestamps, dropzone_path) for queries
- Export files can be retrieved for debugging/audit

**S3 Key Pattern**: `exports/<org_id>/<filename>`

## Best Practices

### JSON Schema Validation
```python
from pydantic import BaseModel

class ExportLineSchema(BaseModel):
    line_no: int
    internal_sku: str
    qty: float
    uom: str
    unit_price: float | None
    currency: str
    customer_sku_raw: str | None
    description: str | None

class ExportSchema(BaseModel):
    export_version: str = "orderflow_export_json_v1"
    org_slug: str
    draft_order_id: str
    approved_at: str
    customer: dict
    header: dict
    lines: list[ExportLineSchema]
    meta: dict

# Validate before export
export_data = ExportSchema(**generate_export_dict(draft_order))
```

### SFTP Error Handling
```python
import paramiko

try:
    ssh.connect(host=config['host'], port=config['port'], username=config['username'], password=config['password'])
    sftp = ssh.open_sftp()
    sftp.put(local_path, remote_path)
except paramiko.AuthenticationException:
    return ExportResult(success=False, error_message="Authentication failed")
except paramiko.SSHException as e:
    return ExportResult(success=False, error_message=f"SSH error: {e}")
except IOError as e:
    return ExportResult(success=False, error_message=f"File error: {e}")
```

## References
- SSOT §12.1: orderflow_export_json_v1 schema
- SSOT §12.2: Ack file format
- SSOT §5.4.15: erp_export table schema
