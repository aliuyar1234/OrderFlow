# Data Model: ERP Connector Framework

**Date**: 2025-12-27

## Entity: ERPConnection

**Purpose**: Stores ERP connector configuration with encrypted credentials.

**Fields**:
- `id`: UUID PRIMARY KEY
- `org_id`: UUID NOT NULL REFERENCES organization
- `connector_type`: TEXT NOT NULL (e.g., 'DROPZONE_JSON_V1', 'SAP_RFC')
- `config_encrypted`: BYTEA NOT NULL (IV + ciphertext + auth tag)
- `status`: TEXT NOT NULL DEFAULT 'ACTIVE' (ACTIVE | DISABLED)
- `last_test_at`: TIMESTAMPTZ NULL (timestamp of last successful test)
- `created_at`: TIMESTAMPTZ DEFAULT NOW()
- `updated_at`: TIMESTAMPTZ DEFAULT NOW()

**Constraints**:
```sql
CREATE UNIQUE INDEX uq_active_connector ON erp_connection(org_id, connector_type)
WHERE status = 'ACTIVE';
```

**Indexes**:
```sql
CREATE INDEX idx_erp_connection_org ON erp_connection(org_id, status);
```

## config_encrypted Format

**Structure**: `IV (12 bytes) + Ciphertext (variable) + Auth Tag (16 bytes)`

**Plaintext JSON Example**:
```json
{
  "mode": "sftp",
  "host": "sftp.example.com",
  "port": 22,
  "username": "orderflow",
  "password": "secret123",
  "export_path": "/import/orders",
  "ack_path": "/import/acks",
  "atomic_write": true
}
```

**After Encryption**: Binary blob (IV + AES-GCM encrypted JSON + tag)

## SQLAlchemy Model

```python
from sqlalchemy import Column, String, LargeBinary, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.sql import func

class ERPConnection(Base):
    __tablename__ = "erp_connection"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    org_id = Column(UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False)
    connector_type = Column(String, nullable=False)
    config_encrypted = Column(LargeBinary, nullable=False)
    status = Column(String, nullable=False, server_default="ACTIVE")
    last_test_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("uq_active_connector", "org_id", "connector_type", unique=True, postgresql_where=(status == 'ACTIVE')),
        Index("idx_erp_connection_org", "org_id", "status"),
    )
```

## ERPConnectorPort Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ExportResult:
    success: bool
    export_id: str | None
    error_message: str | None
    storage_key: str | None
    dropzone_path: str | None

@dataclass
class TestResult:
    success: bool
    error_message: str | None
    latency_ms: int

class ERPConnectorPort(ABC):
    @abstractmethod
    def export(self, draft_order: DraftOrder, config: dict) -> ExportResult:
        """Export draft order to ERP system."""
        pass

    @abstractmethod
    def test_connection(self, config: dict) -> TestResult:
        """Test connection without exporting."""
        pass
```

## ConnectorRegistry

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
```
