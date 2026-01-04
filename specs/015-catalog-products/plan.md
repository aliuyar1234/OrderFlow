# Implementation Plan: Catalog & Products Management

**Branch**: `015-catalog-products` | **Date**: 2025-12-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/015-catalog-products/spec.md`

## Summary

Catalog & Products Management provides product master data import, UoM conversions, customer-specific pricing, and a searchable catalog UI. Products are imported via CSV with validation (UoM canonicalization, SKU uniqueness), supporting upsert for updates. UoM conversions enable pack units (Karton, Palette) to match with base units. Customer prices support tier pricing with min_qty thresholds for DACH B2B scenarios. The catalog UI allows searching, filtering, editing products, and toggling active status. Product changes trigger embedding recompute jobs for downstream matching.

**Technical Approach**: Python backend with FastAPI endpoints for CSV import/validation, SQLAlchemy models for product and customer_price entities. PostgreSQL with pg_trgm for fulltext search, JSONB for attributes/conversions storage. Celery workers for async embedding jobs. Frontend React UI with paginated product table, search, and edit modal.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript/Next.js (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy, Alembic, chardet (CSV encoding), Celery, pandas (CSV parsing)
**Storage**: PostgreSQL 16 with pg_trgm extension, S3-compatible object storage for CSV uploads
**Testing**: pytest (backend unit/integration), Jest + RTL (frontend)
**Target Platform**: Linux server (backend), Web browsers (frontend)
**Project Type**: web (backend + frontend modules)
**Performance Goals**: Import 10k products <30s, product search <200ms, CSV validation <5s
**Constraints**: Multi-tenant isolation via org_id, canonical UoM enforcement, idempotent upsert
**Scale/Scope**: 10k products per org, 100k customer price records, 50 concurrent imports

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Compliance | Notes |
|-----------|------------|-------|
| **I. SSOT-First** | ✅ Pass | Product schema per §5.4.10, UoM standardization §6.2, import API §8.8 |
| **II. Hexagonal Architecture** | ✅ Pass | Domain: Product entity. Ports: CSVImportService, EmbeddingJobPort. Adapters: PostgreSQL, Celery |
| **III. Multi-Tenant Isolation** | ✅ Pass | UNIQUE(org_id, internal_sku), all queries filter by org_id |
| **IV. Idempotent Processing** | ✅ Pass | Upsert logic ensures repeated imports produce same result |
| **V. AI-Layer Deterministic Control** | ✅ Pass | Embedding recompute triggered via job queue, not inline (async, retryable) |
| **VI. Observability First-Class** | ✅ Pass | Import results logged, CSV errors tracked, embedding job metrics exposed |
| **VII. Test Pyramid Discipline** | ✅ Pass | Unit (CSV validation, upsert logic), Integration (import → DB → embedding jobs), Contract (API schemas) |

## Project Structure

### Documentation (this feature)

```text
specs/015-catalog-products/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (SQLAlchemy models)
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── openapi.yaml     # API contract
└── spec.md              # Feature specification (already exists)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   ├── product.py               # Product SQLAlchemy model (§5.4.10)
│   │   └── customer_price.py        # CustomerPrice model (§5.4.11)
│   ├── services/
│   │   ├── catalog/
│   │   │   ├── product_importer.py  # CSV import service
│   │   │   ├── uom_converter.py     # UoM conversion logic
│   │   │   ├── price_validator.py   # Price tier lookup
│   │   │   └── __tests__/
│   │   └── embedding/
│   │       └── job_enqueuer.py      # Trigger embedding recompute
│   ├── api/
│   │   └── v1/
│   │       ├── products.py          # Product CRUD + search endpoints
│   │       └── imports.py           # CSV import endpoint
│   ├── lib/
│   │   ├── csv_parser.py            # CSV encoding detection + parsing
│   │   └── canonical_uom.py         # UoM validation constants
│   └── workers/
│       └── tasks/
│           └── embed_product.py     # Celery task (reuses from 016)
└── tests/
    ├── unit/
    │   ├── test_product_importer.py
    │   ├── test_uom_converter.py
    │   └── test_csv_parser.py
    ├── integration/
    │   └── test_product_import_flow.py
    └── fixtures/
        ├── products.csv             # Test CSV files
        └── customer_prices.csv

frontend/
├── src/
│   ├── components/
│   │   └── catalog/
│   │       ├── ProductTable.tsx     # Paginated product table
│   │       ├── ProductEditModal.tsx # Edit product modal
│   │       ├── ProductImportForm.tsx # CSV upload form
│   │       └── __tests__/
│   ├── pages/
│   │   └── catalog/
│   │       └── products.tsx         # Product catalog page
│   ├── hooks/
│   │   ├── useProductSearch.ts      # Search hook
│   │   └── useProductImport.ts      # Import mutation hook
│   └── services/
│       └── api/
│           └── catalog.ts           # Catalog API client
└── tests/
    └── integration/
        └── catalog.test.ts
```

**Structure Decision**: Backend uses hexagonal architecture with dedicated catalog domain services. CSV import is isolated in `product_importer` service with encoding detection and validation. Frontend provides admin UI for product management with search and import capabilities.

## Complexity Tracking

> **No violations to justify**
