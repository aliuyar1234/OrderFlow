"""Customer SQLAlchemy model"""

from sqlalchemy import Column, Text, ForeignKey, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID, CITEXT, TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text

from .base import Base, PortableJSONB


class Customer(Base):
    """Customer model representing business customers in the OrderFlow system.

    Each customer belongs to one organization and may have an erp_customer_number
    for ERP integration. Customers have default currency/language settings and
    addresses stored as JSONB.
    """
    __tablename__ = "customer"
    __table_args__ = (
        Index("ix_customer_org_id", "org_id"),
        Index("ix_customer_org_erp_number", "org_id", "erp_customer_number"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    org_id = Column(UUID(as_uuid=True), ForeignKey("org.id", ondelete="RESTRICT"), nullable=False)
    name = Column(Text, nullable=False)
    erp_customer_number = Column(Text, nullable=True)
    email = Column(CITEXT, nullable=True)
    default_currency = Column(Text, nullable=False)
    default_language = Column(Text, nullable=False)
    billing_address = Column(PortableJSONB, nullable=True)
    shipping_address = Column(PortableJSONB, nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    # Relationships
    org = relationship("Org", back_populates="customers")
    contacts = relationship("CustomerContact", back_populates="customer", cascade="all, delete-orphan")

    def to_dict(self):
        """Convert customer to dictionary representation"""
        return {
            "id": str(self.id),
            "org_id": str(self.org_id),
            "name": self.name,
            "erp_customer_number": self.erp_customer_number,
            "email": self.email,
            "default_currency": self.default_currency,
            "default_language": self.default_language,
            "billing_address": self.billing_address,
            "shipping_address": self.shipping_address,
            "notes": self.notes,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
