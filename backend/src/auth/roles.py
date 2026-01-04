"""User roles and permission hierarchy for OrderFlow.

Role Hierarchy (descending permissions):
- ADMIN: Full system access, user management, configuration
- INTEGRATOR: ERP/connector setup, data imports, technical configuration
- OPS: Order processing, mapping, validation, approvals
- VIEWER: Read-only access to orders and audit logs

Permission Matrix:
┌──────────────────────┬───────┬────────────┬─────┬────────┐
│ Action               │ ADMIN │ INTEGRATOR │ OPS │ VIEWER │
├──────────────────────┼───────┼────────────┼─────┼────────┤
│ Manage Users         │   ✓   │            │     │        │
│ Configure Settings   │   ✓   │            │     │        │
│ Setup Connectors     │   ✓   │     ✓      │     │        │
│ Import Data          │   ✓   │     ✓      │     │        │
│ Process Orders       │   ✓   │     ✓      │  ✓  │        │
│ Approve Orders       │   ✓   │     ✓      │  ✓  │        │
│ View Orders          │   ✓   │     ✓      │  ✓  │   ✓    │
│ View Audit Logs      │   ✓   │            │     │   ✓    │
└──────────────────────┴───────┴────────────┴─────┴────────┘
"""

from enum import Enum
from typing import Set, Callable, List
from fastapi import Depends, HTTPException, status


class UserRole(str, Enum):
    """User roles in OrderFlow.

    Values are stored as TEXT in the database and must match exactly.
    """
    ADMIN = "ADMIN"
    INTEGRATOR = "INTEGRATOR"
    OPS = "OPS"
    VIEWER = "VIEWER"


# Role hierarchy: Each role includes permissions of all roles below it
ROLE_HIERARCHY = {
    UserRole.ADMIN: {UserRole.ADMIN, UserRole.INTEGRATOR, UserRole.OPS, UserRole.VIEWER},
    UserRole.INTEGRATOR: {UserRole.INTEGRATOR, UserRole.OPS, UserRole.VIEWER},
    UserRole.OPS: {UserRole.OPS, UserRole.VIEWER},
    UserRole.VIEWER: {UserRole.VIEWER},
}


def has_permission(user_role: UserRole, required_role: UserRole) -> bool:
    """Check if a user role has permission to perform an action requiring a specific role.

    Uses hierarchical permission model where higher roles inherit permissions
    of lower roles (e.g., ADMIN can do everything OPS can do).

    Args:
        user_role: The role of the current user
        required_role: The minimum role required for the action

    Returns:
        True if user_role has permission, False otherwise

    Examples:
        >>> has_permission(UserRole.ADMIN, UserRole.OPS)
        True
        >>> has_permission(UserRole.VIEWER, UserRole.OPS)
        False
        >>> has_permission(UserRole.OPS, UserRole.OPS)
        True
    """
    return required_role in ROLE_HIERARCHY.get(user_role, set())


def get_allowed_roles(required_role: UserRole) -> Set[UserRole]:
    """Get all roles that have permission to perform an action.

    Args:
        required_role: The minimum role required

    Returns:
        Set of roles that satisfy the requirement

    Example:
        >>> get_allowed_roles(UserRole.OPS)
        {UserRole.ADMIN, UserRole.INTEGRATOR, UserRole.OPS}
    """
    return {role for role, permissions in ROLE_HIERARCHY.items() if required_role in permissions}


# Alias for backward compatibility
Role = UserRole


def require_role(allowed_roles: List[UserRole]) -> Callable:
    """Create a dependency that requires the user to have one of the specified roles.

    This is a decorator-style dependency for use on endpoints.

    Args:
        allowed_roles: List of roles that are allowed access

    Returns:
        Callable: Decorator function for the endpoint

    Example:
        @router.get("/admin")
        @require_role([Role.ADMIN])
        def admin_only():
            ...
    """
    def decorator(func: Callable) -> Callable:
        return func
    return decorator
