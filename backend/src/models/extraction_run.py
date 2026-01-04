"""ExtractionRun model - Tracks document extraction attempts and results.

SSOT Reference: §5.4.7 (extraction_run table)
"""

import enum
from datetime import datetime

from sqlalchemy import Column, Text, ForeignKey, text, Enum as SQLEnum, Index
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import relationship

from .base import Base, PortableJSONB


class ExtractionRunStatus(str, enum.Enum):
    """Status of extraction run.

    SSOT Reference: §5.2.4 (ExtractionRunStatus)
    """
    PENDING = "PENDING"  # Queued but not yet started
    RUNNING = "RUNNING"  # Currently executing
    SUCCEEDED = "SUCCEEDED"  # Completed successfully
    FAILED = "FAILED"  # Failed with error


class ExtractionRun(Base):
    """ExtractionRun model - Tracks extraction attempts for documents.

    Each document can have multiple extraction runs (e.g., retry after failure,
    different extractor versions). The extraction_run stores the canonical
    output JSON, metrics, and error information.

    Extraction output is stored temporarily in output_json before being
    converted into a draft_order.

    SSOT Reference: §5.4.7
    """
    __tablename__ = "extraction_run"
    __table_args__ = (
        Index("ix_extraction_run_org_id", "org_id"),
        Index("ix_extraction_run_org_document", "org_id", "document_id"),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey('org.id', name='fk_extraction_run_org_id'),
        nullable=False
    )
    document_id = Column(
        UUID(as_uuid=True),
        # FK to document table will be added when document table is created
        nullable=False
    )
    extractor_version = Column(
        Text,
        nullable=False,
        comment="Extractor version identifier (e.g., 'excel_v1', 'llm_gpt4_v1')"
    )
    status = Column(
        SQLEnum(ExtractionRunStatus, name='extractionrunstatus'),
        nullable=False,
        default=ExtractionRunStatus.PENDING
    )
    started_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="When extraction started"
    )
    finished_at = Column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="When extraction finished (success or failure)"
    )
    output_json = Column(
        PortableJSONB,
        nullable=True,
        comment="Canonical extraction output (CanonicalExtractionOutput schema)"
    )
    metrics_json = Column(
        PortableJSONB,
        nullable=True,
        comment="Extraction metrics (runtime_ms, page_count, confidence_breakdown, etc.)"
    )
    error_json = Column(
        PortableJSONB,
        nullable=True,
        comment="Error details if extraction failed"
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()")
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
        onupdate=datetime.utcnow
    )

    # Relationships
    # org relationship
    org = relationship("Org", foreign_keys=[org_id])
    # document relationship will be added when Document model is created

    def __repr__(self):
        return (
            f"<ExtractionRun(id={self.id}, document_id={self.document_id}, "
            f"status={self.status}, extractor_version='{self.extractor_version}')>"
        )

    @property
    def duration_ms(self) -> int:
        """Calculate extraction duration in milliseconds.

        Returns:
            Duration in milliseconds, or 0 if not finished
        """
        if self.started_at and self.finished_at:
            delta = self.finished_at - self.started_at
            return int(delta.total_seconds() * 1000)
        return 0

    @property
    def is_complete(self) -> bool:
        """Check if extraction is complete (success or failure).

        Returns:
            True if status is SUCCEEDED or FAILED
        """
        return self.status in (ExtractionRunStatus.SUCCEEDED, ExtractionRunStatus.FAILED)

    @property
    def confidence_score(self) -> float:
        """Get confidence score from metrics_json.

        Returns:
            Confidence score 0.0-1.0, or 0.0 if not available
        """
        if self.metrics_json and 'confidence' in self.metrics_json:
            return float(self.metrics_json['confidence'])
        return 0.0
