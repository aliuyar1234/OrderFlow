"""JWT token generation and validation

This module handles JWT access token creation and validation for authentication.
Tokens include user_id, org_id, role, and email claims with configurable TTL.

JWT Token Claims Structure (§8.3):
====================================

Standard JWT Claims:
- sub (Subject): User ID as UUID string
  Example: "550e8400-e29b-41d4-a716-446655440000"
  Purpose: Identifies the user this token belongs to

- iat (Issued At): Unix timestamp when token was created
  Example: 1704368400
  Purpose: Track token creation time for audit/debugging

- exp (Expiration): Unix timestamp when token expires
  Example: 1704372000 (iat + JWT_EXPIRY_MINUTES)
  Purpose: Enforce token lifetime (default 60 minutes)

Custom Claims (OrderFlow-specific):
- org_id: Organization (tenant) ID as UUID string
  Example: "7c9e6679-7425-40de-944b-e07fc1f90ae7"
  Purpose: Multi-tenant isolation - every API call filters by this org_id

- role: User's role within the organization
  Values: "ADMIN" | "INTEGRATOR" | "OPS" | "VIEWER"
  Purpose: Role-based access control (RBAC) enforcement

- email: User's email address (case-insensitive)
  Example: "ops@acme.de"
  Purpose: Display in UI, audit logging, user identification

Security Properties:
- Algorithm: HS256 (HMAC-SHA256 symmetric signing)
- Secret: JWT_SECRET environment variable (minimum 256 bits)
- No refresh tokens in MVP (re-login after expiry)
- Stateless validation (no database lookup required for auth)
- Token tamper-proof (signature validation fails if claims modified)

Example Token Payload:
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",
  "org_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "role": "OPS",
  "email": "ops@acme.de",
  "iat": 1704368400,
  "exp": 1704372000
}
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from uuid import UUID
import jwt


def _get_jwt_secret() -> str:
    """Get JWT_SECRET from environment.

    Returns:
        str: The JWT_SECRET value

    Raises:
        ValueError: If JWT_SECRET is not set
    """
    secret = os.getenv('JWT_SECRET')
    if not secret:
        raise ValueError("JWT_SECRET environment variable is not set")
    return secret


def _get_jwt_expiry_minutes() -> int:
    """Get JWT_EXPIRY_MINUTES from environment.

    Returns:
        int: The JWT expiry in minutes (default: 60)
    """
    expiry = os.getenv('JWT_EXPIRY_MINUTES', '60')
    try:
        return int(expiry)
    except ValueError:
        return 60


def create_access_token(
    user_id: UUID,
    org_id: UUID,
    role: str,
    email: str
) -> str:
    """Create a JWT access token for an authenticated user.

    Args:
        user_id: User's UUID
        org_id: Organization's UUID
        role: User's role (ADMIN, INTEGRATOR, OPS, VIEWER)
        email: User's email address

    Returns:
        str: Signed JWT token

    Raises:
        ValueError: If JWT_SECRET is not set
    """
    secret = _get_jwt_secret()
    expiry_minutes = _get_jwt_expiry_minutes()

    now = datetime.now(timezone.utc)
    expiration = now + timedelta(minutes=expiry_minutes)

    payload = {
        'sub': str(user_id),  # Subject: user ID
        'org_id': str(org_id),
        'role': role,
        'email': email,
        'iat': int(now.timestamp()),  # Issued at
        'exp': int(expiration.timestamp())  # Expiration
    }

    token = jwt.encode(payload, secret, algorithm='HS256')
    return token


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT token.

    Args:
        token: JWT token string

    Returns:
        dict: Decoded token payload with claims

    Raises:
        jwt.ExpiredSignatureError: If token has expired
        jwt.InvalidTokenError: If token is invalid or tampered
        ValueError: If JWT_SECRET is not set
    """
    secret = _get_jwt_secret()

    try:
        payload = jwt.decode(token, secret, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        raise jwt.ExpiredSignatureError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise jwt.InvalidTokenError(f"Invalid token: {str(e)}")
