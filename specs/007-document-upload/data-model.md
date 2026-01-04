# Data Model: Document Upload

**Feature**: 007-document-upload | **Date**: 2025-12-27

## Entity Definitions

### Document (Extended from Spec 005)

See spec 005-object-storage/data-model.md for full document entity.

**Additional Context for Upload**:
- `inbound_message_id`: For uploads, this links to an inbound_message with source=UPLOAD
- `status`: For uploaded files, starts as UPLOADED, transitions to STORED after S3 upload

### DocumentStatus Enum

```python
from enum import Enum

class DocumentStatus(str, Enum):
    UPLOADED = "UPLOADED"      # File received via upload API
    STORED = "STORED"          # File persisted to object storage
    PROCESSING = "PROCESSING"  # Extraction in progress
    EXTRACTED = "EXTRACTED"    # Extraction complete
    FAILED = "FAILED"          # Processing failed
```

**State Transitions**:
```
UPLOADED → STORED → PROCESSING → EXTRACTED
           ↓            ↓
         FAILED ← ← ← ←
```

**Validation Function**:
```python
ALLOWED_TRANSITIONS = {
    None: [DocumentStatus.UPLOADED],
    DocumentStatus.UPLOADED: [DocumentStatus.STORED, DocumentStatus.FAILED],
    DocumentStatus.STORED: [DocumentStatus.PROCESSING, DocumentStatus.FAILED],
    DocumentStatus.PROCESSING: [DocumentStatus.EXTRACTED, DocumentStatus.FAILED],
    DocumentStatus.EXTRACTED: [],  # Terminal success
    DocumentStatus.FAILED: [DocumentStatus.PROCESSING]  # Allow retry
}

def can_transition(from_status: DocumentStatus, to_status: DocumentStatus) -> bool:
    return to_status in ALLOWED_TRANSITIONS.get(from_status, [])
```

## Pydantic Models (API Contracts)

### Upload Request

```python
from pydantic import BaseModel
from fastapi import UploadFile

# FastAPI handles multipart/form-data automatically
# No explicit Pydantic model needed for request
```

### Upload Response

```python
from pydantic import BaseModel
from typing import List
from uuid import UUID

class UploadedDocument(BaseModel):
    document_id: UUID
    file_name: str
    size_bytes: int
    sha256: str
    status: str  # DocumentStatus
    is_duplicate: bool  # True if file already existed

class UploadFailure(BaseModel):
    file_name: str
    error: str

class UploadResponse(BaseModel):
    uploaded: List[UploadedDocument]
    failed: List[UploadFailure]
```

## Supported MIME Types

```python
SUPPORTED_MIME_TYPES = {
    'application/pdf',
    'application/vnd.ms-excel',  # .xls
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
    'text/csv',
}

def is_supported_mime_type(mime_type: str) -> bool:
    return mime_type in SUPPORTED_MIME_TYPES
```

## Example Queries

### Create Upload InboundMessage

```python
async def create_upload_message(
    db: Session,
    org_id: UUID,
    user_id: UUID
) -> InboundMessage:
    """Create inbound_message for manual upload"""
    msg = InboundMessage(
        org_id=org_id,
        source="UPLOAD",
        received_at=datetime.utcnow(),
        status=InboundMessageStatus.RECEIVED
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg
```

### Create Document from Upload

```python
async def create_document_from_upload(
    db: Session,
    org_id: UUID,
    inbound_message_id: UUID,
    stored_file: StoredFile,
    filename: str
) -> Document:
    """Create document record from uploaded file"""
    doc = Document(
        org_id=org_id,
        inbound_message_id=inbound_message_id,
        file_name=filename,
        mime_type=stored_file.mime_type,
        size_bytes=stored_file.size_bytes,
        sha256=stored_file.sha256,
        storage_key=stored_file.storage_key,
        status=DocumentStatus.STORED
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc
```
