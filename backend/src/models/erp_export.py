"""ERP Export model - tracks export attempts to ERP.

SSOT Reference: §5.4.15 (erp_export table), §5.2.9 (ERPExportStatus)
"""

from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid

from .base import Base


class ERPExportStatus(str, Enum):
    """Status of an ERP export operation.

    SSOT Reference: §5.2.9

    Values:
        PENDING: Export created but not yet sent
        SENT: Export successfully written to dropzone/ERP
        ACKED: ERP acknowledged successful import (optional)
        FAILED: Export failed (network error, validation error, etc.)
    """
    PENDING = "PENDING"
    SENT = "SENT"
    ACKED = "ACKED"
    FAILED = "FAILED"


class ERPExport(Base):
    """ERP Export record - tracks each export attempt.

    This model records every attempt to export a draft order to ERP,
    including success/failure status, storage location, and ERP response.

    Each export is immutable after creation - retries create new records.

    Attributes:
        id: Primary key UUID
        org_id: Organization ID (for multi-tenant isolation)
        erp_connection_id: Which ERP connection was used
        draft_order_id: Which draft order was exported
        export_format_version: Format schema version (e.g., 'orderflow_export_json_v1')
        export_storage_key: S3/MinIO key where export JSON is stored
        dropzone_path: Actual path where file was written (SFTP/filesystem)
        status: Current status (PENDING, SENT, ACKED, FAILED)
        erp_order_id: ERP's order ID (from acknowledgment file)
        error_json: Error details if status=FAILED
        created_at: When export was initiated
        updated_at: Last status update (e.g., when ack received)
    """

    __tablename__ = "erp_export"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("org.id"), nullable=False)
    erp_connection_id = Column(UUID(as_uuid=True), ForeignKey("erp_connection.id"), nullable=False)
    draft_order_id = Column(UUID(as_uuid=True), nullable=False)  # FK will be added when draft_order model exists
    export_format_version = Column(Text, nullable=False, default="orderflow_export_json_v1")
    export_storage_key = Column(Text, nullable=False)
    dropzone_path = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default=ERPExportStatus.PENDING.value)
    erp_order_id = Column(Text, nullable=True)
    error_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    org = relationship("Org")
    connection = relationship("ERPConnection", back_populates="exports")

    # Indexes
    __table_args__ = (
        Index("idx_erp_export_draft", org_id, draft_order_id, created_at.desc()),
    )

    def __repr__(self):
        return f"<ERPExport(id={self.id}, draft_id={self.draft_order_id}, status={self.status})>"
