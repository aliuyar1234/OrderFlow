"""Pydantic schemas for org entity and settings validation"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from uuid import UUID
import re

# Import settings schemas from tenancy module
from ..tenancy.schemas import (
    OrgSettings,
    MatchingSettings,
    CustomerDetectionSettings,
    AISettings,
    ExtractionSettings,
)


# =============================================================================
# API Schemas
# =============================================================================

class OrgBase(BaseModel):
    """Base schema with common org fields"""
    name: str = Field(..., min_length=1, max_length=200, description="Organization name")
    slug: str = Field(..., min_length=2, max_length=100, description="URL-friendly identifier")

    @field_validator('slug')
    @classmethod
    def validate_slug_pattern(cls, v: str) -> str:
        """Ensure slug matches ^[a-z0-9-]+$ pattern"""
        if not re.match(r'^[a-z0-9-]+$', v):
            raise ValueError(
                "Slug must contain only lowercase letters, numbers, and hyphens"
            )
        return v

    @field_validator('name')
    @classmethod
    def validate_name_not_empty(cls, v: str) -> str:
        """Ensure name is not whitespace-only"""
        if not v.strip():
            raise ValueError("Organization name cannot be empty or whitespace")
        return v.strip()


class OrgCreate(OrgBase):
    """Schema for creating a new organization"""
    settings_json: Optional[OrgSettings] = Field(
        default_factory=OrgSettings,
        description="Organization-specific settings (defaults if not provided)"
    )


class OrgUpdate(BaseModel):
    """Schema for updating an organization (all fields optional)"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    slug: Optional[str] = Field(None, min_length=2, max_length=100)
    settings_json: Optional[OrgSettings] = None

    @field_validator('slug')
    @classmethod
    def validate_slug_pattern(cls, v: Optional[str]) -> Optional[str]:
        """Ensure slug matches ^[a-z0-9-]+$ pattern if provided"""
        if v is not None and not re.match(r'^[a-z0-9-]+$', v):
            raise ValueError(
                "Slug must contain only lowercase letters, numbers, and hyphens"
            )
        return v

    @field_validator('name')
    @classmethod
    def validate_name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        """Ensure name is not whitespace-only if provided"""
        if v is not None and not v.strip():
            raise ValueError("Organization name cannot be empty or whitespace")
        return v.strip() if v is not None else None


class OrgRead(OrgBase):
    """Schema for reading organization data"""
    id: UUID
    settings_json: OrgSettings
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
