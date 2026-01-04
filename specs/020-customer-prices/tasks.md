# Tasks: Customer Prices

**Feature Branch**: `020-customer-prices`
**Generated**: 2025-12-27

## Phase 1: Setup

- [x] T001 Create customer_price module at `backend/src/pricing/`
- [x] T002 Add customer price dependencies

## Phase 2: Database Schema

- [x] T003 Create customer_price table migration (005_create_customer_price_table.py)
- [x] T004 Add unique constraint on (customer_id, internal_sku, currency, uom, min_qty)
- [x] T005 Add indexes for lookups (idx_customer_price_lookup, idx_customer_price_tier_lookup)
- [x] T006 Create CustomerPrice SQLAlchemy model
- [x] T007 Support effective date ranges (valid_from, valid_to)

## Phase 3: [US1] Import Customer Prices

- [x] T008 [US1] Create customer price import CSV parser (PriceImportService)
- [x] T009 [US1] Implement POST /customer-prices/import endpoint
- [x] T010 [US1] Upsert prices (update if exists)
- [x] T011 [US1] Validate customer exists (lookup by erp_customer_number or customer_name)
- [x] T012 [US1] Handle import errors (error reporting with row numbers)
- [x] T013 [US1] Return import summary (imported, updated, failed counts)

## Phase 4: [US2] Price Lookup

- [x] T014 [US2] Query customer_price by (customer_id, internal_sku, currency, uom)
- [x] T015 [US2] Return negotiated price tier based on quantity
- [x] T016 [US2] Tier selection algorithm (max min_qty <= qty)
- [x] T017 [US2] Date range filtering (valid_from, valid_to)
- [x] T018 [US2] POST /customer-prices/lookup endpoint

## Phase 5: [US3] Price Management API

- [x] T019 [US3] Create customer prices router (backend/src/pricing/router.py)
- [x] T020 [US3] Implement GET /customer-prices (with filters)
- [x] T021 [US3] Implement POST /customer-prices
- [x] T022 [US3] Implement PATCH /customer-prices/{id}
- [x] T023 [US3] Implement DELETE /customer-prices/{id}

## Phase 6: [US4] Price Validation Integration

- [x] T024 [US4] Price validation already implemented (domain/validation/rules/price_rules.py)
- [x] T025 [US4] Compare draft price with negotiated price
- [x] T026 [US4] Apply tolerance checks (org.settings_json.price_tolerance_percent)
- [x] T027 [US4] PRICE_MISMATCH and MISSING_PRICE issue types

## Phase 7: Polish

- [x] T028 Support price tiers (volume discounts) - implemented via min_qty
- [x] T029 Add price effective date ranges - implemented via valid_from/valid_to
- [x] T030 Unit tests for price tier selection (tests/unit/pricing/test_price_tier_selection.py)
- [x] T031 Integration tests for CSV import (tests/integration/pricing/test_csv_import.py)
