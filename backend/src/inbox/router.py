"""Inbox API endpoints for OrderFlow

Provides endpoints for viewing and triaging inbound messages (emails and uploads).
Supports filtering, search, and pagination per SSOT §8.5.
"""

from typing import Annotated, Optional
from datetime import datetime
from uuid import UUID
import base64
import json

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc

from database import get_db
from models.inbound_message import InboundMessage
from models.document import Document
from auth.dependencies import CurrentUser
from .schemas import (
    InboxListResponse,
    InboxItemResponse,
    InboxDetailResponse,
    DocumentMetadata
)


router = APIRouter(prefix="/inbox", tags=["Inbox"])


def _encode_cursor(message_id: UUID, received_at: datetime) -> str:
    """Encode pagination cursor (opaque base64 string)

    Cursor contains: {message_id, received_at} for keyset pagination.
    This allows efficient pagination on large datasets.
    """
    cursor_data = {
        "id": str(message_id),
        "received_at": received_at.isoformat()
    }
    json_str = json.dumps(cursor_data)
    return base64.b64encode(json_str.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[UUID, datetime]:
    """Decode pagination cursor

    Returns: (message_id, received_at) tuple
    Raises: HTTPException if cursor is invalid
    """
    try:
        json_str = base64.b64decode(cursor.encode()).decode()
        cursor_data = json.loads(json_str)
        message_id = UUID(cursor_data["id"])
        received_at = datetime.fromisoformat(cursor_data["received_at"])
        return message_id, received_at
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid cursor format"
        )


@router.get("", response_model=InboxListResponse)
async def list_inbox(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (RECEIVED, STORED, PARSED, FAILED)"),
    from_email: Optional[str] = Query(None, description="Filter by sender email (exact match)"),
    date_from: Optional[str] = Query(None, description="Filter by received date from (ISO format YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter by received date to (ISO format YYYY-MM-DD)"),
    q: Optional[str] = Query(None, description="Search in subject or sender email"),
    limit: int = Query(50, ge=1, le=100, description="Page size (default 50, max 100)"),
    cursor: Optional[str] = Query(None, description="Pagination cursor (opaque string)")
):
    """List inbound messages with filters and pagination.

    Returns paginated list of inbox messages with filters for:
    - Status (RECEIVED, STORED, PARSED, FAILED)
    - Sender email (exact match)
    - Date range (received_at)
    - Search query (subject or sender)

    Uses cursor-based pagination for efficient large dataset traversal.
    Multi-tenant isolation enforced via org_id from JWT.

    Args:
        current_user: Current authenticated user from JWT
        db: Database session
        status_filter: Optional status filter
        from_email: Optional sender email filter
        date_from: Optional start date filter
        date_to: Optional end date filter
        q: Optional search query
        limit: Page size (default 50, max 100)
        cursor: Pagination cursor from previous response

    Returns:
        InboxListResponse: Paginated list of messages
    """
    # Build base query with org_id isolation
    query = db.query(InboundMessage).filter(
        InboundMessage.org_id == current_user.org_id
    )

    # Apply filters
    if status_filter:
        query = query.filter(InboundMessage.status == status_filter)

    if from_email:
        query = query.filter(InboundMessage.from_email == from_email.lower())

    if date_from:
        try:
            date_from_dt = datetime.fromisoformat(date_from)
            query = query.filter(InboundMessage.received_at >= date_from_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date_from format. Use ISO format (YYYY-MM-DD)"
            )

    if date_to:
        try:
            date_to_dt = datetime.fromisoformat(date_to)
            query = query.filter(InboundMessage.received_at <= date_to_dt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date_to format. Use ISO format (YYYY-MM-DD)"
            )

    if q:
        # Search in subject or from_email (case-insensitive)
        search_pattern = f"%{q}%"
        query = query.filter(
            or_(
                InboundMessage.subject.ilike(search_pattern),
                InboundMessage.from_email.ilike(search_pattern)
            )
        )

    # Apply cursor-based pagination
    if cursor:
        cursor_id, cursor_received_at = _decode_cursor(cursor)
        # Keyset pagination: (received_at, id) for deterministic ordering
        query = query.filter(
            or_(
                InboundMessage.received_at < cursor_received_at,
                and_(
                    InboundMessage.received_at == cursor_received_at,
                    InboundMessage.id < cursor_id
                )
            )
        )

    # Order by received_at DESC, id DESC (newest first)
    query = query.order_by(desc(InboundMessage.received_at), desc(InboundMessage.id))

    # Fetch limit + 1 to check if more pages exist
    messages = query.limit(limit + 1).all()

    has_more = len(messages) > limit
    if has_more:
        messages = messages[:limit]

    # Build response items with attachment counts
    items = []
    for message in messages:
        # Count attachments (documents)
        attachment_count = db.query(func.count(Document.id)).filter(
            Document.inbound_message_id == message.id
        ).scalar() or 0

        # TODO: Get draft_order_ids when draft_order module is implemented
        draft_order_ids = []

        items.append(InboxItemResponse(
            id=message.id,
            source=message.source,
            from_email=message.from_email,
            to_email=message.to_email,
            subject=message.subject,
            received_at=message.received_at,
            status=message.status.value if hasattr(message.status, 'value') else message.status,
            attachment_count=attachment_count,
            draft_order_ids=draft_order_ids,
            created_at=message.created_at
        ))

    # Generate next cursor if more pages exist
    next_cursor = None
    if has_more and messages:
        last_message = messages[-1]
        next_cursor = _encode_cursor(last_message.id, last_message.received_at)

    return InboxListResponse(
        items=items,
        next_cursor=next_cursor,
        has_more=has_more
    )


@router.get("/{message_id}", response_model=InboxDetailResponse)
async def get_inbox_message(
    message_id: UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)]
):
    """Get inbox message detail with attachments and draft orders.

    Returns full message details including:
    - All message metadata (from, to, subject, received_at, etc.)
    - List of attachments with download/preview URLs
    - List of associated draft orders (if any)

    Enforces multi-tenant isolation (returns 404 if message belongs to different org).

    Args:
        message_id: UUID of the inbound message
        current_user: Current authenticated user from JWT
        db: Database session

    Returns:
        InboxDetailResponse: Full message details

    Raises:
        HTTPException: 404 if message not found or belongs to different org
    """
    # Fetch message with org_id isolation (404 for cross-tenant access)
    message = db.query(InboundMessage).filter(
        and_(
            InboundMessage.id == message_id,
            InboundMessage.org_id == current_user.org_id
        )
    ).first()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )

    # Fetch attachments (documents)
    documents = db.query(Document).filter(
        Document.inbound_message_id == message_id
    ).all()

    attachments = []
    for doc in documents:
        preview_url = None
        if doc.preview_storage_key:
            preview_url = f"/api/v1/documents/{doc.id}/preview"

        attachments.append(DocumentMetadata(
            document_id=doc.id,
            file_name=doc.file_name,
            mime_type=doc.mime_type,
            size_bytes=doc.size_bytes,
            status=doc.status.value if hasattr(doc.status, 'value') else doc.status,
            page_count=doc.page_count,
            preview_url=preview_url,
            download_url=f"/api/v1/documents/{doc.id}/download"
        ))

    # TODO: Fetch draft_orders when draft_order module is implemented
    draft_orders = []

    return InboxDetailResponse(
        id=message.id,
        source=message.source,
        from_email=message.from_email,
        to_email=message.to_email,
        subject=message.subject,
        received_at=message.received_at,
        status=message.status.value if hasattr(message.status, 'value') else message.status,
        source_message_id=message.source_message_id,
        attachments=attachments,
        draft_orders=draft_orders,
        created_at=message.created_at,
        updated_at=message.updated_at
    )
