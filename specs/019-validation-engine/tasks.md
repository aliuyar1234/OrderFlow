# Tasks: Validation Engine

**Feature Branch**: `019-validation-engine`
**Generated**: 2025-12-27
**Status**: COMPLETED

## Phase 1: Setup

- [x] T001 Create validation module at `backend/src/domain/validation/`
- [x] T002 Create validation rules directory at `backend/src/domain/validation/rules/`

## Phase 2: Validation Rule Interface

- [x] T003 Create ValidationIssue dataclass and enums (models.py)
- [x] T004 Define ValidatorPort interface with validate method signature
- [x] T005 Create ReadyCheckResult dataclass
- [x] T006 Support INFO, WARNING and ERROR severity levels

## Phase 3: [US1] Price Validation

- [x] T007 [US1] Implement price_rules.validate_price_rules
- [x] T008 [US1] Compare draft unit_price with customer_price using tier selection
- [x] T009 [US1] Calculate percentage deviation
- [x] T010 [US1] Apply price_tolerance_percent threshold from org settings
- [x] T011 [US1] Generate WARNING/ERROR if exceeded (configurable severity)
- [x] T012 [US1] Store validation issues in validation_issue table

## Phase 4: [US2] Required Fields Validation

- [x] T013 [US2] Implement header_rules.validate_header_rules
- [x] T014 [US2] Check customer_id is set (MISSING_CUSTOMER error)
- [x] T015 [US2] Check all lines have internal_sku (MISSING_SKU, UNKNOWN_PRODUCT errors)
- [x] T016 [US2] Check all lines have qty and uom (MISSING_QTY, INVALID_QTY, MISSING_UOM errors)
- [x] T017 [US2] Generate ERROR for missing required fields

## Phase 5: [US3] Data Consistency Validation

- [x] T018 [US3] Implement validate_currency_consistency
- [x] T019 [US3] Check all lines use same currency as header
- [x] T020 [US3] Currency validation (MISSING_CURRENCY error)
- [x] T021 [US3] Implement uom_rules.validate_uom_rules
- [x] T022 [US3] Check UoM is in canonical list (UNKNOWN_UOM error)
- [x] T023 [US3] Check UoM compatibility with product base_uom (UOM_INCOMPATIBLE error)

## Phase 6: [US4] Validation Pipeline

- [x] T024 [US4] Create ValidationEngine class implementing ValidatorPort
- [x] T025 [US4] Register all validation rule functions
- [x] T026 [US4] Run all rules on draft order with error handling
- [x] T027 [US4] Aggregate results (errors, warnings, info)
- [x] T028 [US4] Implement compute_ready_check method
- [x] T029 [US4] Update draft_order.ready_check_json with is_ready boolean
- [x] T030 [US4] Block READY status if ERROR-level OPEN issues exist

## Phase 7: Database & Infrastructure

- [x] T031 Create validation_issue table migration (006_create_validation_issue_table.py)
- [x] T032 Create ValidationIssue SQLAlchemy model
- [x] T033 Add validation_issue_severity and validation_issue_status ENUMs
- [x] T034 Create ValidationRepository for database operations
- [x] T035 Implement create_issue, get_issues_by_draft_order methods
- [x] T036 Implement acknowledge_issue, resolve_issue methods
- [x] T037 Implement auto_resolve_by_type_and_line for auto-resolution

## Phase 8: API Endpoints

- [x] T038 Create Pydantic schemas for validation responses (schemas/validation.py)
- [x] T039 Create GET /validation/draft-orders/{id}/issues endpoint
- [x] T040 Create GET /validation/draft-orders/{id}/issues/summary endpoint
- [x] T041 Create PATCH /validation/issues/{id}/acknowledge endpoint
- [x] T042 Create POST /validation/issues/{id}/resolve endpoint
- [x] T043 Add status filtering support to issues endpoint

## Phase 9: Documentation

- [x] T044 Create comprehensive README.md for validation module
- [x] T045 Document all validation rules with examples
- [x] T046 Document price tier selection algorithm
- [x] T047 Document ready-check logic
- [x] T048 Document API endpoints with request/response examples
- [x] T049 Document auto-resolution behavior
- [x] T050 Document configuration options (org settings)

## Implementation Summary

All tasks completed successfully. The validation engine implementation includes:

- **Domain Layer**: ValidatorPort, ValidationEngine, validation rules (header, line, price, UoM)
- **Models**: ValidationIssue dataclass, ReadyCheckResult, ValidationContext
- **Database**: validation_issue table with ENUMs, indexes, triggers
- **Repository**: ValidationRepository with CRUD and auto-resolution methods
- **API**: 4 endpoints for listing, summarizing, acknowledging, and resolving issues
- **Documentation**: Comprehensive README with architecture, rules, examples, and configuration

All validation rules from SSOT §7.3 and §7.4 have been implemented with proper severity levels and ready-check integration per §6.3.
