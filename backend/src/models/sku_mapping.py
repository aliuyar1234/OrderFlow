"""SKU Mapping SQLAlchemy model.

SSOT Reference: §5.4.12 (sku_mapping table schema)
"""

from sqlalchemy import Column, Text, ForeignKey, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text

from .base import Base


class SkuMapping(Base):
    """SKU Mapping model for learning customer SKU to internal SKU mappings.

    This entity stores confirmed, suggested, rejected, and deprecated mappings
    from customer SKUs to internal product SKUs. It serves as the learning loop
    for the matching engine.

    Status values:
    - SUGGESTED: Auto-generated mapping from hybrid matcher
    - CONFIRMED: User-confirmed mapping (highest priority)
    - REJECTED: User-rejected mapping (for feedback)
    - DEPRECATED: Auto-deprecated due to rejection threshold

    SSOT Reference: §5.4.12, §7.10.1 (Confirmed Mappings)
    """
    __tablename__ = "sku_mapping"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    org_id = Column(UUID(as_uuid=True), ForeignKey("org.id", ondelete="RESTRICT"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customer.id", ondelete="CASCADE"), nullable=False)

    # Customer SKU fields
    customer_sku_norm = Column(Text, nullable=False)  # Normalized version for matching
    customer_sku_raw_sample = Column(Text, nullable=True)  # Sample raw SKU for reference

    # Internal SKU mapping
    internal_sku = Column(Text, nullable=False)

    # UoM conversion (optional)
    uom_from = Column(Text, nullable=True)  # Customer UoM
    uom_to = Column(Text, nullable=True)  # Internal UoM
    pack_factor = Column(Numeric(18, 6), nullable=True)  # e.g., 1 KAR = 12 ST

    # Mapping status and quality
    status = Column(Text, nullable=False)  # SUGGESTED, CONFIRMED, REJECTED, DEPRECATED
    confidence = Column(Numeric(5, 4), nullable=False, server_default="0.0")  # 0.0-1.0

    # Learning metrics
    support_count = Column(Integer, nullable=False, server_default="0")  # Times confirmed
    reject_count = Column(Integer, nullable=False, server_default="0")  # Times rejected
    last_used_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Audit fields
    created_by = Column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    # Relationships
    org = relationship("Org")
    customer = relationship("Customer")
    creator = relationship("User")

    def to_dict(self):
        """Convert SKU mapping to dictionary representation."""
        return {
            "id": str(self.id),
            "org_id": str(self.org_id),
            "customer_id": str(self.customer_id),
            "customer_sku_norm": self.customer_sku_norm,
            "customer_sku_raw_sample": self.customer_sku_raw_sample,
            "internal_sku": self.internal_sku,
            "uom_from": self.uom_from,
            "uom_to": self.uom_to,
            "pack_factor": float(self.pack_factor) if self.pack_factor else None,
            "status": self.status,
            "confidence": float(self.confidence),
            "support_count": self.support_count,
            "reject_count": self.reject_count,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_by": str(self.created_by) if self.created_by else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
