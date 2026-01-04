# Quickstart: Extraction Core

**Feature**: 009-extraction-core | **Prerequisites**: Python 3.12, PostgreSQL, MinIO, Celery

## Development Setup

### 1. Install Dependencies

```bash
cd backend
pip install openpyxl==3.1.2
pip install pandas==2.1.4
pip install pdfplumber==0.11.0
```

### 2. Run Database Migration

```bash
alembic revision -m "Add extraction_run table"
alembic upgrade head
```

### 3. Start Celery Worker

```bash
celery -A src.workers worker -l info
```

### 4. Trigger Extraction

```python
from src.workers.extraction_worker import extract_document
from uuid import UUID

# Enqueue extraction job
extract_document.delay(
    document_id=str(UUID('...')),
    org_id=str(UUID('...'))
)
```

## Usage Examples

### Extract Excel File

```python
from src.infrastructure.extractors.excel_extractor import ExcelExtractor
from src.domain.documents.document import Document

extractor = ExcelExtractor()
document = await db.query(Document).filter(Document.id == doc_id).first()

result = await extractor.extract(document)

if result.success:
    print(f"Confidence: {result.confidence}")
    print(f"Lines extracted: {len(result.output.lines)}")
    print(f"Runtime: {result.metrics['runtime_ms']}ms")
else:
    print(f"Error: {result.error}")
```

### Check Extraction Output

```sql
-- View extraction runs
SELECT
  er.id,
  er.extractor_version,
  er.status,
  d.file_name,
  JSONB_ARRAY_LENGTH(er.output_json->'lines') as line_count,
  er.metrics_json->>'runtime_ms' as runtime_ms
FROM extraction_run er
JOIN document d ON er.document_id = d.id
ORDER BY er.created_at DESC
LIMIT 10;

-- View extraction output
SELECT
  output_json->'order'->'order_number' as order_number,
  JSONB_PRETTY(output_json->'lines') as lines
FROM extraction_run
WHERE id = 'uuid'
AND status = 'SUCCEEDED';
```

## Testing

```bash
# Unit tests
pytest tests/unit/extraction/ -v

# Component tests (extractor implementations)
pytest tests/component/extractors/ -v

# Integration tests (full pipeline)
pytest tests/integration/extraction/ -v

# Test with fixtures
pytest tests/component/extractors/test_excel_extractor.py::test_extract_valid_excel -v
```

### Component Test Example

```python
# tests/component/extractors/test_excel_extractor.py
import pytest
from src.infrastructure.extractors.excel_extractor import ExcelExtractor

@pytest.mark.asyncio
async def test_extract_excel_valid():
    """Test extraction from well-formed Excel file"""
    extractor = ExcelExtractor()

    # Create test document
    document = create_test_document(
        storage_key='fixtures/orders/order_excel_valid.xlsx',
        mime_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

    result = await extractor.extract(document)

    assert result.success
    assert result.confidence > 0.8
    assert len(result.output.lines) == 5  # Expected line count
    assert result.output.lines[0].customer_sku == 'SKU-12345'
    assert result.output.lines[0].qty == Decimal('10')
```

## Common Issues

### Extraction fails with "No extractor for MIME type"
**Solution**: Register extractor in registry: `extractor_registry.register(ExcelExtractor())`

### Confidence score always 0.0
**Solution**: Ensure `_calculate_confidence()` is called in extractor

### Excel extraction fails with UnicodeDecodeError
**Solution**: File may be corrupt or not actually Excel format

### PDF extraction returns empty lines
**Solution**: PDF may be scanned (no extractable text). Check text_coverage_ratio < 0.3 → use LLM extractor (future)
