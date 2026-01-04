"""Tenancy module - Multi-tenant isolation and org settings management.

This module provides:
- Automatic org_id filtering for all database queries
- Org settings schema validation and management
- Tenant scoping utilities for API and background jobs
- Cross-tenant access prevention (404, not 403)

SSOT Reference: §5.1, §10.1, §11.2
"""

from .schemas import (
    OrgSettings,
    MatchingSettings,
    CustomerDetectionSettings,
    AISettings,
    ExtractionSettings,
)

__all__ = [
    "OrgSettings",
    "MatchingSettings",
    "CustomerDetectionSettings",
    "AISettings",
    "ExtractionSettings",
]
