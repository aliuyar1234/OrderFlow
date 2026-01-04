"""Tests for canonical extraction output schema validation.

Tests that CanonicalExtractionOutput schema correctly validates data
from Excel, CSV, and PDF extractors. Ensures all extractor outputs
conform to the canonical schema contract.

SSOT Reference: §7.1 (Canonical Output Schema)
"""

import pytest
from datetime import date
from decimal import Decimal

from src.domain.extraction.canonical_output import (
    CanonicalExtractionOutput,
    ExtractionOrderHeader,
    ExtractionLineItem,
)


class TestSchemaValidationExcel:
    """T045: Test CanonicalExtractionOutput with Excel-style data.

    Excel extractors typically provide:
    - Rich header metadata (order number, date, addresses)
    - Complete line items with all fields populated
    - High data quality
    """

    def test_excel_full_extraction(self):
        """Test complete Excel extraction with all fields populated"""
        # Arrange: Excel-style data with full header and lines
        output = CanonicalExtractionOutput(
            order=ExtractionOrderHeader(
                order_number='PO-2024-001',
                order_date=date(2024, 1, 15),
                currency='EUR',
                delivery_date=date(2024, 2, 1),
                ship_to={
                    'name': 'ACME Corp',
                    'street': 'Hauptstraße 123',
                    'city': 'München',
                    'postal_code': '80331',
                    'country': 'DE',
                },
                notes='Urgent delivery required',
            ),
            lines=[
                ExtractionLineItem(
                    line_no=1,
                    customer_sku='CUST-12345',
                    description='Widget A',
                    qty=Decimal('100'),
                    uom='PCS',
                    unit_price=Decimal('12.50'),
                    currency='EUR',
                    line_total=Decimal('1250.00'),
                ),
                ExtractionLineItem(
                    line_no=2,
                    customer_sku='CUST-67890',
                    description='Widget B',
                    qty=Decimal('50'),
                    uom='PCS',
                    unit_price=Decimal('25.00'),
                    currency='EUR',
                    line_total=Decimal('1250.00'),
                ),
            ],
            metadata={
                'sheet_name': 'Order',
                'total_rows': 2,
                'header_row_idx': 1,
            }
        )

        # Assert: Schema is valid
        assert output.order.order_number == 'PO-2024-001'
        assert output.order.currency == 'EUR'  # Normalized to uppercase
        assert len(output.lines) == 2
        assert output.lines[0].line_no == 1
        assert output.lines[0].qty == Decimal('100')
        assert output.metadata['sheet_name'] == 'Order'

    def test_excel_partial_extraction(self):
        """Test Excel extraction with some missing fields"""
        # Arrange: Excel data with optional fields missing
        output = CanonicalExtractionOutput(
            order=ExtractionOrderHeader(
                order_number='PO-2024-002',
                # No dates, addresses, or notes
            ),
            lines=[
                ExtractionLineItem(
                    line_no=1,
                    customer_sku='CUST-11111',
                    qty=Decimal('10'),
                    # No description, uom, price
                ),
            ],
            metadata={'sheet_name': 'Sheet1'}
        )

        # Assert: Schema accepts partial data
        assert output.order.order_number == 'PO-2024-002'
        assert output.order.order_date is None
        assert output.lines[0].description is None
        assert output.lines[0].unit_price is None

    def test_excel_european_decimal_format(self):
        """Test Excel extraction with European decimal format"""
        # Arrange: Decimal values (comma separator handled by extractor)
        output = CanonicalExtractionOutput(
            order=ExtractionOrderHeader(),
            lines=[
                ExtractionLineItem(
                    line_no=1,
                    customer_sku='PROD-001',
                    qty=Decimal('1234.56'),  # Parsed from "1.234,56"
                    unit_price=Decimal('99.99'),  # Parsed from "99,99"
                ),
            ],
        )

        # Assert: Decimals stored correctly
        assert output.lines[0].qty == Decimal('1234.56')
        assert output.lines[0].unit_price == Decimal('99.99')

    def test_excel_whitespace_normalization(self):
        """Test that whitespace is stripped from string fields"""
        # Arrange: Data with leading/trailing whitespace
        output = CanonicalExtractionOutput(
            order=ExtractionOrderHeader(
                order_number='  PO-123  ',  # Should be stripped
                notes='  Important  ',  # Should be stripped
            ),
            lines=[
                ExtractionLineItem(
                    line_no=1,
                    customer_sku='  SKU-001  ',  # Should be stripped
                    description='  Product  ',  # Should be stripped
                    uom='  PCS  ',  # Should be stripped
                ),
            ],
        )

        # Assert: Whitespace stripped
        assert output.order.order_number == 'PO-123'
        assert output.order.notes == 'Important'
        assert output.lines[0].customer_sku == 'SKU-001'
        assert output.lines[0].description == 'Product'
        assert output.lines[0].uom == 'PCS'

    def test_excel_currency_normalization(self):
        """Test that currency codes are normalized to uppercase"""
        # Arrange: Currency in lowercase/mixed case
        output = CanonicalExtractionOutput(
            order=ExtractionOrderHeader(
                currency='eur',  # Should be uppercase
            ),
            lines=[
                ExtractionLineItem(
                    line_no=1,
                    customer_sku='PROD-001',
                    currency='usd',  # Should be uppercase
                ),
            ],
        )

        # Assert: Currency uppercase
        assert output.order.currency == 'EUR'
        assert output.lines[0].currency == 'USD'


class TestSchemaValidationCSV:
    """T046: Test CanonicalExtractionOutput with CSV-style data.

    CSV extractors typically provide:
    - Minimal/no header metadata (CSVs usually only have line items)
    - Complete line items from column mapping
    - Good data quality for provided fields
    """

    def test_csv_lines_only(self):
        """Test CSV extraction with only line items (no header metadata)"""
        # Arrange: CSV-style data with empty header
        output = CanonicalExtractionOutput(
            order=ExtractionOrderHeader(),  # No header metadata
            lines=[
                ExtractionLineItem(
                    line_no=1,
                    customer_sku='CSV-SKU-001',
                    description='Product from CSV',
                    qty=Decimal('5'),
                    uom='EA',
                    unit_price=Decimal('19.99'),
                ),
                ExtractionLineItem(
                    line_no=2,
                    customer_sku='CSV-SKU-002',
                    description='Another product',
                    qty=Decimal('10'),
                    uom='KG',
                    unit_price=Decimal('7.50'),
                ),
            ],
            metadata={
                'encoding': 'utf-8',
                'delimiter': ',',
                'total_rows': 2,
            }
        )

        # Assert: Valid schema with empty header
        assert output.order.order_number is None
        assert output.order.order_date is None
        assert len(output.lines) == 2
        assert output.lines[0].customer_sku == 'CSV-SKU-001'
        assert output.metadata['delimiter'] == ','

    def test_csv_semicolon_delimiter(self):
        """Test CSV extraction with semicolon delimiter (European format)"""
        # Arrange: European CSV format (semicolon delimiter)
        output = CanonicalExtractionOutput(
            order=ExtractionOrderHeader(),
            lines=[
                ExtractionLineItem(
                    line_no=1,
                    customer_sku='EUR-001',
                    qty=Decimal('100'),
                ),
            ],
            metadata={
                'encoding': 'iso-8859-1',
                'delimiter': ';',
            }
        )

        # Assert: Metadata captured correctly
        assert output.metadata['delimiter'] == ';'
        assert output.metadata['encoding'] == 'iso-8859-1'

    def test_csv_flexible_column_mapping(self):
        """Test CSV with various column name variations"""
        # Arrange: CSV with columns mapped from various naming conventions
        output = CanonicalExtractionOutput(
            order=ExtractionOrderHeader(),
            lines=[
                ExtractionLineItem(
                    line_no=1,
                    customer_sku='MAPPED-SKU',  # Mapped from "Artikelnummer"
                    description='Mapped description',  # Mapped from "Bezeichnung"
                    qty=Decimal('25'),  # Mapped from "Menge"
                ),
            ],
        )

        # Assert: Column mapping successful
        assert output.lines[0].customer_sku == 'MAPPED-SKU'
        assert output.lines[0].description == 'Mapped description'
        assert output.lines[0].qty == Decimal('25')

    def test_csv_minimal_data(self):
        """Test CSV with minimal required data (only SKU or description)"""
        # Arrange: CSV with sparse data
        output = CanonicalExtractionOutput(
            order=ExtractionOrderHeader(),
            lines=[
                ExtractionLineItem(
                    line_no=1,
                    customer_sku='SPARSE-001',
                    # Only SKU, no other fields
                ),
                ExtractionLineItem(
                    line_no=2,
                    description='Description only',
                    # Only description, no SKU
                ),
            ],
        )

        # Assert: Minimal data accepted
        assert output.lines[0].customer_sku == 'SPARSE-001'
        assert output.lines[0].description is None
        assert output.lines[1].customer_sku is None
        assert output.lines[1].description == 'Description only'


class TestSchemaValidationPDF:
    """T047: Test CanonicalExtractionOutput with PDF-style data.

    PDF extractors typically provide:
    - Variable header quality (depends on text extraction)
    - Line items extracted from table detection
    - Lower data quality due to OCR/text parsing challenges
    """

    def test_pdf_text_extraction(self):
        """Test PDF extraction from text-based PDF"""
        # Arrange: PDF-style data with text extraction metadata
        output = CanonicalExtractionOutput(
            order=ExtractionOrderHeader(
                order_number='PDF-PO-001',  # Extracted from text
                order_date=date(2024, 1, 20),
            ),
            lines=[
                ExtractionLineItem(
                    line_no=1,
                    customer_sku='PDF-SKU-A',
                    description='Product A from PDF',
                    qty=Decimal('15'),
                    unit_price=Decimal('29.99'),
                ),
            ],
            metadata={
                'text_coverage_ratio': 0.95,  # High text coverage
                'extractor_type': 'pdf_text',
                'pages': 2,
            }
        )

        # Assert: PDF data valid
        assert output.order.order_number == 'PDF-PO-001'
        assert output.lines[0].customer_sku == 'PDF-SKU-A'
        assert output.metadata['text_coverage_ratio'] == 0.95

    def test_pdf_table_extraction(self):
        """Test PDF extraction with table structure detection"""
        # Arrange: PDF with detected table
        output = CanonicalExtractionOutput(
            order=ExtractionOrderHeader(),
            lines=[
                ExtractionLineItem(
                    line_no=1,
                    customer_sku='TBL-001',
                    description='From table cell',
                    qty=Decimal('8'),
                ),
                ExtractionLineItem(
                    line_no=2,
                    customer_sku='TBL-002',
                    description='Another row',
                    qty=Decimal('12'),
                ),
            ],
            metadata={
                'tables_detected': 1,
                'rows_in_table': 2,
            }
        )

        # Assert: Table data extracted
        assert len(output.lines) == 2
        assert output.metadata['tables_detected'] == 1

    def test_pdf_partial_extraction_quality(self):
        """Test PDF with partial/low quality extraction"""
        # Arrange: PDF with some extraction failures
        output = CanonicalExtractionOutput(
            order=ExtractionOrderHeader(
                # Header partially extracted
                order_number='PARTIAL-001',
                # Date extraction failed
            ),
            lines=[
                ExtractionLineItem(
                    line_no=1,
                    customer_sku='LOW-Q-001',
                    # Description extraction failed
                    qty=Decimal('5'),
                    # Price extraction failed
                ),
            ],
            metadata={
                'text_coverage_ratio': 0.65,  # Lower coverage
                'extraction_warnings': ['Date format not recognized', 'Price column unclear'],
            }
        )

        # Assert: Partial data accepted
        assert output.order.order_number == 'PARTIAL-001'
        assert output.order.order_date is None
        assert output.lines[0].description is None
        assert output.lines[0].unit_price is None
        assert len(output.metadata['extraction_warnings']) == 2

    def test_pdf_ocr_artifacts(self):
        """Test PDF extraction with OCR artifacts (whitespace issues)"""
        # Arrange: PDF with OCR-introduced whitespace
        output = CanonicalExtractionOutput(
            order=ExtractionOrderHeader(
                order_number='  OCR - PO - 123  ',  # OCR artifacts
            ),
            lines=[
                ExtractionLineItem(
                    line_no=1,
                    customer_sku='  S K U  0 0 1  ',  # Spaced characters
                    description='  Product with   extra  spaces  ',
                ),
            ],
        )

        # Assert: Whitespace stripped (validators handle cleanup)
        # Note: The actual OCR cleanup would happen in the extractor,
        # but schema validators also strip whitespace
        assert output.order.order_number == 'OCR - PO - 123'
        assert output.lines[0].customer_sku == 'S K U  0 0 1'
        assert output.lines[0].description == 'Product with   extra  spaces'


class TestSchemaValidationEdgeCases:
    """Test edge cases and error handling for schema validation."""

    def test_empty_lines_list(self):
        """Test extraction with no lines (valid but unusual)"""
        # Arrange: Order with no line items
        output = CanonicalExtractionOutput(
            order=ExtractionOrderHeader(
                order_number='NO-LINES-001',
            ),
            lines=[],  # Empty lines
        )

        # Assert: Valid schema
        assert output.order.order_number == 'NO-LINES-001'
        assert len(output.lines) == 0

    def test_extra_fields_allowed(self):
        """Test that extra fields are allowed (schema config: extra='allow')"""
        # Arrange: Data with extra fields
        data = {
            'order': {
                'order_number': 'EXTRA-001',
                'custom_field': 'Custom value',  # Extra field
            },
            'lines': [
                {
                    'line_no': 1,
                    'customer_sku': 'SKU-001',
                    'extra_data': 'More data',  # Extra field
                }
            ],
            'metadata': {},
            'extra_top_level': 'Extra',  # Extra top-level field
        }

        # Act: Create output (extra fields allowed)
        output = CanonicalExtractionOutput(**data)

        # Assert: Extra fields don't cause errors
        assert output.order.order_number == 'EXTRA-001'
        assert output.lines[0].customer_sku == 'SKU-001'

    def test_empty_string_fields_converted_to_none(self):
        """Test that empty strings are converted to None"""
        # Arrange: Data with empty strings
        output = CanonicalExtractionOutput(
            order=ExtractionOrderHeader(
                order_number='',  # Empty string
                notes='   ',  # Whitespace only
            ),
            lines=[
                ExtractionLineItem(
                    line_no=1,
                    customer_sku='',  # Empty string
                    description='   ',  # Whitespace only
                ),
            ],
        )

        # Assert: Empty strings converted to None
        assert output.order.order_number is None
        assert output.order.notes is None
        assert output.lines[0].customer_sku is None
        assert output.lines[0].description is None

    def test_decimal_precision_preserved(self):
        """Test that Decimal precision is preserved"""
        # Arrange: High precision decimal values
        output = CanonicalExtractionOutput(
            order=ExtractionOrderHeader(),
            lines=[
                ExtractionLineItem(
                    line_no=1,
                    customer_sku='PREC-001',
                    qty=Decimal('123.456789'),  # High precision
                    unit_price=Decimal('0.001'),  # Small value
                ),
            ],
        )

        # Assert: Precision preserved
        assert output.lines[0].qty == Decimal('123.456789')
        assert output.lines[0].unit_price == Decimal('0.001')

    def test_json_serialization(self):
        """Test that output can be serialized to JSON"""
        # Arrange: Complete output
        output = CanonicalExtractionOutput(
            order=ExtractionOrderHeader(
                order_number='JSON-001',
                order_date=date(2024, 1, 15),
                currency='EUR',
            ),
            lines=[
                ExtractionLineItem(
                    line_no=1,
                    customer_sku='SKU-001',
                    qty=Decimal('10.5'),
                    unit_price=Decimal('99.99'),
                ),
            ],
            metadata={'extractor': 'excel_v1'}
        )

        # Act: Serialize to JSON
        json_str = output.json()

        # Assert: Serialization successful (Pydantic v2 produces compact JSON without spaces)
        assert '"order_number":"JSON-001"' in json_str
        assert '"order_date":"2024-01-15"' in json_str
        assert '"qty":"10.5"' in json_str  # Decimal as string
        assert '"unit_price":"99.99"' in json_str  # Decimal as string
        assert '"currency":"EUR"' in json_str

    def test_dict_conversion(self):
        """Test conversion to dictionary"""
        # Arrange: Output with all field types
        output = CanonicalExtractionOutput(
            order=ExtractionOrderHeader(
                order_number='DICT-001',
                ship_to={'city': 'Munich'},  # Dict field
            ),
            lines=[
                ExtractionLineItem(
                    line_no=1,
                    customer_sku='SKU-001',
                ),
            ],
        )

        # Act: Convert to dict
        data = output.dict()

        # Assert: All fields present
        assert data['order']['order_number'] == 'DICT-001'
        assert data['order']['ship_to'] == {'city': 'Munich'}
        assert data['lines'][0]['line_no'] == 1
