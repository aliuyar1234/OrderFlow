# Data Model: Object Storage

**Feature**: 005-object-storage
**Date**: 2025-12-27

## Entity Definitions

### Document

Represents a file (PDF, Excel, CSV) stored in object storage. Tracks metadata, storage location, and processing status.

**Properties**:
- `id` (UUID): Primary key
- `org_id` (UUID): Organization owning this document (multi-tenant isolation)
- `inbound_message_id` (UUID, nullable): Link to email/upload event that created this document
- `file_name` (TEXT): Original filename (e.g., "order.pdf")
- `mime_type` (TEXT): Content type (e.g., "application/pdf")
- `size_bytes` (BIGINT): File size in bytes
- `sha256` (TEXT): SHA256 hash in hex format (for deduplication and integrity verification)
- `storage_key` (TEXT): S3 object key (format: `{org_id}/{year}/{month}/{sha256}.{ext}`)
- `preview_storage_key` (TEXT, nullable): S3 key for preview/thumbnail image
- `extracted_text_storage_key` (TEXT, nullable): S3 key for extracted text (future use)
- `status` (TEXT): DocumentStatus enum (UPLOADED, STORED, PROCESSING, EXTRACTED, FAILED)
- `page_count` (INT, nullable): Number of pages (for PDFs)
- `text_coverage_ratio` (NUMERIC(4,3), nullable): Ratio of extractable text (0.0-1.0, for PDFs)
- `layout_fingerprint` (TEXT, nullable): SHA256 of document layout structure (for learning)
- `error_json` (JSONB, nullable): Error details if status=FAILED
- `created_at` (TIMESTAMPTZ): Timestamp when document was created
- `updated_at` (TIMESTAMPTZ): Timestamp of last update

**Relationships**:
- `org_id` → `org.id` (many-to-one)
- `inbound_message_id` → `inbound_message.id` (many-to-one, nullable)

**Constraints**:
- `status` must be one of: UPLOADED, STORED, PROCESSING, EXTRACTED, FAILED
- Unique deduplication index: `(org_id, sha256, file_name, size_bytes)`

---

### StoredFile (Value Object)

Non-persisted value object returned by `ObjectStoragePort.store_file()`.

**Properties**:
- `storage_key` (str): S3 object key
- `sha256` (str): SHA256 hash in hex format
- `size_bytes` (int): File size in bytes
- `mime_type` (str): Content type

**Usage**:
```python
stored_file = await storage.store_file(file, org_id, filename, mime_type)
# Use stored_file to populate Document entity
```

---

## SQLAlchemy Models

### Document Model

```python
from sqlalchemy import Column, String, BigInteger, Integer, Numeric, TIMESTAMP, ForeignKey, CheckConstraint, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

class Document(Base):
    __tablename__ = 'document'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey('org.id'), nullable=False, index=True)
    inbound_message_id = Column(UUID(as_uuid=True), ForeignKey('inbound_message.id'), nullable=True)

    file_name = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    sha256 = Column(String, nullable=False, index=True)
    storage_key = Column(String, nullable=False, unique=True)

    preview_storage_key = Column(String, nullable=True)
    extracted_text_storage_key = Column(String, nullable=True)

    status = Column(String, nullable=False, index=True)
    page_count = Column(Integer, nullable=True)
    text_coverage_ratio = Column(Numeric(4, 3), nullable=True)
    layout_fingerprint = Column(String, nullable=True)

    error_json = Column(JSONB, nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    org = relationship("Org", back_populates="documents")
    inbound_message = relationship("InboundMessage", back_populates="documents")
    extraction_runs = relationship("ExtractionRun", back_populates="document")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('UPLOADED', 'STORED', 'PROCESSING', 'EXTRACTED', 'FAILED')",
            name='document_status_check'
        ),
        Index('idx_document_org_created', 'org_id', 'created_at'),
        Index('idx_document_org_status', 'org_id', 'status'),
        Index('idx_document_org_sha256', 'org_id', 'sha256'),
        UniqueConstraint('org_id', 'sha256', 'file_name', 'size_bytes', name='idx_document_dedup'),
    )

    def __repr__(self):
        return f"<Document(id={self.id}, file_name={self.file_name}, status={self.status})>"
```

---

## Database Schema (SQL)

### document Table

```sql
CREATE TABLE document (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES org(id),
  inbound_message_id UUID REFERENCES inbound_message(id),

  file_name TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  size_bytes BIGINT NOT NULL,
  sha256 TEXT NOT NULL,
  storage_key TEXT NOT NULL UNIQUE,

  preview_storage_key TEXT,
  extracted_text_storage_key TEXT,

  status TEXT NOT NULL CHECK (status IN ('UPLOADED', 'STORED', 'PROCESSING', 'EXTRACTED', 'FAILED')),
  page_count INT,
  text_coverage_ratio NUMERIC(4,3),
  layout_fingerprint TEXT,

  error_json JSONB,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_document_org_created ON document(org_id, created_at DESC);
CREATE INDEX idx_document_org_status ON document(org_id, status);
CREATE INDEX idx_document_org_sha256 ON document(org_id, sha256);

-- Deduplication index
CREATE UNIQUE INDEX idx_document_dedup ON document(org_id, sha256, file_name, size_bytes);
```

### Migration Script (Alembic)

```python
"""Add document table

Revision ID: 005_object_storage
Revises: 003_tenancy_isolation
Create Date: 2025-12-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '005_object_storage'
down_revision = '003_tenancy_isolation'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'document',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('org.id'), nullable=False),
        sa.Column('inbound_message_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('inbound_message.id'), nullable=True),

        sa.Column('file_name', sa.String, nullable=False),
        sa.Column('mime_type', sa.String, nullable=False),
        sa.Column('size_bytes', sa.BigInteger, nullable=False),
        sa.Column('sha256', sa.String, nullable=False),
        sa.Column('storage_key', sa.String, nullable=False, unique=True),

        sa.Column('preview_storage_key', sa.String, nullable=True),
        sa.Column('extracted_text_storage_key', sa.String, nullable=True),

        sa.Column('status', sa.String, nullable=False),
        sa.Column('page_count', sa.Integer, nullable=True),
        sa.Column('text_coverage_ratio', sa.Numeric(4, 3), nullable=True),
        sa.Column('layout_fingerprint', sa.String, nullable=True),

        sa.Column('error_json', postgresql.JSONB, nullable=True),

        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),

        sa.CheckConstraint("status IN ('UPLOADED', 'STORED', 'PROCESSING', 'EXTRACTED', 'FAILED')", name='document_status_check')
    )

    op.create_index('idx_document_org_created', 'document', ['org_id', sa.text('created_at DESC')])
    op.create_index('idx_document_org_status', 'document', ['org_id', 'status'])
    op.create_index('idx_document_org_sha256', 'document', ['org_id', 'sha256'])
    op.create_index('idx_document_dedup', 'document', ['org_id', 'sha256', 'file_name', 'size_bytes'], unique=True)

def downgrade():
    op.drop_table('document')
```

---

## Relationships and Constraints

### One-to-Many Relationships

**Org → Documents**
- One organization has many documents
- `document.org_id → org.id`
- Enforces multi-tenant isolation

**InboundMessage → Documents**
- One inbound message (email or upload) can have multiple documents (attachments)
- `document.inbound_message_id → inbound_message.id` (nullable for direct uploads)

**Document → ExtractionRuns**
- One document can have multiple extraction attempts (retries)
- `extraction_run.document_id → document.id`

### Unique Constraints

**Deduplication Constraint**:
```sql
UNIQUE (org_id, sha256, file_name, size_bytes)
```

**Purpose**: Prevent duplicate file storage within an org.

**Behavior**:
- Same file uploaded multiple times → INSERT fails with IntegrityError
- Application handles this by returning existing document
- Storage layer reuses existing storage_key

**Storage Key Constraint**:
```sql
UNIQUE (storage_key)
```

**Purpose**: One storage_key maps to exactly one document record.

---

## Enums

### DocumentStatus

```python
from enum import Enum

class DocumentStatus(str, Enum):
    UPLOADED = "UPLOADED"      # File received via upload
    STORED = "STORED"          # File persisted to object storage
    PROCESSING = "PROCESSING"  # Extraction in progress
    EXTRACTED = "EXTRACTED"    # Extraction complete
    FAILED = "FAILED"          # Processing failed
```

**State Transitions**:
```
UPLOADED → STORED → PROCESSING → EXTRACTED
           ↓           ↓
         FAILED ← ← ← ←
```

**Allowed Transitions**:
```python
ALLOWED_TRANSITIONS = {
    None: [DocumentStatus.UPLOADED],
    DocumentStatus.UPLOADED: [DocumentStatus.STORED, DocumentStatus.FAILED],
    DocumentStatus.STORED: [DocumentStatus.PROCESSING, DocumentStatus.FAILED],
    DocumentStatus.PROCESSING: [DocumentStatus.EXTRACTED, DocumentStatus.FAILED],
    DocumentStatus.EXTRACTED: [],  # Terminal success
    DocumentStatus.FAILED: [DocumentStatus.PROCESSING]  # Allow retry
}
```

---

## Example Queries

### Insert Document (with deduplication handling)

```python
from sqlalchemy.exc import IntegrityError

async def create_document(
    db: Session,
    org_id: UUID,
    stored_file: StoredFile,
    file_name: str,
    inbound_message_id: Optional[UUID] = None
) -> Document:
    """
    Create document record. Handles deduplication gracefully.
    """
    try:
        document = Document(
            org_id=org_id,
            inbound_message_id=inbound_message_id,
            file_name=file_name,
            mime_type=stored_file.mime_type,
            size_bytes=stored_file.size_bytes,
            sha256=stored_file.sha256,
            storage_key=stored_file.storage_key,
            status=DocumentStatus.STORED
        )

        db.add(document)
        await db.commit()
        await db.refresh(document)

        return document

    except IntegrityError as e:
        await db.rollback()

        # Check if deduplication constraint violation
        if 'idx_document_dedup' in str(e):
            # Return existing document
            existing = await db.query(Document).filter(
                Document.org_id == org_id,
                Document.sha256 == stored_file.sha256,
                Document.file_name == file_name,
                Document.size_bytes == stored_file.size_bytes
            ).first()

            return existing

        raise
```

### Find Documents by Org

```python
async def get_documents_by_org(
    db: Session,
    org_id: UUID,
    limit: int = 50,
    offset: int = 0
) -> List[Document]:
    """Get documents for organization, newest first"""
    return await db.query(Document)\
        .filter(Document.org_id == org_id)\
        .order_by(Document.created_at.desc())\
        .limit(limit)\
        .offset(offset)\
        .all()
```

### Find Document by Storage Key

```python
async def get_document_by_storage_key(
    db: Session,
    storage_key: str,
    org_id: UUID
) -> Optional[Document]:
    """Get document by storage key (with org_id check for security)"""
    return await db.query(Document)\
        .filter(
            Document.storage_key == storage_key,
            Document.org_id == org_id
        )\
        .first()
```

### Check for Duplicate

```python
async def find_duplicate_document(
    db: Session,
    org_id: UUID,
    sha256: str,
    file_name: str,
    size_bytes: int
) -> Optional[Document]:
    """Check if identical document already exists"""
    return await db.query(Document)\
        .filter(
            Document.org_id == org_id,
            Document.sha256 == sha256,
            Document.file_name == file_name,
            Document.size_bytes == size_bytes
        )\
        .first()
```

---

## Index Strategy

### Performance Indexes

1. **`idx_document_org_created`**: `(org_id, created_at DESC)`
   - **Purpose**: Fast retrieval of recent documents for org (inbox view)
   - **Query**: `SELECT * FROM document WHERE org_id = ? ORDER BY created_at DESC LIMIT 50`

2. **`idx_document_org_status`**: `(org_id, status)`
   - **Purpose**: Filter documents by status (e.g., "show all FAILED documents")
   - **Query**: `SELECT * FROM document WHERE org_id = ? AND status = 'FAILED'`

3. **`idx_document_org_sha256`**: `(org_id, sha256)`
   - **Purpose**: Fast deduplication check
   - **Query**: `SELECT * FROM document WHERE org_id = ? AND sha256 = ?`

### Unique Indexes

1. **`idx_document_dedup`**: `UNIQUE (org_id, sha256, file_name, size_bytes)`
   - **Purpose**: Prevent duplicate file storage within org
   - **Behavior**: INSERT fails if duplicate detected

2. **`storage_key`**: `UNIQUE (storage_key)`
   - **Purpose**: One storage_key per document
   - **Behavior**: Prevents storage key collisions

---

## Data Integrity

### Constraints

1. **Foreign Keys**: Enforce referential integrity (org_id, inbound_message_id)
2. **NOT NULL**: Required fields cannot be null (file_name, mime_type, sha256, etc.)
3. **CHECK**: status must be valid enum value
4. **UNIQUE**: Deduplication and storage_key uniqueness

### Validation (Application-Level)

```python
from pydantic import BaseModel, validator
from typing import Optional

class DocumentCreate(BaseModel):
    org_id: UUID
    file_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    storage_key: str

    @validator('size_bytes')
    def validate_size(cls, v):
        if v <= 0:
            raise ValueError('size_bytes must be positive')
        if v > 100 * 1024 * 1024:  # 100MB
            raise ValueError('File too large (max 100MB)')
        return v

    @validator('sha256')
    def validate_sha256(cls, v):
        if len(v) != 64:
            raise ValueError('sha256 must be 64 hex characters')
        if not all(c in '0123456789abcdef' for c in v.lower()):
            raise ValueError('sha256 must be hex string')
        return v.lower()
```
