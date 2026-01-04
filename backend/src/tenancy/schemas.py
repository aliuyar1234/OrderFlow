"""Pydantic schemas for organization settings validation.

This module defines the complete OrgSettings schema stored in org.settings_json.
All settings have defaults and validation rules per SSOT §10.1.

Settings are stored as JSONB in PostgreSQL and validated via Pydantic before save.
Invalid settings updates are rejected with clear validation errors.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re


# ISO 4217 Currency Codes (major currencies for DACH region)
VALID_CURRENCIES = {
    "EUR", "CHF", "USD", "GBP", "PLN", "CZK", "HUF", "SEK", "NOK", "DKK"
}


class MatchingSettings(BaseModel):
    """SKU matching configuration.

    Controls automatic mapping behavior for customer SKU → internal SKU matching.
    """
    auto_apply_threshold: float = Field(
        default=0.92,
        ge=0.0,
        le=1.0,
        description="Confidence threshold for automatic mapping application (0.0-1.0)"
    )
    auto_apply_gap: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
        description="Minimum gap between top candidate and runner-up (0.0-1.0)"
    )


class CustomerDetectionSettings(BaseModel):
    """Customer detection configuration.

    Controls automatic customer selection behavior for draft orders.
    """
    auto_select_threshold: float = Field(
        default=0.90,
        ge=0.0,
        le=1.0,
        description="Confidence threshold for automatic customer selection (0.0-1.0)"
    )
    require_manual_review_if_multiple: bool = Field(
        default=True,
        description="Force manual review when multiple customer candidates exist"
    )


class AISettings(BaseModel):
    """AI provider and budget configuration.

    Controls LLM and embedding model usage, budget caps, and provider selection.
    Settings enable future AI features (specs 009-012) but are stored now.
    """
    llm_provider: str = Field(
        default="openai",
        description="LLM provider identifier (openai, anthropic, local)"
    )
    llm_model: str = Field(
        default="gpt-4o-mini",
        description="LLM model identifier"
    )
    llm_budget_daily_usd: float = Field(
        default=10.0,
        ge=0.0,
        description="Daily LLM budget cap in USD (non-negative)"
    )
    vision_enabled: bool = Field(
        default=True,
        description="Enable vision model for scanned/image-based PDFs"
    )
    vision_max_pages: int = Field(
        default=5,
        ge=1,
        description="Maximum pages to process with vision model"
    )
    embedding_provider: str = Field(
        default="openai",
        description="Embedding provider identifier (openai, local)"
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="Embedding model identifier"
    )


class ExtractionSettings(BaseModel):
    """Document extraction configuration.

    Controls rule-based vs LLM extraction strategy and thresholds.
    Settings enable future extraction features but are stored now.
    """
    min_text_coverage_for_rule: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Minimum text coverage ratio to attempt rule-based extraction (0.0-1.0)"
    )
    max_pages_rule_based: int = Field(
        default=10,
        ge=1,
        description="Maximum pages for rule-based extraction attempt"
    )
    llm_on_extraction_failure: bool = Field(
        default=True,
        description="Fallback to LLM if rule-based extraction fails"
    )


class RetentionSettings(BaseModel):
    """Data retention period configuration.

    Controls automatic cleanup of old data for GDPR compliance and storage management.
    All periods in days with min 30, max 3650 (10 years).
    """
    document_retention_days: int = Field(
        default=365,
        ge=30,
        le=3650,
        description="Document retention period in days (30-3650)"
    )
    ai_log_retention_days: int = Field(
        default=90,
        ge=30,
        le=3650,
        description="AI call log retention period in days (30-3650)"
    )
    feedback_event_retention_days: int = Field(
        default=365,
        ge=30,
        le=3650,
        description="Feedback event retention period in days (30-3650)"
    )
    draft_order_retention_days: int = Field(
        default=730,
        ge=30,
        le=3650,
        description="Draft order retention period in days (30-3650)"
    )
    inbound_message_retention_days: int = Field(
        default=90,
        ge=30,
        le=3650,
        description="Inbound message retention period in days (30-3650)"
    )
    soft_delete_grace_period_days: int = Field(
        default=90,
        ge=1,
        le=365,
        description="Grace period before hard-deleting soft-deleted records (1-365)"
    )


class OrgSettings(BaseModel):
    """Complete organization settings schema (SSOT §10.1).

    Stored in org.settings_json JSONB column. Provides tenant-specific configuration
    without requiring schema migrations.

    All nested settings have defaults, so an empty {} is valid and will be populated
    with defaults on read. PATCH updates are deep-merged with existing settings.

    Validation Rules:
    - default_currency must be ISO 4217 code (EUR, CHF, USD, etc.)
    - price_tolerance_percent must be >= 0.0
    - All threshold values must be 0.0 <= x <= 1.0
    - All budget values must be >= 0.0
    - All max_pages/count values must be >= 1
    """
    default_currency: str = Field(
        default="EUR",
        description="ISO 4217 currency code for pricing and validation"
    )
    price_tolerance_percent: float = Field(
        default=5.0,
        ge=0.0,
        description="Acceptable price deviation percentage for validation (non-negative)"
    )
    require_unit_price: bool = Field(
        default=False,
        description="Require unit price in extracted orders (strict mode)"
    )

    # Nested configuration objects (all have defaults)
    matching: MatchingSettings = Field(
        default_factory=MatchingSettings,
        description="SKU matching behavior settings"
    )
    customer_detection: CustomerDetectionSettings = Field(
        default_factory=CustomerDetectionSettings,
        description="Customer detection behavior settings"
    )
    ai: AISettings = Field(
        default_factory=AISettings,
        description="AI provider and budget configuration"
    )
    extraction: ExtractionSettings = Field(
        default_factory=ExtractionSettings,
        description="Document extraction strategy settings"
    )
    retention: RetentionSettings = Field(
        default_factory=RetentionSettings,
        description="Data retention and cleanup settings"
    )

    @field_validator('default_currency')
    @classmethod
    def validate_currency_code(cls, v: str) -> str:
        """Validate ISO 4217 currency code.

        Accepts major currencies for DACH region. Can be extended as needed.

        Raises:
            ValueError: If currency code is not in allowed list
        """
        v_upper = v.upper()
        if v_upper not in VALID_CURRENCIES:
            raise ValueError(
                f"Invalid currency code '{v}'. Must be one of: {', '.join(sorted(VALID_CURRENCIES))}"
            )
        return v_upper


class OrgSettingsUpdate(BaseModel):
    """Schema for partial settings updates (PATCH /org/settings).

    All fields optional. Deep merge with existing settings:
    - Provided fields override existing values
    - Omitted fields keep current values
    - Nested objects are merged, not replaced entirely

    Example:
        Current: {"matching": {"auto_apply_threshold": 0.92, "auto_apply_gap": 0.10}}
        Update:  {"matching": {"auto_apply_threshold": 0.95}}
        Result:  {"matching": {"auto_apply_threshold": 0.95, "auto_apply_gap": 0.10}}
    """
    default_currency: Optional[str] = Field(
        None,
        description="ISO 4217 currency code"
    )
    price_tolerance_percent: Optional[float] = Field(
        None,
        ge=0.0,
        description="Price deviation tolerance (non-negative)"
    )
    require_unit_price: Optional[bool] = Field(
        None,
        description="Require unit price in orders"
    )

    # Nested updates (partial)
    matching: Optional[MatchingSettings] = None
    customer_detection: Optional[CustomerDetectionSettings] = None
    ai: Optional[AISettings] = None
    extraction: Optional[ExtractionSettings] = None
    retention: Optional[RetentionSettings] = None

    @field_validator('default_currency')
    @classmethod
    def validate_currency_code(cls, v: Optional[str]) -> Optional[str]:
        """Validate currency code if provided."""
        if v is None:
            return None
        v_upper = v.upper()
        if v_upper not in VALID_CURRENCIES:
            raise ValueError(
                f"Invalid currency code '{v}'. Must be one of: {', '.join(sorted(VALID_CURRENCIES))}"
            )
        return v_upper
