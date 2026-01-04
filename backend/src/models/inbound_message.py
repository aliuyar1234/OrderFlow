"""InboundMessage model - Represents received emails or uploads.

This model tracks all inbound messages (emails or uploads) that contain
order documents. Each message can have multiple attached documents.

SSOT Reference: §5.4.5 (inbound_message table), §5.2.2 (InboundMessageStatus)
"""

from enum import Enum
from sqlalchemy import Column, String, Text, CheckConstraint, Index, text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP, CITEXT
from sqlalchemy.orm import validates, relationship
from datetime import datetime

from .base import Base, PortableJSONB


class InboundMessageSource(str, Enum):
    """Source type for inbound messages.

    EMAIL: Message received via SMTP server
    UPLOAD: Message created from direct file upload via API
    """
    EMAIL = "EMAIL"
    UPLOAD = "UPLOAD"


class InboundMessageStatus(str, Enum):
    """Processing status for inbound messages.

    State machine transitions (SSOT §5.2.2):
    None → RECEIVED → STORED → PARSED → (terminal)
                  ↓         ↓
                FAILED ← FAILED

    RECEIVED: Email received, awaiting storage
    STORED: Raw MIME/file persisted to object storage
    PARSED: Attachments extracted and document records created
    FAILED: Processing failed (terminal state)
    """
    RECEIVED = "RECEIVED"
    STORED = "STORED"
    PARSED = "PARSED"
    FAILED = "FAILED"


# Allowed state transitions for validation
ALLOWED_TRANSITIONS = {
    None: [InboundMessageStatus.RECEIVED],
    InboundMessageStatus.RECEIVED: [
        InboundMessageStatus.STORED,
        InboundMessageStatus.FAILED
    ],
    InboundMessageStatus.STORED: [
        InboundMessageStatus.PARSED,
        InboundMessageStatus.FAILED
    ],
    InboundMessageStatus.PARSED: [],  # Terminal success state
    InboundMessageStatus.FAILED: [],  # Terminal failure state
}


class InboundMessage(Base):
    """
    InboundMessage model - Tracks received emails or uploaded files.

    Each inbound message represents a single email or upload event that
    may contain one or more order documents (PDF, Excel, CSV attachments).

    Multi-tenant isolation: Every inbound_message belongs to exactly one org.
    Deduplication: Emails with same Message-ID header for same org are rejected.

    SSOT Reference: §5.4.5 (inbound_message table)
    Constitution: §III (Multi-Tenant Isolation)
    """
    __tablename__ = "inbound_message"

    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )

    # Multi-tenant isolation (§5.1 - required for all tables)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("org.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Source tracking
    source = Column(
        Text,
        CheckConstraint("source IN ('EMAIL', 'UPLOAD')"),
        nullable=False
    )

    # Deduplication key (Message-ID for emails, correlation ID for uploads)
    source_message_id = Column(Text, nullable=True)

    # Email metadata (nullable for uploads)
    from_email = Column(CITEXT, nullable=True)
    to_email = Column(CITEXT, nullable=True)
    subject = Column(Text, nullable=True)

    # Timestamps
    received_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()")
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

    # Object storage reference (raw MIME for emails, original file for uploads)
    raw_storage_key = Column(Text, nullable=True)

    # Processing status
    status = Column(
        Text,
        nullable=False,
        server_default="'RECEIVED'"
    )

    # Error tracking (JSONB for structured error data)
    error_json = Column(
        PortableJSONB,
        nullable=True
    )

    # Table constraints
    __table_args__ = (
        # Deduplication constraint: prevent same Message-ID for same org
        # WHERE clause ensures NULL source_message_id values don't conflict
        Index(
            'idx_inbound_unique_source_message',
            'org_id', 'source', 'source_message_id',
            unique=True,
            postgresql_where=text("source_message_id IS NOT NULL")
        ),
        # Performance indexes
        Index('idx_inbound_org_received', 'org_id', 'received_at'),
        Index('idx_inbound_org_status', 'org_id', 'status'),
    )

    # Relationships
    org = relationship("Org", back_populates="inbound_messages")
    documents = relationship("Document", back_populates="inbound_message")

    @validates('status')
    def validate_status_transition(self, key, new_status):
        """
        Validate status state machine transitions.

        Ensures status changes follow allowed transition paths defined in
        ALLOWED_TRANSITIONS. This prevents invalid state changes like
        PARSED → RECEIVED or FAILED → STORED.

        Args:
            key: Column name (always 'status')
            new_status: New status value to transition to

        Returns:
            str: The validated new status

        Raises:
            ValueError: If transition is not allowed by state machine
        """
        # Get current status (None for new records)
        current_status = None
        if hasattr(self, '_sa_instance_state'):
            history = self._sa_instance_state.get_history('status', passive=True)
            if history.deleted:
                current_status_str = history.deleted[0]
                try:
                    current_status = InboundMessageStatus(current_status_str)
                except ValueError:
                    current_status = None

        # Convert string to enum if needed
        if isinstance(new_status, str):
            try:
                new_status = InboundMessageStatus(new_status)
            except ValueError:
                raise ValueError(f"Invalid status value: {new_status}")

        # Check if transition is allowed
        allowed = ALLOWED_TRANSITIONS.get(current_status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Invalid status transition: {current_status} → {new_status}. "
                f"Allowed transitions from {current_status}: {allowed}"
            )

        return new_status.value

    @validates('source')
    def validate_source(self, key, value):
        """Ensure source is valid enum value."""
        if isinstance(value, str):
            try:
                InboundMessageSource(value)
            except ValueError:
                raise ValueError(
                    f"Invalid source: {value}. Must be EMAIL or UPLOAD"
                )
        return value

    def __repr__(self):
        return (
            f"<InboundMessage(id={self.id}, org_id={self.org_id}, "
            f"source={self.source}, status={self.status}, "
            f"from={self.from_email})>"
        )
