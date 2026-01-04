# Tasks: Rule-Based Extractors

**Feature Branch**: `010-extractors-rule-based`
**Generated**: 2025-12-27

## Phase 1: Setup

- [x] T001 Add CSV parsing dependencies to requirements
- [x] T002 Add chardet for encoding detection
- [x] T003 Create column mapping configuration

## Phase 2: CSV Parser

- [x] T004 Implement CSV separator auto-detection (`;`, `,`, `\t`, `|`)
- [x] T005 Implement decimal separator detection (comma vs dot)
- [x] T006 Support encoding auto-detection (UTF-8, Windows-1252, ISO-8859-1)
- [x] T007 Handle quoted fields with embedded separators
- [x] T008 Skip empty rows

## Phase 3: XLSX Parser

- [x] T009 Implement Excel file parsing with openpyxl
- [x] T010 Process first sheet by default
- [x] T011 Handle merged cells (use top-left value)
- [x] T012 Detect header row position
- [x] T013 Extract metadata from first N rows

## Phase 4: [US1] Structured CSV/Excel Order Processing

- [x] T014 [US1] Implement DACH column header mapping (German/English)
- [x] T015 [US1] Map Artikelnummer → customer_sku_raw
- [x] T016 [US1] Map Menge → qty
- [x] T017 [US1] Map Einheit → uom
- [x] T018 [US1] Map Preis → unit_price
- [x] T019 [US1] Map Beschreibung → product_description
- [x] T020 [US1] Normalize UoM values to canonical codes
- [x] T021 [US1] Assign sequential line_no if not present

## Phase 5: Header Extraction

- [x] T022 Extract external_order_number from patterns (Bestellnummer:, Order No:, PO#)
- [x] T023 Extract order_date from patterns (Bestelldatum:, Order Date:, Datum:)
- [x] T024 Extract currency or default to org currency
- [x] T025 Normalize dates to ISO format (YYYY-MM-DD)
- [x] T026 Scan first 20 rows for header metadata

## Phase 6: [US2] Text-Based PDF Order Extraction

- [x] T027 [US2] Implement PDF text extraction using pdfplumber
- [x] T028 [US2] Calculate text_chars_total and page_count
- [x] T029 [US2] Calculate text_coverage_ratio per SSOT §7.2.1
- [x] T030 [US2] Store extracted text in extracted_text_storage_key
- [x] T031 [US2] Detect table structures in extracted text
- [x] T032 [US2] Extract line items from tables

## Phase 7: [US3] Decimal and Separator Auto-Detection

- [x] T033 [US3] Analyze first 100 rows for separator patterns
- [x] T034 [US3] Count occurrences of `;`, `,`, `\t`
- [x] T035 [US3] Detect comma decimal separator from numeric patterns
- [x] T036 [US3] Convert comma decimals to dot internally
- [x] T037 [US3] Try alternative separators on parse failure
- [x] T038 [US3] Log warnings for ambiguous formats

## Phase 8: Confidence Calculation

- [x] T039 Implement per-field confidence scoring
- [x] T040 Calculate header confidence (0.20*order_num + 0.15*date + 0.20*currency + ...)
- [x] T041 Calculate line confidence (0.30*sku + 0.30*qty + 0.20*uom + 0.20*price)
- [x] T042 Apply sanity penalties per SSOT §7.8.1
- [x] T043 Store field-level confidence in output

## Phase 9: Warnings Generation

- [x] T044 Generate warning for missing mandatory columns
- [x] T045 Generate warning for unparseable numeric values
- [x] T046 Generate warning for unmapped columns
- [x] T047 Generate warning for lines missing SKU or description
- [x] T048 Include warnings array in canonical output

## Phase 10: Integration with Decision Logic

- [x] T049 Check extraction_confidence ≥0.60 threshold
- [x] T050 Check lines_count > 0
- [x] T051 Trigger LLM fallback if confidence <0.60 or lines==0
- [x] T052 Set extractor_version to 'rule_v1' in output

## Phase 11: Polish

- [ ] T053 Create test fixtures for DACH region CSVs
- [ ] T054 Create test fixtures for common ERP Excel formats
- [ ] T055 Document column mapping table
- [ ] T056 Add fuzzy column header matching
- [ ] T057 Log unmapped columns for improvement
