"""ERPPushLog model - Push attempt history and debugging"""

from sqlalchemy import Column, Text, ForeignKey, Integer, text, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP, JSONB
from sqlalchemy.orm import relationship, validates
from datetime import datetime

from .base import Base


class ERPPushLog(Base):
    """
    ERP Push Log - Complete history of push attempts.

    Tracks every push attempt with full request/response for debugging,
    idempotency checking, and retry coordination.

    Each push attempt gets a unique idempotency_key to prevent duplicate processing.

    SSOT Reference: Task requirements (erp_push_log table)
    """
    __tablename__ = "erp_push_log"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("org.id", ondelete="RESTRICT"),
        nullable=False
    )
    draft_order_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Reference to draft_order (nullable for connection tests)"
    )
    connector_type = Column(
        Text,
        nullable=False,
        comment="Connector type used for this push attempt"
    )
    status = Column(
        Text,
        nullable=False,
        comment="Push status: SUCCESS, FAILED, PENDING, RETRYING"
    )
    request_json = Column(
        JSONB,
        nullable=True,
        comment="Full request payload sent to connector"
    )
    response_json = Column(
        JSONB,
        nullable=True,
        comment="Full response received from connector"
    )
    error_message = Column(
        Text,
        nullable=True,
        comment="Human-readable error message if status=FAILED"
    )
    idempotency_key = Column(
        Text,
        nullable=False,
        unique=True,
        comment="Unique key for idempotent push operations"
    )
    retry_count = Column(
        Integer,
        nullable=False,
        server_default="0",
        comment="Number of retry attempts made"
    )
    latency_ms = Column(
        Integer,
        nullable=True,
        comment="Total time taken for push operation in milliseconds"
    )
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()")
    )

    # Relationships
    org = relationship("Org", back_populates="erp_push_logs")
    connection = relationship("ERPConnection", back_populates="push_logs")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('SUCCESS', 'FAILED', 'PENDING', 'RETRYING')",
            name='ck_erp_push_log_status'
        ),
        Index('idx_erp_push_log_org', 'org_id', text('created_at DESC')),
        Index('idx_erp_push_log_draft', 'draft_order_id', text('created_at DESC')),
        Index('idx_erp_push_log_idempotency', 'idempotency_key', unique=True),
    )

    @validates('status')
    def validate_status(self, key, value):
        """Ensure status is valid."""
        valid_statuses = ['SUCCESS', 'FAILED', 'PENDING', 'RETRYING']
        if value not in valid_statuses:
            raise ValueError(
                f"Invalid status: {value}. "
                f"Must be one of: {', '.join(valid_statuses)}"
            )
        return value

    @validates('retry_count')
    def validate_retry_count(self, key, value):
        """Ensure retry_count is non-negative."""
        if value < 0:
            raise ValueError("retry_count must be non-negative")
        return value

    def __repr__(self):
        return (
            f"<ERPPushLog(id={self.id}, draft_order_id={self.draft_order_id}, "
            f"connector_type='{self.connector_type}', status='{self.status}', "
            f"retry_count={self.retry_count})>"
        )
