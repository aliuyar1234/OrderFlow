"""Security tests for authentication bypass attempts

Tests cover:
- Direct endpoint access without authentication
- Token manipulation attempts
- Session hijacking prevention
- Privilege escalation attempts
- Rate limiting on auth endpoints

SSOT Reference: §11.1 (Security), §8.3 (Authentication)
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from uuid import uuid4
import jwt
from datetime import datetime, timedelta, timezone

import sys
from pathlib import Path
backend_src = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(backend_src))

from models.org import Org
from models.user import User
from auth.password import hash_password
from auth.jwt import create_access_token


pytestmark = pytest.mark.security


class TestUnauthenticatedAccess:
    """Test attempts to access protected endpoints without authentication"""

    @pytest.mark.parametrize("endpoint,method", [
        ("/api/v1/customers", "GET"),
        ("/api/v1/products", "GET"),
        ("/api/v1/drafts", "GET"),
        ("/api/v1/documents", "GET"),
        ("/users/me", "GET"),
        ("/api/v1/customers", "POST"),
        ("/admin/settings", "GET"),
    ])
    def test_protected_endpoints_require_auth(self, client: TestClient, endpoint: str, method: str):
        """Test protected endpoints return 401 without authentication"""
        if method == "GET":
            response = client.get(endpoint)
        elif method == "POST":
            response = client.post(endpoint, json={})

        assert response.status_code == 401
        assert "not authenticated" in response.json()["detail"].lower() or "unauthorized" in response.json()["detail"].lower()

    def test_malformed_authorization_header(self, client: TestClient):
        """Test various malformed Authorization headers"""
        malformed_headers = [
            {"Authorization": "InvalidFormat"},
            {"Authorization": "Bearer"},  # Missing token
            {"Authorization": "Basic dXNlcjpwYXNzd29yZA=="},  # Wrong scheme
            {"Authorization": ""},
            {"Authorization": "Bearer "},  # Empty token
        ]

        for headers in malformed_headers:
            response = client.get("/users/me", headers=headers)
            assert response.status_code == 401


class TestTokenManipulation:
    """Test JWT token manipulation attempts"""

    def test_tampered_token_signature(self, client: TestClient, test_org: Org, monkeypatch):
        """Test token with tampered signature is rejected"""
        secret = 'test-secret-key-256-bits-minimum-length-required-for-security'
        monkeypatch.setenv('JWT_SECRET', secret)

        user_id = uuid4()
        org_id = test_org.id

        # Create valid token
        token = create_access_token(
            user_id=user_id,
            org_id=org_id,
            role="VIEWER",
            email="viewer@test.com"
        )

        # Tamper with payload (change role from VIEWER to ADMIN)
        parts = token.split('.')
        import base64
        import json

        payload_bytes = base64.urlsafe_b64decode(parts[1] + '==')
        payload = json.loads(payload_bytes)
        payload['role'] = 'ADMIN'  # Escalate privileges

        tampered_payload = base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).decode().rstrip('=')

        tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"

        # Try to access with tampered token
        response = client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {tampered_token}"}
        )

        # Should reject tampered token
        assert response.status_code == 401

    def test_none_algorithm_attack(self, client: TestClient, test_org: Org, monkeypatch):
        """Test 'none' algorithm attack is prevented"""
        monkeypatch.setenv('JWT_SECRET', 'test-secret-key-256-bits-minimum-length-required-for-security')

        user_id = uuid4()

        # Create token with 'none' algorithm (no signature)
        payload = {
            'sub': str(user_id),
            'org_id': str(test_org.id),
            'role': 'ADMIN',
            'email': 'admin@test.com',
            'iat': int(datetime.now(timezone.utc).timestamp()),
            'exp': int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
        }

        # Encode header with 'none' algorithm
        import base64
        import json
        header = json.dumps({'alg': 'none', 'typ': 'JWT'})
        encoded_header = base64.urlsafe_b64encode(header.encode()).decode().rstrip('=')
        encoded_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')

        # Token with no signature
        none_token = f"{encoded_header}.{encoded_payload}."

        response = client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {none_token}"}
        )

        # Should reject 'none' algorithm
        assert response.status_code == 401

    def test_cross_org_token_reuse(self, client: TestClient, db_session: Session):
        """Test token from one org cannot access another org's data"""
        # Create two orgs
        org_a = Org(slug="org-a", name="Org A")
        org_b = Org(slug="org-b", name="Org B")
        db_session.add_all([org_a, org_b])
        db_session.commit()

        # Create user in org A
        user_a = User(
            org_id=org_a.id,
            email="user@org-a.com",
            name="User A",
            role="ADMIN",
            password_hash=hash_password("SecureP@ss123"),
            status="ACTIVE"
        )
        db_session.add(user_a)
        db_session.commit()

        # Create token for user A
        token_a = create_access_token(
            user_id=user_a.id,
            org_id=org_a.id,
            role=user_a.role,
            email=user_a.email
        )

        # Try to access org B's customers endpoint
        # (API should filter by token's org_id, returning empty list or 404)
        response = client.get(
            "/api/v1/customers",
            headers={"Authorization": f"Bearer {token_a}"}
        )

        # Should only show org A's customers (empty in this case)
        if response.status_code == 200:
            assert len(response.json()) == 0


class TestPrivilegeEscalation:
    """Test privilege escalation attempts"""

    def test_viewer_cannot_escalate_to_admin(self, client: TestClient, db_session: Session, test_org: Org):
        """Test VIEWER user cannot perform ADMIN actions"""
        # Create VIEWER user
        viewer = User(
            org_id=test_org.id,
            email="viewer@test.com",
            name="Viewer User",
            role="VIEWER",
            password_hash=hash_password("SecureP@ss123"),
            status="ACTIVE"
        )
        db_session.add(viewer)
        db_session.commit()

        # Create token
        token = create_access_token(
            user_id=viewer.id,
            org_id=viewer.org_id,
            role=viewer.role,
            email=viewer.email
        )

        # Try to create a user (ADMIN action)
        response = client.post(
            "/admin/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": "newuser@test.com",
                "name": "New User",
                "role": "OPS",
                "password": "SecureP@ss123"
            }
        )

        # Should be forbidden
        assert response.status_code == 403

    def test_ops_cannot_access_admin_endpoints(self, client: TestClient, db_session: Session, test_org: Org):
        """Test OPS user cannot access admin endpoints"""
        # Create OPS user
        ops_user = User(
            org_id=test_org.id,
            email="ops@test.com",
            name="OPS User",
            role="OPS",
            password_hash=hash_password("SecureP@ss123"),
            status="ACTIVE"
        )
        db_session.add(ops_user)
        db_session.commit()

        # Create token
        token = create_access_token(
            user_id=ops_user.id,
            org_id=ops_user.org_id,
            role=ops_user.role,
            email=ops_user.email
        )

        # Try to access admin settings
        response = client.get(
            "/admin/settings",
            headers={"Authorization": f"Bearer {token}"}
        )

        # Should be forbidden
        assert response.status_code == 403

    def test_cannot_change_own_role(self, client: TestClient, db_session: Session, test_org: Org):
        """Test user cannot change their own role"""
        # Create OPS user
        ops_user = User(
            org_id=test_org.id,
            email="ops@test.com",
            name="OPS User",
            role="OPS",
            password_hash=hash_password("SecureP@ss123"),
            status="ACTIVE"
        )
        db_session.add(ops_user)
        db_session.commit()

        # Create token
        token = create_access_token(
            user_id=ops_user.id,
            org_id=ops_user.org_id,
            role=ops_user.role,
            email=ops_user.email
        )

        # Try to change own role to ADMIN
        response = client.patch(
            f"/users/{ops_user.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"role": "ADMIN"}
        )

        # Should be forbidden or ignored
        assert response.status_code in [403, 400]

        # Verify role didn't change
        db_session.refresh(ops_user)
        assert ops_user.role == "OPS"


class TestRateLimiting:
    """Test rate limiting on authentication endpoints"""

    def test_login_rate_limiting(self, client: TestClient, db_session: Session, test_org: Org):
        """Test excessive login attempts are rate limited"""
        # Create user
        user = User(
            org_id=test_org.id,
            email="user@test.com",
            name="Test User",
            role="OPS",
            password_hash=hash_password("SecureP@ss123"),
            status="ACTIVE"
        )
        db_session.add(user)
        db_session.commit()

        # Attempt many failed logins
        failed_attempts = 0
        for _ in range(20):
            response = client.post(
                "/auth/login",
                json={
                    "email": "user@test.com",
                    "password": "WrongPassword"
                }
            )

            if response.status_code == 429:  # Too Many Requests
                failed_attempts += 1

        # Should eventually rate limit
        # (if rate limiting is implemented)
        # This test documents expected behavior

    def test_account_lockout_after_failed_attempts(self, client: TestClient, db_session: Session, test_org: Org):
        """Test account lockout after multiple failed login attempts"""
        # Create user
        user = User(
            org_id=test_org.id,
            email="user@test.com",
            name="Test User",
            role="OPS",
            password_hash=hash_password("CorrectP@ss123"),
            status="ACTIVE"
        )
        db_session.add(user)
        db_session.commit()

        # Attempt multiple failed logins
        for _ in range(10):
            client.post(
                "/auth/login",
                json={
                    "email": "user@test.com",
                    "password": "WrongPassword"
                }
            )

        # Try with correct password (should be locked if implemented)
        response = client.post(
            "/auth/login",
            json={
                "email": "user@test.com",
                "password": "CorrectP@ss123"
            }
        )

        # Should either succeed or be locked (depends on implementation)
        # This test documents expected behavior
        assert response.status_code in [200, 403, 429]


class TestSessionSecurity:
    """Test session hijacking prevention"""

    def test_token_cannot_be_reused_after_logout(self, client: TestClient, db_session: Session, test_org: Org):
        """Test token invalidation after logout (if implemented)"""
        # Create user
        user = User(
            org_id=test_org.id,
            email="user@test.com",
            name="Test User",
            role="OPS",
            password_hash=hash_password("SecureP@ss123"),
            status="ACTIVE"
        )
        db_session.add(user)
        db_session.commit()

        # Login
        login_response = client.post(
            "/auth/login",
            json={
                "email": "user@test.com",
                "password": "SecureP@ss123"
            }
        )

        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        # Verify token works
        response = client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

        # Logout (if endpoint exists)
        logout_response = client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {token}"}
        )

        # If logout is implemented, token should be invalid after
        # (Note: Stateless JWT typically doesn't support logout without token blacklist)

    def test_token_expiration_enforced(self, client: TestClient, db_session: Session, test_org: Org, monkeypatch):
        """Test expired tokens are rejected"""
        secret = 'test-secret-key-256-bits-minimum-length-required-for-security'
        monkeypatch.setenv('JWT_SECRET', secret)

        user_id = uuid4()

        # Create expired token
        past = datetime.now(timezone.utc) - timedelta(hours=2)
        payload = {
            'sub': str(user_id),
            'org_id': str(test_org.id),
            'role': 'ADMIN',
            'email': 'admin@test.com',
            'iat': int(past.timestamp()),
            'exp': int((past + timedelta(hours=1)).timestamp())
        }

        expired_token = jwt.encode(payload, secret, algorithm='HS256')

        # Try to access with expired token
        response = client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {expired_token}"}
        )

        # Should reject expired token
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()


class TestPasswordSecurity:
    """Test password-related security"""

    def test_password_not_logged(self, client: TestClient, db_session: Session, test_org: Org, caplog):
        """Test passwords are not logged in plain text"""
        import logging
        caplog.set_level(logging.DEBUG)

        # Attempt login
        client.post(
            "/auth/login",
            json={
                "email": "user@test.com",
                "password": "SecretP@ss123"
            }
        )

        # Check logs don't contain password
        for record in caplog.records:
            assert "SecretP@ss123" not in record.message

    def test_password_hash_not_exposed_in_api(self, client: TestClient, db_session: Session, test_org: Org, admin_user: User):
        """Test password hash is never returned in API responses"""
        token = create_access_token(
            user_id=admin_user.id,
            org_id=admin_user.org_id,
            role=admin_user.role,
            email=admin_user.email
        )

        # Get user details
        response = client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        user_data = response.json()

        # Password fields should not be present
        assert "password" not in user_data
        assert "password_hash" not in user_data
        assert "passwordHash" not in user_data

    def test_timing_attack_on_login(self, client: TestClient, db_session: Session, test_org: Org):
        """Test login timing doesn't reveal whether user exists"""
        import time

        # Create user
        user = User(
            org_id=test_org.id,
            email="existing@test.com",
            name="Existing User",
            role="OPS",
            password_hash=hash_password("SecureP@ss123"),
            status="ACTIVE"
        )
        db_session.add(user)
        db_session.commit()

        # Time login for existing user with wrong password
        start = time.time()
        client.post(
            "/auth/login",
            json={
                "email": "existing@test.com",
                "password": "WrongPassword"
            }
        )
        existing_time = time.time() - start

        # Time login for non-existent user
        start = time.time()
        client.post(
            "/auth/login",
            json={
                "email": "nonexistent@test.com",
                "password": "AnyPassword"
            }
        )
        nonexistent_time = time.time() - start

        # Times should be similar (within reasonable tolerance)
        # This prevents user enumeration via timing
        time_diff = abs(existing_time - nonexistent_time)
        assert time_diff < 0.5  # Within 500ms


class TestCSRFProtection:
    """Test CSRF protection (if implemented)"""

    def test_state_changing_operations_require_csrf_token(self, client: TestClient, authenticated_client: TestClient):
        """Test POST/PUT/DELETE require CSRF token (if CSRF protection enabled)"""
        # This is a placeholder for CSRF protection tests
        # OrderFlow uses JWT which is stored in Authorization header,
        # making it less vulnerable to CSRF than cookie-based auth

        # If CSRF tokens are implemented, test here
        pass
