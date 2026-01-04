"""Customer Detection API routes"""

import logging
from uuid import UUID
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_org_id
from domain.customer_detection.service import CustomerDetectionService
from domain.customer_detection.models import Candidate as DomainCandidate
from schemas.customer_detection import (
    DetectionRequestSchema,
    DetectionResultSchema,
    CandidateSchema,
    DetectionSignalSchema
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/customer-detection", tags=["customer-detection"])


def convert_candidate_to_schema(candidate: DomainCandidate) -> CandidateSchema:
    """Convert domain candidate to API schema"""
    return CandidateSchema(
        customer_id=candidate.customer_id,
        customer_name=candidate.customer_name,
        aggregate_score=candidate.aggregate_score,
        signals=[
            DetectionSignalSchema(
                signal_type=s.signal_type,
                value=s.value,
                score=s.score,
                metadata=s.metadata
            )
            for s in candidate.signals
        ],
        signal_badges=candidate.get_signal_badges()
    )


@router.post("/detect", response_model=DetectionResultSchema)
async def detect_customer(
    request: DetectionRequestSchema,
    db: Annotated[Session, Depends(get_db)],
    org_id: Annotated[UUID, Depends(get_org_id)]
):
    """Detect customer from inbound order data.

    Runs multi-signal customer detection algorithm to identify the most likely
    customer for an incoming order based on:
    - Email exact match (S1)
    - Email domain match (S2)
    - Document customer number (S4)
    - Fuzzy company name match (S5)
    - LLM hints (S6)

    Returns ranked candidates with confidence scores and auto-selection status.
    """
    try:
        # Initialize detection service
        service = CustomerDetectionService(db, org_id)

        # Run detection
        result = service.detect_customer(
            from_email=request.from_email,
            document_text=request.document_text,
            llm_hint=request.llm_hint,
            auto_select_threshold=request.auto_select_threshold,
            min_gap=request.min_gap
        )

        # Convert to schema
        return DetectionResultSchema(
            candidates=[convert_candidate_to_schema(c) for c in result.candidates],
            selected_customer_id=result.selected_customer_id,
            confidence=result.confidence,
            auto_selected=result.auto_selected,
            ambiguous=result.ambiguous,
            reason=result.reason
        )

    except Exception as e:
        logger.error(f"Customer detection failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Customer detection failed: {str(e)}"
        )
