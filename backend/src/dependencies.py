"""Global FastAPI dependencies for tenant isolation and database access.

This module provides:
- get_org_id: Extract org_id from JWT token (automatic tenant scoping)
- get_scoped_session: Database session with automatic org_id filtering
- validate_org_exists: Ensure org_id references valid organization

All multi-tenant endpoints should use get_org_id to ensure isolation.
Database queries should use scoped sessions to prevent cross-tenant data leaks.

SSOT Reference: §5.1 (Multi-Tenant Isolation), §11.2 (Automatic Scoping)
"""

from typing import Generator
from uuid import UUID
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from .database import get_db
from .auth.dependencies import get_current_user
from .models.user import User
from .models.org import Org


def get_org_id(current_user: User = Depends(get_current_user)) -> UUID:
    """Extract org_id from authenticated user's JWT token.

    This dependency automatically derives the tenant context for API requests.
    Every multi-tenant endpoint should use this to ensure org_id filtering.

    The org_id comes from the JWT token (validated by get_current_user), which
    contains the user's organization ID. This prevents clients from tampering
    with org_id via request body/query params.

    Args:
        current_user: Authenticated user from JWT token

    Returns:
        UUID: Organization ID for the current request context

    Raises:
        HTTPException 401: If user is not authenticated
        HTTPException 500: If user.org_id is somehow None (database integrity issue)

    Example:
        @app.get("/documents")
        def list_documents(
            db: Session = Depends(get_db),
            org_id: UUID = Depends(get_org_id)
        ):
            # All queries automatically filtered by org_id
            return db.query(Document).filter(Document.org_id == org_id).all()
    """
    if not current_user.org_id:
        # This should never happen due to NOT NULL constraint, but guard anyway
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User has no organization association",
        )

    return current_user.org_id


def validate_org_exists(
    org_id: UUID = Depends(get_org_id),
    db: Session = Depends(get_db)
) -> UUID:
    """Validate that org_id references an existing organization.

    This dependency ensures the organization exists in the database before
    processing requests. Useful for endpoints that absolutely require org validation.

    Most endpoints don't need this - get_org_id is sufficient since users are
    already associated with valid orgs. Use this for extra safety in critical paths.

    Args:
        org_id: Organization ID from JWT token
        db: Database session

    Returns:
        UUID: Validated organization ID

    Raises:
        HTTPException 404: If organization doesn't exist

    Example:
        @app.post("/orders", dependencies=[Depends(validate_org_exists)])
        def create_order(...):
            # Org existence guaranteed
            ...
    """
    org = db.query(Org).filter(Org.id == org_id).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    return org_id


def get_scoped_session(
    org_id: UUID = Depends(get_org_id),
    db: Session = Depends(get_db)
) -> Session:
    """Get database session with org_id stored in session.info for automatic filtering.

    This dependency provides a session with tenant context attached. The org_id
    is stored in session.info and can be accessed by query helpers or event listeners
    for automatic filtering.

    Note: This is a convenience dependency. Most endpoints can use get_db + get_org_id
    separately and apply filters manually. Use this when you want session-level
    tenant scoping utilities.

    Args:
        org_id: Organization ID from JWT token
        db: Database session

    Returns:
        Session: SQLAlchemy session with org_id in session.info["org_id"]

    Example:
        @app.get("/documents")
        def list_documents(session: Session = Depends(get_scoped_session)):
            # org_id available via session.info["org_id"]
            org_id = session.info.get("org_id")
            return session.query(Document).filter(Document.org_id == org_id).all()
    """
    # Attach org_id to session info for use by query builders
    db.info["org_id"] = org_id
    return db


class TenantQuery:
    """Utility class for building tenant-scoped queries.

    This class provides helper methods for automatic org_id filtering.
    Can be used as a mixin or standalone utility.

    Example:
        @app.get("/documents")
        def list_documents(
            db: Session = Depends(get_db),
            org_id: UUID = Depends(get_org_id)
        ):
            query = TenantQuery.scoped_query(db, Document, org_id)
            return query.all()
    """

    @staticmethod
    def scoped_query(session: Session, model, org_id: UUID):
        """Create a query automatically filtered by org_id.

        Args:
            session: SQLAlchemy session
            model: SQLAlchemy model class (must have org_id column)
            org_id: Organization ID to filter by

        Returns:
            Query: SQLAlchemy query with org_id filter applied

        Raises:
            AttributeError: If model doesn't have org_id attribute

        Example:
            documents = TenantQuery.scoped_query(db, Document, org_id).all()
        """
        if not hasattr(model, 'org_id'):
            raise AttributeError(f"Model {model.__name__} does not have org_id column")

        return session.query(model).filter(model.org_id == org_id)

    @staticmethod
    def get_or_404(session: Session, model, record_id: UUID, org_id: UUID):
        """Get a record by ID with org_id scoping, or raise 404.

        This enforces tenant isolation by returning 404 for both:
        - Records that don't exist
        - Records that exist but belong to another org

        This prevents information leakage (knowing whether a resource exists
        in another tenant).

        Args:
            session: SQLAlchemy session
            model: SQLAlchemy model class
            record_id: Record ID to fetch
            org_id: Organization ID to scope by

        Returns:
            Model instance if found and belongs to org

        Raises:
            HTTPException 404: If record not found or belongs to another org

        Example:
            document = TenantQuery.get_or_404(db, Document, doc_id, org_id)
        """
        if not hasattr(model, 'org_id'):
            raise AttributeError(f"Model {model.__name__} does not have org_id column")

        record = session.query(model).filter(
            model.id == record_id,
            model.org_id == org_id
        ).first()

        if not record:
            # Return 404 (not 403) to prevent org enumeration
            # Same error whether record doesn't exist or belongs to another org
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{model.__name__} not found",
            )

        return record
