# Feature Specification: Extraction Core

**Feature Branch**: `009-extraction-core`
**Created**: 2025-12-27
**Status**: Draft
**Module**: extraction
**SSOT References**: §4.1 (extraction module), §5.2.4 (ExtractionRunStatus), §5.4.7 (extraction_run table), §7.1 (Output Schema), §7.2 (Decision Logic), §7.8.1 (Confidence)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Extract Structured Data from Excel/CSV (Priority: P1)

As a backend system, I need to extract order data from Excel and CSV files so that they can be converted into draft orders.

**Why this priority**: Excel and CSV are the easiest formats to parse and most reliable. This is the MVP happy path for extraction.

**Independent Test**: Can be fully tested by uploading a sample Excel/CSV with known order data, triggering extraction, and verifying the extraction_run produces correct structured JSON matching the canonical schema. Delivers core extraction capability.

**Acceptance Scenarios**:

1. **Given** an Excel file with columns (SKU, Qty, Unit, Price), **When** extraction runs, **Then** structured JSON is produced with correct line items
2. **Given** a CSV file with semicolon separator and decimal comma, **When** extraction runs, **Then** all values are parsed correctly (decimal separator conversion)
3. **Given** an Excel file with header row and data rows, **When** extraction runs, **Then** header row is detected and skipped
4. **Given** a CSV file with quoted values containing commas, **When** extraction runs, **Then** quoted values are parsed correctly (CSV escaping)

---

### User Story 2 - Extract Data from Text-Based PDF (Priority: P1)

As a backend system, I need to extract order data from text-based PDFs (non-scanned) so that digital orders can be processed.

**Why this priority**: Many B2B orders arrive as PDF. Rule-based extraction works for well-structured PDFs and is faster/cheaper than LLM.

**Independent Test**: Can be tested by uploading a text-based PDF with a table of order lines, running extraction, and verifying structured JSON output with correct data.

**Acceptance Scenarios**:

1. **Given** a PDF with extractable text (text_coverage_ratio > 0.8), **When** extraction runs, **Then** rule-based extractor is used (not LLM)
2. **Given** a PDF with a table structure, **When** extraction runs, **Then** table rows are detected and parsed into line items
3. **Given** a PDF with header information (order number, date), **When** extraction runs, **Then** header fields are extracted correctly
4. **Given** a PDF extraction produces valid structured data, **When** extraction completes, **Then** extraction_confidence is calculated and stored

---

### User Story 3 - ExtractorPort Interface (Priority: P1)

As a developer, I need a clear ExtractorPort interface so that I can implement different extraction strategies (rule-based, LLM, hybrid) without changing the core pipeline.

**Why this priority**: Hexagonal architecture requires well-defined ports. This enables future LLM integration and testing with mocks.

**Independent Test**: Can be tested by implementing two extractors (e.g., ExcelExtractor, CSVExtractor), verifying both conform to the same interface, and swapping them without changing the pipeline code.

**Acceptance Scenarios**:

1. **Given** an ExtractorPort interface exists, **When** I implement ExcelExtractor, **Then** it conforms to the interface signature
2. **Given** multiple extractors exist, **When** the pipeline selects an extractor based on file type, **Then** it uses the correct extractor
3. **Given** an extractor is mocked, **When** tests run, **Then** the entire extraction pipeline can be tested without real files
4. **Given** extraction fails, **When** the extractor raises an error, **Then** it is caught and stored in extraction_run.error_json

---

### User Story 4 - Extraction Confidence Calculation (Priority: P2)

As a system, I need to calculate extraction confidence scores so that low-confidence extractions can be flagged for manual review.

**Why this priority**: Not all extractions are perfect. Confidence scores enable automatic routing (high confidence → auto-process, low confidence → manual review).

**Independent Test**: Can be tested by extracting documents with varying quality (complete data, missing fields, partial data), verifying confidence scores reflect data completeness and quality.

**Acceptance Scenarios**:

1. **Given** all required header fields are extracted, **When** confidence is calculated, **Then** header score is high (>0.8)
2. **Given** 50% of header fields are missing, **When** confidence is calculated, **Then** header score is medium (~0.5)
3. **Given** all line items have SKU and quantity, **When** confidence is calculated, **Then** line score is high
4. **Given** extraction confidence is below threshold (e.g., 0.6), **When** draft order is created, **Then** status is set to NEEDS_REVIEW

---

### User Story 5 - Canonical Extraction Output Schema (Priority: P1)

As a developer, I need a canonical JSON schema for extraction output so that downstream processing (matching, validation) has a consistent data structure.

**Why this priority**: Inconsistent extraction output would break downstream processing. Canonical schema ensures all extractors produce compatible data.

**Independent Test**: Can be tested by validating extraction output from different extractors against the canonical schema, verifying all conform to the same structure.

**Acceptance Scenarios**:

1. **Given** an Excel extractor produces output, **When** validated against canonical schema, **Then** it passes validation
2. **Given** a PDF extractor produces output, **When** validated against canonical schema, **Then** it passes validation
3. **Given** extraction output is missing required fields, **When** validated, **Then** validation fails with clear error message
4. **Given** extraction output has extra fields, **When** validated, **Then** validation passes (extra fields allowed but ignored)

---

### Edge Cases

- What happens when Excel file has multiple sheets (which sheet to use)?
- How does the system handle CSV files with inconsistent column counts across rows?
- What happens when PDF has no extractable text (scanned document)?
- How does the system handle very large files (100+ pages)?
- What happens when extraction takes longer than timeout (e.g., 5 minutes)?
- How does the system handle files with mixed languages or special characters?
- What happens when extraction produces zero line items (empty order)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide ExtractorPort interface with method: `extract(document: Document) -> ExtractionResult`
- **FR-002**: System MUST implement ExcelExtractor for .xlsx and .xls files
- **FR-003**: System MUST implement CSVExtractor for .csv files
- **FR-004**: System MUST implement PDFTextExtractor for text-based PDFs (rule-based)
- **FR-005**: System MUST create extraction_run record for each extraction attempt
- **FR-006**: System MUST store extraction output in canonical JSON schema (SSOT §7.1)
- **FR-007**: System MUST calculate extraction_confidence score (SSOT §7.8.1)
- **FR-008**: System MUST support decimal comma (European format) in CSV/Excel
- **FR-009**: System MUST detect and skip header rows in Excel/CSV
- **FR-010**: System MUST handle quoted values and escape sequences in CSV
- **FR-011**: System MUST store extraction metrics (runtime_ms, page_count, etc.) in extraction_run.metrics_json
- **FR-012**: System MUST update document.status based on extraction outcome (EXTRACTED or FAILED)
- **FR-013**: For multi-sheet Excel files, System MUST use the first (active) sheet. extraction_run.metrics_json MUST include sheet_name for user reference. Future: configurable sheet selection.
- **FR-014**: Character encoding handling: (1) Detect charset using chardet library with fallback order: UTF-8 → ISO-8859-1 → Windows-1252, (2) For Excel multi-sheet: use first sheet (sheet index 0), (3) CSV quote handling per RFC 4180: doubled quotes for escaping, (4) Log encoding detection results in extraction_run.metrics_json.

### Orchestration Requirements (E2E Flow)

- **FR-ORQ-001**: Successful extraction MUST automatically trigger DraftOrder creation. After extraction_run.status=SUCCEEDED, system enqueues `create_draft_order(document_id, extraction_run_id)` job. No manual intervention required for happy path.
- **FR-ORQ-002**: Extraction fallback logic: Rule-based extraction runs first. LLM extraction triggers ONLY IF: (1) extraction_confidence < 0.60, OR (2) lines_count == 0, OR (3) document.text_coverage_ratio < 0.3 (scanned PDF). Fallback is automatic, not manual.
- **FR-ORQ-003**: Inbound source handling: Extraction pipeline processes ALL inbound_messages regardless of source (EMAIL or UPLOAD). The source field is informational only; extraction logic is identical for both paths.

### Key Entities

- **ExtractionRun**: Record of an extraction attempt. Tracks which extractor version was used, start/finish times, success/failure status, and metrics. Multiple runs can exist for one document (e.g., retry after failure).

- **Canonical Extraction Output**: Standardized JSON structure produced by all extractors. Contains order header (order_number, date, currency, etc.) and lines (sku, qty, uom, price, etc.). Defined in SSOT §7.1.

- **Extraction Confidence**: Numeric score (0.0-1.0) indicating extraction quality. Calculated from header completeness and line completeness. Used to route drafts to automatic processing vs. manual review.

### Technical Constraints

- **TC-001**: Extractors MUST be idempotent (same input → same output)
- **TC-002**: Extractors MUST complete within timeout (default 5 minutes)
- **TC-003**: Canonical output MUST be validated against Pydantic schema
- **TC-004**: Extraction MUST stream large files (not load into memory)
- **TC-005**: Confidence calculation MUST be deterministic and reproducible

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Excel extraction accuracy >95% for well-formed files (all required fields extracted correctly)
- **SC-002**: CSV extraction accuracy >95% for well-formed files
- **SC-003**: PDF text extraction accuracy >80% for text-based PDFs with clear tables
- **SC-004**: Extraction completes in under 10 seconds for typical files (<10 pages, <1000 lines)
- **SC-005**: Confidence calculation correlates with actual extraction quality (verified by manual review)
- **SC-006**: Zero extraction crashes (all errors handled gracefully with FAILED status)

### Data Quality

- **DQ-001**: Decimal separator conversion is 100% accurate (comma to dot)
- **DQ-002**: Quantity parsing handles integers and decimals correctly
- **DQ-003**: Date parsing supports multiple formats (ISO, DD.MM.YYYY, MM/DD/YYYY)
- **DQ-004**: Currency codes are normalized (uppercase, ISO 4217)

## Dependencies

- **Depends on**: 001-platform-foundation (database, Celery)
- **Depends on**: 005-object-storage (retrieve files for extraction)
- **Depends on**: 007-document-upload (document records)
- **Dependency reason**: Extraction requires files from storage and creates extraction_run records

## Implementation Notes

### Canonical Extraction Output Schema (SSOT §7.1)

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date
from decimal import Decimal

class ExtractionLineItem(BaseModel):
    line_no: int
    customer_sku: Optional[str] = None
    description: Optional[str] = None
    qty: Optional[Decimal] = None
    uom: Optional[str] = None
    unit_price: Optional[Decimal] = None
    currency: Optional[str] = None

class ExtractionOrderHeader(BaseModel):
    order_number: Optional[str] = None
    order_date: Optional[date] = None
    currency: Optional[str] = None
    delivery_date: Optional[date] = None
    ship_to: Optional[dict] = None
    bill_to: Optional[dict] = None
    notes: Optional[str] = None

class CanonicalExtractionOutput(BaseModel):
    """
    Canonical structure that all extractors must produce.
    Defined in SSOT §7.1.
    """
    order: ExtractionOrderHeader
    lines: List[ExtractionLineItem]
    metadata: dict = Field(default_factory=dict)  # Extractor-specific metadata

    class Config:
        # Allow extra fields but ignore them
        extra = "allow"
```

### ExtractorPort Interface

```python
from abc import ABC, abstractmethod
from typing import Protocol
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ExtractionResult:
    """Result of extraction operation"""
    success: bool
    output: Optional[CanonicalExtractionOutput] = None
    error: Optional[str] = None
    confidence: float = 0.0
    metrics: dict = None  # runtime_ms, page_count, etc.

class ExtractorPort(ABC):
    """
    Port interface for document extraction.
    All extractors must implement this interface.
    """

    @abstractmethod
    async def extract(self, document: Document) -> ExtractionResult:
        """
        Extract structured order data from document.

        Args:
            document: Document entity with storage_key to retrieve file

        Returns:
            ExtractionResult with canonical output or error
        """
        pass

    @abstractmethod
    def supports(self, mime_type: str) -> bool:
        """Check if this extractor supports the given MIME type"""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Extractor version for tracking (e.g., 'excel_v1', 'pdf_rule_v1')"""
        pass
```

### Excel Extractor Implementation

```python
import openpyxl
from decimal import Decimal

class ExcelExtractor(ExtractorPort):
    """Extract order data from Excel files (.xlsx, .xls)"""

    def supports(self, mime_type: str) -> bool:
        return mime_type in [
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ]

    @property
    def version(self) -> str:
        return 'excel_v1'

    async def extract(self, document: Document) -> ExtractionResult:
        start_time = datetime.utcnow()

        try:
            # Retrieve file from storage
            file_content = await object_storage.retrieve_file(document.storage_key)

            # Load workbook
            wb = openpyxl.load_workbook(file_content, read_only=True)
            sheet = wb.active  # Use first sheet

            # Detect header row
            header_row_idx = self._detect_header_row(sheet)

            # Extract lines
            lines = []
            for row_idx, row in enumerate(sheet.iter_rows(min_row=header_row_idx + 1), start=1):
                line = self._extract_line(row, row_idx)
                if line:
                    lines.append(line)

            # Extract header (look for order number, date in first few rows)
            header = self._extract_header(sheet, header_row_idx)

            # Build canonical output
            output = CanonicalExtractionOutput(
                order=header,
                lines=lines,
                metadata={
                    'sheet_name': sheet.title,
                    'row_count': sheet.max_row
                }
            )

            # Calculate confidence
            confidence = self._calculate_confidence(output)

            runtime_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            return ExtractionResult(
                success=True,
                output=output,
                confidence=confidence,
                metrics={'runtime_ms': runtime_ms, 'row_count': len(lines)}
            )

        except Exception as e:
            logger.error(f"Excel extraction failed: {e}")
            return ExtractionResult(
                success=False,
                error=str(e),
                metrics={'runtime_ms': (datetime.utcnow() - start_time).total_seconds() * 1000}
            )

    def _detect_header_row(self, sheet) -> int:
        """Detect which row contains column headers"""
        # Simple heuristic: first row with non-numeric values
        for idx, row in enumerate(sheet.iter_rows(max_row=10)):
            values = [cell.value for cell in row if cell.value]
            if any(isinstance(v, str) and v.lower() in ['sku', 'qty', 'artikel', 'menge'] for v in values):
                return idx + 1
        return 1  # Default to first row

    def _extract_line(self, row, line_no: int) -> Optional[ExtractionLineItem]:
        """Extract line item from row"""
        # Assume columns: SKU, Description, Qty, UoM, Price
        # TODO: Make column mapping configurable

        cells = [cell.value for cell in row]
        if not cells or all(c is None for c in cells):
            return None  # Empty row

        return ExtractionLineItem(
            line_no=line_no,
            customer_sku=str(cells[0]) if cells[0] else None,
            description=str(cells[1]) if len(cells) > 1 and cells[1] else None,
            qty=self._parse_decimal(cells[2]) if len(cells) > 2 else None,
            uom=str(cells[3]) if len(cells) > 3 and cells[3] else None,
            unit_price=self._parse_decimal(cells[4]) if len(cells) > 4 else None,
        )

    def _parse_decimal(self, value) -> Optional[Decimal]:
        """Parse decimal value, handling comma separator"""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        if isinstance(value, str):
            # Handle European format (comma as decimal separator)
            value = value.replace(',', '.')
            try:
                return Decimal(value)
            except:
                return None
        return None

    def _extract_header(self, sheet, header_row_idx: int) -> ExtractionOrderHeader:
        """Extract header fields from first few rows"""
        # Search for patterns like "Order Number: 12345" in first N rows
        header = ExtractionOrderHeader()

        for row in sheet.iter_rows(max_row=header_row_idx):
            for cell in row:
                if cell.value and isinstance(cell.value, str):
                    value = cell.value.lower()
                    if 'order' in value or 'po' in value:
                        # Try to extract order number from adjacent cell
                        # This is a simplified heuristic
                        pass

        return header

    def _calculate_confidence(self, output: CanonicalExtractionOutput) -> float:
        """Calculate extraction confidence based on data completeness"""
        # Header score
        header_fields = ['order_number', 'order_date', 'currency']
        header_complete = sum(1 for f in header_fields if getattr(output.order, f)) / len(header_fields)

        # Line score
        if not output.lines:
            return 0.0

        line_scores = []
        for line in output.lines:
            fields_present = sum([
                1 if line.customer_sku else 0,
                1 if line.qty else 0,
                1 if line.uom else 0,
            ])
            line_scores.append(fields_present / 3.0)

        avg_line_score = sum(line_scores) / len(line_scores)

        # Weighted average (SSOT §7.8.1)
        confidence = 0.4 * header_complete + 0.6 * avg_line_score

        return round(confidence, 3)
```

### CSV Extractor Implementation

```python
import csv
from io import StringIO

class CSVExtractor(ExtractorPort):
    """Extract order data from CSV files"""

    def supports(self, mime_type: str) -> bool:
        return mime_type == 'text/csv'

    @property
    def version(self) -> str:
        return 'csv_v1'

    async def extract(self, document: Document) -> ExtractionResult:
        start_time = datetime.utcnow()

        try:
            # Retrieve file
            file_content = await object_storage.retrieve_file(document.storage_key)
            text = file_content.read().decode('utf-8')

            # Detect delimiter (comma or semicolon)
            delimiter = self._detect_delimiter(text)

            # Parse CSV
            reader = csv.DictReader(StringIO(text), delimiter=delimiter)

            lines = []
            for idx, row in enumerate(reader, start=1):
                line = self._extract_line(row, idx)
                if line:
                    lines.append(line)

            output = CanonicalExtractionOutput(
                order=ExtractionOrderHeader(),  # CSV typically doesn't have header info
                lines=lines
            )

            confidence = self._calculate_confidence(output)

            return ExtractionResult(
                success=True,
                output=output,
                confidence=confidence,
                metrics={'runtime_ms': (datetime.utcnow() - start_time).total_seconds() * 1000}
            )

        except Exception as e:
            return ExtractionResult(success=False, error=str(e))

    def _detect_delimiter(self, text: str) -> str:
        """Detect CSV delimiter (comma or semicolon)"""
        first_line = text.split('\n')[0]
        if ';' in first_line:
            return ';'
        return ','

    def _extract_line(self, row: dict, line_no: int) -> Optional[ExtractionLineItem]:
        # Map CSV columns to line item fields
        # TODO: Make column mapping configurable
        return ExtractionLineItem(
            line_no=line_no,
            customer_sku=row.get('sku') or row.get('article') or row.get('artikelnummer'),
            qty=self._parse_decimal(row.get('qty') or row.get('menge')),
            uom=row.get('uom') or row.get('unit') or row.get('einheit'),
            unit_price=self._parse_decimal(row.get('price') or row.get('preis')),
        )
```

### Extraction Run Table Schema (SSOT §5.4.7)

```sql
CREATE TABLE extraction_run (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES org(id),
  document_id UUID NOT NULL REFERENCES document(id),
  extractor_version TEXT NOT NULL,  -- e.g., 'excel_v1', 'pdf_rule_v1'
  status TEXT NOT NULL CHECK (status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED')),
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  output_json JSONB,  -- Canonical extraction output
  metrics_json JSONB,  -- runtime_ms, page_count, etc.
  error_json JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_extraction_run_org_doc ON extraction_run(org_id, document_id, created_at DESC);
```

### Extraction Worker (Celery Task)

```python
from celery import task

@task(bind=True, max_retries=3)
async def extract_document(self, document_id: str, org_id: str):
    """
    Background job to extract structured data from document.
    """
    org_uuid = UUID(org_id)
    doc_uuid = UUID(document_id)

    # Load document
    document = await db.query(Document).filter(
        Document.id == doc_uuid,
        Document.org_id == org_uuid
    ).first()

    if not document:
        raise ValueError(f"Document {document_id} not found")

    # Update document status
    await update_document_status(db, doc_uuid, DocumentStatus.PROCESSING)

    # Create extraction run
    extraction_run = ExtractionRun(
        id=uuid4(),
        org_id=org_uuid,
        document_id=doc_uuid,
        status=ExtractionRunStatus.RUNNING,
        started_at=datetime.utcnow()
    )
    db.add(extraction_run)
    await db.commit()

    try:
        # Select extractor based on MIME type
        extractor = extractor_registry.get_extractor(document.mime_type)
        if not extractor:
            raise ValueError(f"No extractor for MIME type: {document.mime_type}")

        extraction_run.extractor_version = extractor.version
        await db.commit()

        # Run extraction
        result = await extractor.extract(document)

        if result.success:
            # Store output
            extraction_run.output_json = result.output.dict()
            extraction_run.status = ExtractionRunStatus.SUCCEEDED
            extraction_run.metrics_json = result.metrics

            # Update document
            await update_document_status(db, doc_uuid, DocumentStatus.EXTRACTED)

            # Enqueue draft order creation
            await enqueue_draft_order_creation(document_id, extraction_run.id)

        else:
            # Store error
            extraction_run.status = ExtractionRunStatus.FAILED
            extraction_run.error_json = {'error': result.error}
            extraction_run.metrics_json = result.metrics

            # Update document
            await update_document_status(
                db,
                doc_uuid,
                DocumentStatus.FAILED,
                error_json={'extraction_error': result.error}
            )

    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        extraction_run.status = ExtractionRunStatus.FAILED
        extraction_run.error_json = {'exception': str(e)}

        await update_document_status(
            db,
            doc_uuid,
            DocumentStatus.FAILED,
            error_json={'exception': str(e)}
        )

        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries)

    finally:
        extraction_run.finished_at = datetime.utcnow()
        await db.commit()
```

### Extractor Registry

```python
class ExtractorRegistry:
    """Registry of available extractors"""

    def __init__(self):
        self._extractors: List[ExtractorPort] = []

    def register(self, extractor: ExtractorPort):
        self._extractors.append(extractor)

    def get_extractor(self, mime_type: str) -> Optional[ExtractorPort]:
        for extractor in self._extractors:
            if extractor.supports(mime_type):
                return extractor
        return None

# Global registry
extractor_registry = ExtractorRegistry()
extractor_registry.register(ExcelExtractor())
extractor_registry.register(CSVExtractor())
# extractor_registry.register(PDFTextExtractor())  # Future
```

### Confidence Calculation Formula (per SSOT §7.8)

Confidence Calculation: Header confidence = extracted_fields / required_fields (order_date, customer reference). Line confidence = avg(fields_present / 3) for each line where fields = [sku, qty, description]. Overall = 0.4 * header_confidence + 0.6 * line_confidence. Weights are tunable via org settings.

## Out of Scope

- LLM-based extraction (future spec, foundation only)
- OCR for scanned PDFs (future spec)
- Image file support (JPG, PNG)
- Multi-page table extraction (PDF spanning multiple pages)
- Handwritten order recognition
- Auto-detection of column mapping (hardcoded for MVP)
- Learning from user corrections (future spec)
- Extraction templates per customer (future spec)
- Real-time extraction progress updates (background only)
- Extraction retry UI (automatic retry only)
- Custom extraction rules per org (global rules only)

## Testing Strategy

### Contract Tests
- Extraction output JSON MUST be snapshot-tested against Pydantic schema (CanonicalExtractionOutput)
- Use pytest-snapshot or equivalent for schema stability verification
- Schema changes require explicit snapshot update with PR review
- All extractors (Excel, CSV, PDF) tested against same schema snapshot

### Unit Tests
- CanonicalExtractionOutput schema validation
- Confidence calculation (various completeness scenarios)
- Decimal parsing (comma/dot separator)
- Header row detection
- CSV delimiter detection
- Extractor registry (register/lookup)
- ExtractionResult creation

### Integration Tests
- Extract from Excel file (end-to-end)
- Extract from CSV file (end-to-end)
- Extract from PDF (text-based, future)
- Extraction creates extraction_run record
- Extraction updates document.status
- Failed extraction stores error_json
- Extraction retry on failure
- Multiple extractors for same document (retry with different version)

### Extraction Accuracy Tests
- Excel with all required fields → 100% accuracy
- Excel with missing fields → correct confidence score
- CSV with European decimal format → correct decimal parsing
- CSV with quoted values → correct value extraction
- Excel with multiple sheets → uses first sheet
- Empty file → graceful failure

### Performance Tests
- Extract 100-row Excel file (<5 seconds)
- Extract 1000-row CSV file (<10 seconds)
- Extract 10-page PDF (<30 seconds, future)
- Concurrent extractions (10 simultaneous documents)

### Error Handling Tests
- Corrupt Excel file → FAILED status
- Invalid CSV format → FAILED status
- Missing file in storage → FAILED status
- Extraction timeout (>5 minutes) → FAILED status
- Database failure during extraction → job retry

### Confidence Tests
- All header fields present → high header score (>0.8)
- No header fields → low header score (0.0)
- All lines complete → high line score (>0.8)
- 50% lines complete → medium line score (~0.5)
- No lines → zero confidence
- Mixed completeness → weighted average formula
