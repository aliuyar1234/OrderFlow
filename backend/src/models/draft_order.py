"""Draft Order model for OrderFlow

Represents an order draft extracted from a document, containing header information
and a collection of line items. Draft orders move through a state machine from
extraction to approval to ERP push.

SSOT Reference: §5.4.8 (draft_order table schema), §5.2.5 (DraftOrderStatus)
"""

from datetime import datetime, timezone, date
from decimal import Decimal
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, String, Text, DateTime, Numeric, Enum as SQLEnum,
    ForeignKey, Date, Index
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship

from .base import Base


class DraftOrder(Base):
    """Draft Order header containing customer, dates, and extracted metadata.

    Lifecycle:
    1. Created by extraction pipeline (status=NEW)
    2. Populated with lines (status=EXTRACTED)
    3. Customer detected, matches suggested (status=NEEDS_REVIEW or READY)
    4. Ops reviews and edits
    5. Approved by Ops (status=APPROVED)
    6. Pushed to ERP (status=PUSHED)

    Multi-tenant isolation: All queries MUST filter by org_id.
    """

    __tablename__ = 'draft_order'

    # Primary key
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Multi-tenant isolation (REQUIRED on all queries)
    org_id = Column(PGUUID(as_uuid=True), ForeignKey('org.id'), nullable=False)

    # Relationships
    customer_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey('customer.id'),
        nullable=True,
        comment="Set after customer detection or manual selection"
    )
    inbound_message_id = Column(
        PGUUID(as_uuid=True),
        nullable=True,
        comment="Source email/upload event"
    )
    document_id = Column(
        PGUUID(as_uuid=True),
        nullable=False,
        comment="Source document (PDF/Excel/CSV)"
    )

    # Header fields (extracted or manually entered)
    external_order_number = Column(
        Text,
        nullable=True,
        comment="Customer's order number/reference"
    )
    order_date = Column(Date, nullable=True)
    currency = Column(String(3), nullable=True, comment="ISO 4217 (EUR, CHF, USD)")
    requested_delivery_date = Column(Date, nullable=True)

    # Address data (JSONB for flexibility)
    ship_to_json = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Shipping address {street, city, postal_code, country}"
    )
    bill_to_json = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Billing address {street, city, postal_code, country}"
    )

    # Notes and metadata
    notes = Column(Text, nullable=True)

    # State machine
    status = Column(
        SQLEnum(
            'NEW',
            'EXTRACTED',
            'NEEDS_REVIEW',
            'READY',
            'APPROVED',
            'PUSHING',
            'PUSHED',
            'ERROR',
            name='draft_order_status'
        ),
        nullable=False,
        default='NEW',
        comment="State machine: NEW → EXTRACTED → NEEDS_REVIEW|READY → APPROVED → PUSHING → PUSHED|ERROR"
    )

    # Confidence scores (0.000 to 1.000)
    confidence_score = Column(
        Numeric(4, 3),
        nullable=False,
        default=Decimal('0.000'),
        comment="Overall confidence (weighted avg of extraction, customer, matching)"
    )
    extraction_confidence = Column(
        Numeric(4, 3),
        nullable=False,
        default=Decimal('0.000'),
        comment="Quality of data extraction from document"
    )
    customer_confidence = Column(
        Numeric(4, 3),
        nullable=False,
        default=Decimal('0.000'),
        comment="Confidence in customer detection"
    )
    matching_confidence = Column(
        Numeric(4, 3),
        nullable=False,
        default=Decimal('0.000'),
        comment="Average confidence of SKU matches across lines"
    )

    # Ready check and customer detection results (cached for UI)
    ready_check_json = Column(
        JSONB,
        nullable=False,
        default={},
        comment="Ready-check result: {ready: bool, blocking_reasons: [...], warnings: [...]}"
    )
    customer_candidates_json = Column(
        JSONB,
        nullable=False,
        default=[],
        comment="Customer detection candidates (UI quick display; canonical source is customer_detection_candidate table)"
    )

    # Approval tracking
    approved_by_user_id = Column(
        PGUUID(as_uuid=True),
        nullable=True,
        comment="User who approved the draft"
    )
    approved_at = Column(DateTime(timezone=True), nullable=True)

    # ERP integration
    erp_order_id = Column(
        Text,
        nullable=True,
        comment="Order ID assigned by ERP after push"
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Indexes (see __table_args__)
    __table_args__ = (
        Index('ix_draft_order_org_status', 'org_id', 'status'),
        Index('ix_draft_order_org_created', 'org_id', 'created_at'),
        Index('ix_draft_order_org_customer', 'org_id', 'customer_id'),
    )

    # SQLAlchemy relationships (for eager loading)
    lines = relationship(
        "DraftOrderLine",
        back_populates="draft_order",
        cascade="all, delete-orphan",
        order_by="DraftOrderLine.line_no"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary for API responses.

        Returns:
            Dict with all fields, converting UUIDs/datetimes to strings
        """
        return {
            'id': str(self.id),
            'org_id': str(self.org_id),
            'customer_id': str(self.customer_id) if self.customer_id else None,
            'inbound_message_id': str(self.inbound_message_id) if self.inbound_message_id else None,
            'document_id': str(self.document_id),
            'external_order_number': self.external_order_number,
            'order_date': self.order_date.isoformat() if self.order_date else None,
            'currency': self.currency,
            'requested_delivery_date': self.requested_delivery_date.isoformat() if self.requested_delivery_date else None,
            'ship_to_json': self.ship_to_json,
            'bill_to_json': self.bill_to_json,
            'notes': self.notes,
            'status': self.status,
            'confidence_score': float(self.confidence_score) if self.confidence_score else 0.0,
            'extraction_confidence': float(self.extraction_confidence) if self.extraction_confidence else 0.0,
            'customer_confidence': float(self.customer_confidence) if self.customer_confidence else 0.0,
            'matching_confidence': float(self.matching_confidence) if self.matching_confidence else 0.0,
            'ready_check_json': self.ready_check_json,
            'customer_candidates_json': self.customer_candidates_json,
            'approved_by_user_id': str(self.approved_by_user_id) if self.approved_by_user_id else None,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'erp_order_id': self.erp_order_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class DraftOrderLine(Base):
    """Draft Order line item representing a single product/SKU order line.

    Each line contains:
    - Extracted data: customer_sku_raw, qty, uom, unit_price, description
    - Matching result: internal_sku, match_status, match_confidence, match_method
    - Metadata: match_debug_json for troubleshooting

    Multi-tenant isolation: All queries MUST filter by org_id.
    """

    __tablename__ = 'draft_order_line'

    # Primary key
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Multi-tenant isolation
    org_id = Column(PGUUID(as_uuid=True), ForeignKey('org.id'), nullable=False)

    # Parent relationship
    draft_order_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey('draft_order.id', ondelete='CASCADE'),
        nullable=False
    )

    # Line number (1-indexed, unique within draft)
    line_no = Column(
        Column.Integer,
        nullable=False,
        comment="Line number (1-indexed), unique per draft_order"
    )

    # Extracted fields from document
    customer_sku_raw = Column(
        Text,
        nullable=True,
        comment="Raw customer SKU as extracted (before normalization)"
    )
    customer_sku_norm = Column(
        Text,
        nullable=True,
        comment="Normalized customer SKU for matching (uppercase, no spaces/dashes)"
    )
    product_description = Column(
        Text,
        nullable=True,
        comment="Product description from document"
    )
    qty = Column(
        Numeric(18, 3),
        nullable=True,
        comment="Quantity ordered"
    )
    uom = Column(
        String(10),
        nullable=True,
        comment="Unit of measure (ST, M, KG, KAR, PAL, etc.)"
    )
    unit_price = Column(
        Numeric(18, 4),
        nullable=True,
        comment="Unit price in currency"
    )
    currency = Column(
        String(3),
        nullable=True,
        comment="Currency for this line (usually same as header)"
    )

    # Matching results
    internal_sku = Column(
        Text,
        nullable=True,
        comment="Matched internal SKU (from product catalog)"
    )
    match_status = Column(
        SQLEnum(
            'UNMATCHED',
            'SUGGESTED',
            'MATCHED',
            'OVERRIDDEN',
            name='match_status_enum'
        ),
        nullable=False,
        default='UNMATCHED',
        comment="Match status: UNMATCHED|SUGGESTED|MATCHED|OVERRIDDEN"
    )
    match_confidence = Column(
        Numeric(4, 3),
        nullable=False,
        default=Decimal('0.000'),
        comment="Confidence in match (0.000 to 1.000)"
    )
    match_method = Column(
        Text,
        nullable=True,
        comment="Match method: exact_mapping|trigram|embedding|hybrid|manual"
    )
    match_debug_json = Column(
        JSONB,
        nullable=False,
        default={},
        comment="Debug info: scores, features, candidate list"
    )

    # Line-specific metadata
    requested_delivery_date = Column(
        Date,
        nullable=True,
        comment="Line-specific delivery date (overrides header)"
    )
    line_notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Indexes
    __table_args__ = (
        Index('ix_draft_order_line_org_draft', 'org_id', 'draft_order_id'),
        Index('ix_draft_order_line_org_internal_sku', 'org_id', 'internal_sku'),
        Index('ix_draft_order_line_org_customer_sku', 'org_id', 'customer_sku_norm'),
        # Unique constraint: only one line with a given line_no per draft
        Index('uq_draft_order_line_no', 'draft_order_id', 'line_no', unique=True),
    )

    # SQLAlchemy relationship
    draft_order = relationship("DraftOrder", back_populates="lines")

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary for API responses.

        Returns:
            Dict with all fields, converting UUIDs/datetimes to strings
        """
        return {
            'id': str(self.id),
            'org_id': str(self.org_id),
            'draft_order_id': str(self.draft_order_id),
            'line_no': self.line_no,
            'customer_sku_raw': self.customer_sku_raw,
            'customer_sku_norm': self.customer_sku_norm,
            'product_description': self.product_description,
            'qty': float(self.qty) if self.qty else None,
            'uom': self.uom,
            'unit_price': float(self.unit_price) if self.unit_price else None,
            'currency': self.currency,
            'internal_sku': self.internal_sku,
            'match_status': self.match_status,
            'match_confidence': float(self.match_confidence) if self.match_confidence else 0.0,
            'match_method': self.match_method,
            'match_debug_json': self.match_debug_json,
            'requested_delivery_date': self.requested_delivery_date.isoformat() if self.requested_delivery_date else None,
            'line_notes': self.line_notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
