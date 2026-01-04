# Feature Specification: SMTP Ingest

**Feature Branch**: `006-smtp-ingest`
**Created**: 2025-12-27
**Status**: Draft
**Module**: inbox
**SSOT References**: §3.3-3.4 (SMTP Ingest), §5.2.2 (InboundMessageStatus), §5.4.5 (inbound_message table)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Receive Orders via Email (Priority: P1)

As a customer (buyer), I need to forward my purchase orders via email to OrderFlow so that they can be automatically processed.

**Why this priority**: Email ingestion is the core entry point for OrderFlow. Without it, the entire system cannot receive orders.

**Independent Test**: Can be fully tested by sending an email with PDF attachment to the ingest address, verifying the email is received, stored, and an inbound_message record is created. Delivers the fundamental order intake capability.

**Acceptance Scenarios**:

1. **Given** OrderFlow SMTP server is running, **When** I send an email with a PDF attachment to `orders+acme@orderflow.example.com`, **Then** the email is received and stored
2. **Given** an email is received, **When** the SMTP ingest processes it, **Then** an inbound_message record is created with status=RECEIVED
3. **Given** an email has attachments, **When** the SMTP ingest processes it, **Then** each attachment is extracted and stored as a separate document record
4. **Given** an email has no attachments, **When** the SMTP ingest processes it, **Then** an inbound_message is created but no documents are created (warning logged)

---

### User Story 2 - Plus-Addressing for Org Routing (Priority: P1)

As an OrderFlow administrator, I need emails to be routed to the correct organization based on plus-addressing (e.g., orders+acme@...) so that multi-tenant email ingestion works.

**Why this priority**: Multi-tenant email routing is essential for SaaS deployment. Without it, only single-tenant deployment is possible.

**Independent Test**: Can be tested by sending emails to different plus-addresses (orders+orgA, orders+orgB), verifying each is routed to the correct org_id.

**Acceptance Scenarios**:

1. **Given** organization "acme" has slug "acme", **When** an email is sent to `orders+acme@orderflow.example.com`, **Then** the inbound_message is associated with acme's org_id
2. **Given** an email is sent to an unknown plus-address, **When** the SMTP ingest processes it, **Then** the email is rejected or stored with error status
3. **Given** an email is sent without plus-addressing to `orders@orderflow.example.com`, **When** the SMTP ingest processes it, **Then** the email is rejected with SMTP 550 error 'Unknown recipient'. This fail-safe approach prevents misconfigured forwarding from creating orphan messages. Future: configurable default org routing.

---

### User Story 3 - MIME Parsing and Attachment Extraction (Priority: P1)

As a backend developer, I need the SMTP ingest to parse MIME messages and extract all relevant attachments so that order documents are available for processing.

**Why this priority**: Attachments contain the actual order data. Without proper MIME parsing, the system cannot extract PDF/Excel/CSV files.

**Independent Test**: Can be tested by sending emails with various attachment types, verifying all attachments are extracted and stored in object storage with correct metadata.

**Acceptance Scenarios**:

1. **Given** an email contains a PDF attachment, **When** the SMTP ingest processes it, **Then** the PDF is stored in object storage and a document record is created
2. **Given** an email contains multiple attachments, **When** the SMTP ingest processes it, **Then** all attachments are extracted and stored
3. **Given** an email contains inline images and file attachments, **When** the SMTP ingest processes it, **Then** only file attachments (not inline images) are processed as documents
4. **Given** an email contains a ZIP file, **When** the SMTP ingest processes it, **Then** the ZIP file is stored as-is (not extracted) with Document.mime_type='application/zip'. Extraction of ZIP contents is out of scope for MVP.

---

### User Story 4 - Deduplication of Identical Messages (Priority: P2)

As a system administrator, I need duplicate emails (same Message-ID) to be detected and skipped so that accidental re-forwards don't create duplicate processing.

**Why this priority**: Users sometimes forward the same email multiple times. Deduplication prevents wasted processing and duplicate draft orders.

**Independent Test**: Can be tested by sending the same email (same Message-ID) twice, verifying only the first creates an inbound_message, and the second is skipped with logged warning.

**Acceptance Scenarios**:

1. **Given** an email with Message-ID X was already processed, **When** the same email is sent again, **Then** the SMTP ingest skips it (no duplicate inbound_message)
2. **Given** two different emails with different Message-IDs, **When** both are sent, **Then** both are processed (no false positive deduplication)
3. **Given** deduplication is based on Message-ID and org, **When** the same email is sent to two different orgs, **Then** both orgs receive it (org-scoped deduplication)

---

### Edge Cases

- What happens when an email has no Message-ID header (malformed email)?
- How does the system handle very large emails (>25MB)?
- What happens when attachment extraction fails (corrupt attachment)?
- How does the system handle emails with non-UTF8 characters in subject/body?
- What happens when object storage is unavailable during ingestion?
- How does the system handle emails from blacklisted domains (spam)?
- What happens when the org_slug in plus-address doesn't exist?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST run a dedicated SMTP server that receives emails
- **FR-002**: System MUST support plus-addressing for org routing (orders+{org_slug}@domain)
- **FR-003**: System MUST parse MIME messages and extract metadata (From, To, Subject, Date, Message-ID)
- **FR-004**: System MUST extract all file attachments (excluding inline images) from emails
- **FR-005**: System MUST store raw MIME message in object storage
- **FR-006**: System MUST create inbound_message record with status=RECEIVED for each email
- **FR-007**: System MUST create document records for each extracted attachment
- **FR-008**: System MUST deduplicate emails based on (org_id, source='EMAIL', source_message_id) where source_message_id is the Message-ID header
- **FR-009**: System MUST update inbound_message status through state machine (RECEIVED → STORED → PARSED)
- **FR-010**: System MUST handle SMTP errors gracefully (reject with appropriate SMTP status codes)
- **FR-011**: System MUST support configurable SMTP port and bind address
- **FR-012**: System MUST log all received emails for debugging and audit
- **FR-013**: System MUST handle duplicate Message-IDs idempotently. On duplicate detection: (1) Log at WARN level with Message-ID and org_id, (2) Return SMTP 250 (acceptance) to avoid sender retries, (3) Do NOT create duplicate inbound_message record.
- **FR-014**: System MUST expose Prometheus metrics: smtp_emails_received_total{org_id,status}, smtp_attachment_extraction_duration_ms, smtp_processing_errors_total{org_id,error_type}. All SMTP operations MUST include trace_id and org_id for correlation.

### Key Entities

- **InboundMessage**: Represents a received email or upload event. Tracks source (EMAIL or UPLOAD), sender email, subject, received timestamp, and processing status. Each message can have multiple attached documents.

- **Document**: Represents a file (PDF, Excel, CSV) extracted from an inbound message or directly uploaded. Documents are the primary input to the extraction pipeline.

### Technical Constraints

- **TC-001**: SMTP server MUST use Python aiosmtpd or equivalent async SMTP library
- **TC-002**: MIME parsing MUST handle multipart messages correctly
- **TC-003**: Message-ID deduplication MUST use unique database constraint
- **TC-004**: Raw MIME storage MUST happen before parsing (failure safety)
- **TC-005**: Attachment extraction MUST stream to object storage (not load into memory)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: SMTP server accepts and processes emails in under 5 seconds (P95)
- **SC-002**: 100% of emails with valid attachments result in document records
- **SC-003**: Deduplication prevents 100% of duplicate processing for same Message-ID within org
- **SC-004**: SMTP server handles 100 concurrent connections without dropping emails
- **SC-005**: Zero data loss for received emails (all stored to object storage before ACK)
- **SC-006**: Attachment extraction success rate >99% for valid email formats

### Reliability

- **RE-001**: SMTP server recovers automatically from crashes (systemd/docker restart)
- **RE-002**: Failed attachment extraction does not block email receipt
- **RE-003**: Object storage failure during ingest results in email rejection (not silent failure)
- **RE-004**: SMTP server logs include full traceability (Message-ID → inbound_message.id → document.id)

### Orchestration (E2E Flow)

- **FR-ORQ-001**: After creating document records, SMTP ingest MUST enqueue extraction job: `extract_document(document_id, org_id)` for each extracted attachment. This triggers the extraction pipeline (spec 009).
- **FR-ORQ-002**: InboundMessage.source='EMAIL' distinguishes email-originated documents from uploads (source='UPLOAD'). The downstream extraction pipeline (spec 009) processes both sources identically.
- **FR-ORQ-003**: E2E flow: Email received → MIME parsed → attachments stored → documents created → extraction jobs enqueued → (spec 009 takes over). No manual intervention for happy path.

## Dependencies

- **Depends on**: 001-platform-foundation (database, org table)
- **Depends on**: 003-tenancy-isolation (org_id routing from plus-address)
- **Depends on**: 005-object-storage (file storage for MIME and attachments)
- **Dependency reason**: Email ingestion requires org routing and file storage infrastructure
- **Triggers**: 009-extraction-core (via enqueued extraction jobs)

## Implementation Notes

### SMTP Server Architecture

Use **aiosmtpd** for async SMTP handling:

```python
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import SMTP
from email import message_from_bytes
import email.policy

class OrderFlowSMTPHandler:
    async def handle_DATA(self, server, session, envelope):
        """
        Called when SMTP client sends DATA command (email content)
        """
        try:
            # Parse MIME message
            msg = message_from_bytes(
                envelope.content,
                policy=email.policy.default
            )

            # Extract org from recipient (plus-addressing)
            to_email = envelope.rcpt_tos[0]  # orders+acme@orderflow.example.com
            org_slug = extract_org_slug(to_email)

            # Validate org exists
            org = await get_org_by_slug(org_slug)
            if not org:
                return '550 Unknown recipient organization'

            # Store raw MIME
            raw_storage_key = await store_raw_mime(envelope.content, org.id)

            # Create inbound_message
            inbound_msg = await create_inbound_message(
                org_id=org.id,
                from_email=envelope.mail_from,
                to_email=to_email,
                subject=msg.get('Subject', ''),
                message_id=msg.get('Message-ID'),
                raw_storage_key=raw_storage_key
            )

            # Enqueue attachment extraction job
            await enqueue_attachment_extraction(inbound_msg.id)

            return '250 Message accepted'

        except Exception as e:
            logger.error(f"SMTP ingestion failed: {e}")
            return '451 Temporary server error'

# Start SMTP server
controller = Controller(
    OrderFlowSMTPHandler(),
    hostname='0.0.0.0',
    port=25
)
controller.start()
```

### Plus-Addressing Parser

```python
import re

def extract_org_slug(email_address: str) -> Optional[str]:
    """
    Extract org slug from plus-addressed email.

    orders+acme@orderflow.example.com -> "acme"
    orders@orderflow.example.com -> None (or default org)
    """
    match = re.match(r'^[^+]+\+([^@]+)@', email_address)
    if match:
        return match.group(1)
    return None
```

### InboundMessage Table Schema (SSOT §5.4.5)

```sql
CREATE TABLE inbound_message (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES org(id),
  source TEXT NOT NULL CHECK (source IN ('EMAIL', 'UPLOAD')),
  source_message_id TEXT,  -- Email Message-ID or upload correlation ID
  from_email CITEXT,
  to_email CITEXT,
  subject TEXT,
  received_at TIMESTAMPTZ NOT NULL,
  raw_storage_key TEXT,  -- Object storage key for raw MIME
  status TEXT NOT NULL,  -- InboundMessageStatus enum
  error_json JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (org_id, source, source_message_id) WHERE source_message_id IS NOT NULL
);

CREATE INDEX idx_inbound_org_received ON inbound_message(org_id, received_at DESC);
CREATE INDEX idx_inbound_org_status ON inbound_message(org_id, status);
```

### InboundMessageStatus State Machine (SSOT §5.2.2)

```python
class InboundMessageStatus(str, Enum):
    RECEIVED = "RECEIVED"  # Email received, raw MIME stored
    STORED = "STORED"      # Raw MIME persisted
    PARSED = "PARSED"      # Attachments extracted
    FAILED = "FAILED"      # Processing failed

# State transitions
ALLOWED_TRANSITIONS = {
    None: [InboundMessageStatus.RECEIVED],
    InboundMessageStatus.RECEIVED: [InboundMessageStatus.STORED, InboundMessageStatus.FAILED],
    InboundMessageStatus.STORED: [InboundMessageStatus.PARSED, InboundMessageStatus.FAILED],
    InboundMessageStatus.PARSED: [],  # Terminal success state
    InboundMessageStatus.FAILED: []   # Terminal failure state
}
```

### Attachment Extraction Worker

```python
from celery import task
from email import message_from_bytes
import email.policy

@task
async def extract_attachments(inbound_message_id: UUID):
    """
    Background job to extract attachments from inbound message.
    """
    # Load inbound message
    inbound_msg = await get_inbound_message(inbound_message_id)

    # Retrieve raw MIME from storage
    raw_mime = await object_storage.retrieve_file(inbound_msg.raw_storage_key)

    # Parse MIME
    msg = message_from_bytes(raw_mime.read(), policy=email.policy.default)

    # Update status
    await update_inbound_message_status(inbound_msg.id, InboundMessageStatus.STORED)

    # Extract attachments
    document_ids = []
    for part in msg.walk():
        # Skip non-attachment parts
        if part.get_content_maintype() == 'multipart':
            continue
        if part.get('Content-Disposition') is None:
            continue

        filename = part.get_filename()
        if not filename:
            continue

        # Skip inline images
        if part.get_content_disposition() == 'inline':
            continue

        # Extract attachment
        content = part.get_payload(decode=True)
        mime_type = part.get_content_type()

        # Store in object storage
        stored_file = await object_storage.store_file(
            file=io.BytesIO(content),
            org_id=inbound_msg.org_id,
            filename=filename,
            mime_type=mime_type
        )

        # Create document record
        document = await create_document(
            org_id=inbound_msg.org_id,
            inbound_message_id=inbound_msg.id,
            file_name=filename,
            mime_type=mime_type,
            size_bytes=stored_file.size_bytes,
            sha256=stored_file.sha256,
            storage_key=stored_file.storage_key,
            status=DocumentStatus.STORED
        )

        document_ids.append(document.id)

    # Update status
    await update_inbound_message_status(inbound_msg.id, InboundMessageStatus.PARSED)

    # Enqueue extraction jobs for each document
    for doc_id in document_ids:
        await enqueue_document_extraction(doc_id)
```

### Deduplication Logic

```sql
-- Unique constraint prevents duplicate processing
UNIQUE (org_id, source, source_message_id) WHERE source_message_id IS NOT NULL

-- Attempt to insert duplicate will fail with:
-- psycopg2.errors.UniqueViolation: duplicate key value violates unique constraint
```

```python
async def create_inbound_message(...):
    try:
        inbound_msg = InboundMessage(...)
        session.add(inbound_msg)
        await session.commit()
        return inbound_msg
    except IntegrityError as e:
        if 'unique constraint' in str(e):
            logger.warning(f"Duplicate message {source_message_id} for org {org_id}")
            # Return existing message or None
            return None
        raise
```

### Configuration

```bash
# .env
SMTP_HOST=0.0.0.0
SMTP_PORT=25
SMTP_DOMAIN=orderflow.example.com
SMTP_MAX_MESSAGE_SIZE=26214400  # 25MB
SMTP_REQUIRE_TLS=false  # true in production
```

### Docker Compose Integration

```yaml
services:
  smtp_ingest:
    build:
      context: .
      dockerfile: smtp_ingest.Dockerfile
    ports:
      - "25:25"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - OBJECT_STORAGE_ENDPOINT=${OBJECT_STORAGE_ENDPOINT}
    depends_on:
      - postgres
      - redis
      - minio
    restart: always
```

### Supported MIME Types (Attachments)

- `application/pdf` - PDF documents
- `application/vnd.ms-excel` - Excel (.xls)
- `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` - Excel (.xlsx)
- `text/csv` - CSV files
- `application/zip` - ZIP archives (store as-is for MVP)

### Email Parsing Edge Cases

1. **No Message-ID**: Generate synthetic ID from hash of (From, To, Subject, Date)
2. **Malformed MIME**: Log error, store raw email, mark status=FAILED
3. **No attachments**: Create inbound_message but no documents, log warning
4. **Nested multipart**: Walk entire MIME tree to find all attachments
5. **Encoded filenames**: Decode RFC 2047 encoded filenames (=?UTF-8?B?...)

## Out of Scope

- SMTP authentication (accept all for MVP, rely on network security)
- TLS/SSL support (add in production)
- SPF/DKIM/DMARC validation (add for production)
- Spam filtering
- Virus/malware scanning
- Email size limits beyond basic validation
- Bounce handling
- Auto-reply messages
- Email threading (conversation tracking)
- Full-text search on email body (extract attachments only)
- Support for non-standard email formats
- Inline image processing
- ZIP file extraction (store as-is)
- Email forwarding/routing to other systems
- Email retention policies (covered by general document retention)

## Testing Strategy

### Unit Tests
- Plus-addressing parsing (valid, invalid, missing)
- Org slug extraction from email address
- Message-ID extraction from headers
- Deduplication key generation
- Status state machine transitions
- MIME type validation

### Integration Tests
- Send email to SMTP server, verify inbound_message created
- Send email with PDF attachment, verify document created
- Send email with multiple attachments, verify all extracted
- Send duplicate email (same Message-ID), verify only first processed
- Send email to unknown org slug, verify rejection
- Send email with no attachments, verify inbound_message created but no documents
- Send email with inline image, verify not processed as document
- Send malformed email, verify error handling
- Object storage failure during ingest, verify email rejected

### SMTP Protocol Tests
- Connect to SMTP server and send valid email
- Test SMTP response codes (250, 451, 550)
- Test concurrent connections (10+ simultaneous)
- Test large email (near size limit)
- Test email with invalid encoding

### Attachment Extraction Tests
- Extract PDF attachment
- Extract Excel (.xlsx) attachment
- Extract CSV attachment
- Extract ZIP attachment (store as-is)
- Extract attachment with Unicode filename
- Extract attachment with encoded filename (RFC 2047)
- Extract nested multipart attachments
- Handle corrupt attachment gracefully

### Deduplication Tests
- Send same email twice to same org (should deduplicate)
- Send same email to different orgs (should NOT deduplicate)
- Send different emails with same subject (should NOT deduplicate)
- Test Message-ID collision handling

### Performance Tests
- Process 100 emails concurrently
- Process email with 10 attachments
- Process 25MB email (max size)
- SMTP response time <5 seconds (P95)
- Attachment extraction throughput (attachments per second)

### Reliability Tests
- SMTP server restart (no lost emails)
- Database connection failure (reject email)
- Object storage failure (reject email)
- Redis failure (queue email for retry)
- Worker crash during attachment extraction (job retry)
