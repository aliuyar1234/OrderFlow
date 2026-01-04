# Implementation Plan: Rule-Based Extractors (CSV, XLSX, PDF)

**Branch**: `010-extractors-rule-based` | **Date**: 2025-12-27 | **Spec**: [specs/010-extractors-rule-based/spec.md](./spec.md)

## Summary

Implement rule-based extraction for CSV, Excel (XLSX), and text-based PDF files. The system auto-detects file formats, separators (including DACH-specific semicolon/comma decimal), maps column headers to canonical fields, and outputs structured JSON per §7.1. Rule-based extraction provides zero-cost, low-latency processing for structured orders and serves as the first-stage extractor before LLM fallback. Achieves extraction_confidence ≥0.85 for well-structured files, triggering LLM only when necessary (confidence <0.60 or 0 lines).

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, Pydantic, openpyxl, pdfplumber, csv (stdlib), chardet
**Storage**: PostgreSQL 16 (extraction_run, document tables), S3-compatible Object Storage (document files, extracted text)
**Testing**: pytest (unit, integration), fixtures for sample CSV/Excel/PDF files
**Target Platform**: Linux server (Celery workers for async extraction)
**Project Type**: Web application (backend extraction service, frontend displays results)
**Performance Goals**: p95 latency <3s for CSV/Excel extraction, text extraction <5s for 10-page PDF
**Constraints**: Support DACH decimal comma format, handle German/English headers, max file size 25MB
**Scale/Scope**: Process 1000+ documents/day per org, support 500+ line orders

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. SSOT-First** | ✅ PASS | All extraction logic follows §7.1, §7.2, §7.8.1 specs. Canonical output schema enforced. |
| **II. Hexagonal Architecture** | ✅ PASS | Implements ExtractorPort interface (§3.5). CSV/Excel/PDF parsers are adapters. Domain logic independent of parser libraries. |
| **III. Multi-Tenant Isolation** | ✅ PASS | All extraction_run records include org_id, filtered in queries. Document access controlled via org_id. |
| **IV. Idempotent Processing** | ✅ PASS | Re-processing same document with same extractor_version yields identical result. No duplicate drafts created. |
| **V. AI-Layer Deterministic Control** | ✅ PASS | Rule-based extraction is deterministic (no AI). Confidence scores follow §7.8.1 formula exactly. |
| **VI. Observability First-Class** | ✅ PASS | Extraction metrics logged (runtime_ms, lines_extracted, warnings). Structured logging for errors. |
| **VII. Test Pyramid Discipline** | ✅ PASS | Unit tests for each parser, integration tests for end-to-end extraction, fixtures for various file formats. |

## Project Structure

### Documentation (this feature)

```text
specs/010-extractors-rule-based/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── contracts/           # Phase 1 output
    └── extraction-api.yaml
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── domain/
│   │   └── extraction/
│   │       ├── ports.py                    # ExtractorPort interface
│   │       ├── models.py                   # ExtractionResult, CanonicalOutput
│   │       └── confidence.py               # Confidence calculation (§7.8.1)
│   ├── adapters/
│   │   └── extraction/
│   │       ├── csv_extractor.py            # CSV parser with auto-detection
│   │       ├── excel_extractor.py          # XLSX parser (openpyxl)
│   │       ├── pdf_text_extractor.py       # PDF text extraction (pdfplumber)
│   │       ├── column_mapper.py            # Header mapping (DE/EN)
│   │       └── format_detector.py          # Separator/decimal detection
│   ├── services/
│   │   └── extraction_service.py           # Orchestrates extraction, stores results
│   └── workers/
│       └── extraction_worker.py            # Celery task for async processing
└── tests/
    ├── unit/
    │   ├── test_csv_extractor.py
    │   ├── test_excel_extractor.py
    │   ├── test_pdf_text_extractor.py
    │   ├── test_column_mapper.py
    │   └── test_confidence.py
    ├── integration/
    │   └── test_extraction_workflow.py     # Upload → extract → Draft created
    └── fixtures/
        ├── sample.csv                      # DACH format (semicolon, comma decimal)
        ├── sample.xlsx                     # Excel with header rows
        └── sample.pdf                      # Text-based PDF
```

**Structure Decision**: Web application structure chosen (backend/frontend split). Backend contains extraction domain logic, adapters for file formats, and Celery worker tasks. Frontend (separate, not in this spec) will display extraction results. Follows hexagonal architecture with clear port/adapter separation.

## Complexity Tracking

No violations detected. All constitution principles are satisfied.
