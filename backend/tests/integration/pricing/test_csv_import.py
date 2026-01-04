"""Integration tests for customer price CSV import

Tests the CSV import functionality per spec 020-customer-prices:
- Import valid CSV with customer prices
- Handle invalid rows with error reporting
- UPSERT behavior (update existing, insert new)
- Customer lookup (by ERP number and name)
"""

import pytest
from io import BytesIO
from decimal import Decimal

import sys
from pathlib import Path
backend_src = Path(__file__).parent.parent.parent.parent / "src"
sys.path.insert(0, str(backend_src))

from pricing.import_service import PriceImportService
from models.customer_price import CustomerPrice
from models.customer import Customer


class TestCSVImport:
    """Test cases for customer price CSV import"""

    def test_import_valid_csv(self, db_session, test_org, test_customer):
        """Given a valid CSV, when imported, then prices are created"""
        csv_content = b"""erp_customer_number,internal_sku,currency,uom,unit_price,min_qty
CUST001,SKU-001,EUR,EA,10.00,1
CUST001,SKU-001,EUR,EA,9.00,100
CUST001,SKU-002,EUR,EA,15.50,1
"""
        import_service = PriceImportService(db_session, test_org.id)
        result = import_service.import_prices(BytesIO(csv_content))

        assert result.imported == 3
        assert result.updated == 0
        assert result.failed == 0
        assert len(result.errors) == 0

        # Verify prices were created
        prices = db_session.query(CustomerPrice).filter(
            CustomerPrice.org_id == test_org.id
        ).all()
        assert len(prices) == 3

    def test_import_with_customer_name_lookup(self, db_session, test_org, test_customer):
        """Given CSV with customer_name, when imported, then customer is looked up by name"""
        csv_content = b"""customer_name,internal_sku,currency,uom,unit_price
Test Customer,SKU-003,EUR,EA,20.00
"""
        import_service = PriceImportService(db_session, test_org.id)
        result = import_service.import_prices(BytesIO(csv_content))

        assert result.imported == 1
        assert result.updated == 0
        assert result.failed == 0

        # Verify price was created with correct customer
        price = db_session.query(CustomerPrice).filter(
            CustomerPrice.internal_sku == "SKU-003"
        ).first()
        assert price is not None
        assert price.customer_id == test_customer.id

    def test_import_with_optional_fields(self, db_session, test_org, test_customer):
        """Given CSV with valid_from/valid_to, when imported, then dates are stored"""
        csv_content = b"""erp_customer_number,internal_sku,currency,uom,unit_price,min_qty,valid_from,valid_to
CUST001,SKU-004,EUR,EA,12.50,1,2025-01-01,2025-12-31
"""
        import_service = PriceImportService(db_session, test_org.id)
        result = import_service.import_prices(BytesIO(csv_content))

        assert result.imported == 1
        assert result.failed == 0

        # Verify dates were stored
        price = db_session.query(CustomerPrice).filter(
            CustomerPrice.internal_sku == "SKU-004"
        ).first()
        assert price is not None
        assert price.valid_from.isoformat() == "2025-01-01"
        assert price.valid_to.isoformat() == "2025-12-31"

    def test_import_missing_required_field(self, db_session, test_org, test_customer):
        """Given CSV with missing required field, when imported, then row fails with error"""
        csv_content = b"""erp_customer_number,internal_sku,currency,uom,unit_price
CUST001,SKU-005,EUR,,10.00
"""
        import_service = PriceImportService(db_session, test_org.id)
        result = import_service.import_prices(BytesIO(csv_content))

        assert result.imported == 0
        assert result.failed == 1
        assert len(result.errors) == 1
        assert "uom" in result.errors[0]["error"].lower()

    def test_import_invalid_unit_price(self, db_session, test_org, test_customer):
        """Given CSV with invalid unit_price, when imported, then row fails with error"""
        csv_content = b"""erp_customer_number,internal_sku,currency,uom,unit_price
CUST001,SKU-006,EUR,EA,invalid
"""
        import_service = PriceImportService(db_session, test_org.id)
        result = import_service.import_prices(BytesIO(csv_content))

        assert result.imported == 0
        assert result.failed == 1
        assert len(result.errors) == 1
        assert "unit_price" in result.errors[0]["error"].lower()

    def test_import_customer_not_found(self, db_session, test_org):
        """Given CSV with non-existent customer, when imported, then row fails with error"""
        csv_content = b"""erp_customer_number,internal_sku,currency,uom,unit_price
NONEXISTENT,SKU-007,EUR,EA,10.00
"""
        import_service = PriceImportService(db_session, test_org.id)
        result = import_service.import_prices(BytesIO(csv_content))

        assert result.imported == 0
        assert result.failed == 1
        assert len(result.errors) == 1
        assert "not found" in result.errors[0]["error"].lower()

    def test_import_upsert_behavior(self, db_session, test_org, test_customer):
        """Given existing price, when CSV imported with same key, then price is updated"""
        # Create initial price
        existing_price = CustomerPrice(
            org_id=test_org.id,
            customer_id=test_customer.id,
            internal_sku="SKU-008",
            currency="EUR",
            uom="EA",
            unit_price=Decimal("10.00"),
            min_qty=Decimal("1.000")
        )
        db_session.add(existing_price)
        db_session.commit()

        # Import CSV with same key but different price
        csv_content = b"""erp_customer_number,internal_sku,currency,uom,unit_price,min_qty
CUST001,SKU-008,EUR,EA,12.00,1
"""
        import_service = PriceImportService(db_session, test_org.id)
        result = import_service.import_prices(BytesIO(csv_content))

        assert result.imported == 0
        assert result.updated == 1
        assert result.failed == 0

        # Verify price was updated
        price = db_session.query(CustomerPrice).filter(
            CustomerPrice.internal_sku == "SKU-008"
        ).first()
        assert price.unit_price == Decimal("12.00")

    def test_import_multiple_rows_success_and_failure(self, db_session, test_org, test_customer):
        """Given CSV with mix of valid and invalid rows, when imported, then valid succeed, invalid fail"""
        csv_content = b"""erp_customer_number,internal_sku,currency,uom,unit_price
CUST001,SKU-009,EUR,EA,10.00
NONEXISTENT,SKU-010,EUR,EA,15.00
CUST001,SKU-011,EUR,EA,20.00
"""
        import_service = PriceImportService(db_session, test_org.id)
        result = import_service.import_prices(BytesIO(csv_content))

        assert result.imported == 2
        assert result.failed == 1
        assert len(result.errors) == 1

        # Verify valid rows were imported
        prices = db_session.query(CustomerPrice).filter(
            CustomerPrice.org_id == test_org.id
        ).all()
        assert len(prices) == 2

    def test_import_duplicate_within_csv(self, db_session, test_org, test_customer):
        """Given CSV with duplicate keys, when imported, then later row overwrites earlier"""
        csv_content = b"""erp_customer_number,internal_sku,currency,uom,unit_price,min_qty
CUST001,SKU-012,EUR,EA,10.00,1
CUST001,SKU-012,EUR,EA,15.00,1
"""
        import_service = PriceImportService(db_session, test_org.id)
        result = import_service.import_prices(BytesIO(csv_content))

        # First creates, second updates
        assert result.imported == 1
        assert result.updated == 1
        assert result.failed == 0

        # Verify final price is from second row
        price = db_session.query(CustomerPrice).filter(
            CustomerPrice.internal_sku == "SKU-012"
        ).first()
        assert price.unit_price == Decimal("15.00")

    def test_import_sku_normalization(self, db_session, test_org, test_customer):
        """Given CSV with unnormalized SKU, when imported, then SKU is normalized"""
        csv_content = b"""erp_customer_number,internal_sku,currency,uom,unit_price
CUST001,  sku-013  ,EUR,EA,10.00
"""
        import_service = PriceImportService(db_session, test_org.id)
        result = import_service.import_prices(BytesIO(csv_content))

        assert result.imported == 1
        assert result.failed == 0

        # Verify SKU was normalized (trimmed and uppercased)
        price = db_session.query(CustomerPrice).first()
        assert price.internal_sku == "SKU-013"

    def test_import_negative_unit_price(self, db_session, test_org, test_customer):
        """Given CSV with negative unit_price, when imported, then row fails"""
        csv_content = b"""erp_customer_number,internal_sku,currency,uom,unit_price
CUST001,SKU-014,EUR,EA,-10.00
"""
        import_service = PriceImportService(db_session, test_org.id)
        result = import_service.import_prices(BytesIO(csv_content))

        assert result.imported == 0
        assert result.failed == 1
        assert "greater than 0" in result.errors[0]["error"].lower()

    def test_import_invalid_date_format(self, db_session, test_org, test_customer):
        """Given CSV with invalid date format, when imported, then row fails"""
        csv_content = b"""erp_customer_number,internal_sku,currency,uom,unit_price,valid_from
CUST001,SKU-015,EUR,EA,10.00,2025/01/01
"""
        import_service = PriceImportService(db_session, test_org.id)
        result = import_service.import_prices(BytesIO(csv_content))

        assert result.imported == 0
        assert result.failed == 1
        assert "date format" in result.errors[0]["error"].lower()


@pytest.fixture
def test_customer(db_session, test_org):
    """Create a test customer"""
    customer = Customer(
        org_id=test_org.id,
        name="Test Customer",
        erp_customer_number="CUST001",
        default_currency="EUR",
        default_language="de-DE"
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer
