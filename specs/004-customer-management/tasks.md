# Tasks: Customer Management

**Feature Branch**: `004-customer-management`
**Generated**: 2025-12-27

## Phase 1: Setup

- [X] T001 Create customers module structure at `backend/src/customers/`
- [X] T002 Add pandas to `backend/requirements/base.txt` for CSV import

## Phase 2: Database Schema

- [X] T003 Create customer tables migration at `backend/migrations/versions/004_create_customer_tables.py`
- [X] T004 Create customer table with CITEXT email, JSONB addresses
- [X] T005 Create customer_contact table with CITEXT email
- [X] T006 Add unique constraint on (org_id, erp_customer_number)
- [X] T007 Add unique constraint on (customer_id, email) for contacts
- [X] T008 Add indexes for customer (org_id+name, org_id+erp_number)
- [X] T009 Add indexes for customer_contact (org_id+customer_id, org_id+email)
- [X] T010 Create Customer SQLAlchemy model at `backend/src/models/customer.py`
- [X] T011 Create CustomerContact SQLAlchemy model at `backend/src/models/customer_contact.py`

## Phase 3: Pydantic Schemas & Validation

- [X] T012 Create Address Pydantic schema at `backend/src/customers/schemas.py`
- [X] T013 Create Customer Pydantic schema with validation
- [X] T014 Create CustomerContact Pydantic schema
- [X] T015 Add ISO 4217 currency code validation
- [X] T016 Add BCP47 language code validation
- [X] T017 Add email format validation for contacts

## Phase 4: [US1] Import Customer Master Data

- [X] T018 [US1] Create CSV import service at `backend/src/customers/import_service.py`
- [X] T019 [US1] Implement CSV parsing with pandas
- [X] T020 [US1] Implement upsert logic (update if ERP number exists, insert if new)
- [X] T021 [US1] Create POST /imports/customers endpoint
- [X] T022 [US1] Add CSV validation (required fields, data types)
- [X] T023 [US1] Implement error reporting for invalid CSV rows
- [X] T024 [US1] Handle billing/shipping address parsing from CSV
- [X] T025 [US1] Return import summary (imported, updated, failed counts)

## Phase 5: [US2] Manage Customer Contacts

- [X] T026 [US2] Implement POST /customers/{id}/contacts endpoint
- [X] T027 [US2] Implement DELETE /customers/{customer_id}/contacts/{contact_id} endpoint
- [X] T028 [US2] Add primary contact toggle logic (only one primary per customer)
- [X] T029 [US2] Implement contact creation from CSV import
- [X] T030 [US2] Add email uniqueness validation per customer
- [X] T031 [US2] Implement contact email normalization (lowercase, trim)

## Phase 6: [US3] View and Search Customers

- [X] T032 [US3] Create customer CRUD router at `backend/src/customers/router.py`
- [X] T033 [US3] Implement GET /customers endpoint with pagination
- [X] T034 [US3] Add search by name functionality (query parameter ?q=)
- [X] T035 [US3] Add filter by ERP number functionality
- [X] T036 [US3] Implement GET /customers/{id} endpoint with contacts
- [X] T037 [US3] Add cursor-based pagination
- [X] T038 [US3] Include contact_count in customer list response

## Phase 7: [US4] Update Customer Information

- [X] T039 [US4] Implement POST /customers endpoint (ADMIN/INTEGRATOR only)
- [X] T040 [US4] Implement PATCH /customers/{id} endpoint (ADMIN/INTEGRATOR only)
- [X] T041 [US4] Add partial update support (only update provided fields)
- [X] T042 [US4] Validate data updates (empty name, invalid currency)
- [X] T043 [US4] Update billing/shipping addresses via PATCH
- [X] T044 [US4] Support ERP number updates

## Phase 8: Polish

- [X] T045 Create sample CSV import file for testing
- [X] T046 Add customer import performance optimization for large files
- [X] T047 Document CSV import format and field mappings
- [X] T048 Create customer test fixtures for pytest
