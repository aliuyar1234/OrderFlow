"""
AICallLog model - Immutable log of all LLM/embedding API calls.

Tracks costs, latency, errors for budget control, debugging, and quality monitoring.

SSOT Reference: §5.5.1 (ai_call_log table)
"""

from sqlalchemy import Column, String, Text, Integer, ForeignKey, Enum as SQLEnum, text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from datetime import datetime
from enum import Enum as PyEnum

from .base import Base


class AICallStatus(str, PyEnum):
    """Status of AI call execution"""
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class AICallLog(Base):
    """
    AI Call Log - Immutable record of every LLM/embedding API call.

    Used for:
    - Cost tracking and budget enforcement
    - Performance monitoring (latency, token usage)
    - Error analysis and debugging
    - Deduplication (via input_hash)

    SSOT Reference: §5.5.1
    """
    __tablename__ = "ai_call_log"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("org.id", ondelete="CASCADE"),
        nullable=False
    )
    call_type = Column(
        Text,  # Store AICallType enum values as text
        nullable=False
    )
    provider = Column(Text, nullable=False)  # e.g., 'openai', 'anthropic', 'local'
    model = Column(Text, nullable=False)  # e.g., 'gpt-4o-mini', 'claude-3-sonnet'

    # Request tracking
    request_id = Column(Text, nullable=True)  # Provider's request ID if available
    input_hash = Column(Text, nullable=True)  # SHA256 hash of input for deduplication

    # Foreign keys (optional - not all calls relate to a document/draft)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document.id", ondelete="SET NULL"),
        nullable=True
    )
    draft_order_id = Column(
        UUID(as_uuid=True),
        nullable=True  # ForeignKey added later when draft_order table exists
    )

    # Usage metrics
    prompt_tokens = Column(Integer, nullable=True)  # Input tokens
    completion_tokens = Column(Integer, nullable=True)  # Output tokens
    total_tokens = Column(Integer, nullable=True)  # Sum (if provider reports separately)

    # Cost and performance
    cost_usd = Column(Integer, nullable=True)  # Cost in micro-USD (1/1,000,000 USD)
    latency_ms = Column(Integer, nullable=True)  # Latency in milliseconds

    # Status and error tracking
    status = Column(
        SQLEnum(AICallStatus, name="ai_call_status"),
        nullable=False,
        default=AICallStatus.SUCCEEDED
    )
    error_json = Column(JSONB, nullable=True)  # Error details if status=FAILED

    # Timestamps
    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()")
    )

    # Indexes for common queries
    __table_args__ = (
        # Budget tracking query: sum(cost_usd) WHERE org_id=X AND created_at >= today
        Index("ix_ai_call_log_org_created", "org_id", "created_at"),

        # Deduplication query: find by input_hash
        Index("ix_ai_call_log_input_hash", "input_hash"),

        # Document lookup
        Index("ix_ai_call_log_document", "document_id"),

        # Performance analytics by type
        Index("ix_ai_call_log_type_status", "call_type", "status"),
    )

    def __repr__(self):
        return (
            f"<AICallLog(id={self.id}, org_id={self.org_id}, "
            f"type={self.call_type}, provider={self.provider}, "
            f"status={self.status}, cost_usd={self.cost_usd})>"
        )
