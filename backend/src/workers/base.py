"""Base utilities for multi-tenant background tasks.

This module provides utilities for ensuring tenant isolation in Celery tasks:
- org_id validation (verify organization exists)
- Scoped session creation (automatic org_id context)
- Base task class with tenant validation

All Celery tasks should use these utilities to maintain tenant boundaries.

SSOT Reference: §11.2 (Multi-Tenant Background Jobs)

Task Signature Pattern:
======================

Every multi-tenant Celery task MUST follow this signature pattern:

@celery_app.task(base=BaseTask)
def my_task(resource_id: str, org_id: str) -> Dict[str, Any]:
    '''Process resource for specific organization.

    Args:
        resource_id: UUID string of resource to process
        org_id: UUID string of organization (REQUIRED for tenant isolation)

    Returns:
        Dict with processing result

    Raises:
        ValueError: If org_id is invalid or missing
    '''
    # 1. Validate org_id
    org_uuid = validate_org_id(org_id)

    # 2. Get scoped session
    session = get_scoped_session(org_uuid)

    try:
        # 3. Query with explicit org_id filter
        resource = session.query(Resource).filter(
            Resource.id == UUID(resource_id),
            Resource.org_id == org_uuid
        ).first()

        if not resource:
            raise ValueError(f"Resource {resource_id} not found in org {org_id}")

        # 4. Process resource...
        result = process(resource)

        session.commit()
        return {"status": "success", "result": result}

    finally:
        session.close()

Enqueueing Pattern:
==================

When enqueuing tasks from API endpoints:

@router.post("/resources/{resource_id}/process")
def trigger_processing(
    resource_id: UUID,
    org_id: UUID = Depends(get_org_id),
    db: Session = Depends(get_db)
):
    # Enqueue with explicit org_id
    my_task.delay(
        resource_id=str(resource_id),
        org_id=str(org_id)  # REQUIRED - from JWT token, not request body
    )
    return {"status": "enqueued"}

CRITICAL REQUIREMENTS:
======================

1. ALWAYS pass org_id explicitly to task.delay()
2. NEVER derive org_id from global state or "current" context in workers
3. ALWAYS validate org_id in task before processing
4. ALWAYS use explicit org_id filters in queries (never rely on defaults)
5. ALWAYS handle org_id as UUID string in task signatures (JSON serializable)

Security Note:
=============

Org_id MUST come from JWT token (server-side), never from request body/query.
Use get_org_id dependency in API endpoints to extract from authenticated user.
This prevents clients from triggering tasks for other organizations.
"""

from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from celery import Task

from ..database import org_scoped_session, SessionLocal
from ..models.org import Org


def validate_org_id(org_id: str) -> UUID:
    """Validate that org_id is a valid UUID and references an existing organization.

    This function MUST be called at the start of every multi-tenant Celery task
    to ensure the organization exists before processing.

    Args:
        org_id: Organization UUID as string (from task parameters)

    Returns:
        UUID: Validated organization UUID

    Raises:
        ValueError: If org_id is invalid UUID format or organization doesn't exist

    Example:
        @celery_app.task
        def process_document(document_id: str, org_id: str):
            org_uuid = validate_org_id(org_id)  # REQUIRED
            # ... continue with processing ...
    """
    # Parse UUID
    try:
        org_uuid = UUID(org_id)
    except (ValueError, AttributeError, TypeError) as e:
        raise ValueError(f"Invalid org_id format '{org_id}': {str(e)}")

    # Verify organization exists in database
    session = SessionLocal()
    try:
        org = session.query(Org).filter(Org.id == org_uuid).first()
        if not org:
            raise ValueError(f"Organization {org_id} does not exist")
    finally:
        session.close()

    return org_uuid


def get_scoped_session(org_id: UUID) -> Session:
    """Create a database session scoped to a specific organization for worker tasks.

    This is the recommended way to get a database session in Celery tasks.
    The session has org_id attached to session.info for context.

    Args:
        org_id: Organization UUID (validated)

    Returns:
        Session: SQLAlchemy session with tenant context

    Example:
        @celery_app.task
        def process_document(document_id: str, org_id: str):
            org_uuid = validate_org_id(org_id)
            session = get_scoped_session(org_uuid)
            try:
                # All queries MUST filter by org_uuid
                doc = session.query(Document).filter(
                    Document.id == UUID(document_id),
                    Document.org_id == org_uuid
                ).first()
                # ... process ...
                session.commit()
            finally:
                session.close()
    """
    return org_scoped_session(org_id)


class BaseTask(Task):
    """Base Celery task class with tenant validation.

    Extend this class for tasks that require automatic org_id validation.
    Tasks using this base class must include org_id in their signature.

    The base class automatically validates org_id before running the task.
    If org_id is missing or invalid, the task fails with clear error.

    Usage:
        @celery_app.task(base=BaseTask)
        def my_task(resource_id: str, org_id: str):
            # org_id already validated by BaseTask
            org_uuid = UUID(org_id)
            session = get_scoped_session(org_uuid)
            # ... process ...

    Note: This is OPTIONAL. You can also validate org_id manually in tasks
    using validate_org_id() function. Use BaseTask for consistency.
    """

    def __call__(self, *args, **kwargs):
        """Validate org_id before running task.

        Raises:
            ValueError: If org_id parameter is missing or invalid
        """
        # Check if org_id is in kwargs
        org_id = kwargs.get('org_id')

        if not org_id:
            # Check if org_id is in args (positional)
            # Assume org_id is always passed as kwarg (recommended)
            raise ValueError(
                "org_id parameter is required for all multi-tenant tasks. "
                "Ensure you pass org_id=str(org_uuid) when enqueuing the task."
            )

        # Validate org_id exists
        validate_org_id(org_id)

        # Call the actual task
        return super().__call__(*args, **kwargs)


# Example task template (for documentation)
TASK_TEMPLATE = """
from celery import shared_task
from uuid import UUID
from typing import Dict, Any

from .base import BaseTask, validate_org_id, get_scoped_session
from ..models import MyModel


@shared_task(base=BaseTask, bind=True)
def my_background_task(
    self,
    resource_id: str,
    org_id: str,
    **kwargs
) -> Dict[str, Any]:
    '''Process a resource for a specific organization.

    Args:
        resource_id: UUID string of resource to process
        org_id: UUID string of organization (REQUIRED)

    Returns:
        Dict with processing result

    Raises:
        ValueError: If org_id invalid or resource not found
    '''
    # 1. Validate org_id (automatic if using BaseTask, but explicit is clearer)
    org_uuid = validate_org_id(org_id)

    # 2. Get scoped session
    session = get_scoped_session(org_uuid)

    try:
        # 3. Query with EXPLICIT org_id filter
        resource = session.query(MyModel).filter(
            MyModel.id == UUID(resource_id),
            MyModel.org_id == org_uuid  # REQUIRED - never query without org_id
        ).first()

        if not resource:
            raise ValueError(f"Resource {resource_id} not found in org {org_id}")

        # 4. Process resource
        # ... your business logic here ...

        # 5. Commit changes
        session.commit()

        return {
            "status": "success",
            "resource_id": resource_id,
            "org_id": org_id
        }

    except Exception as e:
        session.rollback()
        # Log error with org_id context
        self.retry(exc=e, countdown=60)  # Retry with exponential backoff

    finally:
        session.close()
"""
