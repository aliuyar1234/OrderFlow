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

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from uuid import UUID, uuid4
from typing import Generator

# Adjust imports based on your project structure
import sys
from pathlib import Path
backend_src = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(backend_src))

from database import get_db
from models.base import Base
from models.user import User
from models.org import Org
from auth.password import hash_password
from auth.jwt import create_access_token


# Test database URL (use in-memory SQLite or separate test database)
TEST_DATABASE_URL = "sqlite:///:memory:"

# Create test engine
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite specific
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


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

    app.dependency_overrides[get_db] = override_get_db

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

    app.dependency_overrides[get_db] = override_get_db

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

    app.dependency_overrides[get_db] = override_get_db

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
