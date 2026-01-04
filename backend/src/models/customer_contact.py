"""CustomerContact SQLAlchemy model"""

from sqlalchemy import Column, Text, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID, CITEXT, TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text

from .base import Base


class CustomerContact(Base):
    """CustomerContact model representing contact persons at customer organizations.

    Each contact has an email address used for customer detection. One contact
    per customer can be marked as primary.
    """
    __tablename__ = "customer_contact"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    org_id = Column(UUID(as_uuid=True), ForeignKey("org.id", ondelete="RESTRICT"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customer.id", ondelete="CASCADE"), nullable=False)
    email = Column(CITEXT, nullable=False)
    name = Column(Text, nullable=True)
    phone = Column(Text, nullable=True)
    role = Column(Text, nullable=True)
    is_primary = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    # Relationships
    customer = relationship("Customer", back_populates="contacts")

    def to_dict(self):
        """Convert customer contact to dictionary representation"""
        return {
            "id": str(self.id),
            "customer_id": str(self.customer_id),
            "email": self.email,
            "name": self.name,
            "phone": self.phone,
            "role": self.role,
            "is_primary": self.is_primary,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
