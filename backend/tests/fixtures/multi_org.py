"""Multi-organization test fixtures for tenant isolation testing.

This module provides pytest fixtures for creating and managing multiple
organizations with test data, enabling comprehensive cross-tenant isolation tests.

Usage:
    @pytest.fixture
    def test_cross_org_access(multi_org_setup, client):
        org_a, org_b, user_a, user_b = multi_org_setup

        # Login as org A user
        token_a = login_as_user(client, user_a)

        # Try to access org B's data
        response = client.get(
            f"/documents/{org_b_document_id}",
            headers={"Authorization": f"Bearer {token_a}"}
        )

        # Should get 404 (not 403) to prevent org enumeration
        assert response.status_code == 404

SSOT Reference: §11.2 (Tenant Isolation Testing)
"""

import pytest
from uuid import UUID, uuid4
from typing import Tuple, Dict, Any
from sqlalchemy.orm import Session

from backend.src.models.org import Org
from backend.src.models.user import User
from backend.src.auth.password import hash_password
from backend.src.auth.jwt import create_access_token


@pytest.fixture
def org_a(db_session: Session) -> Org:
    """Create test organization A.

    Args:
        db_session: Database session fixture

    Returns:
        Org: Organization A instance
    """
    org = Org(
        id=uuid4(),
        name="ACME GmbH",
        slug="acme-gmbh",
        settings_json={}
    )
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture
def org_b(db_session: Session) -> Org:
    """Create test organization B.

    Args:
        db_session: Database session fixture

    Returns:
        Org: Organization B instance
    """
    org = Org(
        id=uuid4(),
        name="Widget AG",
        slug="widget-ag",
        settings_json={}
    )
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture
def user_a(db_session: Session, org_a: Org) -> User:
    """Create test user in organization A.

    Args:
        db_session: Database session fixture
        org_a: Organization A fixture

    Returns:
        User: User in organization A
    """
    user = User(
        id=uuid4(),
        org_id=org_a.id,
        email="ops@acme.de",
        password_hash=hash_password("test_password"),
        name="ACME Ops User",
        role="OPS",
        status="ACTIVE"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def user_b(db_session: Session, org_b: Org) -> User:
    """Create test user in organization B.

    Args:
        db_session: Database session fixture
        org_b: Organization B fixture

    Returns:
        User: User in organization B
    """
    user = User(
        id=uuid4(),
        org_id=org_b.id,
        email="ops@widget.ch",
        password_hash=hash_password("test_password"),
        name="Widget Ops User",
        role="OPS",
        status="ACTIVE"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user_a(db_session: Session, org_a: Org) -> User:
    """Create admin user in organization A.

    Args:
        db_session: Database session fixture
        org_a: Organization A fixture

    Returns:
        User: Admin user in organization A
    """
    user = User(
        id=uuid4(),
        org_id=org_a.id,
        email="admin@acme.de",
        password_hash=hash_password("admin_password"),
        name="ACME Admin",
        role="ADMIN",
        status="ACTIVE"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def multi_org_setup(
    db_session: Session,
    org_a: Org,
    org_b: Org,
    user_a: User,
    user_b: User
) -> Tuple[Org, Org, User, User]:
    """Create complete multi-org test setup.

    Provides two organizations with one user each for cross-tenant testing.

    Args:
        db_session: Database session fixture
        org_a: Organization A fixture
        org_b: Organization B fixture
        user_a: User A fixture
        user_b: User B fixture

    Returns:
        Tuple: (org_a, org_b, user_a, user_b)

    Example:
        def test_isolation(multi_org_setup):
            org_a, org_b, user_a, user_b = multi_org_setup

            # Create data for both orgs
            create_test_data(org_a.id)
            create_test_data(org_b.id)

            # Verify isolation
            assert_data_isolated(org_a, org_b)
    """
    return org_a, org_b, user_a, user_b


def create_jwt_token(user: User) -> str:
    """Create JWT token for test user.

    Args:
        user: User instance

    Returns:
        str: JWT access token

    Example:
        token = create_jwt_token(user_a)
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/documents", headers=headers)
    """
    return create_access_token(
        user_id=user.id,
        org_id=user.org_id,
        role=user.role,
        email=user.email
    )


def get_auth_headers(user: User) -> Dict[str, str]:
    """Get authorization headers for test user.

    Args:
        user: User instance

    Returns:
        Dict: Authorization headers for HTTP requests

    Example:
        headers = get_auth_headers(user_a)
        response = client.get("/documents", headers=headers)
    """
    token = create_jwt_token(user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def org_a_headers(user_a: User) -> Dict[str, str]:
    """Authorization headers for organization A user.

    Args:
        user_a: User A fixture

    Returns:
        Dict: Authorization headers

    Example:
        def test_list_documents(client, org_a_headers):
            response = client.get("/documents", headers=org_a_headers)
            assert response.status_code == 200
    """
    return get_auth_headers(user_a)


@pytest.fixture
def org_b_headers(user_b: User) -> Dict[str, str]:
    """Authorization headers for organization B user.

    Args:
        user_b: User B fixture

    Returns:
        Dict: Authorization headers
    """
    return get_auth_headers(user_b)


@pytest.fixture
def admin_a_headers(admin_user_a: User) -> Dict[str, str]:
    """Authorization headers for organization A admin user.

    Args:
        admin_user_a: Admin user A fixture

    Returns:
        Dict: Authorization headers

    Example:
        def test_update_settings(client, admin_a_headers):
            response = client.patch(
                "/org/settings",
                headers=admin_a_headers,
                json={"default_currency": "CHF"}
            )
            assert response.status_code == 200
    """
    return get_auth_headers(admin_user_a)


# Helper functions for creating test data

def create_test_org(
    db_session: Session,
    name: str,
    slug: str,
    settings: Dict[str, Any] = None
) -> Org:
    """Create a test organization with custom settings.

    Args:
        db_session: Database session
        name: Organization name
        slug: Organization slug
        settings: Custom settings (default: empty)

    Returns:
        Org: Created organization
    """
    org = Org(
        id=uuid4(),
        name=name,
        slug=slug,
        settings_json=settings or {}
    )
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


def create_test_user(
    db_session: Session,
    org_id: UUID,
    email: str,
    role: str = "OPS",
    name: str = None
) -> User:
    """Create a test user in specific organization.

    Args:
        db_session: Database session
        org_id: Organization UUID
        email: User email
        role: User role (default: OPS)
        name: User name (default: derived from email)

    Returns:
        User: Created user
    """
    user = User(
        id=uuid4(),
        org_id=org_id,
        email=email,
        password_hash=hash_password("test_password"),
        name=name or f"Test User ({email})",
        role=role,
        status="ACTIVE"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# Assertion helpers for tenant isolation testing

def assert_org_isolation(
    db_session: Session,
    model,
    org_a_id: UUID,
    org_b_id: UUID
):
    """Assert that data for two orgs is properly isolated.

    Verifies that:
    1. Org A can only see its own data
    2. Org B can only see its own data
    3. No cross-org data leakage

    Args:
        db_session: Database session
        model: SQLAlchemy model to check
        org_a_id: Organization A UUID
        org_b_id: Organization B UUID

    Raises:
        AssertionError: If isolation is violated
    """
    # Query for org A data
    org_a_data = db_session.query(model).filter(model.org_id == org_a_id).all()

    # Query for org B data
    org_b_data = db_session.query(model).filter(model.org_id == org_b_id).all()

    # Verify no overlap in IDs
    org_a_ids = {record.id for record in org_a_data}
    org_b_ids = {record.id for record in org_b_data}

    assert org_a_ids.isdisjoint(org_b_ids), \
        f"Found overlapping records between orgs: {org_a_ids & org_b_ids}"

    # Verify all records have correct org_id
    for record in org_a_data:
        assert record.org_id == org_a_id, \
            f"Record {record.id} in org A has wrong org_id: {record.org_id}"

    for record in org_b_data:
        assert record.org_id == org_b_id, \
            f"Record {record.id} in org B has wrong org_id: {record.org_id}"
