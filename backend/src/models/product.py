"""Product SQLAlchemy model"""

from sqlalchemy import Column, Text, ForeignKey, Boolean, Numeric, Index
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text

from .base import Base, PortableJSONB


class Product(Base):
    """Product model representing internal product master data.

    Each product belongs to one organization and has a unique internal_sku.
    Products support UoM conversions and flexible attributes stored as JSONB.
    """
    __tablename__ = "product"
    __table_args__ = (
        Index("ix_product_org_id", "org_id"),
        Index("ix_product_org_sku", "org_id", "internal_sku"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    org_id = Column(UUID(as_uuid=True), ForeignKey("org.id", ondelete="RESTRICT"), nullable=False)
    internal_sku = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    base_uom = Column(Text, nullable=False)
    uom_conversions_json = Column(PortableJSONB, nullable=False, server_default=text("'{}'::jsonb"))
    active = Column(Boolean, nullable=False, server_default="true")
    attributes_json = Column(PortableJSONB, nullable=False, server_default=text("'{}'::jsonb"))
    updated_source_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    # Relationships
    org = relationship("Org", back_populates="products")

    def to_dict(self):
        """Convert product to dictionary representation"""
        return {
            "id": str(self.id),
            "org_id": str(self.org_id),
            "internal_sku": self.internal_sku,
            "name": self.name,
            "description": self.description,
            "base_uom": self.base_uom,
            "uom_conversions_json": self.uom_conversions_json,
            "active": self.active,
            "attributes_json": self.attributes_json,
            "updated_source_at": self.updated_source_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class UnitOfMeasure(Base):
    """Unit of Measure model for managing measurement units.

    Each UoM belongs to one organization and has a unique code.
    Conversion factors define relationships to base units.
    """
    __tablename__ = "unit_of_measure"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    org_id = Column(UUID(as_uuid=True), ForeignKey("org.id", ondelete="RESTRICT"), nullable=False)
    code = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    conversion_factor = Column(Numeric(precision=10, scale=4), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    # Relationships
    org = relationship("Org", back_populates="units_of_measure")

    def to_dict(self):
        """Convert UoM to dictionary representation"""
        return {
            "id": str(self.id),
            "org_id": str(self.org_id),
            "code": self.code,
            "name": self.name,
            "conversion_factor": float(self.conversion_factor) if self.conversion_factor else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
