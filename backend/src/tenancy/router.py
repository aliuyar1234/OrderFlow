"""FastAPI router for organization settings management.

This module provides endpoints for:
- GET /org/settings - Retrieve current organization settings
- PATCH /org/settings - Update organization settings (ADMIN only)

Settings are stored in org.settings_json JSONB column and validated against
OrgSettings Pydantic schema. Partial updates are deep-merged with existing settings.

SSOT Reference: §10.1 (Org Settings), §11.2 (Multi-Tenant Isolation)
"""

from typing import Any, Dict
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import ValidationError

from ..database import get_db
from ..dependencies import get_org_id
from ..auth.dependencies import get_current_user, require_role
from ..auth.roles import UserRole
from ..models.user import User
from ..models.org import Org
from .schemas import OrgSettings, OrgSettingsUpdate


router = APIRouter(prefix="/org", tags=["Organization Settings"])


def deep_merge(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries, with update values taking precedence.

    Nested dictionaries are merged recursively. Lists and other values are replaced.

    Args:
        base: Base dictionary (existing values)
        update: Update dictionary (new values)

    Returns:
        Dict: Merged dictionary

    Example:
        base = {"a": 1, "b": {"c": 2, "d": 3}}
        update = {"b": {"c": 99}}
        result = deep_merge(base, update)
        # result = {"a": 1, "b": {"c": 99, "d": 3}}
    """
    result = base.copy()

    for key, value in update.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dicts
            result[key] = deep_merge(result[key], value)
        else:
            # Replace value (including lists, primitives, etc.)
            result[key] = value

    return result


@router.get("/settings", response_model=OrgSettings)
def get_org_settings(
    org_id: UUID = Depends(get_org_id),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> OrgSettings:
    """Retrieve current organization settings.

    Returns the organization's settings_json with defaults applied for missing values.
    If settings_json is empty ({}), returns all defaults per OrgSettings schema.

    Available to all authenticated users within the organization.

    Args:
        org_id: Organization ID from JWT token (automatic)
        db: Database session
        current_user: Authenticated user (any role)

    Returns:
        OrgSettings: Complete organization settings with defaults

    Raises:
        HTTPException 404: If organization not found
        HTTPException 401: If user not authenticated

    Example Response:
        {
            "default_currency": "EUR",
            "price_tolerance_percent": 5.0,
            "require_unit_price": false,
            "matching": {
                "auto_apply_threshold": 0.92,
                "auto_apply_gap": 0.10
            },
            "customer_detection": {
                "auto_select_threshold": 0.90,
                "require_manual_review_if_multiple": true
            },
            "ai": {
                "llm_provider": "openai",
                "llm_model": "gpt-4o-mini",
                "llm_budget_daily_usd": 10.0,
                "vision_enabled": true,
                "vision_max_pages": 5,
                "embedding_provider": "openai",
                "embedding_model": "text-embedding-3-small"
            },
            "extraction": {
                "min_text_coverage_for_rule": 0.8,
                "max_pages_rule_based": 10,
                "llm_on_extraction_failure": true
            }
        }
    """
    # Fetch organization
    org = db.query(Org).filter(Org.id == org_id).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    # Parse settings_json with defaults
    # If settings_json is empty {}, Pydantic applies all defaults
    try:
        settings = OrgSettings(**org.settings_json)
    except ValidationError as e:
        # Should not happen if data is valid, but handle gracefully
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Invalid settings in database: {str(e)}"
        )

    return settings


@router.patch("/settings", response_model=Dict[str, Any])
def update_org_settings(
    settings_update: OrgSettingsUpdate,
    org_id: UUID = Depends(get_org_id),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_role(UserRole.ADMIN))
) -> Dict[str, Any]:
    """Update organization settings (ADMIN only).

    Performs a deep merge of provided settings with existing settings.
    Only provided fields are updated; omitted fields retain current values.

    Validates the merged settings against OrgSettings schema before saving.
    Changes take effect immediately (no caching).

    Args:
        settings_update: Partial settings update (all fields optional)
        org_id: Organization ID from JWT token (automatic)
        db: Database session
        admin_user: Authenticated ADMIN user

    Returns:
        Dict with message and updated settings

    Raises:
        HTTPException 403: If user is not ADMIN
        HTTPException 404: If organization not found
        HTTPException 422: If validation fails (invalid currency, negative values, etc.)

    Example Request:
        PATCH /org/settings
        {
            "default_currency": "CHF",
            "matching": {
                "auto_apply_threshold": 0.95
            }
        }

    Example Response:
        {
            "message": "Settings updated successfully",
            "settings": {
                "default_currency": "CHF",
                "price_tolerance_percent": 5.0,
                "matching": {
                    "auto_apply_threshold": 0.95,
                    "auto_apply_gap": 0.10
                },
                ...
            }
        }
    """
    # Fetch organization
    org = db.query(Org).filter(Org.id == org_id).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    # Get current settings with defaults
    try:
        current_settings = OrgSettings(**org.settings_json)
    except ValidationError:
        # If current settings are invalid, start from defaults
        current_settings = OrgSettings()

    # Convert current settings to dict for merging
    current_dict = current_settings.model_dump()

    # Convert update to dict, excluding None values (only merge provided fields)
    update_dict = settings_update.model_dump(exclude_none=True)

    # Deep merge update into current settings
    merged_dict = deep_merge(current_dict, update_dict)

    # Validate merged settings against full schema
    try:
        validated_settings = OrgSettings(**merged_dict)
    except ValidationError as e:
        # Return validation errors to client
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid settings: {str(e)}"
        )

    # Save to database (convert to dict for JSONB storage)
    org.settings_json = validated_settings.model_dump()
    db.commit()
    db.refresh(org)

    return {
        "message": "Settings updated successfully",
        "settings": validated_settings.model_dump()
    }
