# Implementation Plan: Tenancy Isolation

**Branch**: `003-tenancy-isolation` | **Date**: 2025-12-27 | **Spec**: [spec.md](./spec.md)

## Summary

Implements automatic tenant scoping for all database queries and API endpoints, org settings management API, and org_id enforcement in background workers. Ensures every query filters by org_id (derived from JWT), provides 404 (not 403) for cross-org access attempts, and validates org settings against Pydantic schemas.

**Technical Approach**: SQLAlchemy session-scoped org_id injection, FastAPI dependency for automatic org_id extraction from JWT, Pydantic validation for settings_json updates, explicit org_id passing to Celery tasks.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, Pydantic, Celery
**Storage**: PostgreSQL (org.settings_json)
**Testing**: Multi-org fixtures, cross-org access tests, SQL query logging verification
**Target Platform**: Linux/macOS servers
**Project Type**: web (backend API + workers)
**Performance Goals**: <1 second settings update effect, <5ms org_id filter overhead
**Constraints**: 100% query coverage for org_id filter, zero cross-org data leaks
**Scale/Scope**: Support 1000+ organizations, millions of multi-tenant records

## Constitution Check

| Principle | Compliance | Notes |
|-----------|------------|-------|
| **I. SSOT-First** | ✅ Pass | SSOT §5.1, §10.1, §11.2 fully implemented |
| **II. Hexagonal Architecture** | ✅ Pass | Tenancy as infrastructure concern, domain-independent |
| **III. Multi-Tenant Isolation** | ✅ Pass | Core feature - automatic org_id enforcement everywhere |
| **IV. Idempotent Processing** | ✅ Pass | Settings updates and org queries are idempotent |
| **V. AI-Layer** | ⚪ N/A | No AI components |
| **VI. Observability** | ✅ Pass | SQL logging tracks org_id filter usage |
| **VII. Test Pyramid** | ✅ Pass | Unit (settings schema), integration (cross-org), security (SQL injection) |

**Verdict**: All applicable principles satisfied.

## Project Structure

### Documentation
```
specs/003-tenancy-isolation/
├── plan.md
├── research.md           # Session scoping patterns, security best practices
├── data-model.md         # Org settings schema (from 001, expanded)
├── quickstart.md         # Testing tenant isolation, creating multi-org fixtures
└── contracts/
    └── openapi.yaml      # /org/settings endpoints
```

### Source Code
```
backend/
├── src/
│   ├── database.py            # Updated with scoped_session factory
│   ├── tenancy/
│   │   ├── __init__.py
│   │   ├── middleware.py      # Org_id extraction from JWT
│   │   ├── schemas.py         # OrgSettings Pydantic schema
│   │   └── router.py          # /org/settings endpoints
│   └── dependencies.py        # get_org_id, get_scoped_session
└── tests/
    ├── integration/
    │   ├── test_multi_org_isolation.py
    │   └── test_org_settings.py
    └── security/
        └── test_cross_org_access.py
```

## Complexity Tracking

*No violations.*
