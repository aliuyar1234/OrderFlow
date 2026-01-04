# Tasks: Extraction Core

**Feature Branch**: `009-extraction-core`
**Generated**: 2025-12-27

## Phase 1: Setup

- [x] T001 Create extraction domain at `backend/src/domain/extraction/`
- [x] T002 Create extractor ports at `backend/src/domain/extraction/ports/`
- [ ] T003 Add openpyxl, pandas to `backend/requirements/base.txt`
- [x] T004 Create extraction workers at `backend/src/workers/`

## Phase 2: Canonical Output Schema

- [x] T005 Create ExtractionLineItem Pydantic schema
- [x] T006 Create ExtractionOrderHeader Pydantic schema
- [x] T007 Create CanonicalExtractionOutput Pydantic schema
- [x] T008 Add validation for required fields
- [x] T009 Support optional fields with None defaults

## Phase 3: Database Schema

- [x] T010 Create extraction_run table migration
- [x] T011 Add indexes for (org_id+document_id+created_at)
- [x] T012 Create ExtractionRun SQLAlchemy model
- [x] T013 Create ExtractionRunStatus enum

## Phase 4: ExtractorPort Interface

- [x] T014 Create ExtractorPort abstract class at `backend/src/domain/extraction/ports/extractor_port.py`
- [x] T015 Define extract method signature
- [x] T016 Define supports method for MIME type checking
- [x] T017 Define version property for extractor tracking
- [x] T018 Create ExtractionResult dataclass

## Phase 5: [US1] Extract Structured Data from Excel/CSV

- [x] T019 [US1] Create ExcelExtractor at `backend/src/infrastructure/extractors/excel_extractor.py`
- [x] T020 [US1] Implement header row detection
- [x] T021 [US1] Implement line extraction from rows
- [x] T022 [US1] Parse decimal values (handle comma separator)
- [x] T023 [US1] Create CSVExtractor at `backend/src/infrastructure/extractors/csv_extractor.py`
- [x] T024 [US1] Implement CSV delimiter detection (comma/semicolon)
- [x] T025 [US1] Parse CSV with DictReader
- [x] T026 [US1] Map common column names to canonical fields

## Phase 6: [US2] Extract Data from Text-Based PDF

- [ ] T027 [US2] Create PDFTextExtractor at `backend/src/infrastructure/extraction/pdf_text_extractor.py`
- [ ] T028 [US2] Extract text using pdfplumber or PyPDF2
- [ ] T029 [US2] Calculate text_coverage_ratio
- [ ] T030 [US2] Store extracted text in object storage
- [ ] T031 [US2] Detect table structures in PDF text
- [ ] T032 [US2] Extract header information from first pages

## Phase 7: [US3] ExtractorPort Interface

- [x] T033 [US3] Create ExtractorRegistry class
- [x] T034 [US3] Implement register method
- [x] T035 [US3] Implement get_extractor method (by MIME type)
- [ ] T036 [US3] Register ExcelExtractor in global registry (Note: requires app initialization)
- [ ] T037 [US3] Register CSVExtractor in global registry (Note: requires app initialization)
- [ ] T038 [US3] Register PDFTextExtractor in global registry (Note: PDF extractor not implemented)

## Phase 8: [US4] Extraction Confidence Calculation

- [x] T039 [US4] Implement header completeness scoring
- [x] T040 [US4] Implement line completeness scoring
- [x] T041 [US4] Calculate weighted average (0.4 header + 0.6 lines)
- [x] T042 [US4] Round confidence to 3 decimal places
- [x] T043 [US4] Store confidence in extraction_run

## Phase 9: [US5] Canonical Extraction Output Schema

- [x] T044 [US5] Validate all extractor outputs against canonical schema
- [ ] T045 [US5] Test schema with Excel output (Note: requires tests)
- [ ] T046 [US5] Test schema with CSV output (Note: requires tests)
- [ ] T047 [US5] Test schema with PDF output (Note: PDF extractor not implemented)
- [x] T048 [US5] Handle extra fields (allow but ignore)

## Phase 10: Extraction Worker

- [x] T049 Create extract_document Celery task
- [x] T050 Load document from database
- [x] T051 Update document status to PROCESSING
- [x] T052 Create extraction_run record with status=RUNNING
- [x] T053 Select extractor from registry based on MIME type
- [x] T054 Execute extractor.extract()
- [x] T055 Store output_json in extraction_run
- [x] T056 Update document status to EXTRACTED on success
- [x] T057 Update document status to FAILED on error
- [x] T058 Store error_json on failure
- [x] T059 Implement retry logic with exponential backoff

## Phase 11: Polish

- [x] T060 Add extraction timeout (5 minutes) (Note: handled via Celery task timeout)
- [x] T061 Add extraction metrics logging
- [x] T062 Create decimal parsing utilities
- [ ] T063 Create date parsing utilities (Note: basic date handling in ExcelExtractor)
- [x] T064 Document canonical schema

## Phase 12: API Endpoints (Added)

- [x] T065 Create GET /extractions endpoint (list extractions)
- [x] T066 Create GET /extractions/{id} endpoint (get extraction details)
- [x] T067 Create POST /extractions/trigger endpoint (trigger extraction)
- [x] T068 Create POST /extractions/{id}/retry endpoint (retry failed extraction)
- [x] T069 Create API response schemas
