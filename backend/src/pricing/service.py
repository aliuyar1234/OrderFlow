"""Price lookup service for customer-specific pricing

Per §5.4.11 and spec 020-customer-prices, this service implements:
- Price tier selection algorithm (max min_qty <= order_qty)
- Date range filtering (valid_from/valid_to)
- Multi-currency and multi-UoM support
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import Optional
from uuid import UUID
from datetime import date
from decimal import Decimal

from models.customer_price import CustomerPrice


class PriceService:
    """Service for customer price operations"""

    @staticmethod
    def select_price_tier(
        db: Session,
        org_id: UUID,
        customer_id: UUID,
        internal_sku: str,
        currency: str,
        uom: str,
        qty: Decimal,
        as_of_date: Optional[date] = None
    ) -> Optional[CustomerPrice]:
        """Select the best matching price tier for a given quantity.

        Algorithm per spec:
        1. Filter prices by customer_id, internal_sku, currency, uom
        2. Filter by date range (valid_from <= date <= valid_to or NULL)
        3. Filter tiers where min_qty <= qty
        4. Return tier with highest min_qty (best match)

        Args:
            db: Database session
            org_id: Organization ID (for tenant isolation)
            customer_id: Customer ID
            internal_sku: Internal SKU (normalized)
            currency: Currency code (e.g., EUR, USD)
            uom: Unit of measure
            qty: Order quantity
            as_of_date: Date for validity check (default: today)

        Returns:
            CustomerPrice object for the best matching tier, or None if no match
        """
        if as_of_date is None:
            as_of_date = date.today()

        # Build query with filters
        query = db.query(CustomerPrice).filter(
            and_(
                CustomerPrice.org_id == org_id,
                CustomerPrice.customer_id == customer_id,
                CustomerPrice.internal_sku == internal_sku,
                CustomerPrice.currency == currency,
                CustomerPrice.uom == uom,
                CustomerPrice.min_qty <= qty,
                # Date range filter: valid_from <= as_of_date
                or_(
                    CustomerPrice.valid_from.is_(None),
                    CustomerPrice.valid_from <= as_of_date
                ),
                # Date range filter: valid_to >= as_of_date OR NULL
                or_(
                    CustomerPrice.valid_to.is_(None),
                    CustomerPrice.valid_to >= as_of_date
                )
            )
        )

        # Get all applicable tiers and find the one with highest min_qty
        applicable_tiers = query.all()

        if not applicable_tiers:
            return None

        # Return tier with highest min_qty (best match)
        return max(applicable_tiers, key=lambda p: p.min_qty)

    @staticmethod
    def get_customer_prices(
        db: Session,
        org_id: UUID,
        customer_id: Optional[UUID] = None,
        internal_sku: Optional[str] = None,
        currency: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> tuple[list[CustomerPrice], int]:
        """Get customer prices with optional filters.

        Args:
            db: Database session
            org_id: Organization ID (for tenant isolation)
            customer_id: Optional customer ID filter
            internal_sku: Optional SKU filter
            currency: Optional currency filter
            limit: Max results per page
            offset: Offset for pagination

        Returns:
            Tuple of (prices list, total count)
        """
        query = db.query(CustomerPrice).filter(CustomerPrice.org_id == org_id)

        if customer_id:
            query = query.filter(CustomerPrice.customer_id == customer_id)

        if internal_sku:
            query = query.filter(CustomerPrice.internal_sku == internal_sku)

        if currency:
            query = query.filter(CustomerPrice.currency == currency.upper())

        total = query.count()
        prices = query.order_by(
            CustomerPrice.customer_id,
            CustomerPrice.internal_sku,
            CustomerPrice.min_qty
        ).limit(limit).offset(offset).all()

        return prices, total

    @staticmethod
    def create_price(
        db: Session,
        org_id: UUID,
        customer_id: UUID,
        internal_sku: str,
        currency: str,
        uom: str,
        unit_price: Decimal,
        min_qty: Decimal = Decimal("1.000"),
        valid_from: Optional[date] = None,
        valid_to: Optional[date] = None,
        source: str = "MANUAL"
    ) -> CustomerPrice:
        """Create a new customer price.

        Args:
            db: Database session
            org_id: Organization ID
            customer_id: Customer ID
            internal_sku: Internal SKU (normalized)
            currency: Currency code
            uom: Unit of measure
            unit_price: Unit price
            min_qty: Minimum quantity for tier (default: 1.000)
            valid_from: Valid from date (optional)
            valid_to: Valid to date (optional)
            source: Source of price (IMPORT, MANUAL, etc.)

        Returns:
            Created CustomerPrice object
        """
        price = CustomerPrice(
            org_id=org_id,
            customer_id=customer_id,
            internal_sku=internal_sku.strip(),
            currency=currency.upper(),
            uom=uom,
            unit_price=unit_price,
            min_qty=min_qty,
            valid_from=valid_from,
            valid_to=valid_to,
            source=source
        )

        db.add(price)
        db.commit()
        db.refresh(price)

        return price

    @staticmethod
    def update_price(
        db: Session,
        price_id: UUID,
        org_id: UUID,
        unit_price: Optional[Decimal] = None,
        min_qty: Optional[Decimal] = None,
        valid_from: Optional[date] = None,
        valid_to: Optional[date] = None,
        source: Optional[str] = None
    ) -> Optional[CustomerPrice]:
        """Update an existing customer price.

        Args:
            db: Database session
            price_id: Price ID to update
            org_id: Organization ID (for tenant isolation)
            unit_price: New unit price (optional)
            min_qty: New min quantity (optional)
            valid_from: New valid from date (optional)
            valid_to: New valid to date (optional)
            source: New source (optional)

        Returns:
            Updated CustomerPrice object, or None if not found
        """
        price = db.query(CustomerPrice).filter(
            and_(
                CustomerPrice.id == price_id,
                CustomerPrice.org_id == org_id
            )
        ).first()

        if not price:
            return None

        if unit_price is not None:
            price.unit_price = unit_price
        if min_qty is not None:
            price.min_qty = min_qty
        if valid_from is not None:
            price.valid_from = valid_from
        if valid_to is not None:
            price.valid_to = valid_to
        if source is not None:
            price.source = source

        db.commit()
        db.refresh(price)

        return price

    @staticmethod
    def delete_price(
        db: Session,
        price_id: UUID,
        org_id: UUID
    ) -> bool:
        """Delete a customer price.

        Args:
            db: Database session
            price_id: Price ID to delete
            org_id: Organization ID (for tenant isolation)

        Returns:
            True if deleted, False if not found
        """
        price = db.query(CustomerPrice).filter(
            and_(
                CustomerPrice.id == price_id,
                CustomerPrice.org_id == org_id
            )
        ).first()

        if not price:
            return False

        db.delete(price)
        db.commit()

        return True
