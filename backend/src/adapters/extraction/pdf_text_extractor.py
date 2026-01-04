"""
PDF text extractor using pdfplumber.
Implements rule-based extraction for text-based PDFs per SSOT §7.2.
"""
import io
import re
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
import time

import pdfplumber

from src.domain.extraction.ports.extractor_port import ExtractorPort, ExtractionResult
from src.domain.extraction.canonical_output import (
    CanonicalExtractionOutput,
    ExtractionOrderHeader,
    ExtractionLineItem
)
from src.domain.extraction.confidence import calculate_confidence

from .format_detector import normalize_uom, parse_decimal
from .column_mapper import ColumnMapper


class PDFTextExtractor(ExtractorPort):
    """
    Rule-based PDF text extractor using pdfplumber.
    Per SSOT §7.2: Used for text-based PDFs with text_coverage_ratio >= 0.15.
    """

    def __init__(self):
        self.column_mapper = ColumnMapper()

    @property
    def version(self) -> str:
        return "pdf_rule_v1"

    @property
    def priority(self) -> int:
        return 10  # High priority (rule-based, fast)

    def supports(self, mime_type: str) -> bool:
        """Check if this extractor supports the MIME type."""
        return mime_type.lower() == 'application/pdf'

    async def extract(self, document: Any) -> ExtractionResult:
        """
        Extract order data from text-based PDF.

        Args:
            document: Document entity with storage_key, mime_type, etc.

        Returns:
            ExtractionResult with canonical output
        """
        start_time = time.time()
        warnings = []

        try:
            # Load file content
            file_content = await self._load_document_content(document)

            # Open PDF with pdfplumber
            pdf = pdfplumber.open(io.BytesIO(file_content))

            # Calculate text coverage metrics per SSOT §7.2.1
            page_count = len(pdf.pages)
            text_chars_total = 0
            extracted_text = []

            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_chars_total += len(page_text)
                    extracted_text.append(page_text)

            # Calculate text coverage ratio per SSOT §7.2.1
            # text_coverage_ratio = min(1, text_chars_total / (page_count * 2500))
            if page_count > 0:
                text_coverage_ratio = min(1.0, text_chars_total / (page_count * 2500))
            else:
                text_coverage_ratio = 0.0

            # Check if text-based per SSOT §7.2.2
            if text_coverage_ratio < 0.15 or text_chars_total < 500:
                warnings.append({
                    'code': 'LOW_TEXT_COVERAGE',
                    'message': f'Text coverage {text_coverage_ratio:.2f} < 0.15, LLM recommended'
                })
                # This is a signal that LLM should be used instead
                # But we'll still try rule-based extraction

            # Join all text
            full_text = '\n'.join(extracted_text)

            # Try to extract tables using pdfplumber
            tables_data = []
            for page in pdf.pages:
                tables = page.extract_tables()
                if tables:
                    tables_data.extend(tables)

            pdf.close()

            # Extract header metadata from text
            header_metadata = self._extract_header_from_text(full_text)

            # Extract line items
            lines_data = []

            if tables_data:
                # Try table-based extraction first
                lines_data = self._extract_from_tables(tables_data)

            if not lines_data:
                # Fallback to text-based extraction
                lines_data = self._extract_from_text(full_text)

            # Build order header
            order_header = ExtractionOrderHeader(
                order_number=header_metadata.get('order_number'),
                order_date=self._parse_date(header_metadata.get('order_date')),
                currency=header_metadata.get('currency') or 'EUR',
                reference=header_metadata.get('reference')
            )

            # Create canonical output
            canonical_output = CanonicalExtractionOutput(
                order=order_header,
                lines=lines_data,
                metadata={
                    'page_count': page_count,
                    'text_chars_total': text_chars_total,
                    'text_coverage_ratio': text_coverage_ratio,
                    'tables_found': len(tables_data),
                    'extraction_method': 'table' if tables_data else 'text'
                }
            )

            # Calculate confidence
            confidence_score, confidence_breakdown = calculate_confidence(canonical_output)

            # Adjust confidence based on text coverage
            if text_coverage_ratio < 0.15:
                confidence_score *= 0.5  # Reduce confidence for low text coverage

            # Check for warnings
            if len(lines_data) == 0:
                warnings.append({
                    'code': 'NO_LINES',
                    'message': 'No line items extracted from PDF'
                })

            missing_sku_count = sum(1 for line in lines_data if not line.customer_sku)
            if missing_sku_count > 0:
                warnings.append({
                    'code': 'MISSING_SKU',
                    'message': f'{missing_sku_count} lines missing SKU'
                })

            # Calculate runtime
            runtime_ms = int((time.time() - start_time) * 1000)

            return ExtractionResult(
                success=True,
                output=canonical_output,
                confidence=round(confidence_score, 3),
                extractor_version=self.version,
                metrics={
                    'runtime_ms': runtime_ms,
                    'page_count': page_count,
                    'text_chars_total': text_chars_total,
                    'text_coverage_ratio': round(text_coverage_ratio, 3),
                    'lines_extracted': len(lines_data),
                    'warnings_count': len(warnings),
                    'tables_found': len(tables_data),
                    **confidence_breakdown
                }
            )

        except Exception as e:
            runtime_ms = int((time.time() - start_time) * 1000)
            return ExtractionResult(
                success=False,
                error=f"PDF extraction failed: {str(e)}",
                confidence=0.0,
                extractor_version=self.version,
                metrics={'runtime_ms': runtime_ms}
            )

    def _extract_header_from_text(self, text: str) -> Dict[str, Optional[str]]:
        """
        Extract header metadata from PDF text.
        Per SSOT FR-008: Extract from patterns.

        Args:
            text: Full PDF text

        Returns:
            Dict with extracted metadata
        """
        metadata = {
            'order_number': None,
            'order_date': None,
            'currency': None,
            'reference': None
        }

        # Patterns per SSOT FR-008
        patterns = {
            'order_number': [
                r'bestellnummer[:\s]+([A-Z0-9-]+)',
                r'order\s+no[:\s\.]+([A-Z0-9-]+)',
                r'po[#\s:]+([A-Z0-9-]+)',
                r'auftrag[:\s]+([A-Z0-9-]+)'
            ],
            'order_date': [
                r'bestelldatum[:\s]+([\d./-]+)',
                r'datum[:\s]+([\d./-]+)',
                r'order\s+date[:\s]+([\d./-]+)',
                r'date[:\s]+([\d./-]+)'
            ],
            'currency': [
                r'währung[:\s]+([A-Z]{3})',
                r'currency[:\s]+([A-Z]{3})',
                r'\b(EUR|CHF|USD|GBP)\b'
            ],
            'reference': [
                r'referenz[:\s]+([A-Z0-9-]+)',
                r'reference[:\s]+([A-Z0-9-]+)',
                r'ihr\s+zeichen[:\s]+([A-Z0-9-]+)'
            ]
        }

        for field, field_patterns in patterns.items():
            for pattern in field_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    metadata[field] = match.group(1).strip()
                    break

        return metadata

    def _extract_from_tables(self, tables: List[List[List[str]]]) -> List[ExtractionLineItem]:
        """
        Extract line items from PDF tables.

        Args:
            tables: List of tables (each table is list of rows, each row is list of cells)

        Returns:
            List of extracted line items
        """
        lines = []

        for table in tables:
            if not table or len(table) < 2:
                continue  # Need at least header + 1 data row

            # First row is likely header
            headers = [str(cell).strip() if cell else '' for cell in table[0]]

            # Map columns
            column_mapping = self.column_mapper.map_columns(headers)

            if not column_mapping or len(column_mapping) < 2:
                continue  # Not a data table

            # Extract data rows
            for row_idx, row in enumerate(table[1:], start=1):
                if not row or not any(cell for cell in row):
                    continue

                row_data = [str(cell).strip() if cell else '' for cell in row]
                line_item = self._extract_line_from_row(
                    row_data, headers, column_mapping, len(lines) + 1
                )

                if line_item:
                    lines.append(line_item)

        return lines

    def _extract_from_text(self, text: str) -> List[ExtractionLineItem]:
        """
        Extract line items from unstructured text.
        This is a best-effort fallback when tables aren't detected.

        Args:
            text: PDF text content

        Returns:
            List of extracted line items
        """
        lines = []

        # Try to find line item patterns
        # Pattern: line_no, SKU, description, qty, uom, price
        # Example: "1 AB-123 Kabel NYM-J 3x1,5 10 M 1,23"

        line_pattern = re.compile(
            r'(\d{1,3})\s+([A-Z0-9-/]+)\s+(.{5,50}?)\s+(\d+[,.]?\d*)\s+([A-Z]{1,5})\s+(\d+[,.]?\d+)',
            re.MULTILINE
        )

        for match in line_pattern.finditer(text):
            line_no = int(match.group(1))
            customer_sku = match.group(2)
            description = match.group(3).strip()
            qty_raw = match.group(4)
            uom_raw = match.group(5)
            price_raw = match.group(6)

            # Parse qty and price
            qty = parse_decimal(qty_raw, ',')
            if qty:
                qty = Decimal(str(qty))

            unit_price = parse_decimal(price_raw, ',')
            if unit_price:
                unit_price = Decimal(str(unit_price))

            # Normalize UoM
            uom = normalize_uom(uom_raw)

            line_item = ExtractionLineItem(
                line_no=line_no,
                customer_sku=customer_sku,
                description=description,
                qty=qty,
                uom=uom,
                unit_price=unit_price
            )

            lines.append(line_item)

        return lines

    def _extract_line_from_row(
        self,
        row: List[str],
        headers: List[str],
        column_mapping: Dict[str, str],
        line_no: int
    ) -> Optional[ExtractionLineItem]:
        """Extract a single line item from table row."""
        # Build field dict
        fields = {}
        for header_idx, header in enumerate(headers):
            if header_idx >= len(row):
                continue

            canonical_field = column_mapping.get(header)
            if canonical_field:
                fields[canonical_field] = row[header_idx]

        # Parse fields
        customer_sku = fields.get('customer_sku', '').strip() or None
        description = fields.get('description', '').strip() or None
        qty_raw = fields.get('qty')
        uom_raw = fields.get('uom')
        price_raw = fields.get('unit_price')

        # Parse quantity (support both comma and dot)
        qty = None
        if qty_raw:
            qty_val = parse_decimal(qty_raw, ',')
            if qty_val is None:
                qty_val = parse_decimal(qty_raw, '.')
            if qty_val is not None:
                qty = Decimal(str(qty_val))

        # Parse price
        unit_price = None
        if price_raw:
            price_val = parse_decimal(price_raw, ',')
            if price_val is None:
                price_val = parse_decimal(price_raw, '.')
            if price_val is not None:
                unit_price = Decimal(str(price_val))

        # Normalize UoM
        uom = normalize_uom(uom_raw)

        # Get line number from data if available
        line_no_field = fields.get('line_no')
        if line_no_field:
            try:
                line_no = int(line_no_field)
            except ValueError:
                pass

        # Skip if no meaningful data
        if not customer_sku and not description and not qty:
            return None

        return ExtractionLineItem(
            line_no=line_no,
            customer_sku=customer_sku,
            description=description,
            qty=qty,
            uom=uom,
            unit_price=unit_price
        )

    def _parse_date(self, date_str: Optional[str]):
        """Parse date string to date object."""
        if not date_str:
            return None

        formats = [
            '%Y-%m-%d',
            '%d.%m.%Y',
            '%d/%m/%Y',
            '%m/%d/%Y',
            '%Y/%m/%d',
            '%d-%m-%Y'
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue

        return None

    async def _load_document_content(self, document: Any) -> bytes:
        """Load document content from storage."""
        if hasattr(document, 'get_content'):
            return await document.get_content()

        raise NotImplementedError("Document content loading not implemented")
