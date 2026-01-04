# Research: Rule-Based Extractors

**Feature**: 010-extractors-rule-based
**Date**: 2025-12-27

## Key Decisions and Rationale

### Decision 1: CSV Separator Auto-Detection Strategy

**Choice**: Use Python's `csv.Sniffer()` as primary detection, fallback to pattern frequency analysis.

**Rationale**:
- `csv.Sniffer()` handles most common cases (comma, semicolon, tab)
- DACH region files often use `;` (semicolon) as separator with `,` (comma) as decimal
- Pattern frequency backup: count occurrences of `;`, `,`, `\t`, `|` in first 5 rows, select most frequent
- Edge case handling: if detection fails, try each separator and validate result (expect consistent column count)

**Alternatives Rejected**:
- Hard-coded separator per org: Too rigid, doesn't handle mixed sources
- User-specified separator: Adds manual step, defeats automation goal

### Decision 2: Decimal Comma Detection

**Choice**: Regex pattern analysis on numeric columns to detect comma vs dot decimal separator.

**Rationale**:
- DACH files use `10,50` (comma) for 10.50
- Pattern: if numbers contain commas and no dots → comma is decimal
- Pattern: if numbers contain dots and commas → dot is decimal, comma is thousands separator
- Apply detection per-column (some columns might have different formats)

**Implementation**:
```python
def detect_decimal_separator(values: list[str]) -> str:
    comma_count = sum(1 for v in values if ',' in v)
    dot_count = sum(1 for v in values if '.' in v)

    if comma_count > 0 and dot_count == 0:
        return ','  # DACH format
    elif dot_count > 0 and comma_count == 0:
        return '.'  # US format
    elif comma_count > 0 and dot_count > 0:
        # Mixed: assume dot=decimal, comma=thousands (or vice versa based on position)
        # Check: does comma appear after dot (e.g., "1.234,56")? → comma=decimal
        # Otherwise: "1,234.56" → dot=decimal
        sample = next((v for v in values if ',' in v and '.' in v), None)
        if sample:
            comma_pos = sample.rindex(',')
            dot_pos = sample.rindex('.')
            return ',' if comma_pos > dot_pos else '.'
    return '.'  # default
```

### Decision 3: Excel Multi-Sheet Handling (MVP)

**Choice**: Process first sheet only in MVP. Log warning if multiple sheets detected.

**Rationale**:
- 95% of order files have single sheet
- Multi-sheet complexity deferred to post-MVP (requires heuristics: which sheet contains order data?)
- First sheet is usually the main data sheet in standard templates

**Future Enhancement**: Detect sheet names like "Order", "Bestellung", "Lines" and prefer those.

### Decision 4: PDF Text Extraction Library

**Choice**: `pdfplumber` (primary), fallback to `PyPDF2` if pdfplumber fails.

**Rationale**:
- `pdfplumber` provides better table detection and layout preservation
- `PyPDF2` is more robust for malformed PDFs but less accurate for tables
- Both are widely used, stable libraries

**Text Coverage Ratio Calculation** (per §7.2.1):
```python
text_coverage_ratio = text_chars_total / (page_count * 2000)
# 2000 = estimated chars per typical business document page
# <0.15 → likely scanned/image PDF → trigger vision LLM
```

### Decision 5: Column Header Mapping Strategy

**Choice**: Fuzzy matching with bilingual (DE/EN) lookup table.

**Rationale**:
- Normalize headers: lowercase, strip whitespace, remove special chars
- Maintain mapping dict with common variations:
  ```python
  HEADER_MAPPING = {
      "customer_sku_raw": ["artikelnummer", "artnr", "sku", "bestellnummer", "article", "partnumber"],
      "qty": ["menge", "anzahl", "quantity", "qty", "stück"],
      "uom": ["einheit", "me", "uom", "unit", "mengeneinheit"],
      "unit_price": ["preis", "epreis", "einzelpreis", "unitprice", "price"],
      "product_description": ["bezeichnung", "beschreibung", "description", "produktname"],
  }
  ```
- Match by: exact match first, then substring match, then Levenshtein distance <2

**Unmapped Columns**: Log as warning, include in extraction debug metadata for learning.

### Decision 6: Confidence Scoring Implementation

**Choice**: Implement §7.8.1 formula exactly with field presence and format validity scoring.

**Rationale**:
- Header confidence: weighted avg of field-level confidences (external_order_number=0.20, order_date=0.15, currency=0.20, customer_hint=0.25, delivery_date=0.10, ship_to=0.10)
- Line confidence: weighted avg of (customer_sku=0.30, qty=0.30, uom=0.20, unit_price=0.20)
- Field confidence rules:
  - Null value → 0.0
  - Present + valid format → base confidence (0.85-0.95 depending on mapping certainty)
  - Present + invalid format → reduced confidence (0.50-0.70)
- Overall extraction_confidence = (0.40 * header_score + 0.60 * avg_line_score) * sanity_penalties

**Sanity Penalties**:
- 0 lines extracted → * 0.60
- CSV/Excel with >50% empty rows → * 0.80
- Unmapped critical columns (SKU, Qty) → * 0.70

### Decision 7: UoM Normalization

**Choice**: Map common UoM variations to canonical codes per §5.2.

**Rationale**:
- Canonical codes: ST, M, CM, MM, KG, G, L, ML, KAR, PAL, SET
- Mapping table:
  ```python
  UOM_MAPPING = {
      "ST": ["st", "stk", "stück", "stuck", "piece", "pc", "pcs", "ea"],
      "M": ["m", "meter", "metre"],
      "KG": ["kg", "kilo", "kilogramm"],
      "L": ["l", "liter", "litre"],
      "KAR": ["kar", "karton", "carton", "ctn"],
      "PAL": ["pal", "palette", "pallet"],
  }
  ```
- Case-insensitive match, log warning if unrecognized UoM (pass through as-is)

## Best Practices for AI Integration

*Not directly applicable to rule-based extraction, but relevant for LLM fallback integration:*

- Rule-based extraction always runs first for text PDFs (fast, deterministic)
- Store extracted text in object storage (extracted_text_storage_key) for LLM fallback
- Calculate confidence immediately to determine if LLM is needed
- Decision logic (§7.2.2): if extraction_confidence <0.60 OR lines_count==0 → trigger LLM

## Best Practices for Extraction Patterns

### CSV/Excel Extraction
1. **Header Detection**: Scan first 20 rows for metadata patterns before table data
2. **Row Skipping**: Skip empty rows, rows with <50% populated columns
3. **Type Inference**: Infer column types from first 10 data rows
4. **Error Tolerance**: Continue processing on parse errors, log warnings

### PDF Text Extraction
1. **Layout Preservation**: Use pdfplumber's table detection when available
2. **Text Cleaning**: Remove header/footer repetitions across pages
3. **Line Merging**: Merge wrapped lines (continuation patterns)
4. **Encoding Handling**: Try UTF-8, fallback to latin-1/windows-1252

### Confidence Transparency
- Per-field confidence allows UI to highlight low-confidence fields for review
- Warnings array helps Ops understand what went wrong
- Debug metadata (column mapping, format detection results) aids troubleshooting

## Performance Considerations

- CSV parsing: Use streaming for large files (>10k rows), process in chunks
- Excel parsing: openpyxl read-only mode for performance
- PDF text extraction: Cache extracted text to avoid re-processing
- Parallel processing: Run extraction for multiple documents concurrently (Celery worker pool)

## Error Handling Strategy

- File format errors: Catch exceptions, return extraction_confidence=0.0, create Draft with 0 lines
- Encoding errors: Try multiple encodings, log warning if fallback used
- Corrupt files: Graceful failure, mark extraction_run status=FAILED, notify user
- Timeout protection: Set max processing time (60s for CSV/Excel, 120s for PDF)

## Testing Data Requirements

### CSV Test Files
- Standard format (comma, dot decimal)
- DACH format (semicolon, comma decimal)
- Tab-separated
- Pipe-separated
- UTF-8 and Windows-1252 encoding
- With/without header metadata rows

### Excel Test Files
- Single sheet, clean structure
- Multi-sheet (first sheet processed)
- Merged cells in header
- Different column orders
- Empty rows interspersed

### PDF Test Files
- Clean text-based (high text_coverage_ratio)
- Poor layout (irregular tables)
- Mixed scanned + text pages
- Multi-page (10+ pages)
- Rotated pages
