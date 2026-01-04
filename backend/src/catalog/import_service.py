"""Product CSV import service"""

import csv
import json
from io import StringIO
from typing import BinaryIO
from uuid import UUID
from datetime import datetime

import chardet
from sqlalchemy.orm import Session
from pydantic import ValidationError

from models.product import Product
from .schemas import ProductImportResult, ProductImportError, CANONICAL_UOMS


class ProductImportService:
    """Service for importing products from CSV files"""

    def __init__(self, db: Session, org_id: UUID):
        self.db = db
        self.org_id = org_id

    def import_from_csv(self, file_bytes: bytes) -> ProductImportResult:
        """Import products from CSV file bytes

        Args:
            file_bytes: Raw CSV file bytes

        Returns:
            ProductImportResult with counts and errors
        """
        # Detect encoding
        detected = chardet.detect(file_bytes)
        encoding = detected['encoding'] or 'utf-8'

        # Decode to text
        try:
            text = file_bytes.decode(encoding)
        except UnicodeDecodeError:
            # Fallback to utf-8 with error handling
            text = file_bytes.decode('utf-8', errors='replace')

        # Parse CSV
        reader = csv.DictReader(StringIO(text))

        result = ProductImportResult(
            total_rows=0,
            imported_count=0,
            error_count=0,
            errors=[]
        )

        for row_num, row in enumerate(reader, start=2):  # Start at 2 (row 1 is header)
            result.total_rows += 1

            try:
                self._validate_and_upsert_product(row)
                result.imported_count += 1
            except Exception as e:
                result.error_count += 1
                result.errors.append(ProductImportError(
                    row=row_num,
                    sku=row.get('internal_sku'),
                    error=str(e)
                ))

        # Commit all successful imports
        if result.imported_count > 0:
            self.db.commit()

        return result

    def _validate_and_upsert_product(self, row: dict) -> None:
        """Validate and upsert a single product row

        Args:
            row: Dictionary containing product data

        Raises:
            ValueError: If validation fails
        """
        # Validate required fields
        internal_sku = row.get('internal_sku', '').strip()
        if not internal_sku:
            raise ValueError("internal_sku is required")

        name = row.get('name', '').strip()
        if not name:
            raise ValueError("name is required")

        base_uom = row.get('base_uom', '').strip().upper()
        if not base_uom:
            raise ValueError("base_uom is required")

        if base_uom not in CANONICAL_UOMS:
            raise ValueError(
                f"Invalid base_uom: {base_uom}. Must be one of: {', '.join(sorted(CANONICAL_UOMS))}"
            )

        # Parse optional fields
        description = row.get('description', '').strip() or None

        # Parse attributes
        attributes_json = {}
        if row.get('manufacturer'):
            attributes_json['manufacturer'] = row['manufacturer'].strip()
        if row.get('ean'):
            attributes_json['ean'] = row['ean'].strip()
        if row.get('category'):
            attributes_json['category'] = row['category'].strip()

        # Parse UoM conversions
        uom_conversions_json = {}
        if row.get('uom_conversions'):
            try:
                uom_conversions_json = json.loads(row['uom_conversions'])
                # Validate structure
                if not isinstance(uom_conversions_json, dict):
                    raise ValueError("uom_conversions must be a JSON object")

                for uom_code, conversion in uom_conversions_json.items():
                    if not isinstance(conversion, dict):
                        raise ValueError(f"Conversion for {uom_code} must be an object")
                    if 'to_base' not in conversion:
                        raise ValueError(f"Conversion for {uom_code} must have 'to_base' key")
                    if not isinstance(conversion['to_base'], (int, float)):
                        raise ValueError(f"to_base for {uom_code} must be a number")
                    if conversion['to_base'] <= 0:
                        raise ValueError(f"to_base for {uom_code} must be positive")

            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in uom_conversions: {str(e)}")

        # Check if product exists
        existing_product = self.db.query(Product).filter(
            Product.org_id == self.org_id,
            Product.internal_sku == internal_sku
        ).first()

        if existing_product:
            # Update existing product
            existing_product.name = name
            existing_product.description = description
            existing_product.base_uom = base_uom
            existing_product.uom_conversions_json = uom_conversions_json
            existing_product.attributes_json = attributes_json
            existing_product.updated_source_at = datetime.utcnow()
        else:
            # Create new product
            new_product = Product(
                org_id=self.org_id,
                internal_sku=internal_sku,
                name=name,
                description=description,
                base_uom=base_uom,
                uom_conversions_json=uom_conversions_json,
                attributes_json=attributes_json,
                active=True,
                updated_source_at=datetime.utcnow()
            )
            self.db.add(new_product)


def generate_error_csv(result: ProductImportResult) -> str:
    """Generate CSV string with import errors

    Args:
        result: Import result containing errors

    Returns:
        CSV string with error rows
    """
    output = StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(['Row', 'SKU', 'Error'])

    # Write error rows
    for error in result.errors:
        writer.writerow([error.row, error.sku or '', error.error])

    return output.getvalue()
