# SMTP Ingest - Email Processing Workflow

This document describes the email ingestion workflow for OrderFlow, including setup, configuration, and operational details.

## Overview

OrderFlow receives purchase orders via email using a dedicated SMTP server. The system uses **plus-addressing** for multi-tenant routing, automatically parsing and extracting attachments from incoming emails.

**Email Address Format**: `orders+<org_slug>@orderflow.example.com`

Example:
- Organization "ACME GmbH" with slug `acme` receives emails at: `orders+acme@orderflow.example.com`
- Organization "Test Org" with slug `test-org` receives emails at: `orders+test-org@orderflow.example.com`

## Architecture

```
┌─────────────────┐
│  Email Client   │
└────────┬────────┘
         │ SMTP
         ▼
┌─────────────────────────────────────────────────────────────┐
│  OrderFlow SMTP Server (aiosmtpd)                           │
│  - Receives email                                            │
│  - Extracts org_slug from plus-addressing                   │
│  - Validates organization exists                            │
│  - Stores raw MIME to object storage                        │
│  - Creates inbound_message record                           │
│  - Enqueues attachment extraction job                       │
└────────┬────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  PostgreSQL: inbound_message table                          │
│  - org_id, source='EMAIL', source_message_id                │
│  - from_email, to_email, subject                            │
│  - raw_storage_key, status='RECEIVED'                       │
│  - Unique constraint prevents duplicate Message-IDs         │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Celery Worker: Attachment Extraction                       │
│  1. Retrieve raw MIME from object storage                   │
│  2. Parse MIME message                                       │
│  3. Extract all file attachments                            │
│  4. Store each attachment to object storage                 │
│  5. Create document record for each attachment              │
│  6. Update inbound_message.status = 'PARSED'                │
└────────┬────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Documents ready for extraction pipeline                    │
└─────────────────────────────────────────────────────────────┘
```

## Email Processing Flow

### 1. Email Receipt (SMTP Handler)

When an email arrives at `orders+acme@orderflow.example.com`:

1. **Plus-addressing parsing**: Extract `acme` from recipient address
2. **Organization validation**: Query database for org with slug `acme`
3. **MIME parsing**: Extract Message-ID, From, To, Subject headers
4. **Raw storage**: Store complete email (MIME format) to S3/MinIO
5. **Database record**: Create `inbound_message` with status `RECEIVED`
6. **Job enqueueing**: Trigger background attachment extraction

**SMTP Response Codes**:
- `250 Message accepted` - Success
- `250 Message accepted (duplicate)` - Duplicate Message-ID (idempotent)
- `550 Unknown recipient organization` - Invalid org slug
- `451 Temporary server error` - Processing failure (sender will retry)

### 2. Attachment Extraction (Background Worker)

Celery task `extract_attachments_task` processes the email:

1. **Retrieve raw email**: Download MIME from object storage
2. **Parse MIME tree**: Walk multipart structure to find attachments
3. **Filter attachments**: Skip inline images, process only file attachments
4. **Store attachments**: Upload each to S3/MinIO with SHA256 deduplication
5. **Create documents**: Generate `document` record for each attachment
6. **Update status**: Set `inbound_message.status = 'PARSED'`

**Supported attachment types**:
- PDF: `application/pdf`
- Excel: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- CSV: `text/csv`
- ZIP: `application/zip` (stored as-is, not extracted)

### 3. Deduplication

**Email-level deduplication** (prevents duplicate processing):
- Unique constraint: `(org_id, source='EMAIL', source_message_id)`
- Same Message-ID header sent twice → second email returns `250` but is not processed
- Deduplication is **org-scoped**: same email to different orgs is allowed

**Missing Message-ID**: If email lacks Message-ID header (malformed), system generates synthetic ID:
```python
hash = SHA256(from_email + to_email + subject + date)
message_id = f"<synthetic-{hash[:16]}@orderflow.generated>"
```

### 4. State Machine

`InboundMessage.status` follows this state machine:

```
None → RECEIVED → STORED → PARSED (success)
          ↓         ↓
        FAILED ← FAILED (error)
```

States:
- `RECEIVED`: Email accepted, raw MIME stored
- `STORED`: Raw MIME persisted to object storage
- `PARSED`: Attachments extracted, documents created (terminal success)
- `FAILED`: Processing error (terminal failure)

## Configuration

### Environment Variables

Add to `.env`:

```bash
# SMTP Configuration
SMTP_HOST=0.0.0.0
SMTP_PORT=25
SMTP_DOMAIN=orderflow.example.com
SMTP_MAX_MESSAGE_SIZE=26214400  # 25MB
SMTP_REQUIRE_TLS=false  # true in production

# Database (required)
DATABASE_URL=postgresql://orderflow:password@localhost:5432/orderflow

# Redis (required for Celery)
REDIS_URL=redis://localhost:6379/0

# Object Storage (required)
MINIO_ENDPOINT=localhost:9000
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_BUCKET=orderflow-documents
MINIO_USE_SSL=false
```

### Docker Compose

SMTP server runs as dedicated service:

```yaml
smtp_ingest:
  build:
    context: .
    dockerfile: smtp_ingest.Dockerfile
  ports:
    - "25:25"
  environment:
    - DATABASE_URL=${DATABASE_URL}
    - REDIS_URL=${REDIS_URL}
    # ... other env vars
  depends_on:
    - postgres
    - redis
    - minio
  restart: always
```

## Running the SMTP Server

### Development (Standalone)

```bash
# Install dependencies
pip install -r backend/requirements/base.txt
pip install asyncpg  # async database driver

# Set environment variables
export DATABASE_URL="postgresql://orderflow:password@localhost:5432/orderflow"
export REDIS_URL="redis://localhost:6379/0"
export MINIO_ENDPOINT="localhost:9000"
export MINIO_ROOT_USER="minioadmin"
export MINIO_ROOT_PASSWORD="minioadmin"
export MINIO_BUCKET="orderflow-documents"

# Run SMTP server
python backend/scripts/start_smtp_server.py
```

### Production (Docker)

```bash
# Start all services including SMTP
docker-compose up -d

# View SMTP server logs
docker logs -f orderflow_smtp_ingest

# Check SMTP server health
docker ps | grep smtp_ingest
```

## Testing Email Ingestion

### Using Python smtplib

```python
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# Create email
msg = MIMEMultipart()
msg['From'] = 'supplier@example.com'
msg['To'] = 'orders+acme@orderflow.example.com'
msg['Subject'] = 'Purchase Order PO-2024-001'

# Add body
msg.attach(MIMEText('Please find attached purchase order.', 'plain'))

# Attach PDF
with open('order.pdf', 'rb') as f:
    attachment = MIMEApplication(f.read(), _subtype='pdf')
    attachment.add_header('Content-Disposition', 'attachment', filename='order.pdf')
    msg.attach(attachment)

# Send email
with smtplib.SMTP('localhost', 25) as server:
    server.send_message(msg)
    print("Email sent successfully")
```

### Using Telnet

```bash
telnet localhost 25
HELO test
MAIL FROM: <supplier@example.com>
RCPT TO: <orders+acme@orderflow.example.com>
DATA
From: supplier@example.com
To: orders+acme@orderflow.example.com
Subject: Test Order

Test message body
.
QUIT
```

### Using Email Clients

Configure your email client (Thunderbird, Outlook, etc.) to send via:
- **SMTP Server**: localhost (or your server IP)
- **Port**: 25
- **Security**: None (TLS disabled for local testing)
- **Authentication**: None required

## Monitoring and Logs

### SMTP Server Logs

```bash
# View SMTP server logs
docker logs -f orderflow_smtp_ingest

# Example log output:
# 2026-01-04 14:30:12 - INFO - Received email: from=supplier@example.com, to=orders+acme@orderflow.example.com, size=45123 bytes
# 2026-01-04 14:30:12 - INFO - Created inbound_message: id=550e8400-e29b-41d4-a716-446655440000, org=acme, message_id=<abc123@example.com>
# 2026-01-04 14:30:12 - INFO - Enqueued attachment extraction for message 550e8400-e29b-41d4-a716-446655440000
```

### Worker Logs

```bash
# View Celery worker logs
docker logs -f orderflow_worker

# Example log output:
# 2026-01-04 14:30:15 - INFO - Processing inbound_message 550e8400-e29b-41d4-a716-446655440000 for org acme
# 2026-01-04 14:30:15 - INFO - Extracted 2 attachments from message
# 2026-01-04 14:30:16 - INFO - Created document ... for attachment order.pdf (45123 bytes)
```

### Database Queries

```sql
-- Check recent inbound messages
SELECT id, org_id, from_email, subject, status, received_at
FROM inbound_message
WHERE org_id = '<org_uuid>'
ORDER BY received_at DESC
LIMIT 10;

-- Check processing status
SELECT status, COUNT(*)
FROM inbound_message
GROUP BY status;

-- Find failed messages
SELECT id, from_email, subject, error_json, received_at
FROM inbound_message
WHERE status = 'FAILED'
ORDER BY received_at DESC;
```

## Troubleshooting

### Email not received

**Symptom**: Email sent but no log entry

1. Check SMTP server is running: `docker ps | grep smtp_ingest`
2. Check port 25 is accessible: `telnet localhost 25`
3. Check firewall rules allow SMTP traffic
4. Review SMTP server logs for connection errors

### Email rejected with "550 Unknown recipient"

**Symptom**: SMTP returns `550 Unknown recipient organization`

1. Verify org slug exists: `SELECT slug FROM org WHERE slug = 'acme';`
2. Check plus-addressing format: `orders+<slug>@domain`
3. Ensure slug matches exactly (case-sensitive, kebab-case)

### Duplicate email warning

**Symptom**: SMTP returns `250 Message accepted (duplicate)`

This is **expected behavior** for idempotent deduplication:
- Same Message-ID sent twice to same org
- Second email logged but not processed
- Prevents duplicate draft orders

### Attachment extraction fails

**Symptom**: `inbound_message.status = 'FAILED'`

1. Check `error_json` field: `SELECT error_json FROM inbound_message WHERE status = 'FAILED';`
2. Common causes:
   - Object storage unavailable (MinIO down)
   - MIME parsing error (malformed email)
   - Attachment too large
3. Retry manually: Re-enqueue extraction task for failed message

### No attachments extracted

**Symptom**: `status = 'PARSED'` but no documents created

1. Check email has file attachments (not inline images)
2. Verify Content-Disposition header: `attachment` (not `inline`)
3. Review MIME parser logs for skipped parts

## Security Considerations

### Production Deployment

For production, enable additional security:

1. **TLS/SSL**: Enable `SMTP_REQUIRE_TLS=true`
2. **Authentication**: Add SMTP AUTH (not implemented in MVP)
3. **SPF/DKIM/DMARC**: Validate sender authenticity
4. **Rate limiting**: Limit emails per sender/org
5. **Network security**: Firewall rules, VPN access
6. **Virus scanning**: Scan attachments before storage

### Email Spoofing

Current MVP does **not validate sender authenticity**. For production:
- Implement SPF/DKIM/DMARC checks
- Whitelist known supplier email domains
- Require authenticated SMTP connections

## Performance

**Benchmarks** (expected):
- Email receipt: <2 seconds (P95)
- Attachment extraction: <5 seconds per email (P95)
- Concurrent connections: 100+ simultaneous SMTP sessions
- Throughput: 1000+ emails per day per org

**Scaling**:
- Horizontal scaling: Run multiple SMTP server instances behind load balancer
- Worker scaling: Add more Celery workers for attachment extraction
- Database optimization: Indexes on `(org_id, received_at)` for fast queries

## Future Enhancements

- [ ] SMTP authentication (AUTH PLAIN, AUTH LOGIN)
- [ ] TLS/SSL support (STARTTLS)
- [ ] SPF/DKIM/DMARC validation
- [ ] Virus/malware scanning (ClamAV integration)
- [ ] Email threading (conversation tracking)
- [ ] Auto-reply messages ("Order received")
- [ ] Bounce handling
- [ ] Email size limits and quotas
- [ ] Connection rate limiting
- [ ] Prometheus metrics export
- [ ] OpenTelemetry distributed tracing

## References

- **SSOT Reference**: §3.3-3.4 (SMTP Ingest), §5.4.5 (inbound_message table)
- **Specification**: `specs/006-smtp-ingest/spec.md`
- **Implementation Plan**: `specs/006-smtp-ingest/plan.md`
- **Tasks**: `specs/006-smtp-ingest/tasks.md`
- **RFC 5321**: Simple Mail Transfer Protocol
- **RFC 5322**: Internet Message Format
- **RFC 2047**: MIME Encoded-Word syntax
