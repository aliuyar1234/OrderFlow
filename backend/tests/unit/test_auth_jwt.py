"""Unit tests for JWT token generation and validation

Tests cover:
- Token creation with valid claims
- Token decoding and validation
- Token expiration handling
- Invalid token handling
- Environment configuration

SSOT Reference: §8.3 (JWT Authentication)
"""

import pytest
import os
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import jwt

import sys
from pathlib import Path
backend_src = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(backend_src))

from auth.jwt import create_access_token, decode_token


class TestCreateAccessToken:
    """Test JWT token creation"""

    def test_create_token_with_valid_claims(self, monkeypatch):
        """Test creating token with all required claims"""
        monkeypatch.setenv('JWT_SECRET', 'test-secret-key-256-bits-minimum-length-required-for-security')
        monkeypatch.setenv('JWT_EXPIRY_MINUTES', '60')

        user_id = uuid4()
        org_id = uuid4()
        role = "ADMIN"
        email = "admin@test.com"

        token = create_access_token(
            user_id=user_id,
            org_id=org_id,
            role=role,
            email=email
        )

        # Token should be a non-empty string
        assert isinstance(token, str)
        assert len(token) > 0

        # Token should have 3 parts (header.payload.signature)
        parts = token.split('.')
        assert len(parts) == 3

    def test_token_contains_correct_claims(self, monkeypatch):
        """Test token payload contains all expected claims"""
        monkeypatch.setenv('JWT_SECRET', 'test-secret-key-256-bits-minimum-length-required-for-security')

        user_id = uuid4()
        org_id = uuid4()
        role = "OPS"
        email = "ops@test.com"

        token = create_access_token(
            user_id=user_id,
            org_id=org_id,
            role=role,
            email=email
        )

        # Decode without verification to inspect payload
        payload = jwt.decode(token, options={"verify_signature": False})

        assert payload['sub'] == str(user_id)
        assert payload['org_id'] == str(org_id)
        assert payload['role'] == role
        assert payload['email'] == email
        assert 'iat' in payload
        assert 'exp' in payload

    def test_token_expiration_time(self, monkeypatch):
        """Test token expires after configured time"""
        monkeypatch.setenv('JWT_SECRET', 'test-secret-key-256-bits-minimum-length-required-for-security')
        monkeypatch.setenv('JWT_EXPIRY_MINUTES', '30')

        user_id = uuid4()
        org_id = uuid4()

        before = datetime.now(timezone.utc)
        token = create_access_token(
            user_id=user_id,
            org_id=org_id,
            role="ADMIN",
            email="test@test.com"
        )
        after = datetime.now(timezone.utc)

        payload = jwt.decode(token, options={"verify_signature": False})

        # Check exp is approximately 30 minutes from now
        # Allow 5 second tolerance for test execution time
        exp_time = datetime.fromtimestamp(payload['exp'], tz=timezone.utc)
        expected_exp = before + timedelta(minutes=30)
        time_diff = abs((exp_time - expected_exp).total_seconds())
        assert time_diff < 5, f'Expected expiry around 30 min from now, got diff of {time_diff}s'


    def test_token_issued_at_time(self, monkeypatch):
        """Test token iat claim is set to current time"""
        monkeypatch.setenv('JWT_SECRET', 'test-secret-key-256-bits-minimum-length-required-for-security')

        user_id = uuid4()
        org_id = uuid4()

        before = int(datetime.now(timezone.utc).timestamp())
        token = create_access_token(
            user_id=user_id,
            org_id=org_id,
            role="ADMIN",
            email="test@test.com"
        )
        after = int(datetime.now(timezone.utc).timestamp())

        payload = jwt.decode(token, options={"verify_signature": False})

        # iat should be between before and after
        assert before <= payload['iat'] <= after

    def test_token_uses_hs256_algorithm(self, monkeypatch):
        """Test token is signed with HS256 algorithm"""
        monkeypatch.setenv('JWT_SECRET', 'test-secret-key-256-bits-minimum-length-required-for-security')

        user_id = uuid4()
        org_id = uuid4()

        token = create_access_token(
            user_id=user_id,
            org_id=org_id,
            role="ADMIN",
            email="test@test.com"
        )

        # Decode header to check algorithm
        header = jwt.get_unverified_header(token)
        assert header['alg'] == 'HS256'

    def test_create_token_without_secret_raises_error(self, monkeypatch):
        """Test creating token without JWT_SECRET raises ValueError"""
        # Unset JWT_SECRET
        monkeypatch.delenv('JWT_SECRET', raising=False)

        user_id = uuid4()
        org_id = uuid4()

        with pytest.raises(ValueError, match="JWT_SECRET environment variable is not set"):
            create_access_token(
                user_id=user_id,
                org_id=org_id,
                role="ADMIN",
                email="test@test.com"
            )

    def test_create_token_with_custom_expiry(self, monkeypatch):
        """Test token expiry respects JWT_EXPIRY_MINUTES env var"""
        monkeypatch.setenv('JWT_SECRET', 'test-secret-key-256-bits-minimum-length-required-for-security')
        monkeypatch.setenv('JWT_EXPIRY_MINUTES', '120')  # 2 hours

        user_id = uuid4()
        org_id = uuid4()

        before = datetime.now(timezone.utc)
        token = create_access_token(
            user_id=user_id,
            org_id=org_id,
            role="ADMIN",
            email="test@test.com"
        )
        after = datetime.now(timezone.utc)

        payload = jwt.decode(token, options={"verify_signature": False})
        exp_time = datetime.fromtimestamp(payload['exp'], tz=timezone.utc)

        # Allow 5 second tolerance for test execution time
        expected_exp = before + timedelta(minutes=120)
        time_diff = abs((exp_time - expected_exp).total_seconds())
        assert time_diff < 5, f'Expected expiry around 120 min from now, got diff of {time_diff}s'


    def test_create_token_with_invalid_expiry_defaults_to_60(self, monkeypatch):
        """Test invalid JWT_EXPIRY_MINUTES falls back to 60 minutes"""
        monkeypatch.setenv('JWT_SECRET', 'test-secret-key-256-bits-minimum-length-required-for-security')
        monkeypatch.setenv('JWT_EXPIRY_MINUTES', 'invalid')

        user_id = uuid4()
        org_id = uuid4()

        before = datetime.now(timezone.utc)
        token = create_access_token(
            user_id=user_id,
            org_id=org_id,
            role="ADMIN",
            email="test@test.com"
        )

        payload = jwt.decode(token, options={"verify_signature": False})
        exp_time = datetime.fromtimestamp(payload['exp'], tz=timezone.utc)

        # Should default to 60 minutes
        expected_exp = before + timedelta(minutes=60)
        time_diff = abs((exp_time - expected_exp).total_seconds())
        assert time_diff < 2  # Allow 2 second tolerance


class TestDecodeToken:
    """Test JWT token decoding and validation"""

    def test_decode_valid_token(self, monkeypatch):
        """Test decoding a valid token returns correct claims"""
        secret = 'test-secret-key-256-bits-minimum-length-required-for-security'
        monkeypatch.setenv('JWT_SECRET', secret)

        user_id = uuid4()
        org_id = uuid4()
        role = "ADMIN"
        email = "admin@test.com"

        token = create_access_token(
            user_id=user_id,
            org_id=org_id,
            role=role,
            email=email
        )

        payload = decode_token(token)

        assert payload['sub'] == str(user_id)
        assert payload['org_id'] == str(org_id)
        assert payload['role'] == role
        assert payload['email'] == email

    def test_decode_expired_token_raises_error(self, monkeypatch):
        """Test decoding expired token raises ExpiredSignatureError"""
        secret = 'test-secret-key-256-bits-minimum-length-required-for-security'
        monkeypatch.setenv('JWT_SECRET', secret)

        # Create token that expires immediately
        user_id = uuid4()
        org_id = uuid4()

        # Manually create expired token
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=10)

        payload = {
            'sub': str(user_id),
            'org_id': str(org_id),
            'role': 'ADMIN',
            'email': 'test@test.com',
            'iat': int(past.timestamp()),
            'exp': int(past.timestamp())  # Already expired
        }

        expired_token = jwt.encode(payload, secret, algorithm='HS256')

        with pytest.raises(jwt.ExpiredSignatureError, match="Token has expired"):
            decode_token(expired_token)

    def test_decode_token_with_invalid_signature(self, monkeypatch):
        """Test decoding token with wrong signature raises error"""
        secret = 'test-secret-key-256-bits-minimum-length-required-for-security'
        wrong_secret = 'wrong-secret-key'
        monkeypatch.setenv('JWT_SECRET', wrong_secret)

        user_id = uuid4()
        org_id = uuid4()

        # Create token with one secret
        token = jwt.encode(
            {
                'sub': str(user_id),
                'org_id': str(org_id),
                'role': 'ADMIN',
                'email': 'test@test.com',
                'iat': int(datetime.now(timezone.utc).timestamp()),
                'exp': int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
            },
            secret,
            algorithm='HS256'
        )

        # Try to decode with different secret
        with pytest.raises(jwt.InvalidTokenError):
            decode_token(token)

    def test_decode_malformed_token(self, monkeypatch):
        """Test decoding malformed token raises error"""
        monkeypatch.setenv('JWT_SECRET', 'test-secret-key-256-bits-minimum-length-required-for-security')

        malformed_tokens = [
            "not.a.token",
            "invalid-token",
            "",
            "header.payload",  # Missing signature
            "a.b.c.d",  # Too many parts
        ]

        for token in malformed_tokens:
            with pytest.raises(jwt.InvalidTokenError):
                decode_token(token)

    def test_decode_token_with_missing_claims(self, monkeypatch):
        """Test decoding token with missing required claims still succeeds (validation is caller's responsibility)"""
        secret = 'test-secret-key-256-bits-minimum-length-required-for-security'
        monkeypatch.setenv('JWT_SECRET', secret)

        # Create token with minimal claims
        token = jwt.encode(
            {
                'sub': str(uuid4()),
                'iat': int(datetime.now(timezone.utc).timestamp()),
                'exp': int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
            },
            secret,
            algorithm='HS256'
        )

        # Should decode successfully (missing org_id, role, email)
        payload = decode_token(token)
        assert 'sub' in payload
        assert 'org_id' not in payload  # Missing custom claim

    def test_decode_token_without_secret_raises_error(self, monkeypatch):
        """Test decoding token without JWT_SECRET raises ValueError"""
        monkeypatch.delenv('JWT_SECRET', raising=False)

        token = "any.token.here"

        with pytest.raises(ValueError, match="JWT_SECRET environment variable is not set"):
            decode_token(token)

    def test_token_cannot_be_tampered(self, monkeypatch):
        """Test tampering with token payload invalidates signature"""
        secret = 'test-secret-key-256-bits-minimum-length-required-for-security'
        monkeypatch.setenv('JWT_SECRET', secret)

        user_id = uuid4()
        org_id = uuid4()

        token = create_access_token(
            user_id=user_id,
            org_id=org_id,
            role="VIEWER",
            email="viewer@test.com"
        )

        # Try to tamper with the token by changing role from VIEWER to ADMIN
        parts = token.split('.')
        import base64
        import json

        # Decode payload
        payload_bytes = base64.urlsafe_b64decode(parts[1] + '==')
        payload = json.loads(payload_bytes)

        # Tamper: change role
        payload['role'] = 'ADMIN'

        # Re-encode payload
        tampered_payload = base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).decode().rstrip('=')

        # Reconstruct token with tampered payload but original signature
        tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"

        # Decoding should fail due to signature mismatch
        with pytest.raises(jwt.InvalidTokenError):
            decode_token(tampered_token)


class TestTokenRolePermissions:
    """Test tokens for different roles"""

    @pytest.mark.parametrize("role", ["ADMIN", "INTEGRATOR", "OPS", "VIEWER"])
    def test_create_token_for_all_roles(self, role, monkeypatch):
        """Test token creation for all valid roles"""
        monkeypatch.setenv('JWT_SECRET', 'test-secret-key-256-bits-minimum-length-required-for-security')

        user_id = uuid4()
        org_id = uuid4()

        token = create_access_token(
            user_id=user_id,
            org_id=org_id,
            role=role,
            email=f"{role.lower()}@test.com"
        )

        payload = decode_token(token)
        assert payload['role'] == role

    def test_token_preserves_email_case(self, monkeypatch):
        """Test email in token preserves original case"""
        monkeypatch.setenv('JWT_SECRET', 'test-secret-key-256-bits-minimum-length-required-for-security')

        user_id = uuid4()
        org_id = uuid4()
        email = "Test.User@Example.COM"

        token = create_access_token(
            user_id=user_id,
            org_id=org_id,
            role="OPS",
            email=email
        )

        payload = decode_token(token)
        assert payload['email'] == email  # Case preserved
