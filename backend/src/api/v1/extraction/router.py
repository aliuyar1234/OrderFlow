"""Extraction API endpoints.

Provides REST API for querying extraction runs and triggering re-extraction.

SSOT Reference: §6 (API Endpoints), §7 (Extraction Logic)
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from auth.dependencies import get_current_user
from database import get_db
from models import ExtractionRun, ExtractionRunStatus, Document, User
from workers.extraction_worker import extract_document_task
from .schemas import (
    ExtractionRunResponse,
    ExtractionRunListResponse,
    TriggerExtractionRequest,
    TriggerExtractionResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/extractions", tags=["extractions"])


@router.get("", response_model=ExtractionRunListResponse)
def list_extractions(
    document_id: Optional[UUID] = None,
    status_filter: Optional[ExtractionRunStatus] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List extraction runs for current organization.

    Args:
        document_id: Filter by document ID (optional)
        status_filter: Filter by status (optional)
        limit: Maximum number of results (default 50, max 100)
        offset: Offset for pagination (default 0)
        db: Database session
        current_user: Authenticated user

    Returns:
        List of extraction runs with pagination metadata

    Example:
        GET /api/v1/extractions?document_id=<uuid>&status=SUCCEEDED&limit=10
    """
    # Validate limit
    if limit > 100:
        limit = 100

    # Build query with org_id filter
    query = db.query(ExtractionRun).filter(
        ExtractionRun.org_id == current_user.org_id
    )

    # Apply optional filters
    if document_id:
        query = query.filter(ExtractionRun.document_id == document_id)

    if status_filter:
        query = query.filter(ExtractionRun.status == status_filter)

    # Get total count before pagination
    total = query.count()

    # Order by created_at descending (most recent first)
    query = query.order_by(desc(ExtractionRun.created_at))

    # Apply pagination
    extractions = query.limit(limit).offset(offset).all()

    logger.info(
        f"Listed {len(extractions)} extraction runs "
        f"(total={total}, document_id={document_id}, status={status_filter})"
    )

    return ExtractionRunListResponse(
        items=[ExtractionRunResponse.from_orm(e) for e in extractions],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{extraction_run_id}", response_model=ExtractionRunResponse)
def get_extraction(
    extraction_run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get extraction run details by ID.

    Args:
        extraction_run_id: Extraction run UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        Extraction run details including output_json and metrics

    Raises:
        404: If extraction run not found or belongs to different org
    """
    extraction = db.query(ExtractionRun).filter(
        ExtractionRun.id == extraction_run_id,
        ExtractionRun.org_id == current_user.org_id  # Tenant isolation
    ).first()

    if not extraction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extraction run {extraction_run_id} not found"
        )

    logger.info(f"Retrieved extraction run {extraction_run_id}")

    return ExtractionRunResponse.from_orm(extraction)


@router.post("/trigger", response_model=TriggerExtractionResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_extraction(
    request: TriggerExtractionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger extraction for a document.

    Creates a background job to extract structured data from the document.
    Returns immediately with job ID (async processing).

    Args:
        request: Request with document_id
        db: Database session
        current_user: Authenticated user

    Returns:
        Response with task_id and status

    Raises:
        404: If document not found or belongs to different org
        409: If document is already being processed

    Example:
        POST /api/v1/extractions/trigger
        {
            "document_id": "123e4567-e89b-12d3-a456-426614174000"
        }
    """
    # Load document with org_id filter (tenant isolation)
    document = db.query(Document).filter(
        Document.id == request.document_id,
        Document.org_id == current_user.org_id
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {request.document_id} not found"
        )

    # Check if already processing
    if document.status == "PROCESSING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document is already being processed"
        )

    # Enqueue extraction task
    task = extract_document_task.delay(
        document_id=str(request.document_id),
        org_id=str(current_user.org_id)
    )

    logger.info(
        f"Triggered extraction for document {request.document_id} "
        f"(task_id={task.id}, org={current_user.org_id})"
    )

    return TriggerExtractionResponse(
        task_id=task.id,
        document_id=request.document_id,
        status="enqueued",
        message=f"Extraction task enqueued with ID {task.id}",
    )


@router.post("/{extraction_run_id}/retry", response_model=TriggerExtractionResponse, status_code=status.HTTP_202_ACCEPTED)
def retry_extraction(
    extraction_run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retry a failed extraction.

    Creates a new extraction task for the same document.

    Args:
        extraction_run_id: Failed extraction run UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        Response with new task_id and status

    Raises:
        404: If extraction run not found
        409: If extraction was successful (cannot retry successful extractions)

    Example:
        POST /api/v1/extractions/{extraction_run_id}/retry
    """
    # Load extraction run with org_id filter
    extraction = db.query(ExtractionRun).filter(
        ExtractionRun.id == extraction_run_id,
        ExtractionRun.org_id == current_user.org_id
    ).first()

    if not extraction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extraction run {extraction_run_id} not found"
        )

    # Cannot retry successful extractions
    if extraction.status == ExtractionRunStatus.SUCCEEDED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot retry successful extraction"
        )

    # Enqueue new extraction task for same document
    task = extract_document_task.delay(
        document_id=str(extraction.document_id),
        org_id=str(current_user.org_id)
    )

    logger.info(
        f"Retrying extraction for document {extraction.document_id} "
        f"(original_extraction={extraction_run_id}, new_task={task.id})"
    )

    return TriggerExtractionResponse(
        task_id=task.id,
        document_id=extraction.document_id,
        status="enqueued",
        message=f"Retry extraction task enqueued with ID {task.id}",
    )
