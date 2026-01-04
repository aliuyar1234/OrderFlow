# Feature Specification: Rule-Based Extractors (CSV, XLSX, PDF)

**Feature Branch**: `010-extractors-rule-based`
**Created**: 2025-12-27
**Status**: Draft
**Module**: extraction
**SSOT Refs**: §7.2 (Decision Logic), §7.1 (Extraction Output Schema), T-302 (CSV), T-303 (XLSX), T-304 (PDF)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Structured CSV/Excel Order Processing (Priority: P1)

An Ops user receives a CSV or Excel order file via email or upload. The system automatically extracts all order lines with high confidence without requiring AI/LLM processing, enabling immediate review and approval.

**Why this priority**: CSV and Excel files are the most common structured order formats in B2B wholesale. Rule-based extraction provides zero-cost, low-latency processing for the majority of inbound orders.

**Independent Test**: Upload a standardized CSV order file → verify all lines are extracted correctly with confidence ≥0.85 → Draft Order status becomes EXTRACTED within 5 seconds.

**Acceptance Scenarios**:

1. **Given** a CSV file with semicolon-separated values and comma decimal separators, **When** the system processes the file, **Then** it auto-detects the separator and decimal format, extracting all lines correctly
2. **Given** an Excel file with order header in rows 1-5 and line items starting at row 7, **When** the system processes the file, **Then** it detects the header section and extracts external_order_number, order_date, and all line items
3. **Given** a CSV with German column headers ("Artikelnummer", "Menge", "Einheit", "Preis"), **When** the system processes the file, **Then** it maps columns to canonical fields (customer_sku_raw, qty, uom, unit_price)

---

### User Story 2 - Text-Based PDF Order Extraction (Priority: P2)

An Ops user receives a text-based PDF purchase order. The system uses rule-based extraction to identify header information and line items from structured regions, falling back to LLM only when confidence is too low.

**Why this priority**: Many B2B orders arrive as PDF exports from ERP systems. Rule-based extraction is sufficient for well-structured PDFs and avoids LLM costs.

**Independent Test**: Upload a PDF with clear table structure → rule-based extractor identifies ≥80% of lines with confidence ≥0.60 → no LLM call triggered.

**Acceptance Scenarios**:

1. **Given** a text-based PDF with tabular line items, **When** text coverage ratio ≥0.15, **Then** rule-based extraction runs first
2. **Given** a rule-based PDF extraction with extraction_confidence ≥0.60, **When** validation completes, **Then** no LLM call is triggered
3. **Given** a rule-based PDF extraction with extraction_confidence <0.60, **When** decision logic evaluates, **Then** LLM extraction is triggered per §7.2.2.B

---

### User Story 3 - Decimal and Separator Auto-Detection (Priority: P1)

Orders from DACH region customers use comma as decimal separator and semicolon/tab as field separator. The system automatically detects these formats without configuration.

**Why this priority**: DACH market requirement. Incorrect decimal parsing causes critical pricing errors.

**Independent Test**: Process CSV with "10,50" as price → system detects comma decimal → stores 10.50 internally.

**Acceptance Scenarios**:

1. **Given** a CSV file with pattern analysis showing `;` as most common separator, **When** parsing, **Then** semicolon is used as field delimiter
2. **Given** numeric fields containing commas (e.g., "1,23"), **When** parsing, **Then** comma is interpreted as decimal separator
3. **Given** ambiguous format, **When** parsing fails, **Then** system tries alternative separators and logs warning

---

### Edge Cases

- What happens when CSV has mixed encodings (UTF-8 vs Windows-1252)?
- How does system handle Excel files with multiple sheets (which sheet to process)?
- What happens when PDF text extraction yields garbled characters (encoding issues)?
- How does system handle CSV files with quoted fields containing separator characters?
- What happens when qty/price fields contain non-numeric text (e.g., "TBD", "siehe Angebot")?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support CSV parsing with auto-detection of separator (`;`, `,`, `\t`, `|`)
- **FR-002**: System MUST support comma (`,`) as decimal separator in numeric fields (DACH requirement)
- **FR-003**: System MUST parse XLSX files (Excel 2007+) and extract first sheet by default
- **FR-004**: System MUST extract text from PDF files using standard PDF text extraction libraries
- **FR-005**: System MUST calculate `text_coverage_ratio` for PDFs per §7.2.1
- **FR-006**: System MUST map common DACH column headers to canonical fields:
  - `Artikelnummer`, `Art.Nr`, `SKU`, `Bestellnummer` → `customer_sku_raw`
  - `Menge`, `Anzahl`, `Quantity` → `qty`
  - `Einheit`, `ME`, `UoM`, `Unit` → `uom`
  - `Preis`, `E-Preis`, `Einzelpreis`, `Unit Price` → `unit_price`
  - `Bezeichnung`, `Beschreibung`, `Description` → `product_description`
- **FR-007**: System MUST normalize UoM values to canonical codes per §5.2 (ST, M, KG, L, KAR, PAL, etc.)
- **FR-008**: System MUST extract header fields from first N rows of structured files:
  - `external_order_number` from patterns: `Bestellnummer:`, `Order No:`, `PO#`
  - `order_date` from patterns: `Bestelldatum:`, `Order Date:`, `Datum:`
  - `currency` from patterns or default to org currency
- **FR-009**: System MUST assign sequential `line_no` starting from 1 if not present in source
- **FR-010**: System MUST output extraction results in canonical JSON schema per §7.1
- **FR-011**: System MUST calculate per-field confidence scores based on:
  - Field presence (0.0 if null, base confidence if present)
  - Format validity (e.g., numeric qty → 0.9, alphanumeric qty → 0.6)
  - Mapping certainty (exact header match → 0.95, fuzzy match → 0.75)
- **FR-012**: System MUST calculate `extraction_confidence` per §7.8.1
- **FR-013**: System MUST set extractor_version to `rule_v1` in output
- **FR-014**: Character encoding handling:
  1. Detect charset using chardet library with fallback order: UTF-8 → ISO-8859-1 → Windows-1252
  2. For Excel multi-sheet: use first sheet (sheet index 0)
  3. CSV quote handling per RFC 4180: doubled quotes for escaping
  4. Log encoding detection results in extraction_run.metrics_json
- **FR-015**: System MUST create warnings for:
  - Missing mandatory columns
  - Unparseable numeric values
  - Unmapped columns
  - Lines with missing SKU or description

### Key Entities

- **ExtractionRun**: Tracks processing of a document with extractor_version=`rule_v1`, status, metrics (runtime_ms, lines_extracted), error_json
- **Document**: File with mime_type (text/csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/pdf), text_coverage_ratio (for PDFs)
- **Canonical Extraction Output**: JSON per §7.1 containing order header, lines array, confidence scores, warnings, extractor_version

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: CSV/Excel files with clear structure extract with extraction_confidence ≥0.85 in ≥90% of cases
- **SC-002**: Rule-based CSV/Excel extraction completes in p95 <3 seconds per file
- **SC-003**: PDF text extraction correctly identifies text_coverage_ratio within ±0.05 accuracy
- **SC-004**: Rule-based PDF extraction achieves extraction_confidence ≥0.60 for ≥60% of text-based PDFs
- **SC-005**: Decimal comma detection works correctly for ≥99% of DACH-region files
- **SC-006**: Column header mapping achieves ≥95% accuracy on standard German/English headers
- **SC-007**: System generates <5% false warnings (warnings for actually correct data)
- **SC-008**: Rule-based extraction triggers LLM fallback per §7.2.2 only when necessary (extraction_confidence <0.60 OR lines_count==0)

## Dependencies

- **Depends on**:
  - Core infrastructure (database, object storage, worker queue)
  - Document storage and retrieval (module: documents)
  - DraftOrder creation APIs (module: draft_orders)

- **Blocks**:
  - 012-extractors-llm (LLM extraction uses rule-based as baseline/fallback input)
  - 013-draft-orders-core (needs extraction results to create drafts)

## Technical Notes

### Implementation Guidance

**CSV Parser:**
- Use Python `csv.Sniffer()` for separator auto-detection
- Implement custom decimal comma detection via regex pattern analysis
- Support encodings: UTF-8, Windows-1252, ISO-8859-1 with auto-detection via `chardet`

**XLSX Parser:**
- Use `openpyxl` or `xlrd`
- Process first sheet by default; future: allow sheet selection
- Handle merged cells gracefully (use top-left cell value)

**PDF Text Extractor:**
- Use `pdfplumber` or `PyPDF2` for text extraction
- Calculate `text_chars_total` and `page_count`
- Store extracted text in `document.extracted_text_storage_key` for debugging and LLM fallback

**Header Detection Heuristics:**
- Scan first 20 rows for patterns matching order metadata
- Use regex for common formats: `Bestellnummer:\s*(\S+)`, `Order Date:\s*(\d{2}.\d{2}.\d{4})`
- Normalize dates to ISO format YYYY-MM-DD

**Column Mapping:**
- Fuzzy match column headers (lowercase, strip whitespace, remove special chars)
- Maintain bilingual mapping table (DE/EN)
- Log unmapped columns for future improvement

**Confidence Calculation:**
- Implement §7.8.1 formula exactly
- Header fields: external_order_number (w=0.20), order_date (w=0.15), currency (w=0.20), customer_hint (w=0.25), delivery_date (w=0.10), ship_to (w=0.10)
- Line fields: customer_sku_raw (w=0.30), qty (w=0.30), uom (w=0.20), unit_price (w=0.20)
- Apply sanity penalties per §7.8.1

### Testing Strategy

**Unit Tests:**
- CSV: semicolon, comma, tab separators
- CSV: comma vs dot decimal separators
- XLSX: header detection in various row positions
- PDF: text_coverage_ratio calculation
- Column mapping: German/English headers
- Confidence scoring: various completeness levels

**Integration Tests:**
- End-to-end: upload CSV → extraction → DraftOrder created
- Fallback: low-confidence PDF triggers decision logic (mock LLM check)

**Contract Tests:**
- Extraction output JSON MUST be snapshot-tested against Pydantic schema. Use pytest-snapshot or equivalent. Schema changes require explicit snapshot update with PR review.

**Test Data:**
- Sample CSVs from DACH region suppliers (anonymized)
- Excel templates from common ERP systems (SAP, Microsoft Dynamics)
- Text-based PDF samples with varying structure quality

## SSOT References

- **§7.1**: Extraction Output Schema (canonical JSON format)
- **§7.2**: Decision Logic for Rule-Based vs LLM
- **§7.2.1**: PDF Pre-Analysis (text_coverage_ratio calculation)
- **§7.2.2**: Trigger conditions for LLM fallback
- **§7.8.1**: Extraction Confidence calculation formula
- **§5.2.4**: ExtractionRunStatus enumeration
- **§5.4.7**: extraction_run table schema
- **T-302**: CSV Parser task
- **T-303**: XLSX Parser task
- **T-304**: PDF Text Extractor task
