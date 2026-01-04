# Data Model: Rule-Based Extractors

**Feature**: 010-extractors-rule-based
**Date**: 2025-12-27

## Entity Definitions

### ExtractionRun

Tracks the processing of a document through a specific extractor version.

**Purpose**: Audit trail and debugging for extraction process. Links document to extraction results.

**Key Fields**:
- `id` (UUID, PK): Unique identifier
- `org_id` (UUID, FK → organization, NOT NULL): Multi-tenant isolation
- `document_id` (UUID, FK → document, NOT NULL): Source document
- `extractor_version` (VARCHAR(50), NOT NULL): `rule_v1` for rule-based extraction
- `status` (ExtractionRunStatus ENUM, NOT NULL): NEW, RUNNING, SUCCEEDED, FAILED
- `started_at` (TIMESTAMP): Extraction start time
- `completed_at` (TIMESTAMP): Extraction completion time
- `runtime_ms` (INT): Processing duration in milliseconds
- `lines_extracted` (INT): Number of lines extracted (0 if failed)
- `extraction_confidence` (DECIMAL(5,4)): Overall confidence score [0.0000..1.0000]
- `metrics_json` (JSONB): Additional metrics (file_size_bytes, row_count, separator_detected, decimal_format, etc.)
- `error_json` (JSONB): Error details if status=FAILED

**Constraints**:
- Index on (org_id, document_id, extractor_version) for lookup
- Index on (org_id, status, created_at) for monitoring queries

### Document (extended attributes)

Stores document metadata relevant to extraction.

**New Fields for Rule-Based Extraction**:
- `text_coverage_ratio` (DECIMAL(5,4)): For PDFs, ratio of text content (§7.2.1). NULL for CSV/Excel.
- `extracted_text_storage_key` (VARCHAR(500)): S3 key for extracted text (PDFs only)
- `page_count` (INT): Number of pages (PDFs only)
- `detected_format` (VARCHAR(50)): CSV_SEMICOLON, CSV_COMMA, XLSX, PDF_TEXT, PDF_SCAN

### Canonical Extraction Output (JSON Schema)

The standard output format for all extractors (§7.1). Stored in `extraction_run.metrics_json` or separate storage.

**Schema**:
```json
{
  "extractor_version": "rule_v1",
  "order": {
    "external_order_number": "PO-2024-12345",
    "order_date": "2024-12-20",
    "currency": "EUR",
    "customer_hint": "Acme GmbH",
    "requested_delivery_date": "2025-01-15",
    "ship_to": {
      "name": "Acme Warehouse",
      "address": "Industriestr. 10",
      "city": "Munich",
      "postal_code": "80339",
      "country": "DE"
    },
    "bill_to": null,
    "notes": "Urgent delivery required"
  },
  "lines": [
    {
      "line_no": 1,
      "customer_sku_raw": "AB-1234",
      "product_description": "Widget Professional 2000",
      "qty": 10.0,
      "uom": "ST",
      "unit_price": 45.50,
      "currency": "EUR",
      "requested_delivery_date": null
    }
  ],
  "confidence": {
    "overall": 0.8735,
    "order": {
      "external_order_number": 0.95,
      "order_date": 0.90,
      "currency": 0.85,
      "customer_hint": 0.75,
      "requested_delivery_date": 0.80,
      "ship_to": 0.70
    },
    "lines": [
      {
        "customer_sku_raw": 0.95,
        "product_description": 0.85,
        "qty": 0.95,
        "uom": 0.90,
        "unit_price": 0.88
      }
    ]
  },
  "warnings": [
    "Column 'notes' was unmapped",
    "Line 5: qty field contains non-numeric text, set to null"
  ],
  "metadata": {
    "separator_detected": ";",
    "decimal_format": ",",
    "header_rows_skipped": 5,
    "unmapped_columns": ["notes", "internal_ref"],
    "row_count": 42
  }
}
```

## SQLAlchemy Model Structures

### ExtractionRun Model

```python
from sqlalchemy import Column, String, Integer, Numeric, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import relationship
import uuid
from enum import Enum

class ExtractionRunStatus(str, Enum):
    NEW = "NEW"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"

class ExtractionRun(Base):
    __tablename__ = "extraction_run"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organization.id"), nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("document.id"), nullable=False)
    extractor_version = Column(String(50), nullable=False)  # "rule_v1", "llm_v1"
    status = Column(SQLEnum(ExtractionRunStatus), nullable=False, default=ExtractionRunStatus.NEW)

    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    runtime_ms = Column(Integer, nullable=True)

    lines_extracted = Column(Integer, default=0)
    extraction_confidence = Column(Numeric(5, 4), nullable=True)  # 0.0000-1.0000

    metrics_json = Column(JSONB, nullable=True)  # Contains canonical extraction output
    error_json = Column(JSONB, nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default="now()")
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default="now()", onupdate="now()")

    # Relationships
    organization = relationship("Organization", back_populates="extraction_runs")
    document = relationship("Document", back_populates="extraction_runs")

    __table_args__ = (
        Index("idx_extraction_run_lookup", "org_id", "document_id", "extractor_version"),
        Index("idx_extraction_run_monitoring", "org_id", "status", "created_at"),
    )
```

### Document Model Extensions

```python
class Document(Base):
    __tablename__ = "document"

    # ... existing fields ...

    # Rule-based extraction specific
    text_coverage_ratio = Column(Numeric(5, 4), nullable=True)  # PDFs only
    extracted_text_storage_key = Column(String(500), nullable=True)  # S3 key
    page_count = Column(Integer, nullable=True)  # PDFs only
    detected_format = Column(String(50), nullable=True)  # CSV_SEMICOLON, XLSX, PDF_TEXT

    # Relationships
    extraction_runs = relationship("ExtractionRun", back_populates="document")
```

## Relationships and Constraints

### Multi-Tenant Isolation
- All queries MUST filter by `org_id`
- `extraction_run.org_id` enforced via FK and app-layer checks
- Row-level security (RLS) can be added at DB level for defense-in-depth

### Document → ExtractionRun
- One document can have multiple extraction runs (e.g., rule_v1 then llm_v1)
- `document_id` FK with ON DELETE CASCADE (delete document → delete extraction runs)

### Idempotency
- Running same extractor_version on same document multiple times creates new extraction_run records
- Latest extraction_run (by created_at DESC) is authoritative
- Hash-based deduplication can be added: check if identical extraction_run already exists before creating new one

### Status Transitions
```
NEW → RUNNING → SUCCEEDED | FAILED
```
- NEW: Created but not started
- RUNNING: Worker processing
- SUCCEEDED: Extraction completed, results in metrics_json
- FAILED: Extraction failed, error in error_json

## Indexes and Performance

### Critical Indexes
1. `(org_id, document_id, extractor_version)`: Fast lookup for "get latest extraction for document"
2. `(org_id, status, created_at)`: Dashboard queries (running/failed extractions)
3. `(org_id, extraction_confidence)`: Sort by confidence for review prioritization

### JSONB Indexes (PostgreSQL)
- GIN index on `metrics_json` for searching within extraction metadata
- Example: Find all extractions with specific warning type

```sql
CREATE INDEX idx_extraction_metrics_gin ON extraction_run USING GIN(metrics_json);
```

## Migration Scripts

### Initial Schema

```sql
-- Create extraction_run table
CREATE TABLE extraction_run (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organization(id),
    document_id UUID NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    extractor_version VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'NEW',

    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    runtime_ms INTEGER,

    lines_extracted INTEGER DEFAULT 0,
    extraction_confidence NUMERIC(5, 4),

    metrics_json JSONB,
    error_json JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX idx_extraction_run_org ON extraction_run(org_id);
CREATE INDEX idx_extraction_run_lookup ON extraction_run(org_id, document_id, extractor_version);
CREATE INDEX idx_extraction_run_monitoring ON extraction_run(org_id, status, created_at);
CREATE INDEX idx_extraction_metrics_gin ON extraction_run USING GIN(metrics_json);

-- Add columns to document table
ALTER TABLE document ADD COLUMN text_coverage_ratio NUMERIC(5, 4);
ALTER TABLE document ADD COLUMN extracted_text_storage_key VARCHAR(500);
ALTER TABLE document ADD COLUMN page_count INTEGER;
ALTER TABLE document ADD COLUMN detected_format VARCHAR(50);
```

## Validation Rules

### ExtractionRun Validation
- `extractor_version` MUST be one of: "rule_v1", "llm_v1"
- `extraction_confidence` MUST be between 0.0000 and 1.0000
- If `status=SUCCEEDED`, `metrics_json` MUST NOT be NULL
- If `status=FAILED`, `error_json` MUST NOT be NULL
- `runtime_ms` MUST be positive if set

### Canonical Output Validation (Pydantic)
```python
from pydantic import BaseModel, Field, validator
from typing import Optional, List

class OrderHeader(BaseModel):
    external_order_number: Optional[str]
    order_date: Optional[str]  # ISO format YYYY-MM-DD
    currency: Optional[str]  # ISO 4217
    customer_hint: Optional[str]
    requested_delivery_date: Optional[str]
    ship_to: Optional[dict]
    bill_to: Optional[dict]
    notes: Optional[str]

class OrderLine(BaseModel):
    line_no: int = Field(ge=1)
    customer_sku_raw: Optional[str]
    product_description: Optional[str]
    qty: Optional[float] = Field(gt=0, le=1_000_000)
    uom: Optional[str]
    unit_price: Optional[float]
    currency: Optional[str]
    requested_delivery_date: Optional[str]

class ConfidenceScores(BaseModel):
    overall: float = Field(ge=0.0, le=1.0)
    order: dict[str, float]
    lines: List[dict[str, float]]

class CanonicalExtractionOutput(BaseModel):
    extractor_version: str
    order: OrderHeader
    lines: List[OrderLine] = Field(max_length=500)
    confidence: ConfidenceScores
    warnings: List[str]
    metadata: dict
```
