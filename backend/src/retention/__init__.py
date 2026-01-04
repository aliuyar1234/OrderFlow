"""Data retention and cleanup module.

Implements GDPR-compliant data retention policies with automatic cleanup.

This module provides:
- Retention policy configuration per organization
- Automatic soft-delete for expired documents
- Automatic hard-delete after grace period
- Manual deletion APIs for admin users
- Audit logging for all deletions

SSOT Reference: §11.5 (Data Retention), Spec 026-data-retention
"""

from .schemas import (
    RetentionSettings,
    RetentionStatistics,
    RetentionReport,
    RetentionSettingsUpdate,
)

# Service and tasks are imported lazily to avoid circular dependencies
# Use: from src.retention.service import RetentionService
# Use: from src.retention.tasks import retention_cleanup_task

__all__ = [
    "RetentionSettings",
    "RetentionStatistics",
    "RetentionReport",
    "RetentionSettingsUpdate",
]
