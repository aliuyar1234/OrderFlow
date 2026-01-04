"""CSV extractor - Rule-based extraction from CSV files.

Extracts order line items from CSV files using Python csv module.
Implements ExtractorPort interface for hexagonal architecture.

SSOT Reference: §7 (Extraction Logic)
"""

import csv
import io
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional, Any, List, Dict

from domain.extraction.canonical_output import (
    CanonicalExtractionOutput,
    ExtractionOrderHeader,
    ExtractionLineItem,
)
from domain.extraction.confidence import calculate_confidence
from domain.extraction.ports import ExtractorPort, ExtractionResult
from domain.documents.ports.object_storage_port import ObjectStoragePort

logger = logging.getLogger(__name__)


class CSVExtractor(ExtractorPort):
    """CSV file extractor using rule-based parsing.

    Extracts order line items from CSV files. Handles delimiter detection
    (comma vs semicolon), European decimal format, and flexible column mapping.

    Features:
    - Automatic delimiter detection (comma or semicolon)
    - European decimal format support (comma as decimal separator)
    - Flexible column name mapping (handles various naming conventions)
    - Encoding detection (UTF-8, ISO-8859-1, Windows-1252)
    - RFC 4180 compliant CSV parsing (quoted values, escaping)
    """

    # Column name mapping patterns
    SKU_COLUMNS = ['sku', 'artikel', 'artikelnummer', 'item', 'product', 'product_code', 'item_no']
    QTY_COLUMNS = ['qty', 'quantity', 'menge', 'anzahl', 'amount']
    UOM_COLUMNS = ['uom', 'unit', 'einheit', 'unit_of_measure']
    PRICE_COLUMNS = ['price', 'preis', 'unit_price', 'unit_preis', 'unitprice']
    DESCRIPTION_COLUMNS = ['description', 'beschreibung', 'bezeichnung', 'name', 'product_name']
    CURRENCY_COLUMNS = ['currency', 'währung', 'waehrung', 'curr']

    def __init__(self, storage: ObjectStoragePort):
        """Initialize CSV extractor.

        Args:
            storage: Object storage adapter for retrieving files
        """
        self.storage = storage

    async def extract(self, document: Any) -> ExtractionResult:
        """Extract structured order data from CSV file.

        Args:
            document: Document entity with storage_key, mime_type, etc.

        Returns:
            ExtractionResult with canonical output or error
        """
        start_time = datetime.utcnow()
        metrics = {}

        try:
            # Retrieve file from storage
            logger.info(f"Retrieving CSV file from storage: {document.storage_key}")
            file_stream = await self.storage.retrieve_file(document.storage_key)

            # Read file content
            file_bytes = file_stream.read()
            file_stream.close()

            # Detect encoding
            encoding = self._detect_encoding(file_bytes)
            text = file_bytes.decode(encoding)
            logger.debug(f"Detected encoding: {encoding}")

            # Detect delimiter
            delimiter = self._detect_delimiter(text)
            logger.debug(f"Detected delimiter: {repr(delimiter)}")

            # Parse CSV
            reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

            # Normalize column names (lowercase, strip whitespace)
            if reader.fieldnames:
                reader.fieldnames = [
                    col.lower().strip() if col else ''
                    for col in reader.fieldnames
                ]

            # Extract lines
            lines = []
            row_count = 0
            for idx, row in enumerate(reader, start=1):
                row_count += 1
                line = self._extract_line(row, idx)
                if line and self._is_valid_line(line):
                    lines.append(line)

            logger.info(f"Extracted {len(lines)} lines from {row_count} rows")

            # CSV typically doesn't have header metadata (only line items)
            header = ExtractionOrderHeader()

            # Build canonical output
            output = CanonicalExtractionOutput(
                order=header,
                lines=lines,
                metadata={
                    'encoding': encoding,
                    'delimiter': delimiter,
                    'total_rows': row_count,
                }
            )

            # Calculate confidence
            confidence, confidence_breakdown = calculate_confidence(output)

            # Calculate metrics
            runtime_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            metrics = {
                'runtime_ms': runtime_ms,
                'row_count': row_count,
                'lines_extracted': len(lines),
                'encoding': encoding,
                'delimiter': delimiter,
                'confidence': confidence,
                **confidence_breakdown,
            }

            logger.info(
                f"CSV extraction succeeded: {len(lines)} lines, "
                f"confidence={confidence:.3f}, runtime={runtime_ms}ms"
            )

            return ExtractionResult(
                success=True,
                output=output,
                confidence=confidence,
                metrics=metrics,
                extractor_version=self.version,
            )

        except Exception as e:
            runtime_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            logger.error(f"CSV extraction failed: {e}", exc_info=True)

            return ExtractionResult(
                success=False,
                error=str(e),
                confidence=0.0,
                metrics={'runtime_ms': runtime_ms, 'error_type': type(e).__name__},
                extractor_version=self.version,
            )

    def _detect_encoding(self, file_bytes: bytes) -> str:
        """Detect file encoding.

        Tries UTF-8 first, then falls back to ISO-8859-1 and Windows-1252.

        Args:
            file_bytes: Raw file bytes

        Returns:
            Encoding name (utf-8, iso-8859-1, or windows-1252)
        """
        # Try UTF-8 first (most common)
        try:
            file_bytes.decode('utf-8')
            return 'utf-8'
        except UnicodeDecodeError:
            pass

        # Try ISO-8859-1 (Latin-1, common in Europe)
        try:
            file_bytes.decode('iso-8859-1')
            return 'iso-8859-1'
        except UnicodeDecodeError:
            pass

        # Fallback to Windows-1252 (Western Europe)
        return 'windows-1252'

    def _detect_delimiter(self, text: str) -> str:
        """Detect CSV delimiter (comma or semicolon).

        Semicolon is common in European CSV files (since comma is decimal separator).

        Args:
            text: CSV file content as text

        Returns:
            Delimiter character (',' or ';')
        """
        # Get first line
        first_line = text.split('\n')[0] if '\n' in text else text

        # Count delimiters
        comma_count = first_line.count(',')
        semicolon_count = first_line.count(';')

        # Use semicolon if it appears more frequently
        if semicolon_count > comma_count:
            return ';'

        # Default to comma
        return ','

    def _extract_line(self, row: Dict[str, str], line_no: int) -> Optional[ExtractionLineItem]:
        """Extract line item from CSV row.

        Uses flexible column name mapping to handle various CSV formats.

        Args:
            row: CSV row as dictionary (column_name -> value)
            line_no: Line number (1-based)

        Returns:
            ExtractionLineItem or None if row is empty
        """
        # Map columns to values using fuzzy matching
        customer_sku = self._find_column_value(row, self.SKU_COLUMNS)
        description = self._find_column_value(row, self.DESCRIPTION_COLUMNS)
        qty_str = self._find_column_value(row, self.QTY_COLUMNS)
        uom = self._find_column_value(row, self.UOM_COLUMNS)
        price_str = self._find_column_value(row, self.PRICE_COLUMNS)
        currency = self._find_column_value(row, self.CURRENCY_COLUMNS)

        # Parse numeric values
        qty = self._parse_decimal(qty_str)
        unit_price = self._parse_decimal(price_str)

        # Skip empty rows
        if not customer_sku and not description and qty is None:
            return None

        return ExtractionLineItem(
            line_no=line_no,
            customer_sku=customer_sku,
            description=description,
            qty=qty,
            uom=uom,
            unit_price=unit_price,
            currency=currency,
        )

    def _find_column_value(self, row: Dict[str, str], column_patterns: List[str]) -> Optional[str]:
        """Find column value using fuzzy name matching.

        Args:
            row: CSV row dictionary
            column_patterns: List of possible column names (lowercase)

        Returns:
            Column value or None if not found
        """
        for col_name, value in row.items():
            col_name_lower = col_name.lower().strip()

            # Check if column name matches any pattern
            for pattern in column_patterns:
                if pattern in col_name_lower or col_name_lower in pattern:
                    # Found matching column
                    if value and str(value).strip():
                        return str(value).strip()

        return None

    def _parse_decimal(self, value: Any) -> Optional[Decimal]:
        """Parse decimal value, handling European format (comma as decimal separator).

        Args:
            value: Value to parse (str, int, float, or None)

        Returns:
            Decimal or None if parsing fails
        """
        if value is None:
            return None

        # Handle numeric types
        if isinstance(value, (int, float)):
            try:
                return Decimal(str(value))
            except InvalidOperation:
                return None

        # Handle string type
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None

            # Remove whitespace and special characters
            value = value.replace(' ', '')
            value = value.replace('\u202f', '')  # Narrow no-break space

            # Handle European format (comma for decimal, dot for thousands)
            if ',' in value and '.' not in value:
                # Simple case: only comma (decimal separator)
                value = value.replace(',', '.')
            elif ',' in value and '.' in value:
                # Complex case: both comma and dot
                comma_pos = value.rindex(',')
                dot_pos = value.rindex('.')

                if comma_pos > dot_pos:
                    # European format: 1.234,56
                    value = value.replace('.', '').replace(',', '.')
                else:
                    # US format: 1,234.56
                    value = value.replace(',', '')

            try:
                return Decimal(value)
            except (InvalidOperation, ValueError):
                logger.warning(f"Failed to parse decimal value: {value}")
                return None

        return None

    def _is_valid_line(self, line: ExtractionLineItem) -> bool:
        """Check if line has minimum required data.

        Args:
            line: Line item to validate

        Returns:
            True if line has minimal required data
        """
        return line.customer_sku is not None or line.description is not None

    def supports(self, mime_type: str) -> bool:
        """Check if this extractor supports the given MIME type.

        Args:
            mime_type: MIME type string

        Returns:
            True if this extractor can handle CSV files
        """
        return mime_type in ['text/csv', 'application/csv']

    @property
    def version(self) -> str:
        """Extractor version identifier.

        Returns:
            Version string for tracking
        """
        return 'csv_v1'

    @property
    def priority(self) -> int:
        """Priority for extractor selection (lower = higher priority).

        Returns:
            Priority (10 = high priority for rule-based extractors)
        """
        return 10
