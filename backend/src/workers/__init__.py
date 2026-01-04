"""Background workers module for async task processing.

This module provides base utilities and patterns for Celery background tasks
with multi-tenant isolation enforcement.

All background tasks MUST:
1. Accept org_id as explicit parameter (UUID string)
2. Validate org_id exists before processing
3. Use org_scoped_session for database access
4. Filter all queries by org_id

SSOT Reference: §11.2 (Background Job Isolation)
"""

from .base import (
    validate_org_id,
    get_scoped_session,
    BaseTask,
)

__all__ = [
    "validate_org_id",
    "get_scoped_session",
    "BaseTask",
]
