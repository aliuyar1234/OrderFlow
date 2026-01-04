# Implementation Plan: Extraction Core

**Branch**: `009-extraction-core` | **Date**: 2025-12-27 | **Spec**: [spec.md](./spec.md)

## Summary

Implement core extraction pipeline with ExtractorPort interface and extractors for Excel (.xlsx, .xls), CSV, and text-based PDFs. Produces canonical JSON output with order header and line items. Calculates extraction confidence scores based on data completeness. Creates extraction_run records for tracking and supports retry on failure. Foundation for future LLM-based extraction.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: openpyxl (Excel), pandas (CSV), pdfplumber (PDF text), Pydantic (schema validation), Celery
**Storage**: PostgreSQL 16, S3-compatible object storage
**Testing**: pytest, pytest-asyncio
**Target Platform**: Linux server
**Project Type**: web
**Performance Goals**: <10s for typical files (<10 pages, <1000 lines), >95% accuracy for well-formed files
**Constraints**: Idempotent extraction, 5-minute timeout, streaming file retrieval
**Scale/Scope**: Handle 100-page PDFs, 10000-row Excel/CSV files

## Constitution Check

### I. SSOT-First
- **Status**: ✅ PASS
- **Evidence**: Extraction module specified in SSOT §4.1, §5.2.4 (ExtractionRunStatus), §5.4.7 (extraction_run table), §7.1-7.8 (extraction logic, output schema, confidence)

### II. Hexagonal Architecture
- **Status**: ✅ PASS
- **Evidence**: ExtractorPort interface with multiple adapter implementations (ExcelExtractor, CSVExtractor, PDFTextExtractor). Domain does not import extraction libraries directly.

### III. Multi-Tenant Isolation
- **Status**: ✅ PASS
- **Evidence**: extraction_run.org_id enforced. Extractors retrieve files using org-scoped storage_key.

### IV. Idempotent Processing
- **Status**: ✅ PASS
- **Evidence**: Same document extracted multiple times produces same output (deterministic extraction). Extraction run creates new record but output is reproducible.

### V. AI-Layer Deterministic Control
- **Status**: ✅ PASS (Foundation Only)
- **Evidence**: LLM extraction not implemented in this spec (future). Rule-based extractors are deterministic. Confidence scores use deterministic formulas.

### VI. Observability First-Class
- **Status**: ✅ PASS
- **Evidence**: extraction_run.metrics_json tracks runtime_ms, page_count. Errors stored in error_json. Confidence scores logged. OpenTelemetry spans for extraction pipeline.

### VII. Test Pyramid Discipline
- **Status**: ✅ PASS
- **Evidence**: Unit tests for confidence calculation, decimal parsing, header detection. Component tests for each extractor. Integration tests for end-to-end extraction flow.

## Project Structure

### Documentation (this feature)

```text
specs/009-extraction-core/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    ├── extractor-port.yaml
    └── canonical-output-schema.json
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── domain/
│   │   └── extraction/
│   │       ├── ports/
│   │       │   └── extractor_port.py
│   │       ├── canonical_output.py      # Pydantic schema
│   │       └── confidence.py            # Confidence calculation
│   ├── infrastructure/
│   │   └── extractors/
│   │       ├── excel_extractor.py
│   │       ├── csv_extractor.py
│   │       ├── pdf_text_extractor.py    # Future
│   │       └── extractor_registry.py
│   ├── workers/
│   │   └── extraction_worker.py         # Celery task
│   └── api/
│       └── v1/
│           └── extraction/
│               └── retry.py             # Manual retry endpoint
└── tests/
    ├── unit/
    │   └── extraction/
    │       ├── test_confidence_calculation.py
    │       ├── test_decimal_parsing.py
    │       └── test_canonical_schema.py
    ├── component/
    │   └── extractors/
    │       ├── test_excel_extractor.py
    │       ├── test_csv_extractor.py
    │       └── test_extractor_registry.py
    └── integration/
        └── extraction/
            └── test_extraction_pipeline_e2e.py

fixtures/
├── orders/
│   ├── order_excel_valid.xlsx
│   ├── order_csv_valid.csv
│   └── order_pdf_text.pdf
```

**Structure Decision**: Web application with extraction domain logic separated from infrastructure (extractors). ExtractorPort defines interface, adapters implement for each file type. Registry pattern for extractor selection.

## Complexity Tracking

> **No violations identified. All constitution checks pass.**
