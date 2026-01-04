# Quickstart: SMTP Ingest

**Feature**: 006-smtp-ingest | **Prerequisites**: Docker, Python 3.12, PostgreSQL, MinIO

## Development Setup

### 1. Install Dependencies

```bash
cd backend
pip install aiosmtpd==1.4.4.post2
```

### 2. Configure Environment

```bash
# .env
SMTP_HOST=0.0.0.0
SMTP_PORT=25
SMTP_DOMAIN=orderflow.local
SMTP_MAX_MESSAGE_SIZE=26214400  # 25MB
```

### 3. Run SMTP Server

```bash
# Development: Run standalone SMTP server
python -m src.infrastructure.ingest.smtp_server

# Or via Docker Compose
docker-compose up smtp_ingest
```

**docker-compose.yml**:
```yaml
services:
  smtp_ingest:
    build:
      context: ./backend
      dockerfile: smtp_ingest.Dockerfile
    ports:
      - "25:25"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - OBJECT_STORAGE_ENDPOINT=${OBJECT_STORAGE_ENDPOINT}
      - SMTP_PORT=25
    depends_on:
      - postgres
      - redis
      - minio
```

### 4. Test Email Ingestion

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

# Create test email
msg = MIMEMultipart()
msg['From'] = 'buyer@customer.com'
msg['To'] = 'orders+acme@orderflow.local'
msg['Subject'] = 'Test Order PO-12345'

# Add text body
msg.attach(MIMEText('Please process this order', 'plain'))

# Add PDF attachment
with open('test_order.pdf', 'rb') as f:
    attachment = MIMEApplication(f.read(), _subtype='pdf')
    attachment.add_header('Content-Disposition', 'attachment', filename='order.pdf')
    msg.attach(attachment)

# Send email
with smtplib.SMTP('localhost', 25) as server:
    server.send_message(msg)
    print("Email sent successfully")
```

### 5. Verify Email Receipt

```sql
-- Check inbound_message created
SELECT id, from_email, subject, status, received_at
FROM inbound_message
ORDER BY received_at DESC
LIMIT 5;

-- Check documents created (after attachment extraction)
SELECT d.id, d.file_name, d.status, im.subject
FROM document d
JOIN inbound_message im ON d.inbound_message_id = im.id
ORDER BY d.created_at DESC
LIMIT 5;
```

## Usage Examples

### Send Email with Plus-Addressing

```bash
# Email to org "acme"
echo "Order content" | mail -s "Test Order" -a order.pdf orders+acme@orderflow.local

# Email to org "widgets-inc"
echo "Order content" | mail -s "Test Order" -a order.xlsx orders+widgets-inc@orderflow.local
```

### Monitor SMTP Logs

```bash
# Docker logs
docker-compose logs -f smtp_ingest

# Look for:
# - "Email received from buyer@customer.com"
# - "Org routed: acme (UUID)"
# - "Raw MIME stored: {storage_key}"
# - "Attachment extraction enqueued"
```

## Testing

```bash
# Unit tests
pytest tests/unit/ingest/test_plus_addressing.py -v
pytest tests/unit/ingest/test_mime_parsing.py -v

# Integration tests
pytest tests/integration/ingest/test_smtp_server.py -v
```

## Common Issues

### Port 25 already in use
**Solution**: Change SMTP_PORT to 2525 for dev

### Email rejected: Unknown org
**Cause**: org_slug doesn't match any org in database
**Solution**: Create org with matching slug first

### Attachments not extracted
**Cause**: Celery worker not running
**Solution**: Start worker: `celery -A src.workers worker -l info`
