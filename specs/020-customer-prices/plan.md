# Implementation Plan: Customer Prices & Price Validation

**Branch**: `020-customer-prices` | **Date**: 2025-12-27 | **Spec**: [specs/020-customer-prices/spec.md](./spec.md)

## Summary

Customer Prices module enables importing, storing, and querying customer-specific pricing data with support for tiered pricing (quantity breaks), date-based validity, and multi-currency. The system validates draft line prices against expected customer prices using configurable tolerance thresholds, creating PRICE_MISMATCH issues when deviations exceed limits. Price data also feeds into the matching engine as a confidence signal (P_price penalty factor). CSV import handles bulk data with error reporting, tier selection algorithm picks the correct price based on order quantity, and UI provides search/edit capabilities for price management.

**Technical Approach**: Customer_price table with UNIQUE constraint on (customer_id, internal_sku, currency, uom, min_qty, date range). Tier selection uses SQL query `max(min_qty) WHERE min_qty <= qty`. Price validation computes percentage deviation and compares against org-level tolerance setting. Import uses batch INSERT with ON CONFLICT UPDATE for upserts.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, pandas (CSV parsing)
**Storage**: PostgreSQL (customer_price table)
**Testing**: pytest (tier selection tests, tolerance tests, import tests)
**Target Platform**: Linux server (containerized)
**Project Type**: Web application (backend API + frontend UI)
**Performance Goals**: CSV import 10k rows <30s, tier selection query <10ms, price lookup <5ms
**Constraints**: UNIQUE constraint prevents duplicate prices, tolerance 0-100%
**Scale/Scope**: 100k customer prices, 1000 customers, 10k products

## Constitution Check

| Principle | Compliance | Notes |
|-----------|------------|-------|
| **I. SSOT-First** | ✅ Pass | Schema from §5.4.11, import spec §8.8, tier algorithm §7.4 |
| **II. Hexagonal Architecture** | ✅ Pass | Price validation is a rule in ValidationEngine. Import service isolated from API layer. |
| **III. Multi-Tenant Isolation** | ✅ Pass | customer_price.org_id enforced. All queries filter by org. |
| **IV. Idempotent Processing** | ✅ Pass | CSV import uses UPSERT (ON CONFLICT UPDATE). Re-importing same data is safe. |
| **V. AI-Layer Deterministic Control** | ✅ Pass | No AI. All logic is deterministic SQL and percentage math. |
| **VI. Observability First-Class** | ✅ Pass | Import logs row counts, errors. Price validation logs mismatches. |
| **VII. Test Pyramid Discipline** | ✅ Pass | Unit tests for tier selection, tolerance calc. Integration tests for CSV import, API queries. |

## Project Structure

```text
backend/
├── src/
│   ├── domain/
│   │   ├── pricing/
│   │   │   ├── service.py           # PriceImportService, tier selection
│   │   │   └── models.py            # CustomerPrice dataclass
│   │   └── validation/
│   │       └── rules/
│   │           └── price_rules.py   # Price validation with tolerance
│   ├── api/
│   │   └── endpoints/
│   │       ├── customer_prices.py   # GET/POST customer prices
│   │       └── imports.py           # POST /imports/customer-prices
│   └── database/
│       └── models/
│           └── customer_price.py    # SQLAlchemy model
└── tests/
    ├── unit/
    │   └── pricing/
    │       ├── test_tier_selection.py
    │       └── test_tolerance.py
    └── integration/
        └── pricing/
            ├── test_csv_import.py
            └── test_price_validation.py

frontend/
├── src/
│   ├── components/
│   │   └── imports/
│   │       └── PriceImportUpload.tsx  # CSV upload UI
│   └── pages/
│       └── CustomerPricesPage.tsx     # Price management UI
```

## Complexity Tracking

No violations. Tier pricing is standard business requirement. CSV import with error reporting is necessary for data quality.
