# Implementation Plan: Customer Management

**Branch**: `004-customer-management` | **Date**: 2025-12-27 | **Spec**: [spec.md](./spec.md)

## Summary

Implements customer and customer contact management with CSV import, CRUD APIs, and search functionality. Customers have ERP numbers (unique per org), addresses (JSONB), default currency/language, and multiple contacts with emails for customer detection. Includes upsert-capable CSV import for bulk customer data loading.

**Technical Approach**: SQLAlchemy models with JSONB for addresses, CSV import with pandas, CITEXT for case-insensitive emails, upsert logic based on ERP number, Pydantic validation for ISO codes (currency/language).

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, pandas, Pydantic
**Storage**: PostgreSQL (customer, customer_contact tables)
**Testing**: Import tests with 1000+ records, unique constraint tests, search performance tests
**Target Platform**: Linux/macOS servers
**Project Type**: web (backend API)
**Performance Goals**: <30s for 1000 customer import, <200ms search, <100ms single retrieval
**Constraints**: Unique ERP number per org, unique email per customer, Unicode support
**Scale/Scope**: 10,000+ customers per org, 100,000+ contacts across all orgs

## Constitution Check

| Principle | Compliance | Notes |
|-----------|------------|-------|
| **I. SSOT-First** | ✅ Pass | SSOT §5.4.3, §5.4.4, §8.4 fully implemented |
| **II. Hexagonal Architecture** | ✅ Pass | Customer as domain entity, CSV import as adapter |
| **III. Multi-Tenant Isolation** | ✅ Pass | customer.org_id enforced, cross-org isolation tested |
| **IV. Idempotent Processing** | ✅ Pass | CSV import upserts (idempotent on re-run) |
| **V. AI-Layer** | ⚪ N/A | No AI (customer detection in future spec) |
| **VI. Observability** | ✅ Pass | Import metrics logged |
| **VII. Test Pyramid** | ✅ Pass | Unit (validation), integration (CRUD/import), performance (large imports) |

**Verdict**: All applicable principles satisfied.

## Project Structure

### Documentation
```
specs/004-customer-management/
├── plan.md
├── research.md           # JSONB patterns, CSV import best practices, ISO code validation
├── data-model.md         # customer, customer_contact schemas
├── quickstart.md         # Creating customers, testing import
└── contracts/
    └── openapi.yaml      # /customers, /imports/customers endpoints
```

### Source Code
```
backend/
├── migrations/versions/
│   └── 004_create_customer_tables.py
├── src/
│   ├── customers/
│   │   ├── __init__.py
│   │   ├── models.py          # Customer, CustomerContact models
│   │   ├── schemas.py         # Pydantic schemas with ISO validation
│   │   ├── router.py          # CRUD endpoints
│   │   └── import_service.py  # CSV import with upsert logic
│   └── models/
│       ├── customer.py
│       └── customer_contact.py
└── tests/
    ├── unit/
    │   └── test_customer_validation.py
    ├── integration/
    │   ├── test_customer_crud.py
    │   └── test_customer_import.py
    └── performance/
        └── test_large_import.py
```

## Complexity Tracking

*No violations.*
