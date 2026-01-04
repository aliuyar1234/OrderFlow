# Data Model: Extraction Core

**Feature**: 009-extraction-core | **Date**: 2025-12-27

## Entity Definitions

### ExtractionRun

**Properties**:
- `id` (UUID): Primary key
- `org_id` (UUID): Organization (multi-tenant)
- `document_id` (UUID): Document being extracted
- `extractor_version` (TEXT): Extractor used (e.g., "excel_v1", "llm_v2")
- `status` (TEXT): ExtractionRunStatus enum
- `started_at` (TIMESTAMPTZ): When extraction started
- `finished_at` (TIMESTAMPTZ): When extraction finished
- `output_json` (JSONB): Canonical extraction output
- `metrics_json` (JSONB): Runtime metrics (runtime_ms, page_count, etc.)
- `error_json` (JSONB): Error details if failed
- `created_at` (TIMESTAMPTZ): Record creation
- `updated_at` (TIMESTAMPTZ): Last update

**Relationships**:
- `org_id` → `org.id`
- `document_id` → `document.id`

### SQLAlchemy Model

```python
from sqlalchemy import Column, String, TIMESTAMP, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

class ExtractionRun(Base):
    __tablename__ = 'extraction_run'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey('org.id'), nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey('document.id'), nullable=False, index=True)

    extractor_version = Column(String, nullable=False)
    status = Column(String, nullable=False, index=True)

    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    finished_at = Column(TIMESTAMP(timezone=True), nullable=True)

    output_json = Column(JSONB, nullable=True)
    metrics_json = Column(JSONB, nullable=True)
    error_json = Column(JSONB, nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    org = relationship("Org")
    document = relationship("Document", back_populates="extraction_runs")

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED')",
            name='extraction_run_status_check'
        ),
    )
```

### Database Schema (SQL)

```sql
CREATE TABLE extraction_run (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES org(id),
  document_id UUID NOT NULL REFERENCES document(id),

  extractor_version TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED')),

  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,

  output_json JSONB,
  metrics_json JSONB,
  error_json JSONB,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_extraction_run_org_doc ON extraction_run(org_id, document_id, created_at DESC);
CREATE INDEX idx_extraction_run_status ON extraction_run(status);
```

## Canonical Output Schema (Pydantic)

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
    order: ExtractionOrderHeader
    lines: List[ExtractionLineItem]
    metadata: dict = Field(default_factory=dict)
```

## Enums

### ExtractionRunStatus

```python
from enum import Enum

class ExtractionRunStatus(str, Enum):
    PENDING = "PENDING"      # Waiting to start
    RUNNING = "RUNNING"      # In progress
    SUCCEEDED = "SUCCEEDED"  # Completed successfully
    FAILED = "FAILED"        # Failed with error
```

## Value Objects

### ExtractionResult

```python
from dataclasses import dataclass

@dataclass
class ExtractionResult:
    success: bool
    output: Optional[CanonicalExtractionOutput] = None
    error: Optional[str] = None
    confidence: float = 0.0
    metrics: dict = None  # runtime_ms, page_count, etc.
```
