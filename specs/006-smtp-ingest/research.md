# Research: SMTP Ingest

**Feature**: 006-smtp-ingest | **Date**: 2025-12-27

## Key Decisions

### 1. aiosmtpd for Async SMTP Server

**Decision**: Use aiosmtpd library for async SMTP handling.

**Rationale**:
- Native asyncio support (integrates well with FastAPI/Celery)
- Simple handler interface
- Production-ready, actively maintained
- No separate SMTP daemon required

**Alternative Rejected**: Postfix + custom scripts (too complex, separate process management)

### 2. Plus-Addressing for Org Routing

**Decision**: Extract org_slug from email address (orders+acme@domain.com → "acme")

**Rationale**:
- Standard email feature, supported by all providers
- No DNS configuration per org required
- Single ingest address for all orgs
- Clear, simple routing logic

**Format**: `orders+{org_slug}@orderflow.example.com`

### 3. Store Raw MIME Before Processing

**Decision**: Store raw email to object storage BEFORE parsing/extraction.

**Rationale**:
- Fault tolerance: if parsing fails, raw email is preserved
- Auditability: can replay email processing
- Debu
gging: inspect exact email received

**Implementation**: Raw MIME → S3 → parse → extract attachments

### 4. Deduplication via Message-ID

**Decision**: Unique constraint on (org_id, source='EMAIL', source_message_id)

**Rationale**:
- Prevents duplicate processing if same email forwarded multiple times
- Message-ID is standard email header
- Per-org deduplication (same email to different orgs is allowed)

### 5. Background Attachment Extraction

**Decision**: SMTP handler creates inbound_message, enqueues Celery job for attachment extraction.

**Rationale**:
- Fast SMTP response (accept email quickly, process later)
- Retry capability for transient failures
- Backpressure handling (queue depth monitoring)

## Best Practices

### MIME Parsing
- Use `email.policy.default` for proper RFC compliance
- Handle multipart/mixed, multipart/alternative correctly
- Decode RFC 2047 encoded headers (=?UTF-8?B?...)
- Skip inline images (Content-Disposition: inline)

### Error Handling
- 250 OK: Email accepted and stored
- 451 Temporary Error: Retry later (storage unavailable)
- 550 Permanent Error: Unknown org or malformed email

### Security
- Validate org_slug exists before accepting email
- Reject emails without Message-ID (generate synthetic ID)
- Rate limiting (future: prevent spam)
- No auto-execute attachments

## Integration Patterns

**Email Receipt Flow**:
1. SMTP server receives email
2. Parse org_slug from To: address
3. Validate org exists
4. Store raw MIME to object storage
5. Create inbound_message (status=RECEIVED)
6. Enqueue attachment_extraction job
7. Return 250 OK

**Attachment Extraction Worker**:
1. Load inbound_message
2. Retrieve raw MIME from storage
3. Parse MIME, extract attachments
4. Store each attachment to object storage
5. Create document records
6. Update inbound_message status=PARSED
7. Enqueue extraction jobs for each document
