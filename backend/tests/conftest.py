"""Pytest fixtures for authentication testing.

Provides reusable test fixtures for:
- Database session with transaction rollback
- Test organizations
- Test users with different roles (ADMIN, OPS, VIEWER)
- Authenticated test clients with JWT tokens

Usage:
    def test_admin_endpoint(authenticated_client, admin_user):
        response = authenticated_client.get("/users")
        assert response.status_code == 200
"""

import sys
import os
from pathlib import Path

# Set environment variables BEFORE any imports to ensure they take effect
# Set very high rate limits for testing (effectively disable rate limiting)
os.environ.setdefault("RATE_LIMIT_MAX_ATTEMPTS", "10000")
os.environ.setdefault("RATE_LIMIT_WINDOW", "1")
os.environ.setdefault("LOCKOUT_THRESHOLD", "10000")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from uuid import UUID, uuid4
from typing import Generator

# Adjust imports based on your project structure
backend_src = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(backend_src))

# Set PYTHONPATH for proper module resolution
# Use PostgreSQL - models require PostgreSQL features (gen_random_uuid, JSONB)
# Docker PostgreSQL runs on port 5433 with orderflow user
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "postgresql://orderflow:dev_password@localhost:5433/orderflow"

# Set required environment variables for testing
if "PASSWORD_PEPPER" not in os.environ:
    os.environ["PASSWORD_PEPPER"] = "test-pepper-secret-key-32-chars-long"

if "JWT_SECRET" not in os.environ:
    os.environ["JWT_SECRET"] = "test-jwt-secret-key-256-bits-minimum-length-required-for-security"

if "MINIO_ROOT_USER" not in os.environ:
    os.environ["MINIO_ROOT_USER"] = "minioadmin"

if "MINIO_ROOT_PASSWORD" not in os.environ:
    os.environ["MINIO_ROOT_PASSWORD"] = "minioadmin"

if "MINIO_ENDPOINT" not in os.environ:
    os.environ["MINIO_ENDPOINT"] = "localhost:9000"

if "MINIO_BUCKET" not in os.environ:
    os.environ["MINIO_BUCKET"] = "test-bucket"


# Import directly from modules (avoid relative import issues)
from sqlalchemy.orm import declarative_base
from models.base import Base
from models.user import User
from models.org import Org
from models.audit_log import AuditLog
from models.document import Document
from models.inbound_message import InboundMessage
from models.draft_order import DraftOrder, DraftOrderLine
from models.extraction_run import ExtractionRun
from models.sku_mapping import SkuMapping
from models.product import Product
from models.customer import Customer
from models.customer_price import CustomerPrice
from models.validation_issue import ValidationIssue
from models.erp_export import ERPExport
from models.ai_call_log import AICallLog
from models.erp_connection import ERPConnection
from models.erp_push_log import ERPPushLog
from auth.password import hash_password
from auth.jwt import create_access_token


# Test database URL - PostgreSQL is required (models use gen_random_uuid, JSONB)
TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://orderflow:dev_password@localhost:5433/orderflow"
)

# Create test engine
test_engine = create_engine(TEST_DATABASE_URL)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


# Import the actual get_db from database to use for dependency override
from database import get_db as database_get_db


@pytest.fixture(scope="function", autouse=True)
def reset_rate_limiter():
    """Reset rate limiting state before each test.

    Clears Redis keys used for rate limiting to ensure fresh state.
    """
    try:
        from auth.rate_limit import rate_limiter
        if rate_limiter.redis:
            # Clear all rate limiting and lockout keys
            keys = rate_limiter.redis.keys("rate_limit:*")
            keys += rate_limiter.redis.keys("lockout:*")
            keys += rate_limiter.redis.keys("failed_attempts:*")
            if keys:
                rate_limiter.redis.delete(*keys)
    except Exception:
        pass  # If Redis not available, no action needed
    yield


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Create a fresh database session for each test.

    Creates all tables before the test and drops them after.
    Each test gets a clean database state.
    """
    # Create all tables
    Base.metadata.create_all(bind=test_engine)

    # Create session
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        # Drop all tables after test
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def test_org(db_session: Session) -> Org:
    """Create a test organization."""
    org = Org(
        slug="test-org",
        name="Test Organization"
    )
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture(scope="function")
def admin_user(db_session: Session, test_org: Org) -> User:
    """Create an ADMIN user for testing."""
    password_hash = hash_password("AdminP@ss123")

    user = User(
        org_id=test_org.id,
        email="admin@test.com",
        name="Admin User",
        role="ADMIN",
        password_hash=password_hash,
        status="ACTIVE"
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def ops_user(db_session: Session, test_org: Org) -> User:
    """Create an OPS user for testing."""
    password_hash = hash_password("OpsP@ss123")

    user = User(
        org_id=test_org.id,
        email="ops@test.com",
        name="OPS User",
        role="OPS",
        password_hash=password_hash,
        status="ACTIVE"
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def viewer_user(db_session: Session, test_org: Org) -> User:
    """Create a VIEWER user for testing."""
    password_hash = hash_password("ViewerP@ss123")

    user = User(
        org_id=test_org.id,
        email="viewer@test.com",
        name="Viewer User",
        role="VIEWER",
        password_hash=password_hash,
        status="ACTIVE"
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def client(db_session: Session):
    """Create an unauthenticated test client.

    Returns a FastAPI TestClient without any authentication.
    Useful for testing public endpoints and auth flow.
    """
    from main import app

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[database_get_db] = override_get_db

    return TestClient(app)


@pytest.fixture(scope="function")
def authenticated_client(db_session: Session, admin_user: User):
    """Create a test client authenticated as admin user.

    Returns a FastAPI TestClient with Authorization header pre-configured.
    """
    from main import app  # Import your FastAPI app

    # Override get_db dependency to use test database
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[database_get_db] = override_get_db

    # Generate JWT token for admin user
    token = create_access_token(
        user_id=admin_user.id,
        org_id=admin_user.org_id,
        role=admin_user.role,
        email=admin_user.email
    )

    # Create test client with Authorization header
    client = TestClient(app)
    client.headers = {
        "Authorization": f"Bearer {token}"
    }

    return client


@pytest.fixture(scope="function")
def ops_client(db_session: Session, ops_user: User):
    """Create a test client authenticated as OPS user."""
    from main import app

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[database_get_db] = override_get_db

    token = create_access_token(
        user_id=ops_user.id,
        org_id=ops_user.org_id,
        role=ops_user.role,
        email=ops_user.email
    )

    client = TestClient(app)
    client.headers = {
        "Authorization": f"Bearer {token}"
    }

    return client


@pytest.fixture(scope="function")
def viewer_client(db_session: Session, viewer_user: User):
    """Create a test client authenticated as VIEWER user."""
    from main import app

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[database_get_db] = override_get_db

    token = create_access_token(
        user_id=viewer_user.id,
        org_id=viewer_user.org_id,
        role=viewer_user.role,
        email=viewer_user.email
    )

    client = TestClient(app)
    client.headers = {
        "Authorization": f"Bearer {token}"
    }

    return client
