# Research: Document Upload

**Feature**: 007-document-upload | **Date**: 2025-12-27

## Key Decisions

### 1. Streaming Upload with FastAPI UploadFile

**Decision**: Use FastAPI's `UploadFile` with SpooledTemporaryFile backend.

**Rationale**:
- Streams large files without loading into memory
- Automatic cleanup of temp files
- Compatible with boto3 for S3 upload
- Built-in MIME type detection

**Implementation**:
```python
@router.post("/uploads")
async def upload_documents(files: List[UploadFile] = File(...)):
    # FastAPI streams file automatically
    # file.file is SpooledTemporaryFile (memory up to 2MB, then disk)
```

### 2. Content-Based MIME Type Validation

**Decision**: Validate actual file content (magic bytes), not just extension.

**Rationale**:
- Prevents fake extensions (virus.pdf → actually .exe)
- Security: only process trusted file types
- Uses python-magic library (libmagic wrapper)

**Alternative Rejected**: Trust Content-Type header (easily spoofed)

### 3. Synchronous Upload, Async Extraction

**Decision**: Upload API returns 201 after file stored, extraction happens in background.

**Rationale**:
- Fast API response (don't wait for extraction)
- Retry-safe extraction (Celery handles failures)
- User sees upload success immediately

### 4. Batch Upload Support

**Decision**: Accept multiple files in single request (multipart/form-data).

**Rationale**:
- Reduces HTTP overhead for multiple files
- Better UX (one click uploads all files)
- Simpler error handling (partial success returned)

### 5. Configurable File Size Limit

**Decision**: Environment variable `MAX_UPLOAD_SIZE_BYTES` (default 100MB).

**Rationale**:
- Prevents DoS via large uploads
- Adjustable per deployment
- Clear error message when exceeded

## Best Practices

### FastAPI Upload Best Practices
- Use `List[UploadFile]` for batch support
- Check `file.content_type` AND magic bytes
- Stream directly to storage (don't buffer)
- Return clear error messages (400 vs 413)

### Security Best Practices
- Validate MIME type (application/pdf, application/vnd.ms-excel, text/csv only)
- Enforce file size limits (prevent DoS)
- Sanitize filenames (prevent path traversal)
- Extract org_id from JWT (never trust request param)

### Error Handling
- 400 Bad Request: Invalid MIME type
- 413 Payload Too Large: File exceeds size limit
- 401 Unauthorized: Missing/invalid JWT
- 403 Forbidden: VIEWER role (not allowed to upload)
- 500 Internal Server Error: Storage failure

## Integration Patterns

**Upload Flow**:
1. Receive multipart/form-data with files
2. Validate MIME types and file sizes
3. Extract org_id from JWT
4. Stream each file to ObjectStoragePort
5. Create inbound_message (source=UPLOAD)
6. Create document records (status=STORED)
7. Enqueue extraction jobs
8. Return 201 with document IDs

**Deduplication Flow**:
1. Storage adapter calculates SHA256
2. Check if (org_id, sha256, file_name, size) exists
3. If exists: Reuse storage_key, create new document record
4. If new: Upload to S3, create new document record
