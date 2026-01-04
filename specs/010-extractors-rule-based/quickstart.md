# Quickstart: Rule-Based Extractors

**Feature**: 010-extractors-rule-based
**Date**: 2025-12-27

## Development Environment Setup

### Prerequisites

- Python 3.12+
- PostgreSQL 16+ (with `pg_trgm` extension)
- Redis 7+ (for Celery)
- S3-compatible object storage (MinIO for local dev)
- Docker + Docker Compose (recommended for local services)

### Step 1: Install Python Dependencies

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Core dependencies for this feature:
# - fastapi
# - pydantic
# - sqlalchemy[asyncio]
# - alembic
# - openpyxl  # Excel parsing
# - pdfplumber  # PDF text extraction
# - chardet  # Encoding detection
# - celery[redis]
# - pytest, pytest-asyncio
```

### Step 2: Start Local Services (Docker Compose)

```bash
# From project root
docker-compose up -d postgres redis minio

# Verify services
docker-compose ps
```

**Docker Compose Config** (add to `docker-compose.yml`):
```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: orderflow_dev
      POSTGRES_USER: orderflow
      POSTGRES_PASSWORD: dev_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data

volumes:
  postgres_data:
  minio_data:
```

### Step 3: Database Migrations

```bash
cd backend

# Create initial migration for extraction_run table
alembic revision --autogenerate -m "Add extraction_run and document extensions"

# Review migration file in alembic/versions/

# Apply migration
alembic upgrade head

# Verify tables created
psql -h localhost -U orderflow -d orderflow_dev -c "\dt"
```

### Step 4: Configure Environment Variables

Create `backend/.env`:
```env
# Database
DATABASE_URL=postgresql://orderflow:dev_password@localhost:5432/orderflow_dev

# Redis
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# S3 (MinIO)
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin
S3_BUCKET_DOCUMENTS=orderflow-documents-dev
S3_BUCKET_EXTRACTED_TEXT=orderflow-extracted-text-dev

# Feature flags
ENABLE_RULE_BASED_EXTRACTION=true
```

### Step 5: Run Celery Worker

```bash
# Terminal 1: Start Celery worker
cd backend
celery -A src.workers.celery_app worker --loglevel=info --queue=extraction

# You should see:
# [tasks]
#   . src.workers.extraction_worker.extract_document_rule_based
```

### Step 6: Run FastAPI Server

```bash
# Terminal 2: Start API server
cd backend
uvicorn src.main:app --reload --port 8000

# API available at http://localhost:8000
# API docs at http://localhost:8000/docs
```

## Running Tests

### Unit Tests

```bash
cd backend

# Run all extraction unit tests
pytest tests/unit/extraction/ -v

# Run specific test file
pytest tests/unit/extraction/test_csv_extractor.py -v

# Run with coverage
pytest tests/unit/extraction/ --cov=src.adapters.extraction --cov-report=html
```

### Integration Tests

```bash
# Integration tests require services running
docker-compose up -d postgres redis minio

# Run integration tests
pytest tests/integration/test_extraction_workflow.py -v

# Full integration test suite
pytest tests/integration/ -v
```

### Test Data

Sample test files are in `backend/tests/fixtures/`:
- `sample_dach.csv`: Semicolon-separated, comma decimal
- `sample_us.csv`: Comma-separated, dot decimal
- `sample_order.xlsx`: Excel with header rows
- `sample_text.pdf`: Text-based PDF order
- `sample_scan.pdf`: Scanned PDF (low text coverage)

## Local Development Workflow

### 1. Upload a Test Document

```bash
# Upload CSV via API
curl -X POST http://localhost:8000/api/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@tests/fixtures/sample_dach.csv" \
  -F "org_id=your-org-uuid"

# Response:
# {
#   "document_id": "123e4567-e89b-12d3-a456-426614174000",
#   "filename": "sample_dach.csv",
#   "mime_type": "text/csv"
# }
```

### 2. Trigger Extraction (Async)

Extraction is triggered automatically via Celery task when document is uploaded.

```bash
# Check extraction status
curl http://localhost:8000/api/extraction-runs/$DOCUMENT_ID/latest \
  -H "Authorization: Bearer $TOKEN"

# Response:
# {
#   "id": "...",
#   "document_id": "...",
#   "extractor_version": "rule_v1",
#   "status": "SUCCEEDED",
#   "lines_extracted": 25,
#   "extraction_confidence": 0.8735,
#   "runtime_ms": 234
# }
```

### 3. View Extraction Results

```bash
# Get canonical extraction output
curl http://localhost:8000/api/extraction-runs/$RUN_ID/output \
  -H "Authorization: Bearer $TOKEN"

# Returns JSON per canonical schema (§7.1)
```

### 4. Debugging

**View Celery Logs**:
```bash
# Worker logs show extraction progress
tail -f logs/celery_worker.log
```

**Check Extraction Metrics**:
```sql
-- Query recent extractions
SELECT
    id,
    extractor_version,
    status,
    lines_extracted,
    extraction_confidence,
    runtime_ms,
    created_at
FROM extraction_run
WHERE org_id = 'your-org-uuid'
ORDER BY created_at DESC
LIMIT 10;

-- Check extraction warnings
SELECT
    id,
    metrics_json->'warnings' AS warnings
FROM extraction_run
WHERE org_id = 'your-org-uuid'
  AND jsonb_array_length(metrics_json->'warnings') > 0;
```

## Common Issues and Solutions

### Issue 1: CSV Encoding Error

**Symptom**: `UnicodeDecodeError` when parsing CSV

**Solution**:
```python
# Use chardet for auto-detection
import chardet

with open(file_path, 'rb') as f:
    raw_data = f.read()
    result = chardet.detect(raw_data)
    encoding = result['encoding']  # e.g., 'windows-1252'

# Parse with detected encoding
df = pd.read_csv(file_path, encoding=encoding)
```

### Issue 2: Excel "No module named 'openpyxl'"

**Symptom**: ImportError when parsing .xlsx

**Solution**:
```bash
pip install openpyxl
```

### Issue 3: PDF Text Extraction Returns Empty String

**Symptom**: `text_coverage_ratio = 0.0` for text-based PDF

**Solution**:
- Check if PDF is actually scanned/image-based (use `pdfplumber` to inspect pages)
- Try alternative library (`PyPDF2`) as fallback
- Verify PDF is not password-protected

### Issue 4: Confidence Score Always 0.0

**Symptom**: All extractions have `extraction_confidence = 0.0`

**Solution**:
- Check if confidence calculation is being called
- Verify per-field confidence scores are being set in extraction output
- Ensure `metrics_json` contains `confidence` object

## Next Steps

After completing local setup:

1. **Run Full Test Suite**: `pytest tests/ -v`
2. **Test with Real Files**: Upload customer order files (anonymized)
3. **Monitor Metrics**: Check extraction_confidence distribution
4. **Tune Thresholds**: Adjust confidence thresholds for LLM fallback (§7.2.2)
5. **Integrate with Draft Orders**: Connect extraction results to Draft creation (Spec 013)

## API Endpoints (for this feature)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/documents/upload` | Upload document, trigger extraction |
| GET | `/api/extraction-runs/{doc_id}/latest` | Get latest extraction run for document |
| GET | `/api/extraction-runs/{run_id}` | Get specific extraction run details |
| GET | `/api/extraction-runs/{run_id}/output` | Get canonical extraction output JSON |
| POST | `/api/extraction-runs/{run_id}/retry` | Retry extraction with different extractor |

See `contracts/extraction-api.yaml` for full OpenAPI spec.
