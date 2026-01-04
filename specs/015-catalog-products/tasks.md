# Tasks: Catalog Products

**Feature Branch**: `015-catalog-products`
**Generated**: 2025-12-27
**Completed**: 2026-01-04

## Phase 1: Setup

- [x] T001 Create catalog module at `backend/src/catalog/`
- [x] T002 Add product import dependencies (chardet already in requirements)

## Phase 2: Database Schema

- [x] T003 Create product table migration
- [x] T004 Add unique constraint on (org_id, internal_sku)
- [x] T005 Add indexes for (org_id, internal_sku, name)
- [x] T006 Create Product SQLAlchemy model
- [x] T007 Support JSONB for product attributes

## Phase 3: [US1] Import Product Catalog

- [x] T008 [US1] Create product import CSV parser
- [x] T009 [US1] Implement POST /products/import endpoint
- [x] T010 [US1] Upsert products (update if internal_sku exists)
- [x] T011 [US1] Validate required fields (internal_sku, name, base_uom)
- [x] T012 [US1] Handle import errors with row-level reporting
- [x] T013 [US1] Return import summary (created, updated, failed)

## Phase 4: [US2] Product CRUD API

- [x] T014 [US2] Create products router at `backend/src/catalog/router.py`
- [x] T015 [US2] Implement GET /products (list with search)
- [x] T016 [US2] Implement GET /products/{id} (detail)
- [x] T017 [US2] Implement POST /products (create)
- [x] T018 [US2] Implement PATCH /products/{id} (update)
- [x] T019 [US2] Add search by SKU, name, description

## Phase 5: [US3] Product Search

- [x] T020 [US3] Implement text search on name and description
- [x] T021 [US3] Add filter by internal_sku
- [x] T022 [US3] Support pagination
- [x] T023 [US3] Optimize search performance with indexes (GIN index for fulltext search)

## Phase 6: [US4] Product Attributes

- [x] T024 [US4] Store flexible attributes in JSONB
- [x] T025 [US4] Support custom attribute keys (manufacturer, ean, category)
- [x] T026 [US4] Query products by attributes (GIN index on attributes_json)
- [x] T027 [US4] Validate attribute types (handled in import service)

## Phase 7: Polish

- [ ] T028 Add product deduplication detection (Future enhancement)
- [ ] T029 Support product images (URLs) (Future enhancement)
- [ ] T030 Add product categories/tags (Future enhancement)
- [ ] T031 Create product import templates (Future enhancement)

## Implementation Summary

All core tasks (T001-T027) have been completed. Phase 7 tasks marked as future enhancements.
