# Feature Specification: Object Storage

**Feature Branch**: `005-object-storage`
**Created**: 2025-12-27
**Status**: Draft
**Module**: documents
**SSOT References**: §3.2 (Object Storage), §5.4.6 (document.storage_key), §10.2 (Environment Variables)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Store Document Files (Priority: P1)

As a backend developer, I need to store uploaded documents in object storage so that they are persisted reliably and separately from the database.

**Why this priority**: Documents (PDFs, Excel, CSV) are the core input to OrderFlow. Without reliable file storage, the system cannot function.

**Independent Test**: Can be fully tested by uploading a file via the storage adapter, retrieving it by its storage key, and verifying the content matches exactly. Delivers fundamental file persistence.

**Acceptance Scenarios**:

1. **Given** I have a PDF file, **When** I store it via the object storage adapter, **Then** it returns a storage key and the file is persisted
2. **Given** a file is stored with a storage key, **When** I retrieve it using that key, **Then** I get back the exact same file content
3. **Given** I store a file, **When** I calculate its SHA256 hash, **Then** the hash can be used for deduplication
4. **Given** I attempt to store a very large file (>100MB), **When** the upload completes, **Then** the file is successfully stored without corruption

---

### User Story 2 - Content Deduplication (Priority: P1)

As a system architect, I need to deduplicate files based on their SHA256 hash so that we don't store the same file multiple times when it's uploaded by different users or at different times.

**Why this priority**: Storage costs add up quickly. Deduplication saves significant storage space and reduces processing overhead for identical documents.

**Independent Test**: Can be tested by uploading the same file twice, verifying only one copy is stored in object storage, and confirming both database records point to the same storage_key.

**Acceptance Scenarios**:

1. **Given** a file is already stored with SHA256 hash X, **When** another identical file is uploaded, **Then** it reuses the same storage key instead of creating a duplicate
2. **Given** two files have the same name but different content, **When** both are uploaded, **Then** they are stored separately with different storage keys
3. **Given** the same file is uploaded by different orgs, **When** storing the files, **Then** deduplication is per-org (org_id scoped) to prevent cross-tenant timing attacks and data access inference. Hash uniqueness check: UNIQUE(org_id, sha256, file_name, size_bytes).

---

### User Story 3 - Environment-Agnostic Storage (Priority: P1)

As a DevOps engineer, I need the storage layer to work with both local MinIO (development) and cloud S3 (production) without code changes.

**Why this priority**: Development/production parity is critical. The same code must work locally and in production with only configuration changes.

**Independent Test**: Can be tested by running the same test suite against MinIO and AWS S3, verifying both pass without code modifications.

**Acceptance Scenarios**:

1. **Given** I configure MinIO endpoint in environment variables, **When** the application starts, **Then** it connects to MinIO for object storage
2. **Given** I configure AWS S3 credentials in environment variables, **When** the application starts, **Then** it connects to S3 for object storage
3. **Given** I switch from MinIO to S3 by changing environment variables only, **When** I restart the application, **Then** it works identically without code changes
4. **Given** storage configuration is missing, **When** the application starts, **Then** it fails fast with a clear error message

---

### User Story 4 - Generate Preview/Thumbnail (Priority: P2)

As an OPS user, I need previews/thumbnails of PDF documents so that I can quickly identify the correct order without downloading the full file.

**Why this priority**: While not essential for MVP happy path, previews significantly improve user experience and triage speed in the inbox.

**Independent Test**: Can be tested by uploading a PDF, triggering preview generation, and verifying a preview image is stored and accessible.

**Acceptance Scenarios**:

1. **Given** a PDF document is uploaded, **When** preview generation runs, **Then** a preview image (first page) is stored at preview_storage_key
2. **Given** a multi-page PDF is uploaded, **When** preview generation runs, **Then** thumbnails for the first N pages are generated and stored
3. **Given** a document has a preview, **When** I request the preview via API, **Then** I receive the preview image with appropriate content-type header
4. **Given** preview generation fails (corrupt PDF), **When** the error occurs, **Then** the document status is not affected (preview is optional)

---

### Edge Cases

- What happens when object storage is unavailable during upload?
- How does the system handle network timeouts during large file uploads?
- What happens when attempting to retrieve a file that exists in DB but is missing from object storage?
- How does the system handle corrupt files (e.g., truncated upload)?
- What happens when storage quota is exceeded?
- How does the system handle concurrent uploads of the same file?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide an object storage adapter that works with S3-compatible services (AWS S3, MinIO, etc.)
- **FR-002**: System MUST calculate SHA256 hash for every uploaded file
- **FR-003**: System MUST generate storage keys in format: `{org_id}/{year}/{month}/{sha256}.{ext}`
- **FR-004**: System MUST support file upload with streaming (not loading entire file into memory)
- **FR-005**: System MUST support file retrieval by storage key
- **FR-006**: System MUST deduplicate files based on SHA256 hash within the same org
- **FR-007**: System MUST store original files separately from generated previews/thumbnails
- **FR-008**: System MUST configure storage via environment variables (endpoint, bucket, credentials)
- **FR-009**: System MUST validate file uploads (size limits, allowed MIME types)
- **FR-010**: System MUST provide presigned URLs for secure direct download (optional for MVP)
- **FR-011**: Deduplication MUST be per-org (org_id scoped) to prevent cross-tenant timing attacks and data access inference. Hash uniqueness check: UNIQUE(org_id, sha256, file_name, size_bytes).
- **FR-012**: System MUST verify SHA256 hash on file retrieval. If hash mismatch detected: (1) Mark file as CORRUPTED in database, (2) Log error with file_id and expected/actual hashes, (3) Return 500 error to client with incident ID for support.

### Key Entities

- **Storage Key**: Unique identifier for a file in object storage. Format includes org_id for isolation, date hierarchy for organization, and SHA256 hash for deduplication. Example: `a1b2c3d4/2025/12/abc123def456...789.pdf`

- **Document Metadata**: Database record that tracks file information (storage_key, sha256, size, mime_type, etc.) separately from the actual file content stored in object storage.

### Technical Constraints

- **TC-001**: Storage adapter MUST use S3-compatible API (boto3 or equivalent)
- **TC-002**: Storage keys MUST include org_id to support multi-tenant isolation
- **TC-003**: SHA256 hashing MUST be performed during upload, not as separate step
- **TC-004**: File uploads MUST support streaming to handle large files (>100MB)
- **TC-005**: Storage configuration MUST fail fast on startup if credentials are invalid

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Files up to 100MB upload successfully in under 60 seconds on typical connection
- **SC-002**: SHA256 calculation adds less than 10% overhead to upload time
- **SC-003**: Deduplication prevents 100% of duplicate file storage for identical files within an org
- **SC-004**: Storage adapter works identically with MinIO and AWS S3 (verified by integration tests)
- **SC-005**: File retrieval responds in under 500ms for files <10MB (P95)
- **SC-006**: Zero file corruption detected (hash verification on critical operations)

### Reliability

- **RE-001**: Storage operations are idempotent (retry-safe)
- **RE-002**: Failed uploads leave no orphaned files in object storage
- **RE-003**: Storage adapter handles network failures gracefully (retry with backoff)
- **RE-004**: System detects and reports missing files (DB record exists but storage missing)

## Dependencies

- **Depends on**: 001-platform-foundation (database, MinIO in docker-compose)
- **Depends on**: 003-tenancy-isolation (org_id for storage key generation)
- **Dependency reason**: Object storage requires infrastructure and org_id for multi-tenant file isolation

## Implementation Notes

### Storage Key Format

```
{org_id}/{year}/{month}/{sha256}.{extension}

Example:
a1b2c3d4-e5f6-7890-abcd-ef1234567890/2025/12/abc123def456...789.pdf
```

**Rationale**:
- `org_id`: Ensures tenant isolation at storage level
- `year/month`: Provides time-based organization for lifecycle management
- `sha256`: Content-addressed storage enables deduplication
- `extension`: Preserves original file type for MIME type detection

### Storage Adapter Interface

```python
from abc import ABC, abstractmethod
from typing import BinaryIO, Optional
from dataclasses import dataclass

@dataclass
class StoredFile:
    storage_key: str
    sha256: str
    size_bytes: int
    mime_type: str

class ObjectStoragePort(ABC):
    """S3-compatible object storage abstraction"""

    @abstractmethod
    async def store_file(
        self,
        file: BinaryIO,
        org_id: UUID,
        filename: str,
        mime_type: str
    ) -> StoredFile:
        """
        Store a file and return metadata.
        Calculates SHA256 during upload.
        Returns existing file if hash already exists (dedup).
        """
        pass

    @abstractmethod
    async def retrieve_file(self, storage_key: str) -> BinaryIO:
        """Retrieve file by storage key"""
        pass

    @abstractmethod
    async def delete_file(self, storage_key: str) -> bool:
        """Delete file by storage key. Returns True if deleted, False if not found."""
        pass

    @abstractmethod
    async def generate_presigned_url(
        self,
        storage_key: str,
        expires_in_seconds: int = 3600
    ) -> str:
        """Generate presigned URL for direct download"""
        pass

    @abstractmethod
    async def file_exists(self, storage_key: str) -> bool:
        """Check if file exists in storage"""
        pass
```

### S3 Adapter Implementation

```python
import boto3
import hashlib
from datetime import datetime
from pathlib import Path

class S3StorageAdapter(ObjectStoragePort):
    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        region: str = "us-east-1"
    ):
        self.s3 = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        self.bucket = bucket_name

    async def store_file(
        self,
        file: BinaryIO,
        org_id: UUID,
        filename: str,
        mime_type: str
    ) -> StoredFile:
        # Calculate SHA256 while uploading
        sha256 = hashlib.sha256()
        size = 0

        # Read file in chunks
        chunks = []
        while chunk := file.read(8192):
            sha256.update(chunk)
            chunks.append(chunk)
            size += len(chunk)

        sha256_hex = sha256.hexdigest()

        # Generate storage key
        now = datetime.utcnow()
        ext = Path(filename).suffix
        storage_key = f"{org_id}/{now.year}/{now.month:02d}/{sha256_hex}{ext}"

        # Check if file already exists (deduplication)
        if await self.file_exists(storage_key):
            return StoredFile(
                storage_key=storage_key,
                sha256=sha256_hex,
                size_bytes=size,
                mime_type=mime_type
            )

        # Upload to S3
        file_content = b''.join(chunks)
        self.s3.put_object(
            Bucket=self.bucket,
            Key=storage_key,
            Body=file_content,
            ContentType=mime_type,
            Metadata={
                'sha256': sha256_hex,
                'original_filename': filename
            }
        )

        return StoredFile(
            storage_key=storage_key,
            sha256=sha256_hex,
            size_bytes=size,
            mime_type=mime_type
        )

    async def retrieve_file(self, storage_key: str) -> BinaryIO:
        response = self.s3.get_object(Bucket=self.bucket, Key=storage_key)
        return response['Body']

    async def file_exists(self, storage_key: str) -> bool:
        try:
            self.s3.head_object(Bucket=self.bucket, Key=storage_key)
            return True
        except:
            return False

    async def generate_presigned_url(
        self,
        storage_key: str,
        expires_in_seconds: int = 3600
    ) -> str:
        return self.s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket, 'Key': storage_key},
            ExpiresIn=expires_in_seconds
        )
```

### Environment Configuration

```bash
# .env file
OBJECT_STORAGE_ENDPOINT=http://localhost:9000  # MinIO for dev, https://s3.amazonaws.com for prod
OBJECT_STORAGE_ACCESS_KEY=minioadmin
OBJECT_STORAGE_SECRET_KEY=minioadmin
OBJECT_STORAGE_BUCKET=orderflow-documents
OBJECT_STORAGE_REGION=us-east-1
```

### Document Table Integration (SSOT §5.4.6)

```sql
CREATE TABLE document (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES org(id),
  inbound_message_id UUID REFERENCES inbound_message(id),
  file_name TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  size_bytes BIGINT NOT NULL,
  sha256 TEXT NOT NULL,  -- hex format
  storage_key TEXT NOT NULL,  -- S3 key
  preview_storage_key TEXT,  -- S3 key for preview/thumbnail
  extracted_text_storage_key TEXT,  -- S3 key for extracted text
  status TEXT NOT NULL,  -- DocumentStatus enum
  page_count INT,
  text_coverage_ratio NUMERIC(4,3),
  layout_fingerprint TEXT,
  error_json JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_document_org_created ON document(org_id, created_at DESC);
CREATE INDEX idx_document_org_sha256 ON document(org_id, sha256);
CREATE UNIQUE INDEX idx_document_dedup ON document(org_id, sha256, file_name, size_bytes);
```

### Preview Generation (Optional for MVP)

```python
from pdf2image import convert_from_bytes
from PIL import Image
import io

async def generate_pdf_preview(
    storage: ObjectStoragePort,
    document: Document,
    max_pages: int = 3
) -> str:
    """Generate preview images for first N pages of PDF"""

    # Retrieve original file
    file_content = await storage.retrieve_file(document.storage_key)
    pdf_bytes = file_content.read()

    # Convert first N pages to images
    images = convert_from_bytes(pdf_bytes, first_page=1, last_page=max_pages)

    # Create thumbnail grid
    # ... (PIL image manipulation)

    # Store preview
    preview_bytes = io.BytesIO()
    # ... save image to preview_bytes

    preview_key = f"{document.storage_key}_preview.jpg"
    # Upload preview (simplified, should use store_file)
    # ...

    return preview_key
```

### File Upload Flow

1. Receive file upload (multipart/form-data)
2. Validate file size and MIME type
3. Stream file to storage adapter
4. Storage adapter calculates SHA256 during upload
5. Check if file with same SHA256 already exists for this org
6. If exists: return existing storage_key (dedup)
7. If new: complete upload and return new storage_key
8. Create document record in database with storage_key and SHA256
9. Enqueue background job for preview generation (optional)

### Deduplication Logic

**Within Org** (Recommended):
- Same file uploaded multiple times by same org → single storage copy
- Benefits: Storage savings, faster upload (hash check + DB insert only)
- Implementation: Unique index on (org_id, sha256)

**Cross-Org** (Security Risk):
- Same file uploaded by different orgs → could share storage
- Risk: Timing attacks could reveal if file exists in another org
- Recommendation: **Do NOT implement cross-org dedup in MVP**

## Out of Scope

- File versioning (overwrite only)
- File encryption at rest (rely on S3 server-side encryption)
- Client-side encryption
- CDN integration for faster downloads
- Automatic file lifecycle management (archival, expiration)
- File access logs / audit trail
- Virus scanning / malware detection
- Multi-part upload for very large files (>5GB)
- Resume broken uploads
- Direct browser-to-S3 upload (presigned POST URLs)

## Testing Strategy

### Unit Tests
- SHA256 calculation correctness
- Storage key generation format
- Deduplication logic (same hash, different hash)
- MIME type validation
- File size validation
- Extension extraction from filename

### Integration Tests
- Store and retrieve file (round-trip test)
- Store duplicate file (deduplication)
- Store different files with same name
- Store same file in different orgs (separate storage keys)
- Generate presigned URL and verify download works
- File exists check (positive and negative cases)
- Delete file and verify it's gone
- MinIO configuration test (local dev)
- AWS S3 configuration test (if available)

### Storage Adapter Tests
- Test with MinIO endpoint
- Test with S3 endpoint (staging/prod)
- Test connection failure handling
- Test credential validation on startup
- Test bucket existence check
- Test large file upload (100MB)
- Test concurrent uploads of same file
- Test network timeout handling

### Error Handling Tests
- Upload with invalid credentials
- Upload to non-existent bucket
- Retrieve non-existent file
- Upload when storage quota exceeded
- Upload when network is interrupted
- Corrupt file detection (hash mismatch)

### Performance Tests
- Upload 10MB file (<5 seconds)
- Upload 100MB file (<60 seconds)
- Download 10MB file (<5 seconds)
- SHA256 calculation overhead (<10% of upload time)
- Deduplication check latency (<100ms)
- Concurrent uploads (10 simultaneous uploads)
