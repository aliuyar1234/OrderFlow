"""Learning analytics API endpoints

Provides endpoints for viewing feedback events and learning metrics.
Restricted to ADMIN and INTEGRATOR roles per SSOT §FR-020.
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models.user import User
from auth.roles import Role, require_role
from .services import LearningService


# Response schemas
class EventByDayResponse(BaseModel):
    """Feedback events aggregated by day"""
    date: str
    count: int


class CorrectedFieldResponse(BaseModel):
    """Top corrected fields"""
    field: str
    count: int


class EventTypeResponse(BaseModel):
    """Event type distribution"""
    event_type: str
    count: int


class LayoutStatsResponse(BaseModel):
    """Layout coverage statistics"""
    fingerprint: str
    seen_count: int
    feedback_count: int
    last_seen_at: str


class LearningAnalyticsResponse(BaseModel):
    """Complete learning analytics response"""
    events_by_day: list[EventByDayResponse]
    corrected_fields: list[CorrectedFieldResponse]
    event_type_distribution: list[EventTypeResponse]
    layout_stats: list[LayoutStatsResponse]
    date_range: dict


# Router
router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/learning", response_model=LearningAnalyticsResponse)
@require_role([Role.ADMIN, Role.INTEGRATOR])
def get_learning_analytics(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get learning analytics for the organization.

    Returns aggregated feedback metrics including:
    - Feedback events over time
    - Top corrected fields
    - Event type distribution
    - Layout coverage statistics

    Restricted to ADMIN and INTEGRATOR roles.

    Args:
        start_date: Optional start date (defaults to 30 days ago)
        end_date: Optional end date (defaults to today)
        current_user: Current authenticated user
        db: Database session

    Returns:
        Learning analytics data
    """
    # Parse dates or use defaults
    if end_date:
        end = datetime.fromisoformat(end_date)
    else:
        end = datetime.utcnow()

    if start_date:
        start = datetime.fromisoformat(start_date)
    else:
        start = end - timedelta(days=30)

    # Get analytics from service
    analytics = LearningService.get_learning_analytics(
        db=db,
        org_id=current_user.org_id,
        start_date=start,
        end_date=end
    )

    # Add date range to response
    analytics["date_range"] = {
        "start_date": start.date().isoformat(),
        "end_date": end.date().isoformat()
    }

    return analytics


@router.get("/learning/layouts/{layout_fingerprint}")
@require_role([Role.ADMIN, Role.INTEGRATOR])
def get_layout_feedback(
    layout_fingerprint: str,
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get feedback events for a specific layout fingerprint.

    Returns recent corrections made to documents with this layout,
    useful for understanding layout-specific quality issues.

    Args:
        layout_fingerprint: Layout fingerprint to query
        limit: Number of events to return (default 10, max 100)
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of feedback events for the layout
    """
    from .models import FeedbackEvent
    from sqlalchemy import desc

    events = db.query(FeedbackEvent).filter(
        FeedbackEvent.org_id == current_user.org_id,
        FeedbackEvent.layout_fingerprint == layout_fingerprint
    ).order_by(desc(FeedbackEvent.created_at)).limit(limit).all()

    return {
        "layout_fingerprint": layout_fingerprint,
        "events": [event.to_dict() for event in events]
    }


@router.get("/learning/few-shot-examples/{layout_fingerprint}")
@require_role([Role.ADMIN, Role.INTEGRATOR])
def get_few_shot_examples(
    layout_fingerprint: str,
    limit: int = Query(3, ge=1, le=10),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get few-shot examples that would be injected for a layout.

    Shows the exact examples that the LLM would receive when processing
    a document with this layout fingerprint.

    Per SSOT §7.10.3, examples are limited to same org and ordered by
    recency (created_at DESC).

    Args:
        layout_fingerprint: Layout fingerprint to query
        limit: Number of examples to return (default 3, max 10)
        current_user: Current authenticated user
        db: Database session

    Returns:
        Few-shot examples in LLM prompt format
    """
    examples = LearningService.get_few_shot_examples(
        db=db,
        org_id=current_user.org_id,
        layout_fingerprint=layout_fingerprint,
        limit=limit
    )

    return {
        "layout_fingerprint": layout_fingerprint,
        "examples": examples,
        "count": len(examples)
    }
