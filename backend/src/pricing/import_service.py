"""Customer price CSV import service with upsert logic

Per spec 020-customer-prices and §8.8, supports:
- CSV import with customer lookup (by erp_customer_number or customer_name)
- SKU normalization
- Tier pricing (min_qty)
- Date-based validity
- UPSERT behavior (update existing or insert new)
"""

import pandas as pd
from io import BytesIO
from typing import BinaryIO, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from datetime import date
from decimal import Decimal, InvalidOperation
import logging

from models.customer_price import CustomerPrice
from models.customer import Customer
from .schemas import PriceImportResult

logger = logging.getLogger(__name__)


class PriceImportService:
    """Service for importing customer prices from CSV files"""

    def __init__(self, db: Session, org_id: UUID):
        self.db = db
        self.org_id = org_id

    def parse_csv(self, file: BinaryIO) -> pd.DataFrame:
        """Parse CSV file into pandas DataFrame.

        Args:
            file: Binary file object (CSV content)

        Returns:
            DataFrame with customer price data

        Raises:
            ValueError: If CSV is malformed or empty
        """
        try:
            df = pd.read_csv(file, dtype=str, keep_default_na=False)

            if df.empty:
                raise ValueError("CSV file is empty")

            return df
        except pd.errors.EmptyDataError:
            raise ValueError("CSV file is empty")
        except pd.errors.ParserError as e:
            raise ValueError(f"CSV parsing error: {str(e)}")

    def lookup_customer(self, row: pd.Series, row_num: int) -> tuple[Optional[UUID], str]:
        """Lookup customer by erp_customer_number or customer_name.

        Args:
            row: Pandas Series representing a row
            row_num: Row number for error reporting

        Returns:
            Tuple of (customer_id or None, error_message)
        """
        erp_number = row.get('erp_customer_number', '').strip()
        customer_name = row.get('customer_name', '').strip()

        if not erp_number and not customer_name:
            return None, f"Row {row_num}: Must provide either 'erp_customer_number' or 'customer_name'"

        # Try lookup by ERP number first
        if erp_number:
            stmt = select(Customer).where(
                and_(
                    Customer.org_id == self.org_id,
                    Customer.erp_customer_number == erp_number
                )
            )
            customer = self.db.execute(stmt).scalar_one_or_none()
            if customer:
                return customer.id, ""
            else:
                return None, f"Row {row_num}: Customer with ERP number '{erp_number}' not found"

        # Fallback to name lookup (exact match)
        if customer_name:
            stmt = select(Customer).where(
                and_(
                    Customer.org_id == self.org_id,
                    Customer.name == customer_name
                )
            )
            customer = self.db.execute(stmt).scalar_one_or_none()
            if customer:
                return customer.id, ""
            else:
                return None, f"Row {row_num}: Customer with name '{customer_name}' not found"

        return None, f"Row {row_num}: Customer lookup failed"

    def normalize_sku(self, sku: str) -> str:
        """Normalize SKU using standard normalization rules.

        Args:
            sku: Raw SKU string

        Returns:
            Normalized SKU
        """
        # Basic normalization: strip whitespace, uppercase
        # TODO: Apply same normalization as product catalog
        return sku.strip().upper()

    def parse_decimal(self, value: str, field_name: str, row_num: int) -> tuple[Optional[Decimal], str]:
        """Parse a decimal value from string.

        Args:
            value: String value to parse
            field_name: Name of field for error reporting
            row_num: Row number for error reporting

        Returns:
            Tuple of (Decimal or None, error_message)
        """
        if not value or not value.strip():
            return None, f"Row {row_num}: Missing required field '{field_name}'"

        try:
            return Decimal(value.strip()), ""
        except InvalidOperation:
            return None, f"Row {row_num}: Invalid {field_name} value '{value}'"

    def parse_date(self, value: str, field_name: str, row_num: int) -> tuple[Optional[date], str]:
        """Parse a date value from string (optional field).

        Args:
            value: String value to parse (YYYY-MM-DD format)
            field_name: Name of field for error reporting
            row_num: Row number for error reporting

        Returns:
            Tuple of (date or None, error_message)
        """
        if not value or not value.strip():
            return None, ""  # Optional field

        try:
            return date.fromisoformat(value.strip()), ""
        except ValueError:
            return None, f"Row {row_num}: Invalid {field_name} date format '{value}' (expected YYYY-MM-DD)"

    def validate_row(self, row: pd.Series, row_num: int) -> tuple[bool, str, dict]:
        """Validate a single CSV row and extract data.

        Args:
            row: Pandas Series representing a row
            row_num: Row number for error reporting

        Returns:
            Tuple of (is_valid, error_message, data_dict)
        """
        data = {}

        # Lookup customer
        customer_id, error = self.lookup_customer(row, row_num)
        if error:
            return False, error, {}
        data['customer_id'] = customer_id

        # Required: internal_sku
        internal_sku = row.get('internal_sku', '').strip()
        if not internal_sku:
            return False, f"Row {row_num}: Missing required field 'internal_sku'", {}
        data['internal_sku'] = self.normalize_sku(internal_sku)

        # Required: currency
        currency = row.get('currency', '').strip().upper()
        if not currency:
            return False, f"Row {row_num}: Missing required field 'currency'", {}
        if len(currency) != 3:
            return False, f"Row {row_num}: Invalid currency code '{currency}' (must be 3 characters)", {}
        data['currency'] = currency

        # Required: uom
        uom = row.get('uom', '').strip()
        if not uom:
            return False, f"Row {row_num}: Missing required field 'uom'", {}
        data['uom'] = uom

        # Required: unit_price
        unit_price, error = self.parse_decimal(row.get('unit_price', ''), 'unit_price', row_num)
        if error:
            return False, error, {}
        if unit_price <= 0:
            return False, f"Row {row_num}: unit_price must be greater than 0", {}
        data['unit_price'] = unit_price

        # Optional: min_qty (default 1.000)
        min_qty_str = row.get('min_qty', '').strip()
        if min_qty_str:
            min_qty, error = self.parse_decimal(min_qty_str, 'min_qty', row_num)
            if error:
                return False, error, {}
            if min_qty <= 0:
                return False, f"Row {row_num}: min_qty must be greater than 0", {}
            data['min_qty'] = min_qty
        else:
            data['min_qty'] = Decimal("1.000")

        # Optional: valid_from
        valid_from, error = self.parse_date(row.get('valid_from', ''), 'valid_from', row_num)
        if error:
            return False, error, {}
        data['valid_from'] = valid_from

        # Optional: valid_to
        valid_to, error = self.parse_date(row.get('valid_to', ''), 'valid_to', row_num)
        if error:
            return False, error, {}
        data['valid_to'] = valid_to

        # Validate date range
        if valid_from and valid_to and valid_to < valid_from:
            return False, f"Row {row_num}: valid_to must be after valid_from", {}

        return True, "", data

    def upsert_price(self, data: dict) -> tuple[CustomerPrice, bool]:
        """Insert or update customer price.

        UPSERT behavior per FR-012:
        - If price exists with same (customer_id, internal_sku, currency, uom, min_qty), update it
        - Otherwise, insert new price

        Args:
            data: Dictionary with validated price data

        Returns:
            Tuple of (price, was_updated)
        """
        # Check if price exists with same key
        stmt = select(CustomerPrice).where(
            and_(
                CustomerPrice.org_id == self.org_id,
                CustomerPrice.customer_id == data['customer_id'],
                CustomerPrice.internal_sku == data['internal_sku'],
                CustomerPrice.currency == data['currency'],
                CustomerPrice.uom == data['uom'],
                CustomerPrice.min_qty == data['min_qty']
            )
        )
        price = self.db.execute(stmt).scalar_one_or_none()

        is_update = price is not None

        if is_update:
            # Update existing price
            price.unit_price = data['unit_price']
            price.valid_from = data.get('valid_from')
            price.valid_to = data.get('valid_to')
            price.source = 'IMPORT'
        else:
            # Create new price
            price = CustomerPrice(
                org_id=self.org_id,
                customer_id=data['customer_id'],
                internal_sku=data['internal_sku'],
                currency=data['currency'],
                uom=data['uom'],
                unit_price=data['unit_price'],
                min_qty=data['min_qty'],
                valid_from=data.get('valid_from'),
                valid_to=data.get('valid_to'),
                source='IMPORT'
            )
            self.db.add(price)

        self.db.flush()

        return price, is_update

    def import_prices(self, file: BinaryIO) -> PriceImportResult:
        """Import customer prices from CSV file.

        CSV columns per §8.8:
        - erp_customer_number OR customer_name (one required)
        - internal_sku (required)
        - currency (required)
        - uom (required)
        - unit_price (required)
        - min_qty (optional, default 1.000)
        - valid_from (optional, YYYY-MM-DD)
        - valid_to (optional, YYYY-MM-DD)

        Args:
            file: Binary file object (CSV content)

        Returns:
            PriceImportResult with counts and errors
        """
        result = PriceImportResult()

        try:
            df = self.parse_csv(file)
        except ValueError as e:
            result.errors.append({"row": 0, "error": str(e)})
            result.failed = 1
            return result

        # Track duplicate keys within CSV
        keys_seen = {}

        # Process each row
        for idx, row in df.iterrows():
            row_num = idx + 2  # +2 because: +1 for 1-based indexing, +1 for header row

            try:
                # Validate row
                is_valid, error_msg, data = self.validate_row(row, row_num)
                if not is_valid:
                    result.errors.append({"row": row_num, "error": error_msg})
                    result.failed += 1
                    continue

                # Create key for duplicate detection
                key = (
                    data['customer_id'],
                    data['internal_sku'],
                    data['currency'],
                    data['uom'],
                    data['min_qty']
                )

                if key in keys_seen:
                    logger.warning(
                        f"Duplicate price key found in CSV at rows {keys_seen[key]} and {row_num}. "
                        f"Row {row_num} will overwrite."
                    )
                keys_seen[key] = row_num

                # Upsert price
                price, was_updated = self.upsert_price(data)

                if was_updated:
                    result.updated += 1
                else:
                    result.imported += 1

            except Exception as e:
                logger.exception(f"Error processing row {row_num}")
                result.errors.append({"row": row_num, "error": str(e)})
                result.failed += 1
                continue

        # Commit all changes
        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.exception("Error committing import transaction")
            result.errors.append({"row": 0, "error": f"Database commit failed: {str(e)}"})
            result.failed = len(df)
            result.imported = 0
            result.updated = 0

        return result
