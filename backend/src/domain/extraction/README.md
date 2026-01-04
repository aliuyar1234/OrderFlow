# Extraction Module

The extraction module is responsible for extracting structured order data from uploaded documents (Excel, CSV, PDF). It follows hexagonal architecture with domain logic separated from infrastructure.

## Architecture

```
domain/extraction/          # Domain layer (business logic)
├── canonical_output.py     # Pydantic schemas for extraction output
├── confidence.py           # Confidence score calculation
└── ports/                  # Port interfaces
    └── extractor_port.py   # ExtractorPort interface

infrastructure/extractors/  # Infrastructure layer (adapters)
├── excel_extractor.py      # Excel file extractor
├── csv_extractor.py        # CSV file extractor
└── extractor_registry.py   # Registry for managing extractors

workers/
└── extraction_worker.py    # Celery task for async extraction

api/v1/extraction/          # API layer
├── router.py               # REST endpoints
└── schemas.py              # Request/response models
```

## Canonical Output Schema

All extractors must produce output conforming to `CanonicalExtractionOutput`:

```python
{
    "order": {
        "order_number": "PO-12345",
        "order_date": "2024-01-15",
        "currency": "EUR",
        "delivery_date": null,
        "ship_to": null,
        "bill_to": null,
        "notes": null,
        "reference": null
    },
    "lines": [
        {
            "line_no": 1,
            "customer_sku": "ART-001",
            "description": "Product Name",
            "qty": 10.0,
            "uom": "PCS",
            "unit_price": 25.50,
            "currency": "EUR",
            "line_total": null
        }
    ],
    "metadata": {
        "sheet_name": "Sheet1",
        "total_rows": 15,
        "encoding": "utf-8"
    }
}
```

## Extractor Interface

All extractors implement `ExtractorPort`:

```python
class ExtractorPort(ABC):
    async def extract(self, document: Document) -> ExtractionResult:
        """Extract structured data from document."""

    def supports(self, mime_type: str) -> bool:
        """Check if this extractor supports the MIME type."""

    @property
    def version(self) -> str:
        """Extractor version (e.g., 'excel_v1')."""

    @property
    def priority(self) -> int:
        """Selection priority (lower = higher priority)."""
```

## Available Extractors

### ExcelExtractor
- **MIME types**: `application/vnd.ms-excel`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- **Version**: `excel_v1`
- **Priority**: 10 (high)
- **Features**:
  - Automatic header row detection
  - European decimal format support (comma separator)
  - Multi-sheet support (uses first/active sheet)
  - Extracts order metadata from first rows

### CSVExtractor
- **MIME types**: `text/csv`, `application/csv`
- **Version**: `csv_v1`
- **Priority**: 10 (high)
- **Features**:
  - Automatic delimiter detection (comma/semicolon)
  - Flexible column name mapping
  - European decimal format support
  - Encoding detection (UTF-8, ISO-8859-1, Windows-1252)

## Confidence Calculation

Confidence score indicates extraction quality (0.0-1.0):

```
header_confidence = extracted_fields / required_fields
line_confidence = avg(fields_present / 3) for each line
overall_confidence = 0.4 * header_confidence + 0.6 * line_confidence
```

Required fields:
- Header: `order_number`, `order_date`, `currency`
- Line: `customer_sku`, `qty`, `description`

## Extraction Flow

1. **Document uploaded** → stored in object storage
2. **Extraction triggered** → Celery task enqueued
3. **Task execution**:
   - Load document from database
   - Update status to PROCESSING
   - Create extraction_run record
   - Select extractor based on MIME type
   - Execute extraction
   - Store results in extraction_run
   - Update document status (EXTRACTED or FAILED)
4. **Results available** via API endpoints

## API Endpoints

### List Extractions
```
GET /api/v1/extractions?document_id=<uuid>&status=SUCCEEDED&limit=10
```

### Get Extraction Details
```
GET /api/v1/extractions/{extraction_run_id}
```

### Trigger Extraction
```
POST /api/v1/extractions/trigger
{
    "document_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

### Retry Failed Extraction
```
POST /api/v1/extractions/{extraction_run_id}/retry
```

## Usage Example

### In Application Startup
```python
from infrastructure.extractors import get_global_registry, ExcelExtractor, CSVExtractor
from infrastructure.storage import get_storage_adapter

# Initialize extractors
storage = get_storage_adapter()
registry = get_global_registry()

registry.register(ExcelExtractor(storage))
registry.register(CSVExtractor(storage))
```

### In API Endpoint
```python
from workers.extraction_worker import extract_document_task

# Enqueue extraction after document upload
extract_document_task.delay(
    document_id=str(document.id),
    org_id=str(current_user.org_id)
)
```

### In Worker
```python
# Worker automatically handles extraction using registry
# See workers/extraction_worker.py for implementation
```

## Database Schema

### extraction_run Table
```sql
CREATE TABLE extraction_run (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL,
    document_id UUID NOT NULL,
    extractor_version TEXT NOT NULL,
    status extractionrunstatus NOT NULL,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    output_json JSONB,  -- CanonicalExtractionOutput
    metrics_json JSONB, -- runtime_ms, confidence, etc.
    error_json JSONB,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
```

## Adding New Extractors

1. Create extractor class implementing `ExtractorPort`:
```python
class PDFExtractor(ExtractorPort):
    def __init__(self, storage: ObjectStoragePort):
        self.storage = storage

    async def extract(self, document) -> ExtractionResult:
        # Implementation

    def supports(self, mime_type: str) -> bool:
        return mime_type == 'application/pdf'

    @property
    def version(self) -> str:
        return 'pdf_v1'

    @property
    def priority(self) -> int:
        return 10  # High priority for rule-based
```

2. Register in application startup:
```python
registry.register(PDFExtractor(storage))
```

3. Extractor is automatically used for matching MIME types!

## Testing

Run tests:
```bash
pytest backend/tests/unit/extraction/
pytest backend/tests/component/extractors/
pytest backend/tests/integration/extraction/
```

## References

- **SSOT**: §7 (Extraction Logic)
- **Spec**: `specs/009-extraction-core/spec.md`
- **Plan**: `specs/009-extraction-core/plan.md`
- **Tasks**: `specs/009-extraction-core/tasks.md`
