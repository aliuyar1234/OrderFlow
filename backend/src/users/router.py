"""User management endpoints (ADMIN only).

All endpoints in this router require ADMIN role. Users can:
- Create new users in their organization
- List users in their organization
- Get individual user details
- Update user details (name, role, status)

Email uniqueness is enforced per organization (UNIQUE constraint).
All mutations trigger audit log events.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from uuid import UUID
from typing import List

from ..database import get_db
from ..models.user import User
from ..models.org import Org
from ..auth.dependencies import require_role
from ..auth.roles import UserRole
from ..auth.password import hash_password
from ..auth.password_policy import check_password_strength, PasswordValidationError
from ..audit.service import log_from_request
from .schemas import UserCreate, UserUpdate, UserResponse, UserListResponse


router = APIRouter(prefix="/users", tags=["User Management"])


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user (ADMIN only)",
    description="Creates a new user in the current organization. Email must be unique per org."
)
def create_user(
    request: Request,
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
) -> UserResponse:
    """Create a new user (T030).

    Requirements:
    - ADMIN role required
    - Email must be unique per organization
    - Password must meet strength requirements (NIST SP 800-63B)
    - Audit event USER_CREATED logged

    Args:
        request: FastAPI request (for audit logging)
        data: User creation data
        db: Database session
        current_user: Current authenticated user (must be ADMIN)

    Returns:
        UserResponse: The created user (excludes password_hash)

    Raises:
        400: Password does not meet strength requirements
        409: Email already exists in organization
    """
    # Get org for password context validation
    org = db.query(Org).filter(Org.id == current_user.org_id).first()

    # Validate password strength with user context
    # Include email, name, and org name to prevent passwords containing user info
    try:
        check_password_strength(
            data.password,
            user_context=[
                data.email,
                data.name,
                org.name if org else None
            ]
        )
    except PasswordValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": e.message,
                "errors": e.errors
            }
        )

    # Check email uniqueness per org
    existing_user = db.query(User).filter(
        User.org_id == current_user.org_id,
        User.email == data.email.lower()
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email {data.email} already exists in organization"
        )

    # Hash password
    password_hash = hash_password(data.password)

    # Create user
    new_user = User(
        org_id=current_user.org_id,
        email=data.email.lower(),
        name=data.name,
        role=data.role,
        password_hash=password_hash,
        status="ACTIVE"
    )

    try:
        db.add(new_user)
        db.flush()

        # Log audit event
        log_from_request(
            db=db,
            request=request,
            org_id=current_user.org_id,
            action="USER_CREATED",
            actor_id=current_user.id,
            entity_type="user",
            entity_id=new_user.id,
            metadata={
                "email": new_user.email,
                "role": new_user.role
            }
        )

        db.commit()
        db.refresh(new_user)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User creation failed due to constraint violation"
        )

    return new_user


@router.get(
    "",
    response_model=UserListResponse,
    summary="List users in organization (ADMIN only)",
    description="Returns all users in the current user's organization."
)
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
) -> UserListResponse:
    """List all users in organization (T032).

    Args:
        db: Database session
        current_user: Current authenticated user (must be ADMIN)

    Returns:
        UserListResponse: List of users and total count
    """
    users = db.query(User).filter(
        User.org_id == current_user.org_id
    ).order_by(User.created_at.desc()).all()

    return UserListResponse(
        users=users,
        total=len(users)
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID (ADMIN only)",
    description="Returns a single user by ID. User must be in same organization."
)
def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
) -> UserResponse:
    """Get single user by ID (T033).

    Args:
        user_id: UUID of user to retrieve
        db: Database session
        current_user: Current authenticated user (must be ADMIN)

    Returns:
        UserResponse: The requested user

    Raises:
        404: User not found or in different organization
    """
    user = db.query(User).filter(
        User.id == user_id,
        User.org_id == current_user.org_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user (ADMIN only)",
    description="Updates user details. Triggers audit events for role/status changes."
)
def update_user(
    user_id: UUID,
    request: Request,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
) -> UserResponse:
    """Update user details (T031).

    Args:
        user_id: UUID of user to update
        request: FastAPI request (for audit logging)
        data: Update data (all fields optional)
        db: Database session
        current_user: Current authenticated user (must be ADMIN)

    Returns:
        UserResponse: The updated user

    Raises:
        404: User not found or in different organization
    """
    user = db.query(User).filter(
        User.id == user_id,
        User.org_id == current_user.org_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Track changes for audit logging
    changes = {}
    audit_events = []

    # Update name
    if data.name is not None:
        old_name = user.name
        user.name = data.name
        changes["name"] = {"old": old_name, "new": data.name}

    # Update role (triggers USER_ROLE_CHANGED audit event)
    if data.role is not None and data.role != user.role:
        old_role = user.role
        user.role = data.role
        changes["role"] = {"old": old_role, "new": data.role}

        audit_events.append({
            "action": "USER_ROLE_CHANGED",
            "metadata": {"old_role": old_role, "new_role": data.role}
        })

    # Update status (triggers USER_DISABLED audit event if disabled)
    if data.status is not None and data.status != user.status:
        old_status = user.status
        user.status = data.status
        changes["status"] = {"old": old_status, "new": data.status}

        if data.status == "DISABLED":
            audit_events.append({
                "action": "USER_DISABLED",
                "metadata": {"old_status": old_status, "new_status": data.status}
            })

    try:
        db.flush()

        # Log primary audit event
        if changes:
            log_from_request(
                db=db,
                request=request,
                org_id=current_user.org_id,
                action="USER_UPDATED",
                actor_id=current_user.id,
                entity_type="user",
                entity_id=user.id,
                metadata=changes
            )

        # Log specific audit events (role change, disabled)
        for event in audit_events:
            log_from_request(
                db=db,
                request=request,
                org_id=current_user.org_id,
                action=event["action"],
                actor_id=current_user.id,
                entity_type="user",
                entity_id=user.id,
                metadata=event["metadata"]
            )

        db.commit()
        db.refresh(user)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User update failed due to constraint violation"
        )

    return user
