# Feature Specification: Dropzone JSON Connector (DROPZONE_JSON_V1)

**Feature Branch**: `022-dropzone-connector`
**Created**: 2025-12-27
**Status**: Draft
**Module**: connectors
**SSOT References**: §5.4.15 (erp_export), §5.2.9 (ERPExportStatus), §10.3 (Dropzone Config), §12 (DROPZONE_JSON_V1), T-603, T-604, T-606

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate Export JSON (Priority: P1)

When a draft order is pushed to ERP, the system must generate a JSON file following the exact `orderflow_export_json_v1` schema, containing all required order data for ERP import.

**Why this priority**: Export JSON generation is the core of the Dropzone connector. Without it, no data reaches ERP. The JSON schema is the contract between OrderFlow and ERP systems.

**Independent Test**: Can be fully tested by pushing a draft order, retrieving the generated JSON file, and validating it against the schema (snapshot test).

**Acceptance Scenarios**:

1. **Given** an APPROVED draft order with customer, header data, and 3 lines, **When** export is generated, **Then** JSON contains `export_version="orderflow_export_json_v1"`, customer block, header block, and 3 line objects
2. **Given** draft has `external_order_number="PO-12345"`, **When** export is generated, **Then** JSON header contains `"external_order_number": "PO-12345"`
3. **Given** draft line has `customer_sku_raw=null`, **When** export is generated, **Then** JSON line contains `"customer_sku_raw": null` (not omitted)
4. **Given** draft has `notes="Urgent delivery"`, **When** export is generated, **Then** JSON header contains `"notes": "Urgent delivery"`
5. **Given** draft has source document with sha256 hash, **When** export is generated, **Then** JSON meta contains `"source_document": {"document_id": "...", "file_name": "...", "sha256": "..."}`

---

### User Story 2 - Write Export to Dropzone (SFTP/Filesystem) (Priority: P1)

The connector must write the export JSON file to the configured dropzone location (SFTP server or local filesystem) with atomic rename to prevent partial reads.

**Why this priority**: Reliable file delivery is critical. Partial writes or corrupted files cause ERP import failures. Atomic rename ensures ERP only sees complete files.

**Independent Test**: Can be fully tested by configuring SFTP dropzone, pushing a draft, and verifying that file appears in SFTP directory with correct filename and atomic rename behavior.

**Acceptance Scenarios**:

1. **Given** dropzone configured with SFTP mode, **When** export is written, **Then** file is written as `.tmp` suffix first, then renamed to final name
2. **Given** dropzone configured with filesystem mode, **When** export is written, **Then** file is written to local path with atomic rename
3. **Given** export for draft_order_id `abc-123` at timestamp `20251227T100000Z`, **When** file is written, **Then** filename is `sales_order_abc-123_20251227T100000Z.json`
4. **Given** SFTP connection drops mid-write, **When** export is attempted, **Then** `.tmp` file is left behind, error is logged, and `erp_export.status=FAILED`
5. **Given** dropzone path has no write permissions, **When** export is attempted, **Then** error is raised and `erp_export.status=FAILED` with error_json containing "Permission denied"

---

### User Story 3 - Store Export Metadata (Priority: P1)

Each export must be recorded in the `erp_export` table with status tracking, storage keys, and error information for debugging and retry logic.

**Why this priority**: Export metadata enables status tracking, retry, audit trail, and debugging. Without it, operators have no visibility into export failures or history.

**Independent Test**: Can be fully tested by pushing a draft, querying `erp_export` table, and verifying that record contains correct draft_order_id, status, storage_key, and timestamps.

**Acceptance Scenarios**:

1. **Given** export succeeds, **When** querying erp_export, **Then** record has `status=SENT`, `export_storage_key=<S3-key>`, `dropzone_path=<SFTP-path>`, `error_json=null`
2. **Given** export fails due to network error, **When** querying erp_export, **Then** record has `status=FAILED`, `error_json={"error": "Connection timeout", "timestamp": "..."}`
3. **Given** export is created, **When** ERP ack is received later, **Then** record is updated with `status=ACKED`, `erp_order_id="SO-2025-000123"`, `updated_at` changes
4. **Given** export is retried after failure, **When** new export is created, **Then** new `erp_export` record is created (not updated), and draft_order links to latest export
5. **Given** export JSON is generated, **When** stored to object storage, **Then** `export_storage_key` contains S3/MinIO key for later retrieval

---

### User Story 4 - Poll for ERP Acknowledgment (Optional) (Priority: P3)

If configured, a background worker polls the `ack_path` directory for acknowledgment files written by ERP, updating export status to ACKED or FAILED based on ERP response.

**Why this priority**: Ack polling enables bidirectional communication with ERP, providing confirmation that ERP successfully imported the order. However, many ERPs don't support acks, making this optional and lower priority.

**Independent Test**: Can be fully tested by writing a mock ack JSON file to ack_path, triggering poller, and verifying that erp_export status is updated to ACKED.

**Acceptance Scenarios**:

1. **Given** ERP writes `ack_sales_order_abc-123_20251227T100000Z.json` with `"status": "ACKED"` and `"erp_order_id": "SO-123"`, **When** poller runs, **Then** erp_export status changes to ACKED and `erp_order_id="SO-123"`
2. **Given** ERP writes `error_sales_order_abc-123_20251227T100000Z.json` with `"status": "FAILED"` and error message, **When** poller runs, **Then** erp_export status changes to FAILED and `error_json` contains ERP error
3. **Given** ack_path is not configured (NULL), **When** poller runs, **Then** poller skips this connector (no-op)
4. **Given** ack file is malformed JSON, **When** poller reads it, **Then** error is logged, ack file is moved to error folder, and export status remains SENT
5. **Given** ack file appears 5 minutes after export, **When** poller runs (60s interval), **Then** ack is processed within next poll cycle (< 60s delay)

---

### User Story 5 - Retry Failed Exports (Priority: P2)

Operators must be able to retry failed exports (e.g., after fixing network issues or credentials) without re-approving the draft.

**Why this priority**: Retry capability reduces manual work and prevents order loss during transient failures. However, initial export (P1) must work first before retry logic is valuable.

**Independent Test**: Can be fully tested by creating a failed export, calling POST `/draft-orders/{id}/retry-push`, and verifying that a new export is created with status SENT.

**Acceptance Scenarios**:

1. **Given** draft has `erp_export` with `status=FAILED`, **When** POST `/draft-orders/{id}/retry-push`, **Then** new `erp_export` record is created with status PENDING
2. **Given** draft has `erp_export` with `status=SENT` (not failed), **When** POST retry, **Then** API returns 409 Conflict "Export already succeeded"
3. **Given** retry is triggered, **When** export worker processes job, **Then** export JSON is regenerated and written to dropzone
4. **Given** retry fails again, **When** querying erp_export, **Then** latest export has status FAILED and error_json contains new error
5. **Given** retry succeeds, **When** querying draft_order, **Then** `draft_order.status=PUSHED` and latest export has status SENT

---

### Edge Cases

- What happens if filename already exists in dropzone (collision)? (Atomic rename will overwrite; filename includes timestamp to minimize collisions)
- How does system handle very large export JSON (10MB+)? (Object storage supports large files; SFTP transfer may timeout; configurable timeout needed)
- What if ack file is written before export completes (race condition)? (Poller checks export status; only processes acks for SENT exports)
- What if dropzone path is changed after exports exist? (Old exports remain in old path; new exports go to new path; dropzone_path stored per export)
- What happens when SFTP host key changes (security)? (Connection fails; admin must update host key in connector config)
- How does system handle clock skew between OrderFlow and ERP? (Timestamps are ISO 8601 UTC; clock skew affects ack matching but not data integrity)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST implement `DropzoneJsonV1Connector` class implementing `ERPConnectorPort` interface
- **FR-002**: System MUST generate export JSON exactly per §12.1 schema (`orderflow_export_json_v1`)
- **FR-003**: System MUST include all required fields: `export_version`, `org_slug`, `draft_order_id`, `approved_at`, `customer`, `header`, `lines`, `meta`
- **FR-004**: System MUST generate filename as `sales_order_<draft_order_id>_<timestamp>_<uuid4_short>.json` where timestamp is `YYYYMMDDTHHMMSSZ` and uuid4_short is first 8 chars of UUID
- **FR-005**: System MUST write export JSON to object storage (S3/MinIO) with key pattern `exports/<org_id>/<filename>`
- **FR-006**: System MUST write export JSON to dropzone (SFTP or filesystem) based on connector config
- **FR-007**: System MUST use atomic write: write to `.tmp` suffix, then rename to final name (if `atomic_write=true` in config)
- **FR-008**: System MUST create `erp_export` record with fields: draft_order_id, erp_connection_id, export_format_version, export_storage_key, dropzone_path, status
- **FR-009**: System MUST set `erp_export.status=PENDING` on creation, `SENT` on success, `FAILED` on error
- **FR-010**: System MUST store error details in `erp_export.error_json` on failure (error message, timestamp, stack trace)
- **FR-011**: System MUST support SFTP mode with config: `host`, `port`, `username`, `password` (or `ssh_key`), `export_path`
- **FR-012**: System MUST support filesystem mode with config: `export_path` (local directory)
- **FR-013**: System MUST validate export JSON against schema before writing (fail fast on schema violations)
- **FR-014**: System MUST implement background worker to poll `ack_path` if configured (interval: 60s default, configurable)
- **FR-015**: System MUST parse ack files matching pattern `ack_<export_filename>.json` or `error_<export_filename>.json`
- **FR-016**: System MUST update `erp_export.status=ACKED` when ack file contains `"status": "ACKED"`
- **FR-017**: System MUST update `erp_export.status=FAILED` when ack file contains `"status": "FAILED"`
- **FR-018**: System MUST extract `erp_order_id` from ack file and store in `erp_export.erp_order_id`
- **FR-019**: System MUST move processed ack files to `processed/` subdirectory after reading
- **FR-020**: System MUST expose API: POST `/draft-orders/{id}/retry-push` to retry failed exports
- **FR-021**: Filename collision handling: (1) Generate filename with timestamp, draft_id, and uuid4_short suffix, (2) UUID suffix guarantees uniqueness, (3) If write fails with 'file exists' error, retry once with new UUID, (4) On second failure, return error to caller. Timestamp format: YYYYMMDD_HHMMSS

### Key Entities *(include if feature involves data)*

- **ERPExport** (§5.4.15): Represents a single export attempt of a draft order to ERP. Tracks status (PENDING, SENT, ACKED, FAILED), storage location, dropzone path, ERP order ID, and error details.

- **DropzoneJsonV1Connector**: Concrete implementation of ERPConnectorPort for JSON dropzone export. Handles JSON generation, SFTP/filesystem write, atomic rename, and error handling.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Export JSON matches §12.1 schema in 100% of snapshot tests
- **SC-002**: Atomic rename prevents partial file reads in 100% of integration tests with SFTP
- **SC-003**: Export metadata (erp_export record) is created in 100% of export attempts
- **SC-004**: Ack poller correctly updates status to ACKED/FAILED in 100% of test cases
- **SC-005**: Export generation completes within 2 seconds for drafts with up to 500 lines
- **SC-006**: SFTP write handles network failures gracefully (no data loss) in 100% of failure scenarios
- **SC-007**: Retry logic creates new export record and succeeds after transient failure in 100% of retry tests

## Dependencies

- **Depends on**:
  - **021-erp-connector-framework**: Requires ERPConnectorPort interface and ConnectorRegistry
  - **001-database-setup**: Requires `erp_export` table (§5.4.15)
  - **010-draft-orders**: Requires draft_order entity with approved_at, customer_id, lines
  - **003-object-storage**: Requires S3/MinIO for export file storage

- **Enables**:
  - **023-approve-push-flow**: Provides export implementation for push endpoint

## Implementation Notes

### ExportResult Alignment

DropzoneConnector returns standard ExportResult per 021-erp-connector-framework. dropzone_path stored in connector_metadata.dropzone_path. Maintain backward compatibility with existing consumers.

### Filename Collision Handling

Generate filename as `sales_order_{draft_id}_{timestamp}_{uuid4_short}.json`:
1. Timestamp format: YYYYMMDD_HHMMSS
2. UUID suffix (first 8 chars of uuid4()) guarantees uniqueness
3. If write fails with 'file exists' error, retry once with new UUID
4. On second failure, return error to caller

### Export JSON Generation

```python
def generate_export_json(draft_order: DraftOrder) -> dict:
    """Generate export JSON per §12.1 schema."""
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    return {
        "export_version": "orderflow_export_json_v1",
        "org_slug": draft_order.org.slug,
        "draft_order_id": str(draft_order.id),
        "approved_at": draft_order.approved_at.isoformat(),
        "customer": {
            "id": str(draft_order.customer.id),
            "erp_customer_number": draft_order.customer.erp_customer_number,
            "name": draft_order.customer.name
        },
        "header": {
            "external_order_number": draft_order.external_order_number,
            "order_date": draft_order.order_date.isoformat() if draft_order.order_date else None,
            "currency": draft_order.currency,
            "requested_delivery_date": draft_order.requested_delivery_date.isoformat() if draft_order.requested_delivery_date else None,
            "notes": draft_order.notes
        },
        "lines": [
            {
                "line_no": line.line_no,
                "internal_sku": line.internal_sku,
                "qty": float(line.qty),
                "uom": line.uom,
                "unit_price": float(line.unit_price) if line.unit_price else None,
                "currency": draft_order.currency,
                "customer_sku_raw": line.customer_sku_raw,
                "description": line.product_description
            }
            for line in draft_order.lines
        ],
        "meta": {
            "created_by": draft_order.approved_by_user.email,
            "source_document": {
                "document_id": str(draft_order.document.id) if draft_order.document else None,
                "file_name": draft_order.document.file_name if draft_order.document else None,
                "sha256": draft_order.document.sha256 if draft_order.document else None
            } if draft_order.document else None
        }
    }
```

### SFTP Write with Atomic Rename

```python
import paramiko

def write_to_sftp(config: dict, filename: str, content: str):
    """Write export JSON to SFTP with atomic rename."""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        hostname=config['host'],
        port=config.get('port', 22),
        username=config['username'],
        password=config.get('password')
    )

    sftp = ssh.open_sftp()
    export_path = config['export_path']
    tmp_path = f"{export_path}/{filename}.tmp"
    final_path = f"{export_path}/{filename}"

    try:
        # Write to .tmp file
        with sftp.open(tmp_path, 'w') as f:
            f.write(content)

        # Atomic rename
        sftp.rename(tmp_path, final_path)

    finally:
        sftp.close()
        ssh.close()
```

### Ack Poller Background Worker

```python
import time
import json
from pathlib import Path

def poll_acks_loop():
    """Background worker to poll ack files."""
    while True:
        connectors = get_active_connectors_with_ack_path()

        for connector in connectors:
            config = decrypt_config(connector.config_encrypted)
            ack_path = config.get('ack_path')

            if not ack_path:
                continue

            # List ack files
            ack_files = list_ack_files(ack_path, mode=config['mode'])

            for ack_file in ack_files:
                process_ack_file(ack_file, connector)

        time.sleep(60)  # Poll every 60 seconds

def process_ack_file(ack_file: str, connector):
    """Process a single ack file."""
    content = read_file(ack_file)
    ack_data = json.loads(content)

    # Extract draft_order_id from filename
    # ack_sales_order_abc-123_20251227T100000Z.json → abc-123
    filename = Path(ack_file).name
    draft_order_id = extract_draft_order_id(filename)

    # Find corresponding export
    export = get_latest_export(draft_order_id, connector.id)

    if ack_data['status'] == 'ACKED':
        export.status = ERPExportStatus.ACKED
        export.erp_order_id = ack_data.get('erp_order_id')
    elif ack_data['status'] == 'FAILED':
        export.status = ERPExportStatus.FAILED
        export.error_json = {
            "error_code": ack_data.get('error_code'),
            "message": ack_data.get('message'),
            "processed_at": ack_data.get('processed_at')
        }

    export.updated_at = datetime.utcnow()
    db.session.commit()

    # Move ack file to processed/
    move_file(ack_file, f"{connector.ack_path}/processed/{Path(ack_file).name}")
```

### Database Schema for ERPExport

```sql
CREATE TABLE erp_export (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organization(id),
    erp_connection_id UUID NOT NULL REFERENCES erp_connection(id),
    draft_order_id UUID NOT NULL REFERENCES draft_order(id),
    export_format_version TEXT NOT NULL DEFAULT 'orderflow_export_json_v1',
    export_storage_key TEXT NOT NULL,  -- S3/MinIO key
    dropzone_path TEXT NULL,  -- Actual SFTP/FS path written
    status TEXT NOT NULL DEFAULT 'PENDING',  -- PENDING | SENT | ACKED | FAILED
    erp_order_id TEXT NULL,  -- ERP's order ID from ack
    error_json JSONB NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT fk_erp_connection FOREIGN KEY (erp_connection_id) REFERENCES erp_connection(id),
    CONSTRAINT fk_draft_order FOREIGN KEY (draft_order_id) REFERENCES draft_order(id)
);

CREATE INDEX idx_erp_export_draft ON erp_export(org_id, draft_order_id, created_at DESC);
```

## Testing Strategy

### Unit Tests
- Export JSON generation with various draft configurations (nulls, multi-line, etc.)
- Filename generation with timestamp formatting
- Ack file parsing (success and error formats)
- Draft order ID extraction from filenames

### Component Tests
- DropzoneJsonV1Connector.export() with mock SFTP client
- Atomic rename behavior (write .tmp → rename)
- Error handling: SFTP connection failure, write permission denied
- Ack poller with mock ack files

### Integration Tests
- End-to-end export: draft → export → JSON in object storage → JSON in SFTP dropzone
- Ack polling: write ack file → poller runs → erp_export status updated
- Retry: failed export → retry → new export created
- Snapshot test: export JSON matches §12.1 schema exactly

### E2E Tests
- Full push workflow: Approve draft → Push → Export appears in dropzone → Ack received → Status shows ACKED
- Failure scenario: SFTP unreachable → Export fails → Operator retries → Export succeeds

## SSOT Compliance Checklist

- [ ] Export JSON schema matches §12.1 exactly (orderflow_export_json_v1)
- [ ] Filename format matches §12.1: `sales_order_<id>_<timestamp>.json`
- [ ] Atomic write uses .tmp suffix then rename (§12.1)
- [ ] `erp_export` table schema matches §5.4.15
- [ ] ERPExportStatus enum matches §5.2.9 (PENDING, SENT, ACKED, FAILED)
- [ ] Ack file format matches §12.2 (ack_<filename>.json, error_<filename>.json)
- [ ] Ack poller interval is 60s (configurable) per §12.2
- [ ] Connector config stored encrypted per §11.3
- [ ] T-603 acceptance criteria met (JSON contains all required fields, snapshot test passes)
- [ ] T-604 acceptance criteria met (atomic rename on network failure, SFTP integration test passes)
- [ ] T-606 acceptance criteria met (ack file → status ACKED, integration test with mock ack)
