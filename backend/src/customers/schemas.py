"""Pydantic schemas for customer management"""

from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional
from uuid import UUID
from datetime import datetime


# ISO 4217 currency codes (common ones for DACH region + major currencies)
VALID_CURRENCIES = {
    'EUR', 'USD', 'CHF', 'GBP', 'JPY', 'CAD', 'AUD', 'NZD',
    'SEK', 'NOK', 'DKK', 'PLN', 'CZK', 'HUF', 'RON', 'BGN',
    'HRK', 'RSD', 'TRY', 'RUB', 'UAH', 'CNY', 'INR', 'BRL',
    'MXN', 'ZAR', 'SGD', 'HKD', 'KRW', 'THB', 'IDR', 'MYR',
    'PHP', 'VND', 'AED', 'SAR', 'ILS', 'EGP'
}

# BCP47 language codes (common ones for DACH region + major languages)
VALID_LANGUAGES = {
    'de-DE', 'de-AT', 'de-CH', 'en-US', 'en-GB', 'fr-FR', 'fr-CH',
    'it-IT', 'it-CH', 'es-ES', 'pt-PT', 'pt-BR', 'nl-NL', 'pl-PL',
    'cs-CZ', 'sk-SK', 'hu-HU', 'ro-RO', 'bg-BG', 'hr-HR', 'sr-RS',
    'sl-SI', 'sv-SE', 'da-DK', 'no-NO', 'fi-FI', 'ru-RU', 'uk-UA',
    'tr-TR', 'el-GR', 'zh-CN', 'zh-TW', 'ja-JP', 'ko-KR', 'ar-SA',
    'he-IL', 'th-TH', 'vi-VN', 'id-ID', 'ms-MY', 'hi-IN'
}


class AddressSchema(BaseModel):
    """Address schema for billing and shipping addresses"""
    street: Optional[str] = Field(None, max_length=200)
    street2: Optional[str] = Field(None, max_length=200)
    city: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=2, description="ISO 3166-1 alpha-2 country code")

    class Config:
        from_attributes = True


class CustomerCreate(BaseModel):
    """Schema for creating a new customer"""
    name: str = Field(..., min_length=1, max_length=500)
    erp_customer_number: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    default_currency: str = Field(..., min_length=3, max_length=3)
    default_language: str = Field(..., min_length=2, max_length=5)
    billing_address: Optional[AddressSchema] = None
    shipping_address: Optional[AddressSchema] = None
    notes: Optional[str] = None
    is_active: bool = True

    @field_validator('default_currency')
    @classmethod
    def validate_currency(cls, v: str) -> str:
        """Validate ISO 4217 currency code"""
        v_upper = v.upper()
        if v_upper not in VALID_CURRENCIES:
            raise ValueError(f"Invalid currency code. Must be one of: {', '.join(sorted(VALID_CURRENCIES))}")
        return v_upper

    @field_validator('default_language')
    @classmethod
    def validate_language(cls, v: str) -> str:
        """Validate BCP47 language code"""
        if v not in VALID_LANGUAGES:
            raise ValueError(f"Invalid language code. Must be one of: {', '.join(sorted(VALID_LANGUAGES))}")
        return v

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate name is not empty after stripping whitespace"""
        if not v.strip():
            raise ValueError("Customer name cannot be empty")
        return v.strip()

    class Config:
        from_attributes = True


class CustomerUpdate(BaseModel):
    """Schema for updating an existing customer (partial updates)"""
    name: Optional[str] = Field(None, min_length=1, max_length=500)
    erp_customer_number: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None
    default_currency: Optional[str] = Field(None, min_length=3, max_length=3)
    default_language: Optional[str] = Field(None, min_length=2, max_length=5)
    billing_address: Optional[AddressSchema] = None
    shipping_address: Optional[AddressSchema] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator('default_currency')
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> Optional[str]:
        """Validate ISO 4217 currency code"""
        if v is None:
            return v
        v_upper = v.upper()
        if v_upper not in VALID_CURRENCIES:
            raise ValueError(f"Invalid currency code. Must be one of: {', '.join(sorted(VALID_CURRENCIES))}")
        return v_upper

    @field_validator('default_language')
    @classmethod
    def validate_language(cls, v: Optional[str]) -> Optional[str]:
        """Validate BCP47 language code"""
        if v is None:
            return v
        if v not in VALID_LANGUAGES:
            raise ValueError(f"Invalid language code. Must be one of: {', '.join(sorted(VALID_LANGUAGES))}")
        return v

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate name is not empty after stripping whitespace"""
        if v is not None and not v.strip():
            raise ValueError("Customer name cannot be empty")
        return v.strip() if v else v

    class Config:
        from_attributes = True


class CustomerContactCreate(BaseModel):
    """Schema for creating a new customer contact"""
    email: EmailStr
    name: Optional[str] = Field(None, max_length=200)
    phone: Optional[str] = Field(None, max_length=50)
    role: Optional[str] = Field(None, max_length=100)
    is_primary: bool = False

    @field_validator('email')
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Normalize email to lowercase"""
        return v.lower().strip()

    class Config:
        from_attributes = True


class CustomerContactResponse(BaseModel):
    """Schema for customer contact response"""
    id: UUID
    customer_id: UUID
    email: str
    name: Optional[str]
    phone: Optional[str]
    role: Optional[str]
    is_primary: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomerResponse(BaseModel):
    """Schema for customer response"""
    id: UUID
    org_id: UUID
    name: str
    erp_customer_number: Optional[str]
    email: Optional[str]
    default_currency: str
    default_language: str
    billing_address: Optional[AddressSchema]
    shipping_address: Optional[AddressSchema]
    notes: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    contacts: Optional[list[CustomerContactResponse]] = None
    contact_count: Optional[int] = None

    class Config:
        from_attributes = True


class CustomerListResponse(BaseModel):
    """Schema for paginated customer list response"""
    items: list[CustomerResponse]
    total: int
    page: int
    per_page: int
    total_pages: int

    class Config:
        from_attributes = True


class ImportResult(BaseModel):
    """Schema for CSV import result"""
    imported: int = 0
    updated: int = 0
    failed: int = 0
    errors: list[dict] = Field(default_factory=list)

    class Config:
        from_attributes = True
