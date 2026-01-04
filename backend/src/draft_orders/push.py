"""Push service for ERP export.

Implements draft order push logic with idempotency support per SSOT §6.5.
Handles export creation, idempotency caching, and worker task enqueueing.

SSOT Reference: §6.5 (Push Rules), §8.6 (push endpoint)
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional
from uuid import UUID
import redis

from sqlalchemy.orm import Session
from fastapi import HTTPException

from ..models.draft_order import DraftOrder
from ..models.erp_export import ERPExport, ERPExportStatus
from ..models.erp_connection import ERPConnection
from .status import DraftOrderStatus, validate_transition, StateTransitionError
from ..audit.service import log_audit_event


# Redis client for idempotency cache (configure in production)
redis_client = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True,
    socket_connect_timeout=2
)


class PushError(Exception):
    """Raised when push validation fails."""
    pass


def get_idempotent_export(
    org_id: UUID,
    draft_id: UUID,
    idempotency_key: str
) -> UUID | None:
    """Retrieve export_id from idempotency cache.

    Args:
        org_id: Organization ID (for key scoping)
        draft_id: Draft order ID
        idempotency_key: Idempotency key from request header

    Returns:
        UUID | None: Export ID if found, None otherwise

    SSOT Reference: §6.5 (FR-008, FR-009)
    """
    cache_key = f"idempotency:{org_id}:{draft_id}:{idempotency_key}"
    try:
        export_id_str = redis_client.get(cache_key)
        return UUID(export_id_str) if export_id_str else None
    except (redis.RedisError, ValueError):
        # Redis unavailable or invalid UUID - proceed without idempotency
        return None


def set_idempotent_export(
    org_id: UUID,
    draft_id: UUID,
    idempotency_key: str,
    export_id: UUID,
    ttl_hours: int = 24
) -> None:
    """Store export_id in idempotency cache with TTL.

    Args:
        org_id: Organization ID (for key scoping)
        draft_id: Draft order ID
        idempotency_key: Idempotency key from request
        export_id: Export ID to cache
        ttl_hours: Time-to-live in hours (default 24)

    SSOT Reference: §6.5 (FR-008)
    """
    cache_key = f"idempotency:{org_id}:{draft_id}:{idempotency_key}"
    try:
        redis_client.setex(
            cache_key,
            ttl_hours * 3600,
            str(export_id)
        )
    except redis.RedisError:
        # Redis unavailable - log warning but continue
        # (idempotency will fall back to database checks)
        pass


def get_active_erp_connection(
    db: Session,
    org_id: UUID
) -> ERPConnection | None:
    """Get active ERP connection for organization.

    Args:
        db: Database session
        org_id: Organization ID

    Returns:
        ERPConnection | None: Active connection or None

    SSOT Reference: §6.5 (FR-012)
    """
    return db.query(ERPConnection).filter(
        ERPConnection.org_id == org_id,
        ERPConnection.active == True
    ).first()


def validate_ready_for_push(draft: DraftOrder) -> None:
    """Validate that a draft order is ready for push.

    Args:
        draft: Draft order to validate

    Raises:
        PushError: If draft is not ready for push

    SSOT Reference: §6.5 (FR-006)
    """
    # Check status is APPROVED
    if draft.status != DraftOrderStatus.APPROVED.value:
        raise PushError(
            f"Draft must be APPROVED to push (current: {draft.status})"
        )


def push_draft_order(
    db: Session,
    draft_id: UUID,
    org_id: UUID,
    user_id: UUID,
    idempotency_key: Optional[str] = None,
    ip_address: str | None = None,
    user_agent: str | None = None
) -> tuple[ERPExport, bool]:
    """Push a draft order to ERP.

    Creates ERPExport record and enqueues background export job.
    Supports idempotent retries via idempotency_key.

    Args:
        db: Database session
        draft_id: Draft order ID to push
        org_id: Organization ID (for multi-tenant isolation)
        user_id: User performing the push
        idempotency_key: Optional idempotency key for duplicate detection
        ip_address: Client IP address for audit log
        user_agent: Client User-Agent for audit log

    Returns:
        tuple[ERPExport, bool]: (Export record, is_duplicate)
            - is_duplicate=True if idempotency key matched existing export

    Raises:
        HTTPException: If draft not found, validation fails, or no connector

    SSOT Reference: §6.5 (FR-005 to FR-016), §8.6 (push endpoint)

    Example:
        export, is_duplicate = push_draft_order(
            db=db,
            draft_id=UUID("..."),
            org_id=UUID("..."),
            user_id=UUID("..."),
            idempotency_key="abc-123-def"
        )
        if is_duplicate:
            return {"status": "duplicate", "export_id": str(export.id)}
    """
    # Fetch draft with org_id filter (multi-tenant isolation)
    draft = db.query(DraftOrder).filter(
        DraftOrder.id == draft_id,
        DraftOrder.org_id == org_id
    ).first()

    if not draft:
        raise HTTPException(
            status_code=404,
            detail=f"Draft order {draft_id} not found"
        )

    # Check idempotency if key provided (SSOT §6.5 FR-007, FR-009)
    if idempotency_key:
        existing_export_id = get_idempotent_export(org_id, draft_id, idempotency_key)
        if existing_export_id:
            # Return existing export
            existing_export = db.query(ERPExport).filter(
                ERPExport.id == existing_export_id,
                ERPExport.org_id == org_id
            ).first()
            if existing_export:
                return (existing_export, True)

    # Fallback idempotency check: prevent duplicate exports
    # (SSOT §6.5 FR-009 - fallback when no idempotency key)
    if draft.status in [
        DraftOrderStatus.PUSHING.value,
        DraftOrderStatus.PUSHED.value
    ]:
        # Find latest export for this draft
        latest_export = db.query(ERPExport).filter(
            ERPExport.org_id == org_id,
            ERPExport.draft_order_id == draft_id
        ).order_by(ERPExport.created_at.desc()).first()

        if latest_export and latest_export.status in [
            ERPExportStatus.PENDING.value,
            ERPExportStatus.SENT.value
        ]:
            raise HTTPException(
                status_code=409,
                detail="Export already in progress or completed"
            )

    # Validate ready for push
    try:
        validate_ready_for_push(draft)
    except PushError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # Validate state transition (SSOT §6.5 FR-010)
    try:
        validate_transition(
            DraftOrderStatus(draft.status),
            DraftOrderStatus.PUSHING
        )
    except StateTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # Get active ERP connection (SSOT §6.5 FR-012)
    connector = get_active_erp_connection(db, org_id)
    if not connector:
        raise HTTPException(
            status_code=400,
            detail="No active ERP connector configured for this organization"
        )

    # Create ERPExport record (SSOT §6.5 FR-011)
    export = ERPExport(
        org_id=org_id,
        erp_connection_id=connector.id,
        draft_order_id=draft_id,
        export_format_version="orderflow_export_json_v1",
        export_storage_key="",  # Will be set by worker
        status=ERPExportStatus.PENDING.value
    )
    db.add(export)

    # Update draft status to PUSHING (SSOT §6.5 FR-010)
    draft.status = DraftOrderStatus.PUSHING.value

    # Flush to get export ID
    db.flush()

    # Store idempotency mapping (SSOT §6.5 FR-008)
    if idempotency_key:
        set_idempotent_export(org_id, draft_id, idempotency_key, export.id)

    # Create audit log entry (SSOT §6.5 FR-015)
    log_audit_event(
        db=db,
        org_id=org_id,
        action="DRAFT_PUSHED",
        actor_id=user_id,
        entity_type="draft_order",
        entity_id=draft_id,
        metadata={
            "draft_id": str(draft_id),
            "export_id": str(export.id),
            "erp_connection_id": str(connector.id),
            "connector_type": connector.connector_type
        },
        ip_address=ip_address,
        user_agent=user_agent
    )

    # Note: Background export job enqueueing will be handled by caller
    # (allows for different worker implementations - Celery, etc.)

    return (export, False)


def retry_push(
    db: Session,
    draft_id: UUID,
    org_id: UUID,
    user_id: UUID,
    ip_address: str | None = None,
    user_agent: str | None = None
) -> tuple[ERPExport, bool]:
    """Retry a failed push.

    Creates new ERPExport record and transitions draft from ERROR to PUSHING.

    Args:
        db: Database session
        draft_id: Draft order ID to retry
        org_id: Organization ID
        user_id: User performing retry
        ip_address: Client IP for audit log
        user_agent: Client User-Agent for audit log

    Returns:
        tuple[ERPExport, bool]: (New export record, False)

    Raises:
        HTTPException: If draft not found or not in ERROR status

    SSOT Reference: §6.5 (FR-017, FR-018, FR-019)

    Example:
        export, _ = retry_push(
            db=db,
            draft_id=UUID("..."),
            org_id=UUID("..."),
            user_id=UUID("...")
        )
    """
    # Fetch draft
    draft = db.query(DraftOrder).filter(
        DraftOrder.id == draft_id,
        DraftOrder.org_id == org_id
    ).first()

    if not draft:
        raise HTTPException(
            status_code=404,
            detail=f"Draft order {draft_id} not found"
        )

    # Validate draft is in ERROR status
    if draft.status != DraftOrderStatus.ERROR.value:
        if draft.status == DraftOrderStatus.PUSHED.value:
            raise HTTPException(
                status_code=409,
                detail="Export already succeeded"
            )
        else:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot retry - draft status is {draft.status}"
            )

    # Validate state transition (ERROR -> PUSHING)
    try:
        validate_transition(
            DraftOrderStatus.ERROR,
            DraftOrderStatus.PUSHING
        )
    except StateTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # Get active ERP connection
    connector = get_active_erp_connection(db, org_id)
    if not connector:
        raise HTTPException(
            status_code=400,
            detail="No active ERP connector configured"
        )

    # Create NEW export record (SSOT §6.5 FR-019 - retries create new records)
    export = ERPExport(
        org_id=org_id,
        erp_connection_id=connector.id,
        draft_order_id=draft_id,
        export_format_version="orderflow_export_json_v1",
        export_storage_key="",  # Will be set by worker
        status=ERPExportStatus.PENDING.value
    )
    db.add(export)

    # Update draft status to PUSHING
    draft.status = DraftOrderStatus.PUSHING.value

    db.flush()

    # Audit log
    log_audit_event(
        db=db,
        org_id=org_id,
        action="DRAFT_PUSH_RETRIED",
        actor_id=user_id,
        entity_type="draft_order",
        entity_id=draft_id,
        metadata={
            "draft_id": str(draft_id),
            "export_id": str(export.id),
            "retry": True
        },
        ip_address=ip_address,
        user_agent=user_agent
    )

    return (export, False)
