"""Unit tests for price tier selection algorithm

Tests the tier selection logic per spec 020-customer-prices:
- Select correct tier based on quantity
- Handle multiple tiers
- Handle date-based validity
- Handle missing prices
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from uuid import uuid4

import sys
from pathlib import Path
backend_src = Path(__file__).parent.parent.parent.parent / "src"
sys.path.insert(0, str(backend_src))

from pricing.service import PriceService
from models.customer_price import CustomerPrice
from models.customer import Customer
from models.org import Org


class TestPriceTierSelection:
    """Test cases for price tier selection algorithm"""

    def test_select_single_tier(self, db_session, test_org, test_customer):
        """Given a single price tier, when qty >= min_qty, then return that tier"""
        # Create a single price tier
        price = CustomerPrice(
            org_id=test_org.id,
            customer_id=test_customer.id,
            internal_sku="SKU-001",
            currency="EUR",
            uom="EA",
            unit_price=Decimal("10.00"),
            min_qty=Decimal("1.000")
        )
        db_session.add(price)
        db_session.commit()

        # Test with qty = 50 (should match tier with min_qty=1)
        result = PriceService.select_price_tier(
            db=db_session,
            org_id=test_org.id,
            customer_id=test_customer.id,
            internal_sku="SKU-001",
            currency="EUR",
            uom="EA",
            qty=Decimal("50.000")
        )

        assert result is not None
        assert result.unit_price == Decimal("10.00")
        assert result.min_qty == Decimal("1.000")

    def test_select_multiple_tiers_lowest_qty(self, db_session, test_org, test_customer):
        """Given multiple tiers, when qty < 100, then return tier with min_qty=1"""
        # Create price tiers: 1→€10, 100→€9, 500→€8
        prices = [
            CustomerPrice(
                org_id=test_org.id,
                customer_id=test_customer.id,
                internal_sku="SKU-002",
                currency="EUR",
                uom="EA",
                unit_price=Decimal("10.00"),
                min_qty=Decimal("1.000")
            ),
            CustomerPrice(
                org_id=test_org.id,
                customer_id=test_customer.id,
                internal_sku="SKU-002",
                currency="EUR",
                uom="EA",
                unit_price=Decimal("9.00"),
                min_qty=Decimal("100.000")
            ),
            CustomerPrice(
                org_id=test_org.id,
                customer_id=test_customer.id,
                internal_sku="SKU-002",
                currency="EUR",
                uom="EA",
                unit_price=Decimal("8.00"),
                min_qty=Decimal("500.000")
            ),
        ]
        for price in prices:
            db_session.add(price)
        db_session.commit()

        # Test with qty = 50 (should match tier with min_qty=1)
        result = PriceService.select_price_tier(
            db=db_session,
            org_id=test_org.id,
            customer_id=test_customer.id,
            internal_sku="SKU-002",
            currency="EUR",
            uom="EA",
            qty=Decimal("50.000")
        )

        assert result is not None
        assert result.unit_price == Decimal("10.00")
        assert result.min_qty == Decimal("1.000")

    def test_select_multiple_tiers_middle_qty(self, db_session, test_org, test_customer):
        """Given multiple tiers, when qty = 150, then return tier with min_qty=100"""
        # Create price tiers: 1→€10, 100→€9, 500→€8
        prices = [
            CustomerPrice(
                org_id=test_org.id,
                customer_id=test_customer.id,
                internal_sku="SKU-003",
                currency="EUR",
                uom="EA",
                unit_price=Decimal("10.00"),
                min_qty=Decimal("1.000")
            ),
            CustomerPrice(
                org_id=test_org.id,
                customer_id=test_customer.id,
                internal_sku="SKU-003",
                currency="EUR",
                uom="EA",
                unit_price=Decimal("9.00"),
                min_qty=Decimal("100.000")
            ),
            CustomerPrice(
                org_id=test_org.id,
                customer_id=test_customer.id,
                internal_sku="SKU-003",
                currency="EUR",
                uom="EA",
                unit_price=Decimal("8.00"),
                min_qty=Decimal("500.000")
            ),
        ]
        for price in prices:
            db_session.add(price)
        db_session.commit()

        # Test with qty = 150 (should match tier with min_qty=100)
        result = PriceService.select_price_tier(
            db=db_session,
            org_id=test_org.id,
            customer_id=test_customer.id,
            internal_sku="SKU-003",
            currency="EUR",
            uom="EA",
            qty=Decimal("150.000")
        )

        assert result is not None
        assert result.unit_price == Decimal("9.00")
        assert result.min_qty == Decimal("100.000")

    def test_select_multiple_tiers_highest_qty(self, db_session, test_org, test_customer):
        """Given multiple tiers, when qty = 600, then return tier with min_qty=500"""
        # Create price tiers: 1→€10, 100→€9, 500→€8
        prices = [
            CustomerPrice(
                org_id=test_org.id,
                customer_id=test_customer.id,
                internal_sku="SKU-004",
                currency="EUR",
                uom="EA",
                unit_price=Decimal("10.00"),
                min_qty=Decimal("1.000")
            ),
            CustomerPrice(
                org_id=test_org.id,
                customer_id=test_customer.id,
                internal_sku="SKU-004",
                currency="EUR",
                uom="EA",
                unit_price=Decimal("9.00"),
                min_qty=Decimal("100.000")
            ),
            CustomerPrice(
                org_id=test_org.id,
                customer_id=test_customer.id,
                internal_sku="SKU-004",
                currency="EUR",
                uom="EA",
                unit_price=Decimal("8.00"),
                min_qty=Decimal("500.000")
            ),
        ]
        for price in prices:
            db_session.add(price)
        db_session.commit()

        # Test with qty = 600 (should match tier with min_qty=500)
        result = PriceService.select_price_tier(
            db=db_session,
            org_id=test_org.id,
            customer_id=test_customer.id,
            internal_sku="SKU-004",
            currency="EUR",
            uom="EA",
            qty=Decimal("600.000")
        )

        assert result is not None
        assert result.unit_price == Decimal("8.00")
        assert result.min_qty == Decimal("500.000")

    def test_select_tier_exact_min_qty(self, db_session, test_org, test_customer):
        """Given multiple tiers, when qty = 100 exactly, then return tier with min_qty=100"""
        # Create price tiers: 1→€10, 100→€9
        prices = [
            CustomerPrice(
                org_id=test_org.id,
                customer_id=test_customer.id,
                internal_sku="SKU-005",
                currency="EUR",
                uom="EA",
                unit_price=Decimal("10.00"),
                min_qty=Decimal("1.000")
            ),
            CustomerPrice(
                org_id=test_org.id,
                customer_id=test_customer.id,
                internal_sku="SKU-005",
                currency="EUR",
                uom="EA",
                unit_price=Decimal("9.00"),
                min_qty=Decimal("100.000")
            ),
        ]
        for price in prices:
            db_session.add(price)
        db_session.commit()

        # Test with qty = 100 exactly (should match tier with min_qty=100, inclusive)
        result = PriceService.select_price_tier(
            db=db_session,
            org_id=test_org.id,
            customer_id=test_customer.id,
            internal_sku="SKU-005",
            currency="EUR",
            uom="EA",
            qty=Decimal("100.000")
        )

        assert result is not None
        assert result.unit_price == Decimal("9.00")
        assert result.min_qty == Decimal("100.000")

    def test_no_price_for_customer_sku(self, db_session, test_org, test_customer):
        """Given no price exists for customer+SKU, when lookup, then return None"""
        result = PriceService.select_price_tier(
            db=db_session,
            org_id=test_org.id,
            customer_id=test_customer.id,
            internal_sku="SKU-NONEXISTENT",
            currency="EUR",
            uom="EA",
            qty=Decimal("50.000")
        )

        assert result is None

    def test_filter_by_valid_from(self, db_session, test_org, test_customer):
        """Given price with valid_from in future, when lookup today, then return None"""
        tomorrow = date.today() + timedelta(days=1)

        price = CustomerPrice(
            org_id=test_org.id,
            customer_id=test_customer.id,
            internal_sku="SKU-006",
            currency="EUR",
            uom="EA",
            unit_price=Decimal("10.00"),
            min_qty=Decimal("1.000"),
            valid_from=tomorrow
        )
        db_session.add(price)
        db_session.commit()

        # Test lookup today (should not match because valid_from is tomorrow)
        result = PriceService.select_price_tier(
            db=db_session,
            org_id=test_org.id,
            customer_id=test_customer.id,
            internal_sku="SKU-006",
            currency="EUR",
            uom="EA",
            qty=Decimal("50.000"),
            as_of_date=date.today()
        )

        assert result is None

    def test_filter_by_valid_to(self, db_session, test_org, test_customer):
        """Given price with valid_to in past, when lookup today, then return None"""
        yesterday = date.today() - timedelta(days=1)

        price = CustomerPrice(
            org_id=test_org.id,
            customer_id=test_customer.id,
            internal_sku="SKU-007",
            currency="EUR",
            uom="EA",
            unit_price=Decimal("10.00"),
            min_qty=Decimal("1.000"),
            valid_to=yesterday
        )
        db_session.add(price)
        db_session.commit()

        # Test lookup today (should not match because valid_to is yesterday)
        result = PriceService.select_price_tier(
            db=db_session,
            org_id=test_org.id,
            customer_id=test_customer.id,
            internal_sku="SKU-007",
            currency="EUR",
            uom="EA",
            qty=Decimal("50.000"),
            as_of_date=date.today()
        )

        assert result is None

    def test_filter_by_currency(self, db_session, test_org, test_customer):
        """Given price in EUR, when lookup with USD, then return None"""
        price = CustomerPrice(
            org_id=test_org.id,
            customer_id=test_customer.id,
            internal_sku="SKU-008",
            currency="EUR",
            uom="EA",
            unit_price=Decimal("10.00"),
            min_qty=Decimal("1.000")
        )
        db_session.add(price)
        db_session.commit()

        # Test lookup with different currency
        result = PriceService.select_price_tier(
            db=db_session,
            org_id=test_org.id,
            customer_id=test_customer.id,
            internal_sku="SKU-008",
            currency="USD",
            uom="EA",
            qty=Decimal("50.000")
        )

        assert result is None


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
