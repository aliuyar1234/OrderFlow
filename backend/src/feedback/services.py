"""Feedback learning services for OrderFlow

This module provides services for:
- Capturing feedback events from user actions
- Layout fingerprinting for PDF documents
- Few-shot example selection for LLM prompts
"""

import hashlib
import json
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from .models import FeedbackEvent, DocLayoutProfile


class FeedbackService:
    """Service for capturing user feedback events.

    Captures operator corrections and confirmations for:
    - Mapping confirms/rejects
    - Customer selection
    - Line edits (qty, price, SKU corrections)
    - Extraction field corrections
    """

    @staticmethod
    def capture_mapping_confirmed(
        db: Session,
        org_id: UUID,
        actor_user_id: UUID,
        sku_mapping_data: Dict[str, Any],
        before_state: Dict[str, Any],
        after_state: Dict[str, Any],
        draft_order_id: Optional[UUID] = None,
        draft_order_line_id: Optional[UUID] = None
    ) -> FeedbackEvent:
        """Capture mapping confirmation feedback.

        Args:
            db: Database session
            org_id: Organization ID
            actor_user_id: User who confirmed the mapping
            sku_mapping_data: SKU mapping metadata
            before_state: State before confirmation
            after_state: State after confirmation
            draft_order_id: Optional draft order reference
            draft_order_line_id: Optional draft line reference

        Returns:
            Created FeedbackEvent
        """
        event = FeedbackEvent(
            org_id=org_id,
            actor_user_id=actor_user_id,
            event_type="MAPPING_CONFIRMED",
            draft_order_id=draft_order_id,
            draft_order_line_id=draft_order_line_id,
            before_json=before_state,
            after_json=after_state,
            meta_json=sku_mapping_data
        )

        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def capture_mapping_rejected(
        db: Session,
        org_id: UUID,
        actor_user_id: UUID,
        sku_mapping_data: Dict[str, Any],
        rejected_internal_sku: str,
        draft_order_id: Optional[UUID] = None,
        draft_order_line_id: Optional[UUID] = None
    ) -> FeedbackEvent:
        """Capture mapping rejection feedback.

        Args:
            db: Database session
            org_id: Organization ID
            actor_user_id: User who rejected the mapping
            sku_mapping_data: SKU mapping metadata
            rejected_internal_sku: The internal SKU that was rejected
            draft_order_id: Optional draft order reference
            draft_order_line_id: Optional draft line reference

        Returns:
            Created FeedbackEvent
        """
        event = FeedbackEvent(
            org_id=org_id,
            actor_user_id=actor_user_id,
            event_type="MAPPING_REJECTED",
            draft_order_id=draft_order_id,
            draft_order_line_id=draft_order_line_id,
            before_json={"rejected_sku": rejected_internal_sku},
            after_json={},
            meta_json=sku_mapping_data
        )

        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def capture_customer_selected(
        db: Session,
        org_id: UUID,
        actor_user_id: UUID,
        candidates: List[Dict[str, Any]],
        selected_customer_id: UUID,
        draft_order_id: UUID
    ) -> FeedbackEvent:
        """Capture customer selection feedback.

        Args:
            db: Database session
            org_id: Organization ID
            actor_user_id: User who selected the customer
            candidates: List of customer candidates that were presented
            selected_customer_id: The customer ID that was selected
            draft_order_id: Draft order reference

        Returns:
            Created FeedbackEvent
        """
        event = FeedbackEvent(
            org_id=org_id,
            actor_user_id=actor_user_id,
            event_type="CUSTOMER_SELECTED",
            draft_order_id=draft_order_id,
            before_json={"candidates": candidates},
            after_json={"selected_customer_id": str(selected_customer_id)},
            meta_json={}
        )

        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def capture_line_corrected(
        db: Session,
        org_id: UUID,
        actor_user_id: UUID,
        draft_order_id: UUID,
        draft_order_line_id: UUID,
        before_values: Dict[str, Any],
        after_values: Dict[str, Any],
        document_id: Optional[UUID] = None,
        layout_fingerprint: Optional[str] = None,
        input_snippet: Optional[str] = None
    ) -> FeedbackEvent:
        """Capture line edit correction feedback.

        Args:
            db: Database session
            org_id: Organization ID
            actor_user_id: User who corrected the line
            draft_order_id: Draft order reference
            draft_order_line_id: Draft line reference
            before_values: Values before correction
            after_values: Values after correction
            document_id: Optional document reference
            layout_fingerprint: Optional layout fingerprint for few-shot learning
            input_snippet: Optional input text snippet (first 1500 chars) for few-shot

        Returns:
            Created FeedbackEvent
        """
        meta_json = {}
        if input_snippet:
            # Truncate to 1500 chars per SSOT §7.10.3
            meta_json["input_snippet"] = input_snippet[:1500]

        event = FeedbackEvent(
            org_id=org_id,
            actor_user_id=actor_user_id,
            event_type="EXTRACTION_LINE_CORRECTED",
            document_id=document_id,
            draft_order_id=draft_order_id,
            draft_order_line_id=draft_order_line_id,
            layout_fingerprint=layout_fingerprint,
            before_json=before_values,
            after_json=after_values,
            meta_json=meta_json
        )

        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def capture_field_corrected(
        db: Session,
        org_id: UUID,
        actor_user_id: UUID,
        field_name: str,
        old_value: Any,
        new_value: Any,
        draft_order_id: UUID,
        document_id: Optional[UUID] = None,
        layout_fingerprint: Optional[str] = None,
        input_snippet: Optional[str] = None
    ) -> FeedbackEvent:
        """Capture field correction feedback.

        Args:
            db: Database session
            org_id: Organization ID
            actor_user_id: User who corrected the field
            field_name: Name of the field that was corrected
            old_value: Value before correction
            new_value: Value after correction
            draft_order_id: Draft order reference
            document_id: Optional document reference
            layout_fingerprint: Optional layout fingerprint for few-shot learning
            input_snippet: Optional input text snippet (first 1500 chars) for few-shot

        Returns:
            Created FeedbackEvent
        """
        meta_json = {"field_name": field_name}
        if input_snippet:
            # Truncate to 1500 chars per SSOT §7.10.3
            meta_json["input_snippet"] = input_snippet[:1500]

        event = FeedbackEvent(
            org_id=org_id,
            actor_user_id=actor_user_id,
            event_type="EXTRACTION_FIELD_CORRECTED",
            document_id=document_id,
            draft_order_id=draft_order_id,
            layout_fingerprint=layout_fingerprint,
            before_json={"value": old_value},
            after_json={"value": new_value},
            meta_json=meta_json
        )

        db.add(event)
        db.commit()
        db.refresh(event)
        return event


class LayoutService:
    """Service for PDF layout fingerprinting.

    Generates SHA256 fingerprints from PDF structure to group similar documents
    for targeted few-shot learning.
    """

    @staticmethod
    def generate_fingerprint(document_metadata: Dict[str, Any]) -> str:
        """Generate SHA256 layout fingerprint from PDF metadata.

        Per SSOT §7.10.3, fingerprint is based on:
        - page_count
        - page_dimensions
        - table_count
        - text_coverage_ratio

        Args:
            document_metadata: Dict containing PDF layout metadata

        Returns:
            SHA256 hash as hex string
        """
        fingerprint_data = {
            "page_count": document_metadata.get("page_count"),
            "page_dimensions": document_metadata.get("page_dimensions", []),
            "table_count": document_metadata.get("table_count"),
            "text_coverage_ratio": round(document_metadata.get("text_coverage_ratio", 0), 2)
        }

        # Normalize to JSON string for consistent hashing
        canonical_json = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

    @staticmethod
    def create_or_update_profile(
        db: Session,
        org_id: UUID,
        document_id: UUID,
        layout_fingerprint: str,
        fingerprint_method: str,
        anchors: Dict[str, Any]
    ) -> DocLayoutProfile:
        """Create or update a layout profile.

        If a profile with the same fingerprint exists, increment seen_count.
        Otherwise, create a new profile.

        Args:
            db: Database session
            org_id: Organization ID
            document_id: Document ID
            layout_fingerprint: SHA256 fingerprint
            fingerprint_method: Method used (PDF_TEXT_SHA256 or PDF_IMAGE_PHASH)
            anchors: Anchor metadata (keywords, page_count, text_chars, etc.)

        Returns:
            Created or updated DocLayoutProfile
        """
        # Try to find existing profile
        existing = db.query(DocLayoutProfile).filter(
            DocLayoutProfile.org_id == org_id,
            DocLayoutProfile.layout_fingerprint == layout_fingerprint
        ).first()

        if existing:
            # Update existing profile
            existing.seen_count += 1
            existing.last_seen_at = datetime.utcnow()
            existing.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            return existing
        else:
            # Create new profile
            profile = DocLayoutProfile(
                org_id=org_id,
                document_id=document_id,
                layout_fingerprint=layout_fingerprint,
                fingerprint_method=fingerprint_method,
                anchors_json=anchors,
                seen_count=1,
                last_seen_at=datetime.utcnow()
            )
            db.add(profile)
            db.commit()
            db.refresh(profile)
            return profile


class LearningService:
    """Service for few-shot learning and analytics.

    Provides methods for selecting few-shot examples and aggregating
    learning analytics.
    """

    @staticmethod
    def get_few_shot_examples(
        db: Session,
        org_id: UUID,
        layout_fingerprint: str,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """Get few-shot examples for a layout fingerprint.

        Per SSOT §7.10.3, returns the last N feedback examples for the same
        layout, filtered by org_id for tenant isolation.

        Args:
            db: Database session
            org_id: Organization ID (for tenant isolation)
            layout_fingerprint: Layout fingerprint to match
            limit: Number of examples to return (default 3)

        Returns:
            List of examples in format:
            [{"input_snippet": "...", "output": {...}}, ...]
        """
        # Query feedback events for this layout
        feedback_events = db.query(FeedbackEvent).filter(
            FeedbackEvent.org_id == org_id,
            FeedbackEvent.layout_fingerprint == layout_fingerprint,
            FeedbackEvent.event_type.in_([
                "EXTRACTION_LINE_CORRECTED",
                "EXTRACTION_FIELD_CORRECTED"
            ])
        ).order_by(desc(FeedbackEvent.created_at)).limit(limit).all()

        examples = []
        for event in feedback_events:
            # Extract input snippet from meta_json
            input_snippet = event.meta_json.get("input_snippet", "")[:1500]

            examples.append({
                "input_snippet": input_snippet,
                "output": event.after_json  # Corrected extraction result
            })

        return examples

    @staticmethod
    def get_learning_analytics(
        db: Session,
        org_id: UUID,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get learning analytics for an organization.

        Returns aggregated metrics for feedback events, layout coverage,
        and correction patterns.

        Args:
            db: Database session
            org_id: Organization ID
            start_date: Start of date range
            end_date: End of date range

        Returns:
            Dict containing analytics data
        """
        # Feedback events by day
        events_by_day = db.query(
            func.date(FeedbackEvent.created_at).label("date"),
            func.count(FeedbackEvent.id).label("count")
        ).filter(
            FeedbackEvent.org_id == org_id,
            FeedbackEvent.created_at >= start_date,
            FeedbackEvent.created_at <= end_date
        ).group_by(func.date(FeedbackEvent.created_at)).all()

        # Top corrected fields (from EXTRACTION_FIELD_CORRECTED events)
        corrected_fields = db.query(
            FeedbackEvent.meta_json['field_name'].astext.label("field"),
            func.count().label("count")
        ).filter(
            FeedbackEvent.org_id == org_id,
            FeedbackEvent.event_type == "EXTRACTION_FIELD_CORRECTED",
            FeedbackEvent.created_at >= start_date,
            FeedbackEvent.created_at <= end_date
        ).group_by(FeedbackEvent.meta_json['field_name'].astext).order_by(
            desc(func.count())
        ).limit(10).all()

        # Event type distribution
        event_type_distribution = db.query(
            FeedbackEvent.event_type,
            func.count().label("count")
        ).filter(
            FeedbackEvent.org_id == org_id,
            FeedbackEvent.created_at >= start_date,
            FeedbackEvent.created_at <= end_date
        ).group_by(FeedbackEvent.event_type).all()

        # Layout coverage
        layout_stats = db.query(
            DocLayoutProfile.layout_fingerprint,
            DocLayoutProfile.seen_count,
            DocLayoutProfile.last_seen_at
        ).filter(
            DocLayoutProfile.org_id == org_id
        ).order_by(desc(DocLayoutProfile.seen_count)).all()

        # Count feedback events per layout
        layout_feedback_counts = {}
        for layout in layout_stats:
            feedback_count = db.query(func.count(FeedbackEvent.id)).filter(
                FeedbackEvent.org_id == org_id,
                FeedbackEvent.layout_fingerprint == layout.layout_fingerprint
            ).scalar()
            layout_feedback_counts[layout.layout_fingerprint] = feedback_count

        return {
            "events_by_day": [
                {"date": str(e.date), "count": e.count}
                for e in events_by_day
            ],
            "corrected_fields": [
                {"field": f.field, "count": f.count}
                for f in corrected_fields if f.field
            ],
            "event_type_distribution": [
                {"event_type": e.event_type, "count": e.count}
                for e in event_type_distribution
            ],
            "layout_stats": [
                {
                    "fingerprint": ls.layout_fingerprint[:8],  # Truncate for display
                    "seen_count": ls.seen_count,
                    "feedback_count": layout_feedback_counts.get(ls.layout_fingerprint, 0),
                    "last_seen_at": ls.last_seen_at.isoformat()
                }
                for ls in layout_stats
            ]
        }
