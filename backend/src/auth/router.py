"""Authentication endpoints for OrderFlow API

Provides endpoints for user login and retrieving current user information.
"""

from datetime import datetime, timezone
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import and_

from database import get_db
from models.user import User
from models.org import Org
from .schemas import LoginRequest, LoginResponse, MeResponse, UserResponse
from .password import verify_password
from .jwt import create_access_token, _get_jwt_expiry_minutes
from .dependencies import CurrentUser
from audit.service import log_audit_event
from .rate_limit import check_rate_limit, rate_limiter


router = APIRouter(prefix="/auth", tags=["Authentication"])


def _get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP address from request.

    Args:
        request: FastAPI request object

    Returns:
        Optional[str]: Client IP address or None
    """
    # Check X-Forwarded-For header first (for proxies)
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        return forwarded.split(',')[0].strip()

    # Fall back to direct client host
    if request.client:
        return request.client.host

    return None


def _get_user_agent(request: Request) -> Optional[str]:
    """Extract User-Agent from request.

    Args:
        request: FastAPI request object

    Returns:
        Optional[str]: User agent string or None
    """
    return request.headers.get('User-Agent')


@router.post("/login", response_model=LoginResponse)
async def login(
    credentials: LoginRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    _: None = Depends(check_rate_limit)
):
    """Authenticate user and return JWT access token.

    This endpoint validates user credentials and returns a JWT token for
    authenticated requests. It enforces multi-tenant isolation by requiring
    org_slug and validates that the user belongs to that organization.

    Security measures:
    - Rate limiting to prevent brute force attacks (5 attempts per 15 min)
    - Account lockout after 10 failed attempts (30 min lockout)
    - Constant-time password verification to prevent timing attacks
    - Failed login attempts are logged to audit_log
    - Disabled accounts are rejected
    - last_login_at is updated on successful login

    Args:
        credentials: Login credentials (org_slug, email, password)
        request: FastAPI request object for IP/user-agent
        db: Database session

    Returns:
        LoginResponse: JWT access token and metadata

    Raises:
        HTTPException: 401 if credentials are invalid or account is disabled
        HTTPException: 429 if rate limit exceeded or account locked out
    """
    # Step 1: Look up organization by slug
    org = db.query(Org).filter(Org.slug == credentials.org_slug).first()
    if not org:
        # Cannot log to audit_log without org_id, so we skip logging
        # In production, consider logging to a separate security log
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"  # Generic message to prevent enumeration
        )

    # Step 2: Look up user by org_id and email
    user = db.query(User).filter(
        and_(
            User.org_id == org.id,
            User.email == credentials.email
        )
    ).first()

    # Step 3: Verify password (constant-time to prevent timing attacks)
    if not user or not verify_password(credentials.password, user.password_hash):
        # Log failed login
        log_audit_event(
            db=db,
            org_id=org.id,
            action="LOGIN_FAILED",
            metadata={"email": credentials.email, "reason": "invalid_credentials"},
            ip_address=_get_client_ip(request),
            user_agent=_get_user_agent(request)
        )

        # Record failed login attempt for rate limiting
        rate_limiter.record_failed_login(credentials.email, credentials.org_slug, request)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Step 4: Check if user is disabled (T022)
    if user.status == 'DISABLED':
        # Log failed login for disabled account
        log_audit_event(
            db=db,
            org_id=org.id,
            actor_id=user.id,
            action="LOGIN_FAILED",
            metadata={"email": credentials.email, "reason": "account_disabled"},
            ip_address=_get_client_ip(request),
            user_agent=_get_user_agent(request)
        )

        # Record failed login attempt for rate limiting
        rate_limiter.record_failed_login(credentials.email, credentials.org_slug, request)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled"
        )

    # Step 5: Update last_login_at (T020)
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    # Step 6: Clear failed login attempts on successful login
    rate_limiter.clear_failed_attempts(credentials.email, credentials.org_slug)

    # Step 7: Log successful login (T021)
    log_audit_event(
        db=db,
        org_id=org.id,
        actor_id=user.id,
        action="LOGIN_SUCCESS",
        metadata={"email": credentials.email},
        ip_address=_get_client_ip(request),
        user_agent=_get_user_agent(request)
    )

    # Step 8: Generate JWT token
    access_token = create_access_token(
        user_id=user.id,
        org_id=user.org_id,
        role=user.role,
        email=user.email
    )

    expiry_minutes = _get_jwt_expiry_minutes()

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expiry_minutes * 60  # Convert minutes to seconds
    )


@router.get("/me", response_model=MeResponse)
async def get_me(
    current_user: CurrentUser
):
    """Get current authenticated user information.

    This endpoint returns the profile information for the currently
    authenticated user based on the JWT token in the Authorization header.

    Args:
        current_user: Current authenticated user from JWT token

    Returns:
        MeResponse: Current user information (excludes password_hash)
    """
    return MeResponse(
        user=UserResponse.model_validate(current_user)
    )
