# Tasks: Authentication & RBAC

**Feature Branch**: `002-auth-rbac`
**Generated**: 2025-12-27

## Phase 1: Setup

- [X] T001 Add authentication dependencies to `backend/requirements/base.txt` (PyJWT, argon2-cffi)
- [X] T002 Create auth module structure at `backend/src/auth/`
- [X] T003 Create users module structure at `backend/src/users/`
- [X] T004 Create audit module structure at `backend/src/audit/`
- [X] T005 Add PASSWORD_PEPPER and JWT_SECRET to `.env.example`

## Phase 2: Database Schema

- [X] T006 Create user table migration at `backend/migrations/versions/002_create_user_and_audit_tables.py`
- [X] T007 Create audit_log table in same migration
- [X] T008 Add indexes for user table (org_id, role, email)
- [X] T009 Add indexes for audit_log table (org_id, actor_id, entity)
- [X] T010 Create User SQLAlchemy model at `backend/src/models/user.py`
- [X] T011 Create AuditLog SQLAlchemy model at `backend/src/models/audit_log.py`

## Phase 3: Password & JWT Infrastructure

- [X] T012 Implement Argon2id password hashing at `backend/src/auth/password.py`
- [X] T013 Implement JWT token generation at `backend/src/auth/jwt.py`
- [X] T014 Implement JWT token validation at `backend/src/auth/jwt.py`
- [X] T015 Create audit logging service at `backend/src/audit/service.py`

## Phase 4: [US1] User Login

- [X] T016 [US1] Create login endpoint at `backend/src/auth/router.py` (POST /auth/login)
- [X] T017 [US1] Implement login Pydantic schemas at `backend/src/auth/schemas.py`
- [X] T018 [US1] Create FastAPI dependency for JWT extraction at `backend/src/auth/dependencies.py`
- [X] T019 [US1] Create get_current_user dependency
- [X] T020 [US1] Implement last_login_at timestamp update on successful login
- [X] T021 [US1] Add audit logging for login success/failure
- [X] T022 [US1] Implement user status check (block DISABLED users)
- [X] T023 [US1] Create /auth/me endpoint for user profile retrieval

## Phase 5: [US2] Role-Based Access Control

- [X] T024 [US2] Create @require_role decorator at `backend/src/auth/dependencies.py`
- [X] T025 [US2] Implement role permission validation logic
- [X] T026 [US2] Create role enum with ADMIN, INTEGRATOR, OPS, VIEWER
- [X] T027 [US2] Implement 403 Forbidden response for unauthorized roles
- [X] T028 [US2] Document role permission matrix in code

## Phase 6: [US3] User Management

- [X] T029 [US3] Create user CRUD router at `backend/src/users/router.py`
- [X] T030 [US3] Implement POST /users endpoint (ADMIN only)
- [X] T031 [US3] Implement PATCH /users/{id} endpoint (ADMIN only)
- [X] T032 [US3] Implement GET /users endpoint (ADMIN only)
- [X] T033 [US3] Implement GET /users/{id} endpoint (ADMIN only)
- [X] T034 [US3] Create User Pydantic schemas at `backend/src/users/schemas.py`
- [X] T035 [US3] Implement email uniqueness validation per org
- [X] T036 [US3] Add audit logging for user creation/updates

## Phase 7: [US4] Audit Trail for Security Events

- [X] T037 [US4] Create audit log query endpoint at `backend/src/audit/router.py` (GET /audit)
- [X] T038 [US4] Implement audit log filtering (by action, entity_type, date range)
- [X] T039 [US4] Add pagination for audit log queries
- [X] T040 [US4] Implement audit entry creation for USER_CREATED event
- [X] T041 [US4] Implement audit entry creation for USER_ROLE_CHANGED event
- [X] T042 [US4] Implement audit entry creation for USER_DISABLED event
- [X] T043 [US4] Store IP address and user_agent in audit log entries

## Phase 8: Polish

- [X] T044 Create seed script for initial admin user creation
- [X] T045 Add password strength validation utilities
- [X] T046 Document JWT token claims structure
- [X] T047 Create authentication testing utilities for pytest
