# Data Model: SMTP Ingest

**Feature**: 006-smtp-ingest | **Date**: 2025-12-27

## Entity Definitions

### InboundMessage

**Properties**:
- `id` (UUID): Primary key
- `org_id` (UUID): Organization (multi-tenant)
- `source` (TEXT): "EMAIL" or "UPLOAD"
- `source_message_id` (TEXT): Email Message-ID or upload correlation ID
- `from_email` (CITEXT): Sender email
- `to_email` (CITEXT): Recipient email
- `subject` (TEXT): Email subject
- `received_at` (TIMESTAMPTZ): When email was received
- `raw_storage_key` (TEXT): S3 key for raw MIME
- `status` (TEXT): InboundMessageStatus enum
- `error_json` (JSONB): Error details if processing failed
- `created_at` (TIMESTAMPTZ): Record creation
- `updated_at` (TIMESTAMPTZ): Last update

**Relationships**:
- `org_id` → `org.id`
- One-to-many with `document` (email can have multiple attachments)

**Constraints**:
- `UNIQUE (org_id, source, source_message_id)` WHERE source_message_id IS NOT NULL
- `status` CHECK IN ('RECEIVED', 'STORED', 'PARSED', 'FAILED')

## SQLAlchemy Model

```python
from sqlalchemy import Column, String, TIMESTAMP, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB, CITEXT
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

class InboundMessage(Base):
    __tablename__ = 'inbound_message'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey('org.id'), nullable=False, index=True)

    source = Column(String, nullable=False, index=True)
    source_message_id = Column(String, nullable=True)
    from_email = Column(CITEXT, nullable=True)
    to_email = Column(CITEXT, nullable=True)
    subject = Column(String, nullable=True)

    received_at = Column(TIMESTAMP(timezone=True), nullable=False)
    raw_storage_key = Column(String, nullable=True)

    status = Column(String, nullable=False, index=True)
    error_json = Column(JSONB, nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    org = relationship("Org", back_populates="inbound_messages")
    documents = relationship("Document", back_populates="inbound_message")

    __table_args__ = (
        CheckConstraint("source IN ('EMAIL', 'UPLOAD')", name='inbound_message_source_check'),
        CheckConstraint("status IN ('RECEIVED', 'STORED', 'PARSED', 'FAILED')", name='inbound_message_status_check'),
        UniqueConstraint('org_id', 'source', 'source_message_id', name='idx_inbound_message_dedup'),
    )
```

## Database Schema (SQL)

```sql
CREATE TABLE inbound_message (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES org(id),

  source TEXT NOT NULL CHECK (source IN ('EMAIL', 'UPLOAD')),
  source_message_id TEXT,
  from_email CITEXT,
  to_email CITEXT,
  subject TEXT,

  received_at TIMESTAMPTZ NOT NULL,
  raw_storage_key TEXT,

  status TEXT NOT NULL CHECK (status IN ('RECEIVED', 'STORED', 'PARSED', 'FAILED')),
  error_json JSONB,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE (org_id, source, source_message_id) WHERE source_message_id IS NOT NULL
);

CREATE INDEX idx_inbound_org_received ON inbound_message(org_id, received_at DESC);
CREATE INDEX idx_inbound_org_status ON inbound_message(org_id, status);
```

## Enums

### InboundMessageStatus

```python
from enum import Enum

class InboundMessageStatus(str, Enum):
    RECEIVED = "RECEIVED"  # Email received, raw MIME stored
    STORED = "STORED"      # Raw MIME persisted to storage
    PARSED = "PARSED"      # Attachments extracted
    FAILED = "FAILED"      # Processing failed
```

**State Transitions**:
```
RECEIVED → STORED → PARSED
    ↓         ↓
  FAILED ← ← ←
```
