"""CustomerPrice SQLAlchemy model"""

from sqlalchemy import Column, Text, ForeignKey, Numeric, Date, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text
from decimal import Decimal

from .base import Base


class CustomerPrice(Base):
    """CustomerPrice model representing customer-specific pricing for products.

    Per §5.4.11, each price record supports:
    - Tiered pricing via min_qty (quantity breaks)
    - Date-based validity (valid_from/valid_to)
    - Multiple currencies and UoMs
    - Source tracking (IMPORT, MANUAL, etc.)

    Used for price validation and matching confidence boosting.
    """
    __tablename__ = "customer_price"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    org_id = Column(UUID(as_uuid=True), ForeignKey("org.id", ondelete="RESTRICT"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customer.id", ondelete="RESTRICT"), nullable=False)
    internal_sku = Column(Text, nullable=False)
    currency = Column(Text, nullable=False)
    uom = Column(Text, nullable=False)
    unit_price = Column(Numeric(18, 4), nullable=False)
    min_qty = Column(Numeric(18, 3), nullable=False, server_default=text("1.000"))
    valid_from = Column(Date, nullable=True)
    valid_to = Column(Date, nullable=True)
    source = Column(Text, nullable=False, server_default=text("'IMPORT'"))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    # Indexes and constraints
    __table_args__ = (
        Index("ix_customer_price_org_id", "org_id"),
        Index("ix_customer_price_org_customer_sku", "org_id", "customer_id", "internal_sku"),
        CheckConstraint('unit_price > 0', name='ck_customer_price_unit_price_positive'),
        CheckConstraint('min_qty > 0', name='ck_customer_price_min_qty_positive'),
    )

    # Relationships
    org = relationship("Org", backref="customer_prices")
    customer = relationship("Customer", backref="prices")

    def to_dict(self):
        """Convert customer price to dictionary representation"""
        return {
            "id": str(self.id),
            "org_id": str(self.org_id),
            "customer_id": str(self.customer_id),
            "internal_sku": self.internal_sku,
            "currency": self.currency,
            "uom": self.uom,
            "unit_price": float(self.unit_price) if self.unit_price else None,
            "min_qty": float(self.min_qty) if self.min_qty else None,
            "valid_from": self.valid_from.isoformat() if self.valid_from else None,
            "valid_to": self.valid_to.isoformat() if self.valid_to else None,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
