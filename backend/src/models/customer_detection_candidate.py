"""CustomerDetectionCandidate SQLAlchemy model"""

from sqlalchemy import Column, Text, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text

from .base import Base, PortableJSONB


class CustomerDetectionCandidate(Base):
    """CustomerDetectionCandidate model storing detection results for draft orders.

    Each candidate represents a potential customer match with signals and confidence score.
    When customer is selected, the candidate status is updated to SELECTED.
    """
    __tablename__ = "customer_detection_candidate"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    org_id = Column(UUID(as_uuid=True), ForeignKey("org.id", ondelete="RESTRICT"), nullable=False)
    draft_order_id = Column(UUID(as_uuid=True), nullable=False)  # FK to draft_order when that table exists
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customer.id", ondelete="CASCADE"), nullable=False)
    score = Column(Float, nullable=False)
    signals_json = Column(PortableJSONB, nullable=False, server_default=text("'{}'::jsonb"))
    status = Column(Text, nullable=False, server_default="'CANDIDATE'")  # CANDIDATE, SELECTED, REJECTED
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    # Relationships
    customer = relationship("Customer")

    def to_dict(self):
        """Convert customer detection candidate to dictionary representation"""
        return {
            "id": str(self.id),
            "org_id": str(self.org_id),
            "draft_order_id": str(self.draft_order_id),
            "customer_id": str(self.customer_id),
            "score": self.score,
            "signals_json": self.signals_json,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
