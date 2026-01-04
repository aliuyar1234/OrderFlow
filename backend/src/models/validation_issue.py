"""ValidationIssue SQLAlchemy model (SSOT §5.4.13)"""

from sqlalchemy import Column, Text, ForeignKey, Integer, Enum as SQLEnum, Index
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text

from .base import Base, PortableJSONB
from domain.validation.models import ValidationIssueSeverity, ValidationIssueStatus


class ValidationIssue(Base):
    """Validation issue model representing rule violations in draft orders.

    Each issue is linked to a draft_order and optionally to a specific line.
    Issues have a type (from SSOT §7.3 list), severity (INFO/WARNING/ERROR),
    and status (OPEN/ACKNOWLEDGED/RESOLVED/OVERRIDDEN).

    Table schema per SSOT §5.4.13:
    - id: UUID primary key
    - org_id: organization (multi-tenant isolation)
    - draft_order_id: FK to draft_order
    - draft_order_line_id: FK to draft_order_line (nullable for header issues)
    - type: issue type from §7.3 (TEXT)
    - severity: ERROR/WARNING/INFO (ENUM)
    - status: OPEN/ACKNOWLEDGED/RESOLVED/OVERRIDDEN (ENUM)
    - message: human-readable message
    - details_json: JSONB with issue-specific metadata
    - resolved_at: timestamp when resolved
    - resolved_by_user_id: user who resolved
    - acknowledged_at: timestamp when acknowledged
    - acknowledged_by_user_id: user who acknowledged
    - created_at, updated_at: standard timestamps
    """
    __tablename__ = "validation_issue"
    __table_args__ = (
        Index("ix_validation_issue_org_id", "org_id"),
        Index("ix_validation_issue_org_draft", "org_id", "draft_order_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    org_id = Column(UUID(as_uuid=True), ForeignKey("org.id", ondelete="RESTRICT"), nullable=False)
    draft_order_id = Column(UUID(as_uuid=True), nullable=False)  # FK added in migration
    draft_order_line_id = Column(UUID(as_uuid=True), nullable=True)  # FK added in migration
    type = Column(Text, nullable=False)
    severity = Column(
        SQLEnum(ValidationIssueSeverity, name="validation_issue_severity"),
        nullable=False
    )
    status = Column(
        SQLEnum(ValidationIssueStatus, name="validation_issue_status"),
        nullable=False,
        server_default="OPEN"
    )
    message = Column(Text, nullable=False)
    details_json = Column(PortableJSONB, nullable=False, server_default=text("'{}'::jsonb"))

    resolved_at = Column(TIMESTAMP(timezone=True), nullable=True)
    resolved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="SET NULL"), nullable=True)

    acknowledged_at = Column(TIMESTAMP(timezone=True), nullable=True)
    acknowledged_by_user_id = Column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    # Relationships
    org = relationship("Org")
    resolved_by_user = relationship("User", foreign_keys=[resolved_by_user_id])
    acknowledged_by_user = relationship("User", foreign_keys=[acknowledged_by_user_id])

    def to_dict(self):
        """Convert validation issue to dictionary representation"""
        return {
            "id": str(self.id),
            "org_id": str(self.org_id),
            "draft_order_id": str(self.draft_order_id),
            "draft_order_line_id": str(self.draft_order_line_id) if self.draft_order_line_id else None,
            "type": self.type,
            "severity": self.severity.value if hasattr(self.severity, 'value') else self.severity,
            "status": self.status.value if hasattr(self.status, 'value') else self.status,
            "message": self.message,
            "details": self.details_json,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by_user_id": str(self.resolved_by_user_id) if self.resolved_by_user_id else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "acknowledged_by_user_id": str(self.acknowledged_by_user_id) if self.acknowledged_by_user_id else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
