# Object Storage Infrastructure

This directory contains the infrastructure layer implementation for S3-compatible object storage.

## Architecture Overview

The storage layer follows **Hexagonal Architecture** (Ports & Adapters):

- **Domain Port** (`domain/documents/ports/object_storage_port.py`): Interface defining storage operations
- **Infrastructure Adapter** (`infrastructure/storage/s3_storage_adapter.py`): S3-compatible implementation using boto3
- **Configuration** (`infrastructure/storage/storage_config.py`): Environment-based configuration

This design allows swapping storage backends (MinIO ↔ S3) without changing domain logic.

## Storage Key Format

Files are stored with keys following this pattern:

```
{org_id}/{year}/{month}/{sha256}.{extension}
```

Example:
```
a1b2c3d4-e5f6-7890-abcd-ef1234567890/2026/01/abc123def456...789.pdf
```

### Design Rationale

- **org_id**: Multi-tenant isolation (SSOT §5.1)
- **year/month**: Time-based organization for lifecycle management
- **sha256**: Content-addressed storage enables deduplication
- **extension**: Preserves file type for MIME type detection

## Deduplication Strategy

Files are deduplicated **per-organization only** (not cross-tenant):

- Same file uploaded multiple times within an org → single storage copy
- Database unique constraint: `(org_id, sha256, file_name, size_bytes)`
- Security: Prevents timing attacks that could reveal if file exists in another org

### How Deduplication Works

1. File uploaded via API
2. SHA256 calculated during streaming upload
3. Storage key generated: `{org_id}/{year}/{month}/{sha256}.{ext}`
4. Check if file exists in S3 with HEAD request
5. If exists: return existing metadata (skip upload)
6. If new: upload file and create database record

## Configuration

Storage is configured via environment variables:

### MinIO (Development)

```bash
MINIO_ENDPOINT=localhost:9000
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_BUCKET=orderflow-documents
MINIO_USE_SSL=false
```

### AWS S3 (Production)

```bash
# MINIO_ENDPOINT not set (uses AWS default regional endpoints)
MINIO_ROOT_USER=AKIAIOSFODNN7EXAMPLE
MINIO_ROOT_PASSWORD=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
MINIO_BUCKET=orderflow-prod-documents
MINIO_USE_SSL=true
AWS_REGION=eu-central-1
```

## Usage Examples

### Storing a File

```python
from infrastructure.storage.s3_storage_adapter import S3StorageAdapter
from infrastructure.storage.storage_config import load_storage_config_from_env

# Initialize storage adapter
config = load_storage_config_from_env()
storage = S3StorageAdapter(
    endpoint_url=config.endpoint_url,
    access_key=config.access_key,
    secret_key=config.secret_key,
    bucket_name=config.bucket_name,
    region=config.region,
)

# Store file
with open('invoice.pdf', 'rb') as f:
    stored = await storage.store_file(
        file=f,
        org_id=UUID('a1b2c3d4-e5f6-7890-abcd-ef1234567890'),
        filename='invoice.pdf',
        mime_type='application/pdf',
    )

print(f"Stored at: {stored.storage_key}")
print(f"SHA256: {stored.sha256}")
print(f"Size: {stored.size_bytes} bytes")
```

### Retrieving a File

```python
# Retrieve file
file_stream = await storage.retrieve_file(stored.storage_key)

# Write to local file
with open('downloaded.pdf', 'wb') as f:
    f.write(file_stream.read())
```

### Generating Presigned URL

```python
# Generate presigned URL (valid for 1 hour)
url = await storage.generate_presigned_url(
    storage_key=stored.storage_key,
    expires_in_seconds=3600,
)

print(f"Download URL: {url}")
# Client can download directly from this URL without authentication
```

## File Upload Flow

1. **Upload Request**: Client uploads file via `POST /api/v1/documents/upload`
2. **Validation**: Check file size, MIME type, filename
3. **Streaming Upload**: File streamed to storage adapter
4. **SHA256 Calculation**: Hash calculated during upload (< 10% overhead)
5. **Storage Key Generation**: `{org_id}/{year}/{month}/{sha256}.{ext}`
6. **Deduplication Check**: HEAD request to check if file exists
7. **Upload or Reuse**: Upload if new, return existing if duplicate
8. **Database Record**: Create Document record with storage_key
9. **Response**: Return document metadata to client

## Performance Characteristics

- **Upload Speed**: < 60s for 100MB files on typical connection
- **SHA256 Overhead**: < 10% additional time for hash calculation
- **Deduplication Check**: < 100ms HEAD request
- **Download Speed**: < 500ms for files < 10MB (P95)

## Error Handling

All storage operations use structured error handling:

- `StorageError`: Base exception for storage failures
- `FileNotFoundError`: File doesn't exist in storage
- Automatic retry with exponential backoff (boto3 default)
- Network timeout handling (configurable)

## Security Considerations

### Multi-Tenant Isolation

- Storage keys include org_id prefix
- Database queries filter by org_id (server-side enforced)
- Return 404 (not 403) for cross-tenant access attempts

### Deduplication Security

- **Per-org deduplication only**: Prevents timing attacks
- No cross-tenant file sharing
- Unique constraint: `(org_id, sha256, file_name, size_bytes)`

### File Integrity

- SHA256 verification on upload
- Hash stored in database and S3 metadata
- Optional: Verify hash on critical downloads (SSOT §FR-012)

## Observability

All storage operations are logged with structured logging:

```json
{
  "level": "info",
  "message": "Uploaded file",
  "storage_key": "a1b2c3d4/.../abc123.pdf",
  "sha256": "abc123...",
  "size": 1048576,
  "mime_type": "application/pdf",
  "duration_ms": 2341
}
```

Integration with OpenTelemetry for distributed tracing:
- Span: `storage.upload`
- Attributes: `storage_key`, `size_bytes`, `mime_type`, `deduplication`

## Database Schema

The `document` table tracks file metadata:

```sql
CREATE TABLE document (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES org(id),
  file_name TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  size_bytes BIGINT NOT NULL,
  sha256 TEXT NOT NULL,
  storage_key TEXT NOT NULL,
  preview_storage_key TEXT NULL,
  extracted_text_storage_key TEXT NULL,
  status documentstatus NOT NULL DEFAULT 'UPLOADED',
  page_count INT NULL,
  text_coverage_ratio NUMERIC(4,3) NULL,
  layout_fingerprint TEXT NULL,
  error_json JSONB NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Indexes
  CONSTRAINT uq_document_dedup UNIQUE (org_id, sha256, file_name, size_bytes)
);

CREATE INDEX idx_document_org_created ON document(org_id, created_at DESC);
CREATE INDEX idx_document_org_sha256 ON document(org_id, sha256);
```

## Preview Generation (Optional)

PDF previews/thumbnails can be generated using `pdf2image`:

```python
from pdf2image import convert_from_bytes
from PIL import Image
import io

async def generate_pdf_preview(
    storage: ObjectStoragePort,
    document: Document,
    max_pages: int = 3
) -> str:
    """Generate preview images for first N pages of PDF."""

    # Retrieve original file
    file_stream = await storage.retrieve_file(document.storage_key)
    pdf_bytes = file_stream.read()

    # Convert first N pages to images
    images = convert_from_bytes(pdf_bytes, first_page=1, last_page=max_pages)

    # Create thumbnail (resize first page)
    thumbnail = images[0].resize((300, 400), Image.LANCZOS)

    # Store preview
    preview_bytes = io.BytesIO()
    thumbnail.save(preview_bytes, format='JPEG', quality=85)
    preview_bytes.seek(0)

    preview_stored = await storage.store_file(
        file=preview_bytes,
        org_id=document.org_id,
        filename=f"{document.file_name}_preview.jpg",
        mime_type="image/jpeg",
    )

    return preview_stored.storage_key
```

## Testing

### Unit Tests

Test storage key generation, SHA256 calculation, deduplication logic:

```python
def test_storage_key_generation():
    org_id = UUID('a1b2c3d4-e5f6-7890-abcd-ef1234567890')
    sha256 = 'abc123'
    filename = 'invoice.pdf'

    key = adapter._generate_storage_key(org_id, sha256, filename)
    assert key.startswith(str(org_id))
    assert sha256 in key
    assert key.endswith('.pdf')
```

### Integration Tests

Test with MinIO using `moto` for S3 mocking:

```python
import pytest
from moto import mock_s3

@pytest.fixture
def s3_storage():
    with mock_s3():
        # Setup mock S3
        storage = S3StorageAdapter(...)
        yield storage

async def test_upload_and_retrieve(s3_storage):
    # Upload file
    stored = await s3_storage.store_file(...)

    # Retrieve file
    retrieved = await s3_storage.retrieve_file(stored.storage_key)

    # Verify content matches
    assert retrieved.read() == original_content
```

## SSOT References

- **§3.2**: Object Storage architecture
- **§5.4.6**: Document table schema
- **§5.1**: Database conventions (org_id, timestamps)
- **§10.2**: Environment variables configuration
- **§FR-011**: Per-org deduplication requirement
- **§FR-012**: SHA256 verification requirement
