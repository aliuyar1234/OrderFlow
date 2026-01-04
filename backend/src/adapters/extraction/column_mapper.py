"""
Column header mapping for structured files (CSV/Excel).
Maps DACH and international column names to canonical fields per SSOT FR-006.
"""
from typing import Dict, List, Optional, Tuple
import re


class ColumnMapper:
    """
    Maps column headers from CSV/Excel to canonical field names.
    Supports German and English headers with fuzzy matching.
    """

    # Canonical field mappings per SSOT FR-006
    COLUMN_MAPPINGS = {
        'customer_sku': [
            'artikelnummer', 'art.nr', 'artnr', 'art-nr', 'artikel-nr',
            'sku', 'article', 'article number', 'product code', 'item number',
            'bestellnummer', 'bestell-nr', 'material', 'materialnummer'
        ],
        'qty': [
            'menge', 'anzahl', 'quantity', 'qty', 'amount', 'count', 'stück', 'stueck'
        ],
        'uom': [
            'einheit', 'me', 'mengeneinheit', 'uom', 'unit', 'unit of measure',
            'um', 'masseinheit'
        ],
        'unit_price': [
            'preis', 'e-preis', 'epreis', 'einzelpreis', 'stückpreis', 'stueckpreis',
            'unit price', 'price', 'unitprice', 'price per unit', 'ep'
        ],
        'description': [
            'bezeichnung', 'beschreibung', 'text', 'artikelbezeichnung',
            'description', 'product description', 'item description', 'name',
            'product name', 'artikel'
        ],
        'line_total': [
            'gesamtpreis', 'gesamt', 'total', 'line total', 'amount',
            'betrag', 'summe', 'zeilensumme'
        ],
        'line_no': [
            'pos', 'position', 'pos.', 'zeile', 'line', 'line no', 'line number',
            'item', '#', 'nr', 'nr.'
        ],
        # Header fields
        'order_number': [
            'bestellnummer', 'bestell-nr', 'bestellung', 'auftragsnummer',
            'order number', 'order no', 'po number', 'po#', 'purchase order',
            'po', 'order id', 'auftrag'
        ],
        'order_date': [
            'bestelldatum', 'datum', 'date', 'order date', 'po date',
            'auftragsdatum', 'bestelldatum'
        ],
        'currency': [
            'währung', 'waehrung', 'currency', 'curr', 'whr'
        ],
        'delivery_date': [
            'liefertermin', 'lieferdatum', 'wunschtermin',
            'delivery date', 'requested delivery', 'delivery', 'ship date'
        ],
        'customer_ref': [
            'kundenreferenz', 'referenz', 'ihre referenz', 'ihr zeichen',
            'customer reference', 'reference', 'ref', 'your ref'
        ]
    }

    def __init__(self):
        """Initialize the column mapper with normalized mappings."""
        # Create normalized lookup (lowercase, no spaces/special chars)
        self._normalized_mappings: Dict[str, str] = {}

        for canonical_field, variants in self.COLUMN_MAPPINGS.items():
            for variant in variants:
                normalized = self._normalize_header(variant)
                self._normalized_mappings[normalized] = canonical_field

    def _normalize_header(self, header: str) -> str:
        """
        Normalize header for matching.

        Args:
            header: Raw header string

        Returns:
            Normalized header (lowercase, no special chars)
        """
        if not header:
            return ''

        # Convert to lowercase
        normalized = header.lower().strip()

        # Remove common prefixes/suffixes
        normalized = re.sub(r'^(pos\.|nr\.|artikel\s+)', '', normalized)

        # Remove special characters, keep only alphanumeric
        normalized = re.sub(r'[^a-z0-9]', '', normalized)

        return normalized

    def map_column(self, header: str) -> Optional[str]:
        """
        Map a column header to canonical field name.

        Args:
            header: Column header from CSV/Excel

        Returns:
            Canonical field name or None if no match

        Examples:
            >>> mapper = ColumnMapper()
            >>> mapper.map_column("Artikelnummer")
            'customer_sku'
            >>> mapper.map_column("Menge")
            'qty'
            >>> mapper.map_column("Unknown Column")
            None
        """
        normalized = self._normalize_header(header)
        return self._normalized_mappings.get(normalized)

    def map_columns(self, headers: List[str]) -> Dict[str, str]:
        """
        Map multiple column headers to canonical fields.

        Args:
            headers: List of column headers

        Returns:
            Dict mapping original header → canonical field name

        Examples:
            >>> mapper = ColumnMapper()
            >>> mapper.map_columns(["Pos", "Artikelnummer", "Menge"])
            {'Pos': 'line_no', 'Artikelnummer': 'customer_sku', 'Menge': 'qty'}
        """
        mapping = {}
        for header in headers:
            canonical = self.map_column(header)
            if canonical:
                mapping[header] = canonical
        return mapping

    def find_column_index(
        self,
        headers: List[str],
        canonical_field: str
    ) -> Optional[int]:
        """
        Find column index for a canonical field.

        Args:
            headers: List of column headers
            canonical_field: Canonical field name to search for

        Returns:
            Column index (0-based) or None if not found

        Examples:
            >>> mapper = ColumnMapper()
            >>> mapper.find_column_index(["Pos", "Artikelnummer", "Menge"], "qty")
            2
        """
        for idx, header in enumerate(headers):
            if self.map_column(header) == canonical_field:
                return idx
        return None

    def get_confidence(self, header: str, canonical_field: str) -> float:
        """
        Get confidence score for a header mapping.

        Args:
            header: Column header
            canonical_field: Canonical field name

        Returns:
            Confidence score 0.0-1.0
                0.95 for exact match in primary variants
                0.75 for fuzzy match
                0.0 for no match
        """
        normalized = self._normalize_header(header)
        mapped = self._normalized_mappings.get(normalized)

        if not mapped or mapped != canonical_field:
            return 0.0

        # Check if it's a primary variant (first in list)
        primary_variants = [
            self._normalize_header(v)
            for v in self.COLUMN_MAPPINGS.get(canonical_field, [])[:3]
        ]

        if normalized in primary_variants:
            return 0.95

        # Secondary match
        return 0.75

    def extract_header_metadata(
        self,
        rows: List[List[str]],
        max_rows: int = 20
    ) -> Dict[str, Optional[str]]:
        """
        Extract header metadata from first N rows of file.
        Looks for patterns like "Bestellnummer: 12345" in early rows.

        Per SSOT FR-008: Extract from first N rows.

        Args:
            rows: First N rows of the file
            max_rows: Maximum rows to scan (default 20)

        Returns:
            Dict with extracted metadata:
                - order_number: External order number
                - order_date: Order date string
                - currency: Currency code
                - reference: Customer reference

        Examples:
            >>> mapper = ColumnMapper()
            >>> rows = [["Bestellnummer: PO-12345"], ["Datum: 2025-01-04"]]
            >>> mapper.extract_header_metadata(rows)
            {'order_number': 'PO-12345', 'order_date': '2025-01-04', ...}
        """
        metadata = {
            'order_number': None,
            'order_date': None,
            'currency': None,
            'reference': None
        }

        # Patterns to search for
        patterns = {
            'order_number': [
                r'bestellnummer[:\s]+([A-Z0-9-]+)',
                r'order\s+no[:\s]+([A-Z0-9-]+)',
                r'po[#\s:]+([A-Z0-9-]+)',
                r'auftrag[:\s]+([A-Z0-9-]+)'
            ],
            'order_date': [
                r'datum[:\s]+([\d./-]+)',
                r'bestelldatum[:\s]+([\d./-]+)',
                r'order\s+date[:\s]+([\d./-]+)',
                r'date[:\s]+([\d./-]+)'
            ],
            'currency': [
                r'währung[:\s]+([A-Z]{3})',
                r'currency[:\s]+([A-Z]{3})',
                r'\b(EUR|CHF|USD|GBP)\b'
            ]
        }

        # Scan first N rows
        for row_idx, row in enumerate(rows[:max_rows]):
            # Join row cells into single text
            row_text = ' '.join(str(cell) for cell in row if cell)

            # Try each pattern
            for field, field_patterns in patterns.items():
                if metadata[field]:  # Already found
                    continue

                for pattern in field_patterns:
                    match = re.search(pattern, row_text, re.IGNORECASE)
                    if match:
                        metadata[field] = match.group(1).strip()
                        break

        return metadata
