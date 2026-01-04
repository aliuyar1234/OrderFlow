"""FastAPI router for retention management endpoints.

Provides admin APIs for:
- Viewing retention settings
- Updating retention settings
- Generating retention reports
- Manually triggering cleanup for an organization

All endpoints require ADMIN role.

SSOT Reference: §11.5 (Data Retention), FR-020, FR-021
"""

import logging
from uuid import UUID
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user, get_org_id
from auth.roles import require_role, Role
from models.user import User
from models.org import Org
from audit.service import log_audit_event
from .schemas import (
    RetentionSettings,
    RetentionSettingsUpdate,
    RetentionReport,
)
from .service import RetentionService
from .tasks import retention_cleanup_org_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/retention", tags=["retention"])


@router.get("/settings", response_model=RetentionSettings)
@require_role(Role.ADMIN)
def get_retention_settings(
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_org_id),
    db: Session = Depends(get_db),
) -> RetentionSettings:
    """Get current retention settings for organization.

    Requires ADMIN role.

    Returns:
        RetentionSettings: Current retention configuration

    Raises:
        HTTPException 404: Organization not found
    """
    org = db.query(Org).filter(Org.id == org_id).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization {org_id} not found"
        )

    # Parse retention settings from org.settings_json
    retention_data = org.settings_json.get('retention', {})
    settings = RetentionSettings(**retention_data)

    logger.info(
        f"Retrieved retention settings for org {org_id}",
        extra={"org_id": str(org_id), "user_id": str(current_user.id)}
    )

    return settings


@router.patch("/settings", response_model=RetentionSettings)
@require_role(Role.ADMIN)
def update_retention_settings(
    updates: RetentionSettingsUpdate,
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_org_id),
    db: Session = Depends(get_db),
) -> RetentionSettings:
    """Update retention settings for organization.

    Requires ADMIN role. Partial updates supported - only provided fields are updated.

    Validation:
    - All retention periods must be 30-3650 days
    - Grace period must be 1-365 days

    Audit log entry created with action RETENTION_SETTINGS_UPDATED.

    Args:
        updates: Partial retention settings update

    Returns:
        RetentionSettings: Updated retention configuration

    Raises:
        HTTPException 404: Organization not found
        HTTPException 400: Validation error
    """
    org = db.query(Org).filter(Org.id == org_id).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization {org_id} not found"
        )

    # Get current settings
    current_retention = org.settings_json.get('retention', {})
    current_settings = RetentionSettings(**current_retention)

    # Apply updates (merge partial update with current settings)
    update_data = updates.dict(exclude_unset=True)
    updated_settings = current_settings.copy(update=update_data)

    # Update org.settings_json
    org.settings_json['retention'] = updated_settings.dict()
    db.commit()

    # Audit log
    log_audit_event(
        db=db,
        org_id=org_id,
        action="RETENTION_SETTINGS_UPDATED",
        actor_id=current_user.id,
        entity_type="organization",
        entity_id=org_id,
        metadata={
            'updates': update_data,
            'new_settings': updated_settings.dict(),
        }
    )
    db.commit()

    logger.info(
        f"Updated retention settings for org {org_id}",
        extra={
            "org_id": str(org_id),
            "user_id": str(current_user.id),
            "updates": update_data,
        }
    )

    return updated_settings


@router.get("/report", response_model=RetentionReport)
@require_role(Role.ADMIN)
def get_retention_report(
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_org_id),
    db: Session = Depends(get_db),
) -> RetentionReport:
    """Generate retention report showing records eligible for deletion.

    Requires ADMIN role.

    This endpoint provides a preview of what would be deleted if retention
    cleanup runs, without actually deleting anything. Useful for administrators
    to understand impact before running cleanup.

    Returns:
        RetentionReport: Summary of eligible records and estimated storage freed

    Raises:
        HTTPException 404: Organization not found
    """
    service = RetentionService(db=db, org_id=org_id, storage_client=None)
    report = service.generate_retention_report()

    logger.info(
        f"Generated retention report for org {org_id}",
        extra={
            "org_id": str(org_id),
            "user_id": str(current_user.id),
            "total_eligible": report.total_eligible_for_deletion,
        }
    )

    return report


@router.post("/cleanup", response_model=Dict[str, Any])
@require_role(Role.ADMIN)
def trigger_retention_cleanup(
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_org_id),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Manually trigger retention cleanup for this organization.

    Requires ADMIN role.

    This enqueues a background task to run retention cleanup immediately
    for the current organization. Use this for testing or handling special cases.

    The cleanup task runs asynchronously. This endpoint returns immediately
    with the task ID to check status.

    Audit log entry created with action RETENTION_CLEANUP_TRIGGERED.

    Returns:
        Dict with:
        - status: "enqueued"
        - task_id: Celery task ID for status checking
        - org_id: Organization UUID

    Raises:
        HTTPException 404: Organization not found
    """
    org = db.query(Org).filter(Org.id == org_id).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization {org_id} not found"
        )

    # Enqueue cleanup task
    task = retention_cleanup_org_task.delay(org_id=str(org_id))

    # Audit log
    log_audit_event(
        db=db,
        org_id=org_id,
        action="RETENTION_CLEANUP_TRIGGERED",
        actor_id=current_user.id,
        entity_type="organization",
        entity_id=org_id,
        metadata={'task_id': task.id}
    )
    db.commit()

    logger.info(
        f"Retention cleanup triggered for org {org_id}",
        extra={
            "org_id": str(org_id),
            "user_id": str(current_user.id),
            "task_id": task.id,
        }
    )

    return {
        'status': 'enqueued',
        'task_id': task.id,
        'org_id': str(org_id),
    }


@router.get("/statistics", response_model=Dict[str, Any])
@require_role(Role.ADMIN)
def get_retention_statistics(
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_org_id),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get retention cleanup statistics for organization.

    Requires ADMIN role.

    Returns summary of most recent retention cleanup execution:
    - When it ran
    - How many records were deleted
    - Any errors encountered

    Returns:
        Dict with retention statistics

    Note:
        This is a placeholder. Full implementation requires storing
        retention job history in database (future enhancement).
    """
    # TODO: Implement when retention job history table is added
    # For now, return basic info

    service = RetentionService(db=db, org_id=org_id, storage_client=None)
    settings = service.get_retention_settings()

    return {
        'org_id': str(org_id),
        'retention_settings': settings.dict(),
        'last_run': None,  # TODO: Query from job history table
        'next_run': "02:00 UTC daily",  # From Celery Beat schedule
    }
