"""Extraction API schemas - Request/response models for extraction endpoints.

Pydantic models for type-safe API request/response handling.

SSOT Reference: §6 (API Endpoints)
"""

from datetime import datetime
from typing import List, Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field


class ExtractionRunResponse(BaseModel):
    """Response model for extraction run details.

    Attributes:
        id: Extraction run UUID
        document_id: Document UUID
        org_id: Organization UUID
        extractor_version: Extractor version used (e.g., 'excel_v1')
        status: Current status (PENDING, RUNNING, SUCCEEDED, FAILED)
        started_at: When extraction started (optional)
        finished_at: When extraction finished (optional)
        output_json: Canonical extraction output (optional)
        metrics_json: Extraction metrics (optional)
        error_json: Error details if failed (optional)
        created_at: When extraction run was created
        updated_at: When extraction run was last updated
    """

    id: UUID
    document_id: UUID
    org_id: UUID
    extractor_version: str
    status: str
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    output_json: Optional[Any]
    metrics_json: Optional[dict]
    error_json: Optional[dict]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class ExtractionRunListResponse(BaseModel):
    """Response model for list of extraction runs with pagination.

    Attributes:
        items: List of extraction runs
        total: Total number of matching runs (before pagination)
        limit: Number of items per page
        offset: Current offset
    """

    items: List[ExtractionRunResponse]
    total: int
    limit: int
    offset: int


class TriggerExtractionRequest(BaseModel):
    """Request model for triggering extraction.

    Attributes:
        document_id: UUID of document to extract
    """

    document_id: UUID = Field(
        ...,
        description="UUID of document to extract data from"
    )


class TriggerExtractionResponse(BaseModel):
    """Response model for triggered extraction.

    Attributes:
        task_id: Celery task ID for tracking
        document_id: Document UUID
        status: Task status ('enqueued')
        message: Human-readable message
    """

    task_id: str = Field(..., description="Celery task ID for async tracking")
    document_id: UUID = Field(..., description="Document UUID being processed")
    status: str = Field(..., description="Task status (enqueued)")
    message: str = Field(..., description="Human-readable status message")
