# Extraction Helpers

This directory contains helper utilities for document extraction.

**NOTE**: Extractor implementations (CSVExtractor, ExcelExtractor, etc.) have been consolidated into `infrastructure/extractors/` to follow proper hexagonal architecture.

## Architecture

The extraction system follows **Hexagonal Architecture (Ports & Adapters)** per SSOT §3.5:

- **Domain Layer** (`src/domain/extraction/`): Defines ports (interfaces) and domain models
- **Infrastructure Layer** (`src/infrastructure/extractors/`): Concrete extractor implementations
- **Adapters Layer** (`src/adapters/extraction/`): Helper utilities for extraction

## Components

1. **ColumnMapper** (`column_mapper.py`)
   - Maps DACH (German) and English column headers to canonical fields
   - Supports fuzzy matching (normalized, case-insensitive)
   - Extracts header metadata from first N rows
   - Per SSOT FR-006

2. **FormatDetector** (`format_detector.py`)
   - Encoding detection with chardet
   - Separator detection (CSV)
   - Decimal separator detection (comma vs dot)
   - Numeric parsing with locale support
   - UoM normalization to canonical codes (per SSOT §6.2)

3. **PDFTextExtractor** (`pdf_text_extractor.py`)
   - Supports: `application/pdf`
   - Uses pdfplumber library
   - Calculates text coverage ratio per SSOT §7.2.1
   - Extracts tables when available
   - Falls back to pattern matching for unstructured text
   - Version: `pdf_rule_v1`
   - Priority: 10 (high)

## Usage

### Basic Extraction

```python
from src.infrastructure.extractors import get_global_registry

# Get registry
registry = get_global_registry()

# Get appropriate extractor for a document
extractor = registry.get_extractor(
    mime_type='text/csv',
    filename='order.csv'
)

# Extract
result = await extractor.extract(document)

if result.success:
    print(f"Extracted {len(result.output.lines)} lines")
    print(f"Confidence: {result.confidence:.3f}")
else:
    print(f"Extraction failed: {result.error}")
```

### Using Helper Utilities

```python
from src.adapters.extraction import ColumnMapper, detect_encoding, normalize_uom

# Map columns
mapper = ColumnMapper()
column_mapping = mapper.map_columns(['Artikelnummer', 'Menge', 'Preis'])
# Returns: {'Artikelnummer': 'customer_sku', 'Menge': 'qty', 'Preis': 'unit_price'}

# Detect encoding
encoding = detect_encoding(file_bytes)

# Normalize UoM
canonical_uom = normalize_uom('Stück')  # Returns: 'ST'
```

### Confidence Scores

All extractors calculate confidence per SSOT §7.8.1:

- **Header confidence**: Weighted by field presence and format validity
- **Line confidence**: Weighted average of SKU, qty, uom, price
- **Overall confidence**: 30% header + 70% lines
- **Sanity penalties**: Applied for missing data, warnings

Confidence threshold for LLM fallback: **0.60** (per SSOT §7.2.2.B)

### DACH Locale Support

Per SSOT FR-002, the extractors support DACH (German-speaking region) formats:

- **Decimal separator**: Comma (`,`) e.g., `10,50` = 10.5
- **Thousands separator**: Dot (`.`) e.g., `1.234,56` = 1234.56
- **CSV separator**: Semicolon (`;`) is common in DACH
- **Column headers**: German names like "Artikelnummer", "Menge", "Einheit"

### Column Mapping

The `ColumnMapper` recognizes these canonical fields:

| Canonical Field | German Headers | English Headers |
|----------------|----------------|-----------------|
| `customer_sku` | Artikelnummer, Art.Nr, Bestellnummer | SKU, Article Number, Product Code |
| `qty` | Menge, Anzahl, Stück | Quantity, Qty, Amount |
| `uom` | Einheit, ME, Mengeneinheit | UoM, Unit, Unit of Measure |
| `unit_price` | Preis, E-Preis, Einzelpreis | Unit Price, Price |
| `description` | Bezeichnung, Beschreibung, Artikelbezeichnung | Description, Product Description |
| `line_no` | Pos, Position | Line, Line No |

### UoM Normalization

Per SSOT §6.2, UoM values are normalized to canonical codes:

| Input | Canonical |
|-------|-----------|
| Stk, Stück, pcs, piece | ST |
| m, Meter | M |
| kg, Kilogramm | KG |
| Karton, ctn | KAR |
| Palette, pallet | PAL |

## Extraction Pipeline

1. **Document arrives** → Stored in S3
2. **MIME type detected** → ExtractorRegistry selects extractor
3. **Rule-based extraction runs** → Fast, zero-cost
4. **Confidence calculated** → Per SSOT §7.8.1
5. **Decision point**:
   - If confidence ≥ 0.60 AND lines > 0 → **Success, create Draft**
   - If confidence < 0.60 OR lines == 0 → **Trigger LLM fallback** (not implemented in this phase)

## Testing

Run tests with:

```bash
pytest backend/tests/unit/test_csv_extractor.py
pytest backend/tests/unit/test_excel_extractor.py
pytest backend/tests/unit/test_pdf_text_extractor.py
pytest backend/tests/unit/test_column_mapper.py
```

## Future Extensions

- **LLMExtractor**: For scanned PDFs and complex layouts (priority: 90)
- **EDIExtractor**: For EDIFACT/XML formats
- **APIExtractor**: For direct API integrations (e.g., Shopify orders)

## References

- **SSOT §7.1**: Canonical Extraction Output Schema
- **SSOT §7.2**: Decision Logic (Rule-Based vs LLM)
- **SSOT §7.8.1**: Confidence Calculation Formula
- **SSOT §6.2**: UoM Standardization
- **SSOT FR-001 to FR-015**: Functional Requirements
