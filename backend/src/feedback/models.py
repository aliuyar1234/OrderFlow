"""Feedback and layout profile SQLAlchemy models"""

from sqlalchemy import Column, Text, ForeignKey, Integer, Index
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP, JSONB
from sqlalchemy.sql import text

from ..models.base import Base


class FeedbackEvent(Base):
    """FeedbackEvent captures user corrections and confirmations for learning.

    Stores before/after snapshots of operator actions (mapping confirms, line edits,
    customer selections) to support:
    - Few-shot learning for LLM extraction
    - Quality monitoring and analytics
    - Continuous improvement without model retraining

    Schema per SSOT §5.5.5
    """
    __tablename__ = "feedback_event"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    org_id = Column(UUID(as_uuid=True), ForeignKey("org.id", ondelete="RESTRICT"), nullable=False)
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="SET NULL"), nullable=True)

    # Event type - SSOT list: MAPPING_CONFIRMED, MAPPING_REJECTED,
    # EXTRACTION_FIELD_CORRECTED, EXTRACTION_LINE_CORRECTED,
    # CUSTOMER_SELECTED, ISSUE_OVERRIDDEN
    event_type = Column(Text, nullable=False)

    # Links to entities
    document_id = Column(UUID(as_uuid=True), ForeignKey("document.id", ondelete="SET NULL"), nullable=True)
    draft_order_id = Column(UUID(as_uuid=True), ForeignKey("draft_order.id", ondelete="SET NULL"), nullable=True)
    draft_order_line_id = Column(UUID(as_uuid=True), ForeignKey("draft_order_line.id", ondelete="SET NULL"), nullable=True)

    # Layout fingerprint for few-shot learning
    layout_fingerprint = Column(Text, nullable=True)

    # Before/after snapshots
    before_json = Column(JSONB, nullable=True)
    after_json = Column(JSONB, nullable=True)

    # Metadata (method, confidence, reason, input_snippet for few-shot)
    meta_json = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    def to_dict(self):
        """Convert feedback event to dictionary representation"""
        return {
            "id": str(self.id),
            "org_id": str(self.org_id),
            "actor_user_id": str(self.actor_user_id) if self.actor_user_id else None,
            "event_type": self.event_type,
            "document_id": str(self.document_id) if self.document_id else None,
            "draft_order_id": str(self.draft_order_id) if self.draft_order_id else None,
            "draft_order_line_id": str(self.draft_order_line_id) if self.draft_order_line_id else None,
            "layout_fingerprint": self.layout_fingerprint,
            "before_json": self.before_json,
            "after_json": self.after_json,
            "meta_json": self.meta_json,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


# Indexes per SSOT §5.5.5
Index("idx_feedback_event_org_created", FeedbackEvent.org_id, FeedbackEvent.created_at.desc())
Index("idx_feedback_event_org_type_created", FeedbackEvent.org_id, FeedbackEvent.event_type, FeedbackEvent.created_at.desc())
Index("idx_feedback_event_org_layout", FeedbackEvent.org_id, FeedbackEvent.layout_fingerprint)


class DocLayoutProfile(Base):
    """DocLayoutProfile tracks PDF layout fingerprints for few-shot learning.

    Each unique PDF layout (based on structure/dimensions) is tracked to enable:
    - Grouping similar documents for targeted learning
    - Few-shot example injection for same-layout PDFs
    - Analytics on layout coverage and quality

    Schema per SSOT §5.5.3
    """
    __tablename__ = "doc_layout_profile"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    org_id = Column(UUID(as_uuid=True), ForeignKey("org.id", ondelete="RESTRICT"), nullable=False)

    # SHA256 fingerprint of layout structure
    layout_fingerprint = Column(Text, nullable=False)

    # Reference document (first seen with this layout)
    document_id = Column(UUID(as_uuid=True), ForeignKey("document.id", ondelete="SET NULL"), nullable=False)

    # Fingerprinting method
    fingerprint_method = Column(Text, nullable=False)  # PDF_TEXT_SHA256 or PDF_IMAGE_PHASH

    # Anchor metadata (keywords, page_count, text_chars, etc.)
    anchors_json = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    # Usage tracking
    seen_count = Column(Integer, nullable=False, server_default=text("1"))
    last_seen_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    def to_dict(self):
        """Convert layout profile to dictionary representation"""
        return {
            "id": str(self.id),
            "org_id": str(self.org_id),
            "layout_fingerprint": self.layout_fingerprint,
            "document_id": str(self.document_id),
            "fingerprint_method": self.fingerprint_method,
            "anchors_json": self.anchors_json,
            "seen_count": self.seen_count,
            "last_seen_at": self.last_seen_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


# Indexes per SSOT §5.5.3
Index("idx_doc_layout_profile_unique", DocLayoutProfile.org_id, DocLayoutProfile.layout_fingerprint, unique=True)
Index("idx_doc_layout_profile_org_seen", DocLayoutProfile.org_id, DocLayoutProfile.last_seen_at.desc())
