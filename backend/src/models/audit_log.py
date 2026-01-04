"""AuditLog SQLAlchemy model"""

from sqlalchemy import Column, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP, INET
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text

from .base import Base, PortableJSONB


class AuditLog(Base):
    """AuditLog model for immutable security event logging.

    Records all security-relevant events for compliance, auditing, and forensics.
    Entries are append-only and should never be updated or deleted.
    """
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_org_id", "org_id"),
        Index("ix_audit_log_org_id_created_at", "org_id", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    org_id = Column(UUID(as_uuid=True), ForeignKey("org.id", ondelete="RESTRICT"), nullable=False)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    action = Column(Text, nullable=False)
    entity_type = Column(Text, nullable=True)
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    metadata_json = Column(PortableJSONB, nullable=True)
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    # Relationships
    org = relationship("Org")
    actor = relationship("User")

    def to_dict(self):
        """Convert audit log entry to dictionary representation"""
        return {
            "id": str(self.id),
            "org_id": str(self.org_id),
            "actor_id": str(self.actor_id) if self.actor_id else None,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": str(self.entity_id) if self.entity_id else None,
            "metadata": self.metadata_json,
            "ip_address": str(self.ip_address) if self.ip_address else None,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat()
        }
