"""PDF text extractor - Rule-based extraction from text-based PDFs.

Extracts order header and line items from text-based PDFs using pdfplumber.
Implements ExtractorPort interface for hexagonal architecture.

SSOT Reference: §7.2 (PDF text extraction), §7.8 (text_coverage_ratio)
"""

import io
import logging
import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Optional, List, Any, Dict

import pdfplumber
from pdfplumber.page import Page

from domain.extraction.canonical_output import (
    CanonicalExtractionOutput,
    ExtractionOrderHeader,
    ExtractionLineItem,
)
from domain.extraction.confidence import calculate_confidence
from domain.extraction.ports import ExtractorPort, ExtractionResult
from domain.documents.ports.object_storage_port import ObjectStoragePort

logger = logging.getLogger(__name__)


class PDFTextExtractor(ExtractorPort):
    """PDF text extractor using rule-based parsing.

    Extracts order data from text-based PDF files using pdfplumber library.
    Handles table detection, text extraction, and header parsing.

    Features:
    - Text coverage ratio calculation (determines if PDF is text-based or scanned)
    - Table structure detection using regex patterns
    - Header information extraction from first pages
    - Extracted text storage for debugging/LLM fallback
    - European decimal format support (comma as decimal separator)

    Note: This extractor is designed for well-structured text-based PDFs.
    Scanned PDFs (text_coverage_ratio < 0.15) should use LLM extraction instead.
    """

    # Characters per page threshold for coverage ratio (SSOT §7.2.1)
    CHARS_PER_PAGE_THRESHOLD = 2500

    # Minimum text coverage for text-based PDF (SSOT §7.2.2)
    TEXT_COVERAGE_THRESHOLD = 0.15

    def __init__(self, storage: ObjectStoragePort):
        """Initialize PDF text extractor.

        Args:
            storage: Object storage adapter for retrieving and storing files
        """
        self.storage = storage

    async def extract(self, document: Any) -> ExtractionResult:
        """Extract structured order data from PDF file.

        Args:
            document: Document entity with storage_key, mime_type, etc.

        Returns:
            ExtractionResult with canonical output or error
        """
        start_time = datetime.utcnow()
        metrics = {}

        try:
            # Retrieve file from storage
            logger.info(f"Retrieving PDF file from storage: {document.storage_key}")
            file_stream = await self.storage.retrieve_file(document.storage_key)

            # Read into BytesIO for pdfplumber
            file_content = io.BytesIO(file_stream.read())
            file_stream.close()

            # Open PDF with pdfplumber
            with pdfplumber.open(file_content) as pdf:
                page_count = len(pdf.pages)
                logger.info(f"Processing PDF with {page_count} pages")

                # Extract text from all pages
                all_text = ""
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    all_text += page_text + "\n"

                # Calculate text coverage ratio (SSOT §7.2.1)
                text_chars_total = len(all_text.strip())
                text_coverage_ratio = self._calculate_text_coverage(
                    text_chars_total, page_count
                )

                logger.info(
                    f"PDF text stats: {text_chars_total} chars, "
                    f"coverage_ratio={text_coverage_ratio:.3f}"
                )

                # Store extracted text in object storage for debugging/LLM fallback
                extracted_text_key = await self._store_extracted_text(
                    document.org_id, document.id, all_text
                )

                # Check if PDF is text-based (SSOT §7.2.2)
                if text_coverage_ratio < self.TEXT_COVERAGE_THRESHOLD:
                    logger.warning(
                        f"PDF appears to be scanned (coverage={text_coverage_ratio:.3f} "
                        f"< {self.TEXT_COVERAGE_THRESHOLD}). Rule-based extraction may fail."
                    )

                # Detect table structures and extract lines
                lines = self._extract_lines_from_text(all_text, pdf.pages)
                logger.info(f"Extracted {len(lines)} lines from PDF text")

                # Extract header information from first pages
                header = self._extract_header_from_text(all_text, pdf.pages[:3])

                # Build canonical output
                output = CanonicalExtractionOutput(
                    order=header,
                    lines=lines,
                    metadata={
                        'page_count': page_count,
                        'text_chars_total': text_chars_total,
                        'text_coverage_ratio': float(text_coverage_ratio),
                        'extracted_text_key': extracted_text_key,
                    }
                )

                # Calculate confidence
                confidence, confidence_breakdown = calculate_confidence(output)

                # Calculate metrics
                runtime_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                metrics = {
                    'runtime_ms': runtime_ms,
                    'page_count': page_count,
                    'text_chars_total': text_chars_total,
                    'text_coverage_ratio': float(text_coverage_ratio),
                    'lines_extracted': len(lines),
                    'confidence': confidence,
                    **confidence_breakdown,
                }

                logger.info(
                    f"PDF extraction succeeded: {len(lines)} lines, "
                    f"confidence={confidence:.3f}, coverage={text_coverage_ratio:.3f}, "
                    f"runtime={runtime_ms}ms"
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
            logger.error(f"PDF extraction failed: {e}", exc_info=True)

            return ExtractionResult(
                success=False,
                error=str(e),
                confidence=0.0,
                metrics={'runtime_ms': runtime_ms, 'error_type': type(e).__name__},
                extractor_version=self.version,
            )

    def _calculate_text_coverage(self, text_chars_total: int, page_count: int) -> float:
        """Calculate text coverage ratio.

        SSOT §7.2.1: text_coverage_ratio = min(1, text_chars_total / (page_count * 2500))
        Interpretation: ~2500 chars/page ≈ "text-rich" PDF

        Args:
            text_chars_total: Total extractable characters
            page_count: Number of pages

        Returns:
            Coverage ratio (0.0-1.0)
        """
        if page_count == 0:
            return 0.0

        expected_chars = page_count * self.CHARS_PER_PAGE_THRESHOLD
        ratio = text_chars_total / expected_chars if expected_chars > 0 else 0.0
        return min(1.0, ratio)

    async def _store_extracted_text(
        self, org_id: str, document_id: str, text: str
    ) -> str:
        """Store extracted text in object storage for debugging/LLM fallback.

        Args:
            org_id: Organization ID
            document_id: Document ID
            text: Extracted text content

        Returns:
            Storage key where text was saved
        """
        storage_key = f"orgs/{org_id}/documents/{document_id}/extracted_text.txt"

        try:
            text_bytes = text.encode('utf-8')
            text_stream = io.BytesIO(text_bytes)

            await self.storage.store_file(
                key=storage_key,
                file_stream=text_stream,
                content_type='text/plain',
                file_size=len(text_bytes),
            )

            logger.debug(f"Stored extracted text at: {storage_key}")
            return storage_key

        except Exception as e:
            logger.warning(f"Failed to store extracted text: {e}")
            return ""

    def _extract_lines_from_text(
        self, text: str, pages: List[Page]
    ) -> List[ExtractionLineItem]:
        """Extract line items from PDF text using table detection.

        Uses multiple strategies:
        1. pdfplumber table detection (best for clean tables)
        2. Regex pattern matching for table-like structures
        3. Line-by-line parsing with heuristics

        Args:
            text: Full extracted text
            pages: List of pdfplumber Page objects

        Returns:
            List of extracted line items
        """
        lines = []

        # Strategy 1: Try pdfplumber's built-in table detection
        for page_idx, page in enumerate(pages, start=1):
            tables = page.extract_tables()

            for table in tables:
                if not table or len(table) < 2:  # Need header + at least 1 data row
                    continue

                # Try to extract lines from table
                table_lines = self._extract_lines_from_table(table)
                if table_lines:
                    lines.extend(table_lines)
                    logger.debug(
                        f"Extracted {len(table_lines)} lines from table on page {page_idx}"
                    )

        # Strategy 2: If no tables found, try regex patterns
        if not lines:
            logger.debug("No tables detected, trying regex pattern matching")
            lines = self._extract_lines_from_regex_patterns(text)

        # Renumber lines sequentially
        for idx, line in enumerate(lines, start=1):
            line.line_no = idx

        return lines

    def _extract_lines_from_table(self, table: List[List]) -> List[ExtractionLineItem]:
        """Extract line items from a detected table.

        Args:
            table: Table data (list of rows, each row is a list of cells)

        Returns:
            List of extracted line items
        """
        if not table or len(table) < 2:
            return []

        lines = []

        # First row is assumed to be header - detect column positions
        header_row = [str(cell).lower().strip() if cell else "" for cell in table[0]]

        # Map common column names to indices
        col_map = self._map_table_columns(header_row)

        # Extract data rows (skip header)
        for row_idx, row in enumerate(table[1:], start=1):
            if not row or all(not cell or str(cell).strip() == "" for cell in row):
                continue  # Skip empty rows

            line = self._extract_line_from_table_row(row, col_map, row_idx)
            if line and self._is_valid_line(line):
                lines.append(line)

        return lines

    def _map_table_columns(self, header_row: List[str]) -> Dict[str, int]:
        """Map table column names to standard field names.

        Args:
            header_row: List of column headers (lowercase)

        Returns:
            Dict mapping field names to column indices
        """
        col_map = {}

        # Define column name patterns
        sku_patterns = ['sku', 'artikel', 'artikelnr', 'item', 'product', 'art.nr']
        desc_patterns = ['description', 'bezeichnung', 'beschreibung', 'name', 'desc']
        qty_patterns = ['qty', 'menge', 'quantity', 'anzahl', 'qté']
        uom_patterns = ['uom', 'unit', 'einheit', 'me', 'unité']
        price_patterns = ['price', 'preis', 'unit price', 'einzelpreis', 'prix']
        currency_patterns = ['currency', 'währung', 'curr', 'monnaie']
        total_patterns = ['total', 'amount', 'betrag', 'summe', 'montant']

        for idx, col_name in enumerate(header_row):
            if not col_name:
                continue

            # Check each pattern list
            if any(pattern in col_name for pattern in sku_patterns):
                col_map.setdefault('customer_sku', idx)
            elif any(pattern in col_name for pattern in desc_patterns):
                col_map.setdefault('description', idx)
            elif any(pattern in col_name for pattern in qty_patterns):
                col_map.setdefault('qty', idx)
            elif any(pattern in col_name for pattern in uom_patterns):
                col_map.setdefault('uom', idx)
            elif any(pattern in col_name for pattern in price_patterns):
                col_map.setdefault('unit_price', idx)
            elif any(pattern in col_name for pattern in currency_patterns):
                col_map.setdefault('currency', idx)
            elif any(pattern in col_name for pattern in total_patterns):
                col_map.setdefault('line_total', idx)

        return col_map

    def _extract_line_from_table_row(
        self, row: List, col_map: Dict[str, int], line_no: int
    ) -> Optional[ExtractionLineItem]:
        """Extract a line item from a table row.

        Args:
            row: Table row cells
            col_map: Column mapping from _map_table_columns
            line_no: Line number

        Returns:
            ExtractionLineItem or None if row is invalid
        """
        # Extract values using column map
        customer_sku = self._get_cell_string(row, col_map.get('customer_sku'))
        description = self._get_cell_string(row, col_map.get('description'))
        qty = self._parse_decimal(self._get_cell_value(row, col_map.get('qty')))
        uom = self._get_cell_string(row, col_map.get('uom'))
        unit_price = self._parse_decimal(self._get_cell_value(row, col_map.get('unit_price')))
        currency = self._get_cell_string(row, col_map.get('currency'))
        line_total = self._parse_decimal(self._get_cell_value(row, col_map.get('line_total')))

        return ExtractionLineItem(
            line_no=line_no,
            customer_sku=customer_sku,
            description=description,
            qty=qty,
            uom=uom,
            unit_price=unit_price,
            currency=currency,
            line_total=line_total,
        )

    def _extract_lines_from_regex_patterns(self, text: str) -> List[ExtractionLineItem]:
        """Extract line items using regex patterns when table detection fails.

        Looks for common order line patterns like:
        - "ABC123  Product Name  10  PCS  12.50"
        - "SKU-001 | Description | 5 | EUR 25.00"

        Args:
            text: Full PDF text

        Returns:
            List of extracted line items
        """
        lines = []
        line_no = 1

        # Pattern: SKU (alphanumeric) followed by description, quantity, and optional price
        # This is a simplified heuristic - real-world PDFs vary greatly
        pattern = re.compile(
            r'([A-Z0-9\-_./]+)\s+([A-Za-z0-9\s,.\-äöüßÄÖÜ]+?)\s+'
            r'(\d+[,.]?\d*)\s*([A-Z]{2,4})?\s*'
            r'(\d+[,.]?\d*)?',
            re.MULTILINE
        )

        for match in pattern.finditer(text):
            sku = match.group(1)
            description = match.group(2).strip()
            qty_str = match.group(3)
            uom = match.group(4)
            price_str = match.group(5)

            # Parse values
            qty = self._parse_decimal(qty_str)
            unit_price = self._parse_decimal(price_str) if price_str else None

            # Create line item
            line = ExtractionLineItem(
                line_no=line_no,
                customer_sku=sku,
                description=description,
                qty=qty,
                uom=uom,
                unit_price=unit_price,
            )

            if self._is_valid_line(line):
                lines.append(line)
                line_no += 1

        # Limit to reasonable number of lines (avoid false positives)
        if len(lines) > 500:
            logger.warning(
                f"Regex extracted {len(lines)} lines, truncating to 500 "
                "(possible false positives)"
            )
            lines = lines[:500]

        return lines

    def _extract_header_from_text(
        self, text: str, first_pages: List[Page]
    ) -> ExtractionOrderHeader:
        """Extract order header information from first pages.

        Searches for patterns like:
        - "Order Number: 12345" or "PO: 67890"
        - "Date: 2024-01-15" or "Order Date: 15.01.2024"
        - "Currency: EUR"

        Args:
            text: Full PDF text
            first_pages: First few pages (typically header info is here)

        Returns:
            ExtractionOrderHeader with any found fields
        """
        header = ExtractionOrderHeader()

        # Limit search to first 3000 characters (header area)
        search_text = text[:3000]

        # Extract order number
        order_patterns = [
            r'(?:order\s*(?:number|nr|no|#)|po|bestellung|commande)\s*:?\s*([A-Z0-9\-/_]+)',
            r'(?:auftrag|purchase\s*order)\s*:?\s*([A-Z0-9\-/_]+)',
        ]

        for pattern in order_patterns:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                header.order_number = match.group(1).strip()
                break

        # Extract order date
        date_patterns = [
            r'(?:order\s*date|date|datum|bestelldatum)\s*:?\s*(\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4})',
            r'(?:order\s*date|date|datum)\s*:?\s*(\d{4}[./\-]\d{1,2}[./\-]\d{1,2})',
        ]

        for pattern in date_patterns:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                parsed_date = self._parse_date(date_str)
                if parsed_date:
                    header.order_date = parsed_date
                    break

        # Extract currency
        currency_pattern = r'(?:currency|währung|curr)\s*:?\s*([A-Z]{3})'
        match = re.search(currency_pattern, search_text, re.IGNORECASE)
        if match:
            header.currency = match.group(1).upper()

        # Extract delivery date
        delivery_patterns = [
            r'(?:delivery\s*date|lieferdatum|requested\s*delivery)\s*:?\s*(\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4})',
            r'(?:delivery\s*date|lieferdatum)\s*:?\s*(\d{4}[./\-]\d{1,2}[./\-]\d{1,2})',
        ]

        for pattern in delivery_patterns:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                parsed_date = self._parse_date(date_str)
                if parsed_date:
                    header.delivery_date = parsed_date
                    break

        return header

    def _get_cell_value(self, cells: List, index: Optional[int]) -> Any:
        """Safely get cell value by index.

        Args:
            cells: List of cell values
            index: Cell index (can be None)

        Returns:
            Cell value or None if index is None or out of range
        """
        if index is None or index >= len(cells):
            return None
        return cells[index]

    def _get_cell_string(self, cells: List, index: Optional[int]) -> Optional[str]:
        """Safely get cell value as string.

        Args:
            cells: List of cell values
            index: Cell index (can be None)

        Returns:
            String value or None if empty/missing
        """
        value = self._get_cell_value(cells, index)
        if value is None:
            return None
        str_value = str(value).strip()
        return str_value if str_value else None

    def _parse_decimal(self, value: Any) -> Optional[Decimal]:
        """Parse decimal value, handling European format (comma as decimal separator).

        Args:
            value: Value to parse (int, float, str, or None)

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

            # Remove currency symbols and spaces
            value = re.sub(r'[€$£¥\s]', '', value)

            # Handle European format: replace comma with dot
            # Remove thousand separators (spaces, dots in European format)
            value = value.replace('\u202f', '')  # Remove narrow no-break space

            # Check if this uses European format (comma for decimal)
            if ',' in value and '.' not in value:
                # Simple case: only comma (decimal separator)
                value = value.replace(',', '.')
            elif ',' in value and '.' in value:
                # Complex case: both comma and dot
                # Determine which is decimal separator by position
                comma_pos = value.rindex(',')
                dot_pos = value.rindex('.')

                if comma_pos > dot_pos:
                    # Comma is decimal separator (European: 1.234,56)
                    value = value.replace('.', '').replace(',', '.')
                else:
                    # Dot is decimal separator (US: 1,234.56)
                    value = value.replace(',', '')

            try:
                return Decimal(value)
            except (InvalidOperation, ValueError):
                logger.debug(f"Failed to parse decimal value: {value}")
                return None

        return None

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date string in various formats.

        Supports:
        - DD.MM.YYYY (European)
        - DD/MM/YYYY
        - YYYY-MM-DD (ISO)
        - MM/DD/YYYY (US)

        Args:
            date_str: Date string to parse

        Returns:
            date object or None if parsing fails
        """
        if not date_str:
            return None

        date_str = date_str.strip()

        # Try different formats
        formats = [
            '%d.%m.%Y',  # DD.MM.YYYY
            '%d/%m/%Y',  # DD/MM/YYYY
            '%Y-%m-%d',  # YYYY-MM-DD
            '%m/%d/%Y',  # MM/DD/YYYY
            '%d.%m.%y',  # DD.MM.YY
            '%d/%m/%y',  # DD/MM/YY
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        logger.debug(f"Failed to parse date: {date_str}")
        return None

    def _is_valid_line(self, line: ExtractionLineItem) -> bool:
        """Check if line has minimum required data.

        A valid line should have at least a SKU or description.

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
            True if this extractor can handle PDF files
        """
        return mime_type == 'application/pdf'

    @property
    def version(self) -> str:
        """Extractor version identifier.

        Returns:
            Version string for tracking
        """
        return 'pdf_rule_v1'

    @property
    def priority(self) -> int:
        """Priority for extractor selection (lower = higher priority).

        Returns:
            Priority (10 = high priority for rule-based extractors)
        """
        return 10
