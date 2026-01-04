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
from typing import Set


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
