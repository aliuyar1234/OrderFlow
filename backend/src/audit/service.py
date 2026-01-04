"""Audit logging service for security events.

This service provides a centralized interface for creating immutable audit log
entries. All security-relevant events must be logged through this service.

Audit Events (§11.4):
- LOGIN_SUCCESS, LOGIN_FAILED
- USER_CREATED, USER_UPDATED, USER_DISABLED
- USER_ROLE_CHANGED
- PASSWORD_CHANGED
- PERMISSION_DENIED
"""

from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional, Dict, Any
from fastapi import Request

from ..models.audit_log import AuditLog


def log_audit_event(
    db: Session,
    org_id: UUID,
    action: str,
    actor_id: Optional[UUID] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[UUID] = None,
    metadata: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditLog:
    """Create an audit log entry.

    All parameters are stored as-is. This function does not validate action names
    or entity types - callers must ensure correct values per §11.4.

    Args:
        db: Database session
        org_id: Organization ID
        action: Event action (e.g., "USER_CREATED", "LOGIN_SUCCESS")
        actor_id: User who performed the action (None for anonymous/system events)
        entity_type: Type of entity affected (e.g., "user", "draft_order")
        entity_id: ID of affected entity
        metadata: Additional context as JSON (e.g., {"old_role": "OPS", "new_role": "ADMIN"})
        ip_address: Client IP address (IPv4 or IPv6)
        user_agent: Client User-Agent header

    Returns:
        AuditLog: The created audit log entry

    Example:
        log_audit_event(
            db=db,
            org_id=user.org_id,
            action="USER_CREATED",
            actor_id=current_user.id,
            entity_type="user",
            entity_id=new_user.id,
            metadata={"email": new_user.email, "role": new_user.role},
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0..."
        )
    """
    audit_entry = AuditLog(
        org_id=org_id,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=metadata,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    db.add(audit_entry)
    db.flush()  # Get ID without committing transaction

    return audit_entry


def log_from_request(
    db: Session,
    request: Request,
    org_id: UUID,
    action: str,
    actor_id: Optional[UUID] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[UUID] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """Create audit log entry extracting IP and User-Agent from FastAPI request.

    Convenience wrapper around log_audit_event that extracts client information
    from the request object.

    Args:
        db: Database session
        request: FastAPI Request object
        org_id: Organization ID
        action: Event action
        actor_id: User who performed the action
        entity_type: Type of entity affected
        entity_id: ID of affected entity
        metadata: Additional context as JSON

    Returns:
        AuditLog: The created audit log entry

    Example:
        @app.post("/users")
        def create_user(request: Request, data: UserCreate, ...):
            new_user = ...
            log_from_request(
                db=db,
                request=request,
                org_id=current_user.org_id,
                action="USER_CREATED",
                actor_id=current_user.id,
                entity_type="user",
                entity_id=new_user.id,
                metadata={"email": new_user.email}
            )
    """
    # Extract client IP (handle proxies via X-Forwarded-For)
    ip_address = request.client.host if request.client else None
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Use first IP in chain (original client)
        ip_address = forwarded_for.split(",")[0].strip()

    # Extract User-Agent header
    user_agent = request.headers.get("User-Agent")

    return log_audit_event(
        db=db,
        org_id=org_id,
        action=action,
        actor_id=actor_id,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata=metadata,
        ip_address=ip_address,
        user_agent=user_agent,
    )
