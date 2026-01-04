"""Integration tests for authentication flow

Tests cover:
- Login endpoint with valid/invalid credentials
- JWT token issuance
- Token-based authentication
- Logout behavior
- Password validation on registration
- Multi-org user isolation

SSOT Reference: §8.3 (Authentication)
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from uuid import uuid4

import sys
from pathlib import Path
backend_src = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(backend_src))

from models.user import User
from models.org import Org
from auth.password import hash_password
from auth.jwt import decode_token


pytestmark = pytest.mark.integration


class TestLoginEndpoint:
    """Test POST /auth/login endpoint"""

    def test_login_with_valid_credentials(self, client: TestClient, db_session: Session, test_org: Org):
        """Test login with correct email and password"""
        # Create user
        password = "SecureP@ss123"
        user = User(
            org_id=test_org.id,
            email="ops@test.com",
            name="Ops User",
            role="OPS",
            password_hash=hash_password(password),
            status="ACTIVE"
        )
        db_session.add(user)
        db_session.commit()

        # Attempt login
        response = client.post(
            "/auth/login",
            json={
                "email": "ops@test.com",
                "password": password
            }
        )

        # Should succeed
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["email"] == "ops@test.com"
        assert data["user"]["role"] == "OPS"

    def test_login_with_wrong_password(self, client: TestClient, db_session: Session, test_org: Org):
        """Test login with incorrect password"""
        # Create user
        user = User(
            org_id=test_org.id,
            email="ops@test.com",
            name="Ops User",
            role="OPS",
            password_hash=hash_password("CorrectP@ss123"),
            status="ACTIVE"
        )
        db_session.add(user)
        db_session.commit()

        # Attempt login with wrong password
        response = client.post(
            "/auth/login",
            json={
                "email": "ops@test.com",
                "password": "WrongP@ss456"
            }
        )

        # Should fail
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]

    def test_login_with_nonexistent_user(self, client: TestClient):
        """Test login with email that doesn't exist"""
        response = client.post(
            "/auth/login",
            json={
                "email": "nonexistent@test.com",
                "password": "AnyP@ss123"
            }
        )

        # Should fail
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]

    def test_login_case_insensitive_email(self, client: TestClient, db_session: Session, test_org: Org):
        """Test login with email in different case"""
        # Create user with lowercase email
        password = "SecureP@ss123"
        user = User(
            org_id=test_org.id,
            email="ops@test.com",
            name="Ops User",
            role="OPS",
            password_hash=hash_password(password),
            status="ACTIVE"
        )
        db_session.add(user)
        db_session.commit()

        # Login with uppercase email
        response = client.post(
            "/auth/login",
            json={
                "email": "OPS@TEST.COM",
                "password": password
            }
        )

        # Should succeed (email is case-insensitive)
        assert response.status_code == 200

    def test_login_with_disabled_user(self, client: TestClient, db_session: Session, test_org: Org):
        """Test login with disabled user account"""
        password = "SecureP@ss123"
        user = User(
            org_id=test_org.id,
            email="disabled@test.com",
            name="Disabled User",
            role="OPS",
            password_hash=hash_password(password),
            status="DISABLED"
        )
        db_session.add(user)
        db_session.commit()

        # Attempt login
        response = client.post(
            "/auth/login",
            json={
                "email": "disabled@test.com",
                "password": password
            }
        )

        # Should fail
        assert response.status_code == 403
        assert "disabled" in response.json()["detail"].lower()

    def test_login_missing_email(self, client: TestClient):
        """Test login without email"""
        response = client.post(
            "/auth/login",
            json={
                "password": "SecureP@ss123"
            }
        )

        assert response.status_code == 422  # Validation error

    def test_login_missing_password(self, client: TestClient):
        """Test login without password"""
        response = client.post(
            "/auth/login",
            json={
                "email": "ops@test.com"
            }
        )

        assert response.status_code == 422  # Validation error

    def test_login_updates_last_login_timestamp(self, client: TestClient, db_session: Session, test_org: Org):
        """Test successful login updates last_login_at timestamp"""
        password = "SecureP@ss123"
        user = User(
            org_id=test_org.id,
            email="ops@test.com",
            name="Ops User",
            role="OPS",
            password_hash=hash_password(password),
            status="ACTIVE",
            last_login_at=None
        )
        db_session.add(user)
        db_session.commit()

        # Initial last_login_at should be None
        assert user.last_login_at is None

        # Login
        response = client.post(
            "/auth/login",
            json={
                "email": "ops@test.com",
                "password": password
            }
        )

        assert response.status_code == 200

        # Refresh user and check last_login_at is set
        db_session.refresh(user)
        assert user.last_login_at is not None


class TestJWTTokenValidation:
    """Test JWT token validation in protected endpoints"""

    def test_access_protected_endpoint_with_valid_token(self, authenticated_client: TestClient):
        """Test accessing protected endpoint with valid JWT"""
        response = authenticated_client.get("/users/me")

        assert response.status_code == 200
        data = response.json()
        assert "email" in data
        assert "role" in data

    def test_access_protected_endpoint_without_token(self, client: TestClient):
        """Test accessing protected endpoint without Authorization header"""
        response = client.get("/users/me")

        assert response.status_code == 401
        assert "Not authenticated" in response.json()["detail"]

    def test_access_protected_endpoint_with_invalid_token(self, client: TestClient):
        """Test accessing protected endpoint with malformed token"""
        response = client.get(
            "/users/me",
            headers={"Authorization": "Bearer invalid-token-format"}
        )

        assert response.status_code == 401

    def test_access_protected_endpoint_with_expired_token(self, client: TestClient, db_session: Session, test_org: Org, monkeypatch):
        """Test accessing protected endpoint with expired token"""
        import jwt
        from datetime import datetime, timedelta, timezone

        # Create expired token
        secret = 'test-secret-key-256-bits-minimum-length-required-for-security'
        monkeypatch.setenv('JWT_SECRET', secret)

        user_id = uuid4()
        past = datetime.now(timezone.utc) - timedelta(hours=2)

        payload = {
            'sub': str(user_id),
            'org_id': str(test_org.id),
            'role': 'ADMIN',
            'email': 'test@test.com',
            'iat': int(past.timestamp()),
            'exp': int((past + timedelta(minutes=60)).timestamp())
        }

        expired_token = jwt.encode(payload, secret, algorithm='HS256')

        response = client.get(
            "/users/me",
            headers={"Authorization": f"Bearer {expired_token}"}
        )

        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    def test_token_contains_correct_user_info(self, authenticated_client: TestClient, admin_user: User):
        """Test JWT token contains correct user claims"""
        # Extract token from client
        auth_header = authenticated_client.headers.get("Authorization")
        token = auth_header.replace("Bearer ", "")

        payload = decode_token(token)

        assert payload['sub'] == str(admin_user.id)
        assert payload['org_id'] == str(admin_user.org_id)
        assert payload['role'] == admin_user.role
        assert payload['email'] == admin_user.email


class TestRoleBasedAccess:
    """Test role-based access control"""

    def test_admin_can_access_admin_endpoint(self, authenticated_client: TestClient):
        """Test ADMIN role can access admin-only endpoints"""
        response = authenticated_client.get("/admin/settings")

        # Should have access (not 403)
        assert response.status_code in [200, 404]  # 404 if endpoint not implemented

    def test_viewer_cannot_access_admin_endpoint(self, viewer_client: TestClient):
        """Test VIEWER role cannot access admin-only endpoints"""
        response = viewer_client.get("/admin/settings")

        # Should be forbidden
        assert response.status_code == 403

    def test_ops_can_upload_documents(self, ops_client: TestClient):
        """Test OPS role can upload documents"""
        import io

        files = {
            'files': ('order.pdf', io.BytesIO(b"%PDF-1.4\n"), 'application/pdf')
        }

        response = ops_client.post("/api/v1/uploads", files=files)

        # Should have access
        assert response.status_code in [200, 201]

    def test_viewer_cannot_upload_documents(self, viewer_client: TestClient):
        """Test VIEWER role cannot upload documents"""
        import io

        files = {
            'files': ('order.pdf', io.BytesIO(b"%PDF-1.4\n"), 'application/pdf')
        }

        response = viewer_client.post("/api/v1/uploads", files=files)

        # Should be forbidden
        assert response.status_code == 403


class TestMultiOrgUserIsolation:
    """Test users from different orgs are isolated"""

    def test_user_can_only_login_to_own_org(self, client: TestClient, db_session: Session):
        """Test user can only see their own org data"""
        # Create two orgs
        org_a = Org(slug="org-a", name="Org A")
        org_b = Org(slug="org-b", name="Org B")
        db_session.add_all([org_a, org_b])
        db_session.commit()

        # Create users in both orgs with same email
        password = "SecureP@ss123"
        user_a = User(
            org_id=org_a.id,
            email="ops@company.com",
            name="Ops A",
            role="OPS",
            password_hash=hash_password(password),
            status="ACTIVE"
        )
        user_b = User(
            org_id=org_b.id,
            email="ops@company.com",
            name="Ops B",
            role="OPS",
            password_hash=hash_password(password),
            status="ACTIVE"
        )
        db_session.add_all([user_a, user_b])
        db_session.commit()

        # Login as user A
        response_a = client.post(
            "/auth/login",
            json={"email": "ops@company.com", "password": password}
        )

        assert response_a.status_code == 200
        token_a = response_a.json()["access_token"]
        payload_a = decode_token(token_a)

        # Token should contain org_a
        assert payload_a['org_id'] == str(org_a.id)

    def test_users_from_different_orgs_have_different_tokens(self, client: TestClient, db_session: Session):
        """Test users from different orgs get different org_id in tokens"""
        # Create two orgs
        org_a = Org(slug="org-a", name="Org A")
        org_b = Org(slug="org-b", name="Org B")
        db_session.add_all([org_a, org_b])
        db_session.commit()

        # Create users with different emails
        password = "SecureP@ss123"
        user_a = User(
            org_id=org_a.id,
            email="ops-a@company.com",
            name="Ops A",
            role="OPS",
            password_hash=hash_password(password),
            status="ACTIVE"
        )
        user_b = User(
            org_id=org_b.id,
            email="ops-b@company.com",
            name="Ops B",
            role="OPS",
            password_hash=hash_password(password),
            status="ACTIVE"
        )
        db_session.add_all([user_a, user_b])
        db_session.commit()

        # Login as both users
        response_a = client.post("/auth/login", json={"email": "ops-a@company.com", "password": password})
        response_b = client.post("/auth/login", json={"email": "ops-b@company.com", "password": password})

        token_a = response_a.json()["access_token"]
        token_b = response_b.json()["access_token"]

        payload_a = decode_token(token_a)
        payload_b = decode_token(token_b)

        # Different org_ids
        assert payload_a['org_id'] != payload_b['org_id']
        assert payload_a['org_id'] == str(org_a.id)
        assert payload_b['org_id'] == str(org_b.id)


class TestPasswordSecurity:
    """Test password security requirements"""

    def test_weak_password_rejected_on_registration(self, client: TestClient, db_session: Session, test_org: Org):
        """Test weak password is rejected during user creation"""
        response = client.post(
            "/admin/users",
            json={
                "email": "newuser@test.com",
                "name": "New User",
                "role": "OPS",
                "password": "weak"  # Too short, no special chars, etc.
            }
        )

        # Should fail validation
        assert response.status_code == 400
        assert "password" in response.json()["detail"].lower()

    def test_strong_password_accepted(self, client: TestClient, db_session: Session, test_org: Org, authenticated_client: TestClient):
        """Test strong password is accepted"""
        response = authenticated_client.post(
            "/admin/users",
            json={
                "email": "newuser@test.com",
                "name": "New User",
                "role": "OPS",
                "password": "SecureP@ss123"
            }
        )

        # Should succeed
        assert response.status_code in [200, 201]

    def test_password_not_returned_in_api_response(self, authenticated_client: TestClient, admin_user: User):
        """Test password hash is never returned in API responses"""
        response = authenticated_client.get("/users/me")

        assert response.status_code == 200
        data = response.json()

        # Password fields should not be present
        assert "password" not in data
        assert "password_hash" not in data


class TestAuditLogging:
    """Test authentication events are logged"""

    def test_failed_login_creates_audit_log(self, client: TestClient, db_session: Session, test_org: Org):
        """Test failed login attempt is logged"""
        from models.audit_log import AuditLog

        # Attempt failed login
        client.post(
            "/auth/login",
            json={
                "email": "nonexistent@test.com",
                "password": "AnyP@ss123"
            }
        )

        # Check audit log
        audit_entry = db_session.query(AuditLog).filter(
            AuditLog.event_type == "LOGIN_FAILED"
        ).first()

        assert audit_entry is not None
        assert "nonexistent@test.com" in audit_entry.event_data

    def test_successful_login_creates_audit_log(self, client: TestClient, db_session: Session, test_org: Org):
        """Test successful login is logged"""
        from models.audit_log import AuditLog

        # Create user
        password = "SecureP@ss123"
        user = User(
            org_id=test_org.id,
            email="ops@test.com",
            name="Ops User",
            role="OPS",
            password_hash=hash_password(password),
            status="ACTIVE"
        )
        db_session.add(user)
        db_session.commit()

        # Login
        client.post(
            "/auth/login",
            json={
                "email": "ops@test.com",
                "password": password
            }
        )

        # Check audit log
        audit_entry = db_session.query(AuditLog).filter(
            AuditLog.event_type == "LOGIN_SUCCESS",
            AuditLog.user_id == user.id
        ).first()

        assert audit_entry is not None
