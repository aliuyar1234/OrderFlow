# Implementation Plan: Authentication & RBAC

**Branch**: `002-auth-rbac` | **Date**: 2025-12-27 | **Spec**: [spec.md](./spec.md)

## Summary

Implements secure authentication with JWT tokens and role-based access control (RBAC) for OrderFlow. Users authenticate with email/password (Argon2id hashed), receive JWT tokens with org_id and role claims, and access endpoints according to their role (ADMIN, INTEGRATOR, OPS, VIEWER). Includes audit logging for all security events and user management endpoints.

**Technical Approach**: FastAPI dependency injection for auth middleware, PyJWT for token generation/validation, argon2-cffi for password hashing with PASSWORD_PEPPER, decorator-based RBAC enforcement (@require_role), and immutable audit log for security events.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, PyJWT, argon2-cffi, SQLAlchemy 2.x, Pydantic
**Storage**: PostgreSQL (user table, audit_log table)
**Testing**: pytest with role-based fixtures, security tests for timing attacks and token tampering
**Target Platform**: Linux/macOS servers (containerized)
**Project Type**: web (backend API)
**Performance Goals**: <500ms login (P95), <10ms JWT validation overhead (P95)
**Constraints**: Argon2id parameters per OWASP, JWT secret minimum 256 bits, audit log append-only
**Scale/Scope**: Support 100+ concurrent users per org, handle 1000+ login attempts/hour

## Constitution Check

*All Core Principles from Constitution v1.0.0*

| Principle | Compliance | Notes |
|-----------|------------|-------|
| **I. SSOT-First** | ✅ Pass | SSOT §5.2.1 (Roles), §5.4.2 (user table), §8.3 (Auth Endpoints), §11 (Auth/RBAC/Audit) fully followed |
| **II. Hexagonal Architecture** | ✅ Pass | Auth as infrastructure adapter, domain-independent. Password hashing and JWT generation are ports |
| **III. Multi-Tenant Isolation** | ✅ Pass | user.org_id enforced, JWT contains org_id claim, cross-org login impossible via org_slug validation |
| **IV. Idempotent Processing** | ✅ Pass | Login is read-only (idempotent), user creation checks uniqueness (prevents duplicates) |
| **V. AI-Layer Deterministic Control** | ⚪ N/A | No AI components in this feature |
| **VI. Observability First-Class** | ✅ Pass | Audit log for all security events, structured logging for auth failures |
| **VII. Test Pyramid Discipline** | ✅ Pass | Unit tests for password/JWT, integration tests for endpoints, security tests for attacks |

**Verdict**: All applicable principles satisfied. No violations.

## Project Structure

### Documentation (this feature)

```text
specs/002-auth-rbac/
├── plan.md              # This file
├── research.md          # Argon2id configuration, JWT best practices, RBAC patterns
├── data-model.md        # user and audit_log table schemas
├── quickstart.md        # Testing auth locally, creating test users
└── contracts/
    └── openapi.yaml     # Auth API contract (login, me, user CRUD)
```

### Source Code (repository root)

```text
backend/
├── migrations/versions/
│   └── 002_create_user_and_audit_tables.py
├── src/
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── password.py          # Argon2id hashing/verification
│   │   ├── jwt.py               # Token generation/validation
│   │   ├── dependencies.py      # FastAPI dependencies (get_current_user, require_role)
│   │   └── router.py            # Auth endpoints (/auth/login, /auth/me)
│   ├── users/
│   │   ├── __init__.py
│   │   ├── models.py            # User model
│   │   ├── schemas.py           # Pydantic schemas
│   │   └── router.py            # User CRUD endpoints
│   ├── audit/
│   │   ├── __init__.py
│   │   ├── models.py            # AuditLog model
│   │   └── service.py           # Audit logging service
│   └── models/
│       ├── user.py              # User SQLAlchemy model
│       └── audit_log.py         # AuditLog SQLAlchemy model
└── tests/
    ├── unit/
    │   ├── test_password_hashing.py
    │   └── test_jwt_tokens.py
    ├── integration/
    │   ├── test_auth_endpoints.py
    │   ├── test_user_management.py
    │   └── test_rbac_enforcement.py
    └── security/
        ├── test_timing_attacks.py
        ├── test_token_tampering.py
        └── test_cross_org_access.py
```

**Structure Decision**: Web application backend structure. Auth module separate from users module (auth is mechanism, users is entity). Audit module provides shared logging service used by auth and users.

## Complexity Tracking

*No Constitution violations - table not required.*
