# Feature Specification: Document Upload

**Feature Branch**: `007-document-upload`
**Created**: 2025-12-27
**Status**: Draft
**Module**: inbox, documents
**SSOT References**: §5.2.3 (DocumentStatus), §5.4.6 (document table), §8.5 (Upload API)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Manual Document Upload (Priority: P1)

As an OPS user, I need to manually upload order documents (PDF/Excel/CSV) via the UI so that I can process orders that weren't received via email.

**Why this priority**: Not all customers send orders via email. Manual upload provides an alternative entry point and is essential for comprehensive order coverage.

**Independent Test**: Can be fully tested by uploading a PDF file via the upload API, verifying the file is stored in object storage, a document record is created, and the upload appears in the inbox. Delivers manual order intake capability.

**Acceptance Scenarios**:

1. **Given** I am logged in as OPS, **When** I upload a PDF file via the UI, **Then** the file is stored and a document record is created with status=UPLOADED
2. **Given** I upload a document, **When** the upload completes, **Then** I can see it in the inbox with source=UPLOAD
3. **Given** I upload an Excel file, **When** the upload completes, **Then** extraction is automatically triggered in the background
4. **Given** I upload multiple files at once, **When** the upload completes, **Then** all files are stored as separate documents

---

### User Story 2 - File Type Validation (Priority: P1)

As a system administrator, I need to validate uploaded file types so that only supported formats (PDF, Excel, CSV) are accepted.

**Why this priority**: Accepting unsupported file types wastes storage and processing resources. Validation prevents user confusion and processing failures.

**Independent Test**: Can be tested by attempting to upload various file types (valid: PDF, XLSX, CSV; invalid: DOCX, JPG, EXE), verifying only valid types are accepted.

**Acceptance Scenarios**:

1. **Given** I attempt to upload a PDF file, **When** the upload is processed, **Then** it is accepted
2. **Given** I attempt to upload an unsupported file type (e.g., .docx), **When** the upload is processed, **Then** I receive a 400 Bad Request error with clear message
3. **Given** I attempt to upload a file with fake extension (e.g., virus.pdf but actually .exe), **When** MIME type validation runs, **Then** the file is rejected
4. **Given** I upload a very large file (>100MB), **When** the upload is processed, **Then** the upload is rejected with 413 Payload Too Large. Limit is configurable via MAX_UPLOAD_SIZE_BYTES environment variable (default: 104857600). Response includes max allowed size for client display.

---

### User Story 3 - Deduplication of Uploaded Files (Priority: P2)

As a system administrator, I need to prevent duplicate file uploads based on SHA256 hash so that the same order isn't processed multiple times.

**Why this priority**: Users may accidentally upload the same file multiple times. Deduplication prevents duplicate processing and wasted storage.

**Independent Test**: Can be tested by uploading the same file twice, verifying only one copy is stored in object storage, and the UI indicates the file was already uploaded.

**Acceptance Scenarios**:

1. **Given** a file with SHA256 hash X was already uploaded, **When** I upload the same file again, **Then** the system reuses the existing storage and creates a new document record pointing to it
2. **Given** I upload a file that matches an existing email attachment, **When** the upload completes, **Then** the storage is deduplicated but both document records exist
3. **Given** I upload the same file in a different org, **When** the upload completes, **Then** it is stored separately (org-scoped deduplication)

---

### User Story 4 - DocumentStatus State Machine (Priority: P1)

As a backend developer, I need a clear status progression for documents so that I can track where each document is in the processing pipeline.

**Why this priority**: Status tracking is essential for observability and error handling. Without it, debugging processing failures is nearly impossible.

**Independent Test**: Can be tested by uploading a document, observing status transitions (UPLOADED → STORED → PROCESSING → EXTRACTED), and verifying each transition is valid.

**Acceptance Scenarios**:

1. **Given** a document is newly uploaded, **When** it is created, **Then** status is UPLOADED
2. **Given** a document is stored in object storage, **When** storage succeeds, **Then** status transitions to STORED
3. **Given** extraction is triggered, **When** the worker picks up the job, **Then** status transitions to PROCESSING
4. **Given** extraction succeeds, **When** the worker completes, **Then** status transitions to EXTRACTED
5. **Given** extraction fails, **When** an error occurs, **Then** status transitions to FAILED and error_json contains details

---

### Edge Cases

- What happens when upload is interrupted mid-transfer?
- How does the system handle files with invalid/missing MIME types?
- What happens when uploading a 0-byte file?
- How does the system handle filename collisions (same name, different content)?
- What happens when object storage is full?
- How does the system handle filenames with special characters or very long names?
- What happens when a document is uploaded but extraction never completes (stuck in PROCESSING)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide API endpoint for file upload (multipart/form-data)
- **FR-002**: System MUST validate file MIME types (allow: PDF, Excel, CSV)
- **FR-003**: System MUST calculate SHA256 hash during upload for deduplication
- **FR-004**: System MUST create inbound_message record with source=UPLOAD for uploaded files
- **FR-005**: System MUST create document record with status=UPLOADED for each uploaded file
- **FR-006**: System MUST transition document status through state machine (UPLOADED → STORED → PROCESSING → EXTRACTED or FAILED)
- **FR-007**: System MUST enforce file size limits (configurable, default 100MB)
- **FR-008**: System MUST automatically trigger extraction after successful upload
- **FR-009**: System MUST deduplicate files based on SHA256 hash within org
- **FR-010**: System MUST support batch upload (multiple files in single request)
- **FR-011**: System MUST store error details in error_json when status=FAILED
- **FR-012**: System MUST restrict upload endpoint to authenticated users (OPS, ADMIN, INTEGRATOR roles)

### Key Entities

- **Document**: Represents an uploaded or email-attached file. Tracks storage location, SHA256 hash, processing status, file metadata, and errors. Documents flow through a state machine from upload to extraction. Terminology: 'document' refers to an uploaded or email-attached file (PDF/Excel/CSV). The extraction process converts a document file into structured data via extraction_run.

- **DocumentStatus**: Enum representing document processing state. Valid states: UPLOADED, STORED, PROCESSING, EXTRACTED, FAILED. State transitions enforce correct processing order.

### Technical Constraints

- **TC-001**: Upload endpoint MUST use streaming to handle large files (not load into memory)
- **TC-002**: MIME type validation MUST check actual content, not just file extension
- **TC-003**: SHA256 calculation MUST happen during upload (single pass)
- **TC-004**: Status transitions MUST be validated (cannot skip states)
- **TC-005**: Document records MUST be immutable after creation (status and error_json only mutable fields)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: File upload completes in under 10 seconds for 10MB files (P95)
- **SC-002**: File upload completes in under 60 seconds for 100MB files (P95)
- **SC-003**: 100% of uploaded files with valid types result in document records
- **SC-004**: Deduplication prevents 100% of duplicate file storage for identical files within org
- **SC-005**: Status transitions are always valid (verified by state machine validation)
- **SC-006**: Zero file corruption detected (SHA256 verification on retrieval)

### User Experience

- **UX-001**: Upload progress is visible to user (if UI supports it)
- **UX-002**: Upload errors provide clear, actionable messages (e.g., "File too large", "Unsupported file type")
- **UX-003**: Batch upload supports minimum 10 files simultaneously
- **UX-004**: Upload response includes document IDs for tracking

### Orchestration (E2E Flow)

- **FR-ORQ-001**: After document record is created with status=STORED, upload handler MUST enqueue extraction job: `extract_document(document_id, org_id)`. This triggers the extraction pipeline (spec 009).
- **FR-ORQ-002**: InboundMessage.source='UPLOAD' distinguishes upload-originated documents from emails (source='EMAIL'). The downstream extraction pipeline (spec 009) processes both sources identically.
- **FR-ORQ-003**: E2E flow: File uploaded → validated → stored → document created → extraction job enqueued → (spec 009 takes over). No manual intervention for happy path.

### Terminology

'Document' refers to an uploaded or email-attached file (PDF/Excel/CSV). The extraction process converts a document file into structured data via extraction_run.

## Dependencies

- **Depends on**: 001-platform-foundation (database)
- **Depends on**: 002-auth-rbac (role enforcement)
- **Depends on**: 003-tenancy-isolation (org_id scoping)
- **Depends on**: 005-object-storage (file storage)
- **Triggers**: 009-extraction-core (via enqueued extraction jobs)
- **Dependency reason**: Upload requires authentication, file storage, and org isolation

## Implementation Notes

### DocumentStatus State Machine (SSOT §5.2.3)

```python
from enum import Enum

class DocumentStatus(str, Enum):
    UPLOADED = "UPLOADED"      # File received via upload
    STORED = "STORED"          # File persisted to object storage
    PROCESSING = "PROCESSING"  # Extraction in progress
    EXTRACTED = "EXTRACTED"    # Extraction complete
    FAILED = "FAILED"          # Processing failed

# State transitions
ALLOWED_TRANSITIONS = {
    None: [DocumentStatus.UPLOADED],
    DocumentStatus.UPLOADED: [DocumentStatus.STORED, DocumentStatus.FAILED],
    DocumentStatus.STORED: [DocumentStatus.PROCESSING, DocumentStatus.FAILED],
    DocumentStatus.PROCESSING: [DocumentStatus.EXTRACTED, DocumentStatus.FAILED],
    DocumentStatus.EXTRACTED: [],  # Terminal success
    DocumentStatus.FAILED: [DocumentStatus.PROCESSING]  # Allow retry
}

def can_transition(from_status: DocumentStatus, to_status: DocumentStatus) -> bool:
    """Validate status transition is allowed"""
    return to_status in ALLOWED_TRANSITIONS.get(from_status, [])
```

### Document Table Schema (SSOT §5.4.6)

```sql
CREATE TABLE document (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES org(id),
  inbound_message_id UUID REFERENCES inbound_message(id),  -- NULL for direct upload
  file_name TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  size_bytes BIGINT NOT NULL,
  sha256 TEXT NOT NULL,  -- hex format, for deduplication
  storage_key TEXT NOT NULL,
  preview_storage_key TEXT,
  extracted_text_storage_key TEXT,
  status TEXT NOT NULL CHECK (status IN ('UPLOADED', 'STORED', 'PROCESSING', 'EXTRACTED', 'FAILED')),
  page_count INT,
  text_coverage_ratio NUMERIC(4,3),  -- For PDFs: ratio of text-extractable content
  layout_fingerprint TEXT,  -- SHA256 of layout structure (for learning)
  error_json JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_document_org_created ON document(org_id, created_at DESC);
CREATE INDEX idx_document_org_sha256 ON document(org_id, sha256);
CREATE UNIQUE INDEX idx_document_dedup ON document(org_id, sha256, file_name, size_bytes);
```

### Upload API Endpoint (SSOT §8.5)

#### POST `/uploads`

Requires authentication (OPS, ADMIN, or INTEGRATOR role).

**Request**: multipart/form-data with one or more files

```http
POST /api/v1/uploads HTTP/1.1
Authorization: Bearer {token}
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary

------WebKitFormBoundary
Content-Disposition: form-data; name="files"; filename="order.pdf"
Content-Type: application/pdf

{binary data}
------WebKitFormBoundary--
```

**Response 201**:
```json
{
  "uploaded": [
    {
      "document_id": "uuid",
      "file_name": "order.pdf",
      "size_bytes": 123456,
      "sha256": "abc123...",
      "status": "STORED",
      "is_duplicate": false
    }
  ],
  "failed": []
}
```

**Response 400** (validation error):
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid file type",
    "details": [
      {
        "file_name": "document.docx",
        "error": "Unsupported MIME type: application/vnd.openxmlformats-officedocument.wordprocessingml.document"
      }
    ]
  }
}
```

**Response 413** (file too large):
```json
{
  "error": {
    "code": "FILE_TOO_LARGE",
    "message": "File exceeds maximum size of 100MB",
    "max_size_bytes": 104857600
  }
}
```

### Upload Implementation

```python
from fastapi import APIRouter, UploadFile, File, Depends
from typing import List

router = APIRouter()

@router.post("/uploads")
async def upload_documents(
    files: List[UploadFile] = File(...),
    org_id: UUID = Depends(get_org_id),
    storage: ObjectStoragePort = Depends(get_storage),
    db: Session = Depends(get_db)
):
    """
    Upload one or more documents for processing.
    """
    uploaded = []
    failed = []

    for file in files:
        try:
            # Validate MIME type
            if not is_supported_mime_type(file.content_type):
                failed.append({
                    "file_name": file.filename,
                    "error": f"Unsupported MIME type: {file.content_type}"
                })
                continue

            # Validate file size
            file.file.seek(0, 2)  # Seek to end
            size_bytes = file.file.tell()
            file.file.seek(0)  # Reset

            if size_bytes > MAX_FILE_SIZE:
                failed.append({
                    "file_name": file.filename,
                    "error": f"File too large: {size_bytes} bytes (max: {MAX_FILE_SIZE})"
                })
                continue

            # Store file (with deduplication)
            stored_file = await storage.store_file(
                file=file.file,
                org_id=org_id,
                filename=file.filename,
                mime_type=file.content_type
            )

            # Check if duplicate
            is_duplicate = await check_duplicate_document(
                db,
                org_id=org_id,
                sha256=stored_file.sha256,
                file_name=file.filename,
                size_bytes=stored_file.size_bytes
            )

            # Create inbound_message for upload
            inbound_msg = await create_inbound_message(
                db,
                org_id=org_id,
                source="UPLOAD",
                received_at=datetime.utcnow()
            )

            # Create document record
            document = await create_document(
                db,
                org_id=org_id,
                inbound_message_id=inbound_msg.id,
                file_name=file.filename,
                mime_type=file.content_type,
                size_bytes=stored_file.size_bytes,
                sha256=stored_file.sha256,
                storage_key=stored_file.storage_key,
                status=DocumentStatus.STORED
            )

            # Enqueue extraction
            await enqueue_document_extraction(document.id, org_id)

            uploaded.append({
                "document_id": str(document.id),
                "file_name": file.filename,
                "size_bytes": stored_file.size_bytes,
                "sha256": stored_file.sha256,
                "status": document.status,
                "is_duplicate": is_duplicate
            })

        except Exception as e:
            logger.error(f"Upload failed for {file.filename}: {e}")
            failed.append({
                "file_name": file.filename,
                "error": str(e)
            })

    return {
        "uploaded": uploaded,
        "failed": failed
    }
```

### Supported MIME Types

```python
SUPPORTED_MIME_TYPES = {
    'application/pdf',
    'application/vnd.ms-excel',  # .xls
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
    'text/csv',
    'application/zip',  # For future ZIP extraction
}

def is_supported_mime_type(mime_type: str) -> bool:
    return mime_type in SUPPORTED_MIME_TYPES
```

### MIME Type Validation (Content-Based)

```python
import magic

def validate_mime_type(file_path: str, declared_mime_type: str) -> bool:
    """
    Validate MIME type by inspecting file content (magic bytes).
    Prevents fake extensions (e.g., virus.pdf that's actually .exe)
    """
    actual_mime_type = magic.from_file(file_path, mime=True)
    return actual_mime_type == declared_mime_type
```

### Deduplication Check

```python
async def check_duplicate_document(
    db: Session,
    org_id: UUID,
    sha256: str,
    file_name: str,
    size_bytes: int
) -> bool:
    """
    Check if identical document already exists.
    Uses unique index on (org_id, sha256, file_name, size_bytes)
    """
    existing = await db.query(Document).filter(
        Document.org_id == org_id,
        Document.sha256 == sha256,
        Document.file_name == file_name,
        Document.size_bytes == size_bytes
    ).first()

    return existing is not None
```

### Status Transition Validation

```python
async def update_document_status(
    db: Session,
    document_id: UUID,
    new_status: DocumentStatus,
    error_json: Optional[dict] = None
):
    """
    Update document status with state machine validation.
    """
    document = await db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise ValueError(f"Document {document_id} not found")

    # Validate transition
    if not can_transition(DocumentStatus(document.status), new_status):
        raise ValueError(
            f"Invalid status transition: {document.status} -> {new_status}"
        )

    # Update status
    document.status = new_status.value
    document.updated_at = datetime.utcnow()

    if error_json:
        document.error_json = error_json

    await db.commit()
```

### Configuration

```python
# config.py
MAX_FILE_SIZE = int(os.getenv('MAX_UPLOAD_SIZE_BYTES', 100 * 1024 * 1024))  # 100MB default
MAX_BATCH_FILES = int(os.getenv('MAX_BATCH_UPLOAD_FILES', 10))
```

## Out of Scope

- Drag-and-drop UI (API only, UI covered in spec 008)
- Upload resume for interrupted transfers
- Client-side file chunking
- Direct browser-to-S3 upload (presigned POST URLs)
- ZIP file auto-extraction (store as-is for MVP)
- Image file support (OCR of scanned documents)
- Automatic file format conversion
- Virus/malware scanning (add in production)
- Upload from URL (drag-and-drop only)
- Folder upload (individual files only)
- Upload queue management (background processing automatic)
- Upload bandwidth throttling

## Testing Strategy

### Unit Tests
- DocumentStatus state machine transitions (valid/invalid)
- MIME type validation (supported/unsupported)
- SHA256 deduplication logic
- File size validation
- Filename sanitization
- Error JSON structure

### Integration Tests
- Upload single PDF file
- Upload single Excel file
- Upload single CSV file
- Upload multiple files in batch
- Upload duplicate file (same SHA256)
- Upload file with unsupported MIME type (expect error)
- Upload file exceeding size limit (expect error)
- Upload with invalid auth token (expect 401)
- Upload as VIEWER role (expect 403)
- Upload triggers extraction job (verify job enqueued)
- Status transition UPLOADED → STORED → PROCESSING → EXTRACTED

### API Tests
- POST /uploads with valid PDF (expect 201)
- POST /uploads with invalid MIME type (expect 400)
- POST /uploads with file too large (expect 413)
- POST /uploads with empty file (expect 400)
- POST /uploads without auth (expect 401)
- POST /uploads as VIEWER (expect 403)
- POST /uploads with 10 files (batch upload)

### Deduplication Tests
- Upload same file twice (verify single storage copy)
- Upload same file in different orgs (verify separate storage)
- Upload files with same name but different content (verify separate storage)
- Upload file matching email attachment (verify deduplication across sources)

### Error Handling Tests
- Object storage failure during upload (verify error response)
- Database failure during document creation (verify rollback)
- MIME type validation failure (verify error response)
- Extraction job enqueueing failure (verify document still created)
- Concurrent uploads of same file (verify deduplication)

### Performance Tests
- Upload 10MB file (<10 seconds)
- Upload 100MB file (<60 seconds)
- Batch upload 10 files (<30 seconds)
- SHA256 calculation overhead (<10% of upload time)
- Concurrent uploads (10 simultaneous users)

### Security Tests
- Upload with fake extension (virus.pdf but actually .exe)
- Upload with path traversal in filename (../../etc/passwd)
- Upload with extremely long filename (>255 chars)
- Upload with special characters in filename
- Upload with null bytes in filename
- Cross-org upload attempt (verify org_id isolation)
