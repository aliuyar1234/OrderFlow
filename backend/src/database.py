"""Database session factory and configuration.

Provides database connectivity and session management for OrderFlow backend.
Includes multi-tenant scoped session factory for automatic org_id filtering.

SSOT Reference: §5.1 (Database Conventions)
"""

import os
from contextlib import contextmanager
from typing import Generator, Optional
from uuid import UUID

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from models.base import Base

# Get database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://orderflow:dev_password@localhost:5432/orderflow"
)

# Create engine with connection pooling
# Pool settings only apply to PostgreSQL (not SQLite)
_engine_kwargs = {
    "pool_pre_ping": True,  # Verify connections before using
    "echo": False,  # Set to True for SQL query logging
}

# Only add pool settings for non-SQLite databases
if not DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 10

engine = create_engine(DATABASE_URL, **_engine_kwargs)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager for database sessions.

    Usage:
        with get_db_session() as session:
            session.query(Org).all()

    Automatically commits on success, rolls back on exception.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """Dependency for FastAPI endpoints.

    Usage:
        @app.get("/orgs")
        def list_orgs(db: Session = Depends(get_db)):
            return db.query(Org).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def org_scoped_session(org_id: UUID) -> Session:
    """Create a database session scoped to a specific organization.

    This factory creates a session with org_id attached to session.info,
    enabling automatic tenant filtering for queries. Useful for background
    jobs and workers that process data for a specific organization.

    The org_id is stored in session.info["org_id"] and can be accessed by
    query builders or event listeners for automatic filtering.

    Args:
        org_id: Organization UUID to scope this session to

    Returns:
        Session: SQLAlchemy session with tenant context

    Example:
        # In a Celery task
        @celery_app.task
        def process_document(document_id: str, org_id: str):
            org_uuid = UUID(org_id)
            session = org_scoped_session(org_uuid)
            try:
                # All queries can use org_uuid for filtering
                doc = session.query(Document).filter(
                    Document.id == UUID(document_id),
                    Document.org_id == org_uuid
                ).first()
                # ... process document ...
                session.commit()
            finally:
                session.close()
    """
    session = SessionLocal()
    session.info["org_id"] = org_id
    return session


@event.listens_for(Session, "before_flush")
def auto_populate_org_id(session, flush_context, instances):
    """Automatically populate org_id on INSERT for new records.

    This event listener automatically sets org_id on new model instances
    if org_id is not already set and session has org_id in session.info.

    This provides a safety net for INSERT operations, ensuring org_id is
    never forgotten. However, explicit org_id setting is still recommended
    for clarity.

    Note: Only applies to models with org_id attribute. Skips models without it.
    """
    org_id = session.info.get("org_id")
    if not org_id:
        # No org_id in session context, skip auto-population
        return

    for instance in session.new:
        # Only set org_id if model has the attribute and it's not already set
        if hasattr(instance, 'org_id') and instance.org_id is None:
            instance.org_id = org_id
