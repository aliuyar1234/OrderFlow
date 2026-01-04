"""Pydantic schemas for Inbox API

Defines request/response models for inbox and document endpoints.
Enforces type safety and automatic validation per SSOT §8.5.
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


# Document Schemas

class DocumentMetadata(BaseModel):
    """Document metadata for attachment list in inbox detail"""
    model_config = ConfigDict(from_attributes=True)

    document_id: UUID = Field(..., description="Document UUID")
    file_name: str = Field(..., description="Original filename")
    mime_type: str = Field(..., description="MIME type (e.g., application/pdf)")
    size_bytes: int = Field(..., description="File size in bytes")
    status: str = Field(..., description="Document processing status")
    page_count: Optional[int] = Field(None, description="Number of pages (PDF only)")
    preview_url: Optional[str] = Field(None, description="Preview URL")
    download_url: str = Field(..., description="Download URL")


class DocumentResponse(BaseModel):
    """Full document metadata response"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    inbound_message_id: Optional[UUID] = None
    file_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    status: str
    page_count: Optional[int] = None
    text_coverage_ratio: Optional[float] = None
    error_json: Optional[dict] = None
    created_at: datetime
    updated_at: datetime


# Inbox List Schemas

class InboxItemResponse(BaseModel):
    """Inbox list item - summary view for message list"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: str = Field(..., description="EMAIL or UPLOAD")
    from_email: Optional[str] = None
    to_email: Optional[str] = None
    subject: Optional[str] = None
    received_at: datetime
    status: str = Field(..., description="InboundMessage status")
    attachment_count: int = Field(..., description="Number of documents attached")
    draft_order_ids: List[UUID] = Field(default_factory=list, description="Associated draft order UUIDs")
    created_at: datetime


class InboxListResponse(BaseModel):
    """Paginated inbox list response"""
    items: List[InboxItemResponse]
    next_cursor: Optional[str] = Field(None, description="Cursor for next page (opaque string)")
    has_more: bool = Field(..., description="Whether more pages exist")


# Inbox Detail Schemas

class DraftOrderSummary(BaseModel):
    """Draft order summary for inbox detail view"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    customer_name: Optional[str] = None
    line_count: int = Field(..., description="Number of order lines")
    created_at: datetime


class InboxDetailResponse(BaseModel):
    """Full inbox message detail with attachments and drafts"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: str
    from_email: Optional[str] = None
    to_email: Optional[str] = None
    subject: Optional[str] = None
    received_at: datetime
    status: str
    source_message_id: Optional[str] = None
    attachments: List[DocumentMetadata] = Field(default_factory=list)
    draft_orders: List[DraftOrderSummary] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
