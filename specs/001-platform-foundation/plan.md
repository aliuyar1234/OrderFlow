# Implementation Plan: Platform Foundation

**Branch**: `001-platform-foundation` | **Date**: 2025-12-27 | **Spec**: [spec.md](./spec.md)

## Summary

Establishes the foundational infrastructure for OrderFlow including Docker Compose development environment (PostgreSQL 16 with pg_trgm and pgvector extensions, Redis, MinIO), Alembic migration system, and multi-tenant data conventions with the org table. This feature provides the absolute foundation upon which all other features depend - without it, no development or data storage is possible.

**Technical Approach**: Use Docker Compose for local development orchestration, Alembic for database schema versioning, and establish org table as the tenant anchor with UUID-based identifiers and JSONB settings storage. All infrastructure services include health checks for reliable startup.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: PostgreSQL 16, Redis (latest stable), MinIO, Alembic, SQLAlchemy 2.x
**Storage**: PostgreSQL (primary database), MinIO (S3-compatible object storage), Redis (Celery broker, cache)
**Testing**: pytest for unit/integration tests, docker-compose health checks for infrastructure
**Target Platform**: Linux/macOS development environments, containerized services
**Project Type**: web (backend + frontend structure)
**Performance Goals**: <2 minutes for full dev environment startup, <10 seconds for migration execution
**Constraints**: All services must support graceful startup/shutdown, health checks required, PostgreSQL extensions must be available
**Scale/Scope**: Foundation for multi-tenant SaaS supporting 1000+ organizations

## Constitution Check

*All Core Principles from Constitution v1.0.0*

| Principle | Compliance | Notes |
|-----------|------------|-------|
| **I. SSOT-First** | ✅ Pass | SSOT §3.2 (Tech Stack), §5.1 (Konventions), §5.4.1 (org table) fully adhered to |
| **II. Hexagonal Architecture** | ✅ Pass | Infrastructure layer only; no domain logic yet. Database adapter pattern via SQLAlchemy |
| **III. Multi-Tenant Isolation** | ✅ Pass | org table established with unique slug constraint. All future tables will enforce org_id NOT NULL foreign key |
| **IV. Idempotent Processing** | ✅ Pass | Alembic migrations are idempotent by design (versioned, upgrade/downgrade support) |
| **V. AI-Layer Deterministic Control** | ⚪ N/A | No AI components in this feature |
| **VI. Observability First-Class** | ✅ Pass | Health checks for all services. Structured logging setup deferred to API implementation |
| **VII. Test Pyramid Discipline** | ✅ Pass | Schema tests verify table structure, integration tests verify Docker services, unit tests for settings validation |

**Verdict**: All applicable principles satisfied. No violations to justify.

## Project Structure

### Documentation (this feature)

```text
specs/001-platform-foundation/
├── plan.md              # This file
├── research.md          # Tech stack justification, Docker best practices
├── data-model.md        # org table schema and migration structure
├── quickstart.md        # Local development setup guide
└── (no contracts - infrastructure only)
```

### Source Code (repository root)

```text
backend/
├── alembic.ini                    # Alembic configuration
├── migrations/
│   ├── env.py                     # Migration environment (multi-tenant aware)
│   ├── script.py.mako             # Migration template
│   └── versions/
│       └── 001_create_org_table.py
├── src/
│   ├── __init__.py
│   ├── database.py                # SQLAlchemy session factory
│   └── models/
│       ├── __init__.py
│       └── org.py                 # Org model with settings schema
├── tests/
│   ├── integration/
│   │   ├── test_docker_services.py
│   │   └── test_migrations.py
│   ├── unit/
│   │   └── test_org_model.py
│   └── schema/
│       └── test_table_conventions.py
└── requirements/
    ├── base.txt                   # Production dependencies
    └── dev.txt                    # Development dependencies

docker-compose.yml                 # Development services
.env.example                       # Environment variable template
README.md                          # Updated with setup instructions
```

**Structure Decision**: Web application structure (backend/frontend split) selected per SSOT §3.2. Backend uses src/ for application code following Python best practices. Alembic migrations live alongside backend code for tight coupling with database schema.

## Complexity Tracking

*No Constitution violations - table not required.*
