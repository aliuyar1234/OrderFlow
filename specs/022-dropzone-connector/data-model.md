# Data Model: Dropzone JSON Connector

**Date**: 2025-12-27

## Entity: ERPExport

**Purpose**: Tracks export attempts of draft orders to ERP.

**Fields**:
- `id`: UUID PRIMARY KEY
- `org_id`: UUID NOT NULL REFERENCES organization
- `erp_connection_id`: UUID NOT NULL REFERENCES erp_connection
- `draft_order_id`: UUID NOT NULL REFERENCES draft_order
- `export_format_version`: TEXT NOT NULL DEFAULT 'orderflow_export_json_v1'
- `export_storage_key`: TEXT NOT NULL (S3/MinIO key)
- `dropzone_path`: TEXT NULL (actual SFTP/filesystem path written)
- `status`: TEXT NOT NULL DEFAULT 'PENDING' (PENDING | SENT | ACKED | FAILED)
- `erp_order_id`: TEXT NULL (ERP's order ID from ack file)
- `error_json`: JSONB NULL (error details if FAILED)
- `created_at`: TIMESTAMPTZ DEFAULT NOW()
- `updated_at`: TIMESTAMPTZ DEFAULT NOW()

**Indexes**:
```sql
CREATE INDEX idx_erp_export_draft ON erp_export(org_id, draft_order_id, created_at DESC);
CREATE INDEX idx_erp_export_status ON erp_export(org_id, status, created_at DESC);
```

## Export JSON Schema (orderflow_export_json_v1)

**Top-Level Structure**:
```json
{
  "export_version": "orderflow_export_json_v1",
  "org_slug": "acme-corp",
  "draft_order_id": "uuid",
  "approved_at": "2025-12-27T10:00:00Z",
  "customer": {
    "id": "uuid",
    "erp_customer_number": "CUST-4711",
    "name": "Muster GmbH"
  },
  "header": {
    "external_order_number": "PO-12345",
    "order_date": "2025-12-25",
    "currency": "EUR",
    "requested_delivery_date": "2025-12-30",
    "notes": "Urgent delivery"
  },
  "lines": [
    {
      "line_no": 1,
      "internal_sku": "SKU-ABC",
      "qty": 100.0,
      "uom": "PCE",
      "unit_price": 10.50,
      "currency": "EUR",
      "customer_sku_raw": "CUST-SKU-001",
      "description": "Product ABC"
    }
  ],
  "meta": {
    "created_by": "operator@acme.com",
    "source_document": {
      "document_id": "uuid",
      "file_name": "order.pdf",
      "sha256": "abc123..."
    }
  }
}
```

## Ack File Schema

**Success Ack** (`ack_sales_order_<id>_<timestamp>.json`):
```json
{
  "status": "ACKED",
  "erp_order_id": "SO-2025-000123",
  "processed_at": "2025-12-27T10:10:00Z"
}
```

**Error Ack** (`error_sales_order_<id>_<timestamp>.json`):
```json
{
  "status": "FAILED",
  "error_code": "INVALID_CUSTOMER",
  "message": "Customer 4711 not found",
  "processed_at": "2025-12-27T10:10:00Z"
}
```

## SQLAlchemy Model

```python
class ERPExport(Base):
    __tablename__ = "erp_export"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    org_id = Column(UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False)
    erp_connection_id = Column(UUID(as_uuid=True), ForeignKey("erp_connection.id"), nullable=False)
    draft_order_id = Column(UUID(as_uuid=True), ForeignKey("draft_order.id"), nullable=False)
    export_format_version = Column(String, nullable=False, server_default="orderflow_export_json_v1")
    export_storage_key = Column(String, nullable=False)
    dropzone_path = Column(String, nullable=True)
    status = Column(String, nullable=False, server_default="PENDING")
    erp_order_id = Column(String, nullable=True)
    error_json = Column(JSONB, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('PENDING', 'SENT', 'ACKED', 'FAILED')", name="ck_export_status"),
        Index("idx_erp_export_draft", "org_id", "draft_order_id", created_at.desc()),
    )
```
