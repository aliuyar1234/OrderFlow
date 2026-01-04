"""Document SQLAlchemy model

Document represents uploaded/attached files (PDF, Excel, CSV).
Tracks storage location, processing status, and file metadata.
"""

from sqlalchemy import Column, Text, ForeignKey, BigInteger, Integer, Numeric, Enum as SQLEnum, Index
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text
import enum

from .base import Base, PortableJSONB


class DocumentStatus(str, enum.Enum):
    """Status values for Document processing

    SSOT Reference: §5.2.3 (DocumentStatus state machine)
    State flow: UPLOADED → STORED → PROCESSING → EXTRACTED or FAILED
    """
    UPLOADED = "UPLOADED"      # File received via upload
    STORED = "STORED"          # File persisted to object storage
    PROCESSING = "PROCESSING"  # Extraction in progress
    EXTRACTED = "EXTRACTED"    # Extraction complete (terminal success)
    FAILED = "FAILED"          # Processing failed (can retry)


class Document(Base):
    """Document model representing file attachments.

    Each document belongs to one organization and may be associated with an
    inbound message (if from email). Documents are stored in object storage
    with SHA256 hash for deduplication. Processing status tracks extraction.
    """
    __tablename__ = "document"
    __table_args__ = (
        Index("ix_document_org_id", "org_id"),
        Index("ix_document_org_sha256", "org_id", "sha256"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    org_id = Column(UUID(as_uuid=True), ForeignKey("org.id", ondelete="RESTRICT"), nullable=False)
    inbound_message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("inbound_message.id", ondelete="CASCADE"),
        nullable=True
    )
    file_name = Column(Text, nullable=False)
    mime_type = Column(Text, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    sha256 = Column(Text, nullable=False)  # hex string
    storage_key = Column(Text, nullable=False)  # Object storage key for original
    preview_storage_key = Column(Text, nullable=True)  # Rendered preview/thumbnails
    extracted_text_storage_key = Column(Text, nullable=True)  # Text dump for debug/LLM
    status = Column(
        SQLEnum(DocumentStatus, name="documentstatus", create_type=False),
        nullable=False,
        server_default="UPLOADED"
    )
    layout_fingerprint = Column(Text, nullable=True)  # SHA256 of layout structure (§5.4.6)
    page_count = Column(Integer, nullable=True)
    text_coverage_ratio = Column(Numeric(4, 3), nullable=True)  # 0..1 for PDF text coverage
    error_json = Column(PortableJSONB, nullable=True)  # Error details if status=FAILED
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    # Relationships
    org = relationship("Org", back_populates="documents")
    inbound_message = relationship("InboundMessage", back_populates="documents")

    def to_dict(self):
        """Convert document to dictionary representation"""
        return {
            "id": str(self.id),
            "org_id": str(self.org_id),
            "inbound_message_id": str(self.inbound_message_id) if self.inbound_message_id else None,
            "file_name": self.file_name,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "storage_key": self.storage_key,
            "preview_storage_key": self.preview_storage_key,
            "extracted_text_storage_key": self.extracted_text_storage_key,
            "status": self.status.value if isinstance(self.status, enum.Enum) else self.status,
            "page_count": self.page_count,
            "text_coverage_ratio": float(self.text_coverage_ratio) if self.text_coverage_ratio else None,
            "error_json": self.error_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
