"""FastAPI dependencies for authentication and authorization.

This module provides dependency injection functions for:
- Extracting and validating JWT tokens from requests
- Loading the current authenticated user
- Enforcing role-based access control (RBAC)

Usage:
    @app.get("/protected")
    def protected_endpoint(user: User = Depends(get_current_user)):
        return {"message": f"Hello {user.name}"}

    @app.get("/admin-only")
    def admin_endpoint(user: User = Depends(require_role(UserRole.ADMIN))):
        return {"message": "Admin access granted"}
"""

from typing import Callable, Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from uuid import UUID
import jwt

from database import get_db
from models.user import User
from .jwt import decode_token
from .roles import UserRole, has_permission


# HTTP Bearer token security scheme
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Extract and validate JWT token, returning the authenticated user.

    This dependency:
    1. Extracts Bearer token from Authorization header
    2. Validates token signature and expiration
    3. Loads user from database
    4. Checks user is ACTIVE (not DISABLED)
    5. Returns User object for use in endpoint

    Args:
        credentials: HTTP Bearer token from request header
        db: Database session

    Returns:
        User: The authenticated user object

    Raises:
        HTTPException 401: If token is missing, invalid, expired, or user not found
        HTTPException 403: If user status is DISABLED

    Example:
        @app.get("/me")
        def get_profile(user: User = Depends(get_current_user)):
            return {"id": user.id, "email": user.email}
    """
    token = credentials.credentials

    try:
        # Decode and validate JWT token
        payload = decode_token(token)

        # Extract user_id from token claims
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID claim",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id = UUID(user_id_str)

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token claims: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Load user from database
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check user status (SSOT §8.3: DISABLED users must not authenticate)
    if user.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    return user


def require_role(required_role: UserRole) -> Callable:
    """Create a dependency that enforces role-based access control.

    This factory function returns a dependency that checks if the current user
    has sufficient permissions based on role hierarchy. Higher roles inherit
    permissions from lower roles (e.g., ADMIN can do everything OPS can do).

    Role Hierarchy (descending permissions):
    - ADMIN > INTEGRATOR > OPS > VIEWER

    Args:
        required_role: Minimum role required to access the endpoint

    Returns:
        Callable: FastAPI dependency function that validates user role

    Raises:
        HTTPException 403: If user's role is insufficient

    Example:
        # Only ADMIN users can access
        @app.post("/users")
        def create_user(
            data: UserCreate,
            user: User = Depends(require_role(UserRole.ADMIN))
        ):
            ...

        # ADMIN, INTEGRATOR, and OPS can access (VIEWER cannot)
        @app.post("/orders/approve")
        def approve_order(
            user: User = Depends(require_role(UserRole.OPS))
        ):
            ...
    """

    def role_dependency(current_user: User = Depends(get_current_user)) -> User:
        """Validate that current user has required role permissions.

        Args:
            current_user: User object from get_current_user dependency

        Returns:
            User: The current user (if authorized)

        Raises:
            HTTPException 403: If user lacks required permissions
        """
        # Parse user's role from string to enum
        try:
            user_role = UserRole(current_user.role)
        except ValueError:
            # Invalid role in database (should never happen due to CHECK constraint)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Invalid user role: {current_user.role}",
            )

        # Check permissions using role hierarchy
        if not has_permission(user_role, required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role.value}",
            )

        return current_user

    return role_dependency


def get_current_admin(current_user: User = Depends(require_role(UserRole.ADMIN))) -> User:
    """Convenience dependency for ADMIN-only endpoints.

    Example:
        @app.delete("/users/{user_id}")
        def delete_user(user_id: UUID, admin: User = Depends(get_current_admin)):
            ...
    """
    return current_user


def get_current_ops_or_higher(current_user: User = Depends(require_role(UserRole.OPS))) -> User:
    """Convenience dependency for OPS+ endpoints (ADMIN, INTEGRATOR, OPS).

    Example:
        @app.post("/orders/approve")
        def approve_order(user: User = Depends(get_current_ops_or_higher)):
            ...
    """
    return current_user


# Type alias for dependency injection
CurrentUser = Annotated[User, Depends(get_current_user)]
