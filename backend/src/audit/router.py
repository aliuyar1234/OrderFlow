"""Audit log query endpoints (ADMIN only).

All endpoints in this router are read-only. Audit logs are immutable and
cannot be created, updated, or deleted through the API.

ADMIN users can query audit logs for their organization with filtering by:
- Action type (LOGIN_SUCCESS, USER_CREATED, etc.)
- Entity type (user, draft_order, etc.)
- Date range (start_date, end_date)
- Pagination (page, per_page)
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from ..database import get_db
from ..models.audit_log import AuditLog
from ..auth.dependencies import require_role
from ..auth.roles import UserRole
from ..models.user import User
from .schemas import AuditLogResponse, AuditLogListResponse


router = APIRouter(prefix="/audit", tags=["Audit Logs"])


@router.get(
    "",
    response_model=AuditLogListResponse,
    summary="Query audit logs (ADMIN only)",
    description="Query audit logs with filtering and pagination. ADMIN users see only logs from their organization."
)
def query_audit_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    action: Optional[str] = Query(
        None,
        description="Filter by action type (e.g., LOGIN_SUCCESS, USER_CREATED)",
        example="USER_CREATED"
    ),
    entity_type: Optional[str] = Query(
        None,
        description="Filter by entity type (e.g., user, draft_order)",
        example="user"
    ),
    start_date: Optional[datetime] = Query(
        None,
        description="Filter by minimum created_at timestamp (ISO 8601)",
        example="2025-01-01T00:00:00Z"
    ),
    end_date: Optional[datetime] = Query(
        None,
        description="Filter by maximum created_at timestamp (ISO 8601)",
        example="2025-01-31T23:59:59Z"
    ),
    page: int = Query(
        1,
        ge=1,
        description="Page number (1-indexed)",
        example=1
    ),
    per_page: int = Query(
        50,
        ge=1,
        le=100,
        description="Entries per page (max 100)",
        example=50
    )
) -> AuditLogListResponse:
    """Query audit logs with filtering and pagination (T037, T038, T039, T043).

    Requirements:
    - ADMIN role required
    - Multi-tenant isolation (only org's logs visible)
    - Filters: action, entity_type, start_date, end_date
    - Pagination: page, per_page (default 50, max 100)
    - Results ordered by created_at DESC (newest first)

    Args:
        db: Database session
        current_user: Current authenticated user (must be ADMIN)
        action: Optional action filter (e.g., "USER_CREATED")
        entity_type: Optional entity type filter (e.g., "user")
        start_date: Optional minimum timestamp filter
        end_date: Optional maximum timestamp filter
        page: Page number (1-indexed)
        per_page: Entries per page (max 100)

    Returns:
        AuditLogListResponse: Filtered and paginated audit log entries

    Example:
        GET /audit?action=USER_CREATED&start_date=2025-01-01T00:00:00Z&page=1&per_page=50
    """
    # Build base query with multi-tenant isolation
    query = db.query(AuditLog).filter(
        AuditLog.org_id == current_user.org_id
    )

    # Apply action filter (T038)
    if action:
        query = query.filter(AuditLog.action == action)

    # Apply entity_type filter (T038)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)

    # Apply date range filters (T038)
    if start_date:
        query = query.filter(AuditLog.created_at >= start_date)

    if end_date:
        query = query.filter(AuditLog.created_at <= end_date)

    # Get total count before pagination
    total = query.count()

    # Apply pagination (T039)
    offset = (page - 1) * per_page
    entries = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(per_page).all()

    return AuditLogListResponse(
        entries=entries,
        total=total,
        page=page,
        per_page=per_page
    )
