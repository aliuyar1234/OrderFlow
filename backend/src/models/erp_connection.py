"""ERP Connection model - stores connector configuration.

SSOT Reference: §5.4.14 (erp_connection table)
"""

from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid

from .base import Base


class ERPConnection(Base):
    """ERP Connection configuration for an organization.

    This model stores the configuration for ERP export connectors.
    Each org can have one active ERP connection (MVP constraint).

    Attributes:
        id: Primary key UUID
        org_id: Organization this connection belongs to
        connector_type: Type of connector (e.g., 'DROPZONE_JSON_V1')
        config_encrypted: Encrypted connector configuration (credentials, paths)
        active: Whether this connection is active
        last_test_at: When connection was last tested
        last_test_success: Result of last connection test
        created_at: When connection was created
        updated_at: When connection was last modified
    """

    __tablename__ = "erp_connection"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("org.id"), nullable=False)
    connector_type = Column(Text, nullable=False)  # e.g., 'DROPZONE_JSON_V1'
    config_encrypted = Column(Text, nullable=False)  # Encrypted JSON config
    active = Column(Boolean, nullable=False, default=True)
    last_test_at = Column(DateTime(timezone=True), nullable=True)
    last_test_success = Column(Boolean, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    org = relationship("Org", back_populates="erp_connections")
    exports = relationship("ERPExport", back_populates="connection", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("idx_erp_connection_org_active", org_id, active),
        Index("uq_erp_connection_org_type", org_id, connector_type, unique=True),
    )

    def __repr__(self):
        return f"<ERPConnection(id={self.id}, org_id={self.org_id}, type={self.connector_type})>"
