# Data Model: Tenancy Isolation

**Feature**: 003-tenancy-isolation
**Date**: 2025-12-27
**SSOT Reference**: §10.1 (Org Settings Schema)

## Overview

This feature extends the `org` table from 001-platform-foundation with comprehensive settings schema definition and validation. No new tables are created - this is purely infrastructure and API layer.

## Org Settings Schema

See 001-platform-foundation/data-model.md for `org` table definition. This document provides the complete Pydantic validation schema for `settings_json`.

### Full Python Schema

```python
from pydantic import BaseModel, Field

class MatchingSettings(BaseModel):
    auto_apply_threshold: float = Field(default=0.92, ge=0.0, le=1.0)
    auto_apply_gap: float = Field(default=0.10, ge=0.0, le=1.0)

class CustomerDetectionSettings(BaseModel):
    auto_select_threshold: float = Field(default=0.90, ge=0.0, le=1.0)
    require_manual_review_if_multiple: bool = True

class AISettings(BaseModel):
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_budget_daily_usd: float = Field(default=10.0, ge=0.0)
    vision_enabled: bool = True
    vision_max_pages: int = Field(default=5, ge=1)
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"

class ExtractionSettings(BaseModel):
    min_text_coverage_for_rule: float = Field(default=0.8, ge=0.0, le=1.0)
    max_pages_rule_based: int = Field(default=10, ge=1)
    llm_on_extraction_failure: bool = True

class OrgSettings(BaseModel):
    default_currency: str = "EUR"  # ISO 4217
    price_tolerance_percent: float = Field(default=5.0, ge=0.0)
    require_unit_price: bool = False

    matching: MatchingSettings = MatchingSettings()
    customer_detection: CustomerDetectionSettings = CustomerDetectionSettings()
    ai: AISettings = AISettings()
    extraction: ExtractionSettings = ExtractionSettings()
```

### Example Settings JSON

```json
{
  "default_currency": "CHF",
  "price_tolerance_percent": 3.0,
  "require_unit_price": false,
  "matching": {
    "auto_apply_threshold": 0.95,
    "auto_apply_gap": 0.10
  },
  "customer_detection": {
    "auto_select_threshold": 0.90,
    "require_manual_review_if_multiple": true
  },
  "ai": {
    "llm_provider": "openai",
    "llm_model": "gpt-4o-mini",
    "llm_budget_daily_usd": 20.0,
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
```

## Session Scoping Implementation

### Database Helper

```python
from uuid import UUID
from sqlalchemy.orm import Session
from src.database import SessionLocal

def get_scoped_session(org_id: UUID) -> Session:
    """Create session with org_id context"""
    session = SessionLocal()
    session.info["org_id"] = org_id
    return session

def scoped_query(session: Session, model):
    """Query helper that auto-filters by org_id"""
    org_id = session.info.get("org_id")
    if not org_id:
        raise ValueError("org_id not set in session")
    return session.query(model).filter(model.org_id == org_id)
```

### FastAPI Dependency

```python
from fastapi import Depends, HTTPException
from src.auth.dependencies import get_current_user
from src.models.user import User

async def get_org_id(current_user: User = Depends(get_current_user)) -> UUID:
    """Extract org_id from authenticated user"""
    return current_user.org_id

async def get_org_scoped_session(org_id: UUID = Depends(get_org_id)) -> Session:
    """Get database session scoped to current org"""
    session = get_scoped_session(org_id)
    try:
        yield session
    finally:
        session.close()
```

## References

- SSOT §10.1: Complete settings schema
- SSOT §5.1: Multi-tenant conventions
- 001-platform-foundation/data-model.md: org table definition
