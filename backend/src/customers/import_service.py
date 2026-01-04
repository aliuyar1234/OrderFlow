"""Customer CSV import service with upsert logic"""

import pandas as pd
from io import BytesIO
from typing import BinaryIO
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select
import logging

from ..models.customer import Customer
from ..models.customer_contact import CustomerContact
from .schemas import ImportResult, AddressSchema

logger = logging.getLogger(__name__)


class CustomerImportService:
    """Service for importing customers from CSV files"""

    def __init__(self, db: Session, org_id: UUID):
        self.db = db
        self.org_id = org_id

    def parse_csv(self, file: BinaryIO) -> pd.DataFrame:
        """
        Parse CSV file into pandas DataFrame.

        Args:
            file: Binary file object (CSV content)

        Returns:
            DataFrame with customer data

        Raises:
            ValueError: If CSV is malformed or empty
        """
        try:
            df = pd.read_csv(file, dtype=str, keep_default_na=False)

            # Check if DataFrame is empty
            if df.empty:
                raise ValueError("CSV file is empty")

            return df
        except pd.errors.EmptyDataError:
            raise ValueError("CSV file is empty")
        except pd.errors.ParserError as e:
            raise ValueError(f"CSV parsing error: {str(e)}")

    def validate_row(self, row: pd.Series, row_num: int) -> tuple[bool, str]:
        """
        Validate a single CSV row.

        Args:
            row: Pandas Series representing a row
            row_num: Row number for error reporting

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Required fields
        if not row.get('name') or str(row['name']).strip() == '':
            return False, f"Row {row_num}: Missing required field 'name'"

        if not row.get('default_currency') or str(row['default_currency']).strip() == '':
            return False, f"Row {row_num}: Missing required field 'default_currency'"

        if not row.get('default_language') or str(row['default_language']).strip() == '':
            return False, f"Row {row_num}: Missing required field 'default_language'"

        # Currency validation
        currency = str(row['default_currency']).upper().strip()
        from .schemas import VALID_CURRENCIES
        if currency not in VALID_CURRENCIES:
            return False, f"Row {row_num}: Invalid currency code '{currency}'"

        # Language validation
        language = str(row['default_language']).strip()
        from .schemas import VALID_LANGUAGES
        if language not in VALID_LANGUAGES:
            return False, f"Row {row_num}: Invalid language code '{language}'"

        return True, ""

    def parse_address(self, row: pd.Series, prefix: str) -> dict | None:
        """
        Parse address fields from CSV row.

        Args:
            row: Pandas Series representing a row
            prefix: 'billing' or 'shipping'

        Returns:
            Address dictionary or None if all fields are empty
        """
        address_fields = {
            'street': row.get(f'{prefix}_street', ''),
            'street2': row.get(f'{prefix}_street2', ''),
            'city': row.get(f'{prefix}_city', ''),
            'postal_code': row.get(f'{prefix}_postal_code', ''),
            'state': row.get(f'{prefix}_state', ''),
            'country': row.get(f'{prefix}_country', '')
        }

        # Convert empty strings to None
        address_fields = {k: (v if v and str(v).strip() else None) for k, v in address_fields.items()}

        # If all fields are None, return None
        if all(v is None for v in address_fields.values()):
            return None

        return address_fields

    def upsert_customer(self, row: pd.Series) -> tuple[Customer, bool]:
        """
        Insert or update customer based on ERP customer number.

        Args:
            row: Pandas Series with customer data

        Returns:
            Tuple of (customer, was_updated)
        """
        erp_number = row.get('erp_customer_number', None)
        erp_number = erp_number.strip() if erp_number and str(erp_number).strip() else None

        # Check if customer exists with this ERP number
        customer = None
        if erp_number:
            stmt = select(Customer).where(
                Customer.org_id == self.org_id,
                Customer.erp_customer_number == erp_number
            )
            customer = self.db.execute(stmt).scalar_one_or_none()

        is_update = customer is not None

        # Parse addresses
        billing_address = self.parse_address(row, 'billing')
        shipping_address = self.parse_address(row, 'shipping')

        # Get email if present
        email = row.get('email', None)
        email = email.strip().lower() if email and str(email).strip() else None

        # Get notes if present
        notes = row.get('notes', None)
        notes = notes.strip() if notes and str(notes).strip() else None

        if is_update:
            # Update existing customer
            customer.name = str(row['name']).strip()
            customer.default_currency = str(row['default_currency']).upper().strip()
            customer.default_language = str(row['default_language']).strip()
            customer.email = email
            customer.billing_address = billing_address
            customer.shipping_address = shipping_address
            customer.notes = notes
            customer.is_active = True
        else:
            # Create new customer
            customer = Customer(
                org_id=self.org_id,
                name=str(row['name']).strip(),
                erp_customer_number=erp_number,
                email=email,
                default_currency=str(row['default_currency']).upper().strip(),
                default_language=str(row['default_language']).strip(),
                billing_address=billing_address,
                shipping_address=shipping_address,
                notes=notes,
                is_active=True
            )
            self.db.add(customer)

        # Flush to get customer ID for contacts
        self.db.flush()

        # Handle contact if present
        contact_email = row.get('contact_email', None)
        if contact_email and str(contact_email).strip():
            contact_email = str(contact_email).strip().lower()
            contact_name = row.get('contact_name', None)
            contact_name = contact_name.strip() if contact_name and str(contact_name).strip() else None
            contact_phone = row.get('contact_phone', None)
            contact_phone = contact_phone.strip() if contact_phone and str(contact_phone).strip() else None
            is_primary = str(row.get('contact_is_primary', 'false')).lower() in ('true', '1', 'yes')

            # Check if contact already exists
            stmt = select(CustomerContact).where(
                CustomerContact.customer_id == customer.id,
                CustomerContact.email == contact_email
            )
            contact = self.db.execute(stmt).scalar_one_or_none()

            if contact:
                # Update existing contact
                contact.name = contact_name
                contact.phone = contact_phone
                if is_primary:
                    # Unset other primary contacts
                    self._unset_primary_contacts(customer.id)
                    contact.is_primary = True
            else:
                # Create new contact
                if is_primary:
                    # Unset other primary contacts
                    self._unset_primary_contacts(customer.id)

                contact = CustomerContact(
                    org_id=self.org_id,
                    customer_id=customer.id,
                    email=contact_email,
                    name=contact_name,
                    phone=contact_phone,
                    is_primary=is_primary
                )
                self.db.add(contact)

        return customer, is_update

    def _unset_primary_contacts(self, customer_id: UUID):
        """Unset all primary contacts for a customer"""
        stmt = select(CustomerContact).where(
            CustomerContact.customer_id == customer_id,
            CustomerContact.is_primary == True
        )
        primary_contacts = self.db.execute(stmt).scalars().all()
        for contact in primary_contacts:
            contact.is_primary = False

    def import_customers(self, file: BinaryIO) -> ImportResult:
        """
        Import customers from CSV file.

        Args:
            file: Binary file object (CSV content)

        Returns:
            ImportResult with counts and errors
        """
        result = ImportResult()

        try:
            df = self.parse_csv(file)
        except ValueError as e:
            result.errors.append({"row": 0, "error": str(e)})
            result.failed = 1
            return result

        # Track duplicate ERP numbers within the CSV
        erp_numbers_seen = {}

        # Process each row
        for idx, row in df.iterrows():
            row_num = idx + 2  # +2 because: +1 for 1-based indexing, +1 for header row

            try:
                # Validate row
                is_valid, error_msg = self.validate_row(row, row_num)
                if not is_valid:
                    result.errors.append({"row": row_num, "error": error_msg})
                    result.failed += 1
                    continue

                # Check for duplicate ERP number in CSV
                erp_number = row.get('erp_customer_number', None)
                if erp_number and str(erp_number).strip():
                    erp_number = str(erp_number).strip()
                    if erp_number in erp_numbers_seen:
                        logger.warning(
                            f"Duplicate ERP number '{erp_number}' found in CSV at rows "
                            f"{erp_numbers_seen[erp_number]} and {row_num}. Row {row_num} will overwrite."
                        )
                    erp_numbers_seen[erp_number] = row_num

                # Upsert customer
                customer, was_updated = self.upsert_customer(row)

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
