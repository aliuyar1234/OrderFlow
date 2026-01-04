# Quickstart: Object Storage

**Feature**: 005-object-storage
**Prerequisites**: Docker, Python 3.12, PostgreSQL 16

## Development Setup

### 1. Start MinIO (Local S3)

```bash
# Using docker-compose
cd D:\Projekte\OrderFlow

# Add MinIO service to docker-compose.yml (if not already present)
docker-compose up -d minio

# MinIO Console: http://localhost:9001
# Access Key: minioadmin
# Secret Key: minioadmin
```

**docker-compose.yml snippet**:
```yaml
services:
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"  # S3 API
      - "9001:9001"  # Console UI
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  minio_data:
```

### 2. Create MinIO Bucket

```bash
# Install MinIO client (mc)
wget https://dl.min.io/client/mc/release/windows-amd64/mc.exe
# Or use Docker:
docker run --rm --network host minio/mc alias set local http://localhost:9000 minioadmin minioadmin

# Create bucket
docker run --rm --network host minio/mc mb local/orderflow-documents

# Verify bucket
docker run --rm --network host minio/mc ls local/
```

### 3. Configure Environment Variables

```bash
# .env (backend directory)
OBJECT_STORAGE_ENDPOINT=http://localhost:9000
OBJECT_STORAGE_ACCESS_KEY=minioadmin
OBJECT_STORAGE_SECRET_KEY=minioadmin
OBJECT_STORAGE_BUCKET=orderflow-documents
OBJECT_STORAGE_REGION=us-east-1
```

### 4. Install Python Dependencies

```bash
cd backend

# Install boto3 for S3 interaction
pip install boto3==1.34.34

# Install optional preview dependencies (for PDF preview generation)
pip install pdf2image==1.16.3 Pillow==10.2.0

# Or use requirements.txt
pip install -r requirements.txt
```

**requirements.txt** (add these lines):
```
boto3==1.34.34
pdf2image==1.16.3
Pillow==10.2.0
```

### 5. Run Database Migrations

```bash
# Create migration for document table
alembic revision -m "Add document table for object storage"

# Edit migration file (see data-model.md for migration script)

# Apply migration
alembic upgrade head
```

### 6. Verify Setup

```bash
# Test S3 connection
python -c "
import boto3
import os

s3 = boto3.client(
    's3',
    endpoint_url=os.getenv('OBJECT_STORAGE_ENDPOINT'),
    aws_access_key_id=os.getenv('OBJECT_STORAGE_ACCESS_KEY'),
    aws_secret_access_key=os.getenv('OBJECT_STORAGE_SECRET_KEY')
)

# List buckets
buckets = s3.list_buckets()
print('Buckets:', [b['Name'] for b in buckets['Buckets']])
"
```

---

## Usage Examples

### Store a File

```python
from src.infrastructure.storage.s3_storage_adapter import S3StorageAdapter
from uuid import UUID
import io

# Initialize adapter
storage = S3StorageAdapter(
    endpoint_url='http://localhost:9000',
    access_key='minioadmin',
    secret_key='minioadmin',
    bucket_name='orderflow-documents'
)

# Store file
org_id = UUID('a1b2c3d4-e5f6-7890-abcd-ef1234567890')

with open('order.pdf', 'rb') as f:
    stored_file = await storage.store_file(
        file=f,
        org_id=org_id,
        filename='order.pdf',
        mime_type='application/pdf'
    )

print(f"Stored at: {stored_file.storage_key}")
print(f"SHA256: {stored_file.sha256}")
print(f"Size: {stored_file.size_bytes} bytes")
```

### Retrieve a File

```python
# Retrieve file
file_content = await storage.retrieve_file(stored_file.storage_key)

# Save to disk
with open('downloaded_order.pdf', 'wb') as f:
    f.write(file_content.read())
```

### Generate Presigned URL

```python
# Generate presigned URL (valid for 1 hour)
download_url = await storage.generate_presigned_url(
    storage_key=stored_file.storage_key,
    expires_in_seconds=3600
)

print(f"Download URL: {download_url}")
# User can download directly from this URL without authentication
```

### Check if File Exists

```python
exists = await storage.file_exists(stored_file.storage_key)
print(f"File exists: {exists}")
```

---

## Testing

### Run Unit Tests

```bash
cd backend

# Test storage key generation
pytest tests/unit/storage/test_storage_key_generation.py -v

# Test SHA256 calculation
pytest tests/unit/storage/test_sha256_calculation.py -v

# Test deduplication logic
pytest tests/unit/storage/test_deduplication.py -v
```

### Run Integration Tests

```bash
# Test S3 adapter with MinIO
pytest tests/integration/storage/test_s3_adapter_minio.py -v

# Run all storage tests
pytest tests/ -k storage -v
```

### Integration Test Example

```python
# tests/integration/storage/test_s3_adapter_minio.py
import pytest
from src.infrastructure.storage.s3_storage_adapter import S3StorageAdapter
from uuid import uuid4
import io

@pytest.fixture
def storage():
    return S3StorageAdapter(
        endpoint_url='http://localhost:9000',
        access_key='minioadmin',
        secret_key='minioadmin',
        bucket_name='orderflow-documents-test'
    )

@pytest.mark.asyncio
async def test_store_and_retrieve_file(storage):
    """Test round-trip: store → retrieve → verify"""
    org_id = uuid4()
    content = b"Test PDF content"

    # Store file
    stored = await storage.store_file(
        file=io.BytesIO(content),
        org_id=org_id,
        filename='test.pdf',
        mime_type='application/pdf'
    )

    assert stored.storage_key is not None
    assert stored.sha256 is not None
    assert stored.size_bytes == len(content)

    # Retrieve file
    retrieved = await storage.retrieve_file(stored.storage_key)
    retrieved_content = retrieved.read()

    assert retrieved_content == content

@pytest.mark.asyncio
async def test_deduplication(storage):
    """Test same file uploaded twice → single storage copy"""
    org_id = uuid4()
    content = b"Duplicate test content"

    # Upload first time
    stored1 = await storage.store_file(
        file=io.BytesIO(content),
        org_id=org_id,
        filename='duplicate.pdf',
        mime_type='application/pdf'
    )

    # Upload second time (same content)
    stored2 = await storage.store_file(
        file=io.BytesIO(content),
        org_id=org_id,
        filename='duplicate.pdf',
        mime_type='application/pdf'
    )

    # Same storage key (deduplicated)
    assert stored1.storage_key == stored2.storage_key
    assert stored1.sha256 == stored2.sha256
```

---

## Common Issues

### Issue: "NoSuchBucket" error

**Cause**: Bucket doesn't exist in MinIO

**Solution**:
```bash
# Create bucket using mc
docker run --rm --network host minio/mc mb local/orderflow-documents
```

### Issue: "Access Denied" error

**Cause**: Incorrect credentials or bucket policy

**Solution**:
```bash
# Verify credentials
docker run --rm --network host minio/mc admin info local

# Check bucket policy
docker run --rm --network host minio/mc anonymous get local/orderflow-documents
```

### Issue: Connection refused to localhost:9000

**Cause**: MinIO not running

**Solution**:
```bash
# Start MinIO
docker-compose up -d minio

# Check MinIO logs
docker-compose logs minio
```

### Issue: SHA256 mismatch on retrieval

**Cause**: File corruption during upload or storage

**Solution**:
```python
# Verify SHA256 on retrieval
import hashlib

retrieved = await storage.retrieve_file(storage_key)
content = retrieved.read()

calculated_sha256 = hashlib.sha256(content).hexdigest()
assert calculated_sha256 == expected_sha256
```

---

## Production Deployment

### Switch to AWS S3

```bash
# .env (production)
OBJECT_STORAGE_ENDPOINT=  # Leave empty for AWS S3
OBJECT_STORAGE_ACCESS_KEY=<AWS_ACCESS_KEY>
OBJECT_STORAGE_SECRET_KEY=<AWS_SECRET_KEY>
OBJECT_STORAGE_BUCKET=orderflow-documents-prod
OBJECT_STORAGE_REGION=eu-central-1
```

**No code changes required** — boto3 automatically uses AWS S3 when `endpoint_url` is empty.

### Create S3 Bucket

```bash
# Using AWS CLI
aws s3 mb s3://orderflow-documents-prod --region eu-central-1

# Enable versioning (optional but recommended)
aws s3api put-bucket-versioning \
  --bucket orderflow-documents-prod \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket orderflow-documents-prod \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'

# Block public access
aws s3api put-public-access-block \
  --bucket orderflow-documents-prod \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

### IAM Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:HeadObject"
      ],
      "Resource": "arn:aws:s3:::orderflow-documents-prod/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:HeadBucket"
      ],
      "Resource": "arn:aws:s3:::orderflow-documents-prod"
    }
  ]
}
```

---

## Monitoring

### Check Storage Usage

```bash
# MinIO
docker run --rm --network host minio/mc du local/orderflow-documents

# AWS S3
aws s3 ls s3://orderflow-documents-prod --recursive --summarize
```

### Monitor Upload/Download Metrics

```python
# Log metrics in storage adapter
import logging
import time

logger = logging.getLogger(__name__)

async def store_file(self, file, org_id, filename, mime_type):
    start = time.time()

    # ... store file logic ...

    elapsed_ms = (time.time() - start) * 1000

    logger.info(
        "File stored",
        extra={
            "storage_key": storage_key,
            "size_bytes": size_bytes,
            "elapsed_ms": elapsed_ms,
            "org_id": str(org_id)
        }
    )
```

---

## Next Steps

1. Implement upload API endpoint (spec 007-document-upload)
2. Implement document extraction worker (spec 009-extraction-core)
3. Add preview generation (optional, P2)
4. Configure S3 lifecycle policies for archival
5. Set up CloudFront CDN for downloads (production optimization)
