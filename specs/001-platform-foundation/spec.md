# Feature Specification: Platform Foundation

**Feature Branch**: `001-platform-foundation`
**Created**: 2025-12-27
**Status**: Draft
**Module**: tenancy
**SSOT References**: §3.2 (Tech Stack), §5.1 (Konventionen), §5.4.1 (org table), §14.1 (Deployment)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Development Environment Setup (Priority: P1)

As a developer, I need a working local development environment so that I can start building OrderFlow features.

**Why this priority**: Without a working dev environment, no other features can be developed. This is the absolute foundation.

**Independent Test**: Can be fully tested by running `docker compose up` and verifying all services (postgres, redis, minio) are healthy and accepting connections. Delivers a ready-to-code environment.

**Acceptance Scenarios**:

1. **Given** Docker and Docker Compose are installed, **When** I run `docker compose up`, **Then** all services (postgres with pg_trgm + pgvector extensions, redis, minio) start successfully and pass health checks
2. **Given** the services are running, **When** I attempt to connect to PostgreSQL, **Then** I can connect successfully and the pg_trgm and pgvector extensions are available
3. **Given** the services are running, **When** I attempt to connect to Redis, **Then** I can successfully ping Redis and get a response
4. **Given** the services are running, **When** I attempt to connect to MinIO, **Then** I can access the MinIO console and create a bucket

---

### User Story 2 - Database Migration System (Priority: P1)

As a developer, I need a database migration system so that I can evolve the database schema in a controlled, version-controlled manner.

**Why this priority**: Database migrations are essential for team collaboration and deployment. Without them, schema changes become chaotic and risky.

**Independent Test**: Can be tested by creating a simple migration, running `alembic upgrade head`, verifying the migration applied, then running `alembic downgrade -1` and verifying it rolled back.

**Acceptance Scenarios**:

1. **Given** Alembic is configured, **When** I run `alembic upgrade head`, **Then** all pending migrations are applied to the database
2. **Given** migrations have been applied, **When** I run `alembic current`, **Then** it shows the current migration version matching the latest migration
3. **Given** a migration has been applied, **When** I run `alembic downgrade -1`, **Then** the last migration is rolled back successfully
4. **Given** I create a new migration file, **When** I run `alembic upgrade head`, **Then** only the new migration is applied

---

### User Story 3 - Multi-Tenant Data Foundation (Priority: P1)

As a platform architect, I need the org table and multi-tenant conventions established so that all future features are built with tenant isolation from day one.

**Why this priority**: Multi-tenant isolation is a core architectural requirement. Adding it later would require refactoring all tables and queries.

**Independent Test**: Can be tested by creating multiple orgs in the database and verifying that all tables following the conventions have org_id columns with proper foreign keys and indexes.

**Acceptance Scenarios**:

1. **Given** the org table exists, **When** I insert a new organization with name and slug, **Then** it is created with a UUID id, timestamps, and settings_json field
2. **Given** an org exists, **When** I query the org table by slug, **Then** I can retrieve the organization
3. **Given** multiple orgs exist, **When** I create test data for each org, **Then** each org's data is isolated by org_id
4. **Given** the org table has a unique slug constraint, **When** I attempt to create two orgs with the same slug, **Then** the second insert fails with a unique constraint violation

---

### Edge Cases

- What happens when PostgreSQL extensions (pg_trgm, pgvector) fail to install?
- How does the system handle migration conflicts when multiple developers create migrations simultaneously?
- What happens if MinIO fails to start but other services are healthy?
- How does the system handle org slug collisions (case sensitivity, special characters)?
- Attempting to delete an org with dependent data returns 409 Conflict with list of blocking dependencies.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a Docker Compose configuration that includes PostgreSQL 16, Redis, and MinIO (S3-compatible storage)
- **FR-002**: PostgreSQL MUST have the pg_trgm and pgvector extensions installed and enabled
- **FR-003**: System MUST use Alembic for database migrations with support for upgrade and downgrade operations
- **FR-004**: System MUST enforce that all tables (except global system tables) include: id UUID PRIMARY KEY, org_id UUID NOT NULL, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ
- **FR-005**: System MUST provide an `org` table with fields: id, name, slug (unique), settings_json (JSONB), created_at, updated_at
- **FR-006**: Org slug MUST be unique across the system and suitable for use in URLs
- **FR-007**: System MUST use Python 3.12 as the runtime environment
- **FR-008**: System MUST support local development with hot-reload for code changes
- **FR-009**: Database connection strings and credentials MUST be configurable via environment variables
- **FR-010**: System MUST provide health check endpoints for all infrastructure services
- **FR-011**: All multi-tenant tables MUST use ON DELETE RESTRICT for org_id foreign keys. Org deletion requires explicit cleanup of all dependent data first.

### Key Entities

- **Organization (org)**: Represents a tenant in the multi-tenant system. Each organization has a unique slug for URL-friendly identification and a settings_json field for tenant-specific configuration. All business data is scoped to an organization via org_id foreign keys.

### Technical Constraints

- **TC-001**: All database IDs MUST use UUID type, not auto-incrementing integers
- **TC-002**: All timestamps MUST use TIMESTAMPTZ (timezone-aware) not TIMESTAMP
- **TC-003**: Multi-tenant isolation MUST be enforced at the database level via org_id foreign keys
- **TC-004**: Settings storage MUST use JSONB for flexibility while maintaining queryability
- **TC-005**: Migration files MUST be version controlled and follow Alembic naming conventions

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Developers can start local development environment with a single `docker compose up` command in under 2 minutes
- **SC-002**: All required PostgreSQL extensions (pg_trgm, pgvector) are verified present in automated tests
- **SC-003**: Migration system successfully handles upgrade and downgrade operations for all migration files
- **SC-004**: 100% of data tables include org_id and follow the multi-tenant conventions (verified by automated schema tests)
- **SC-005**: Zero data leakage between orgs is verified through automated tenant isolation tests
- **SC-006**: Database schema matches the Alembic migration history exactly (no drift)

### Technical Validation

- **TV-001**: Docker Compose health checks pass for all services within 30 seconds of startup
- **TV-002**: PostgreSQL connection pool can handle minimum 10 concurrent connections
- **TV-003**: Alembic migration execution completes in under 10 seconds for empty database
- **TV-004**: Org table supports minimum 1000 tenants with unique slugs without performance degradation

## Dependencies

- **None** - This is the foundational feature that all other features depend on

## Implementation Notes

### Docker Compose Services

Reference SSOT §14.1 for complete service definitions. Minimum required services for this feature:
- `postgres`: PostgreSQL 16 with pg_trgm and pgvector extensions
- `redis`: Latest stable Redis
- `minio`: S3-compatible object storage

### Alembic Configuration

- Migration files stored in: `migrations/versions/`
- Alembic env.py must support multi-tenant awareness for future data migrations
- Migration naming: `{revision}_{description}.py`

### Org Settings JSON Schema

Reference SSOT §10.1 for the complete settings schema. The settings_json field should support:
- `default_currency`: ISO 4217 currency code
- `price_tolerance_percent`: Decimal value
- Nested configuration objects for matching, customer_detection, ai, and extraction settings

### Database Conventions (SSOT §5.1)

Every table MUST include:
- `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
- `org_id UUID NOT NULL REFERENCES org(id)` (except global tables)
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

Consider implementing an `updated_at` trigger function that automatically updates the timestamp on row modifications.

### Indexing Strategy

Reference SSOT §5.4.1:
- UNIQUE index on org.slug
- Consider GIN index on settings_json for common query patterns

## Out of Scope

- API implementation (covered in later specs)
- Worker/Celery setup (covered in later specs)
- SMTP ingest service (covered in spec 006)
- Frontend service (covered in later specs)
- Production deployment configuration
- Advanced monitoring and observability (basic health checks only)

## Testing Strategy

### Unit Tests
- Org model validation (slug format, uniqueness)
- Settings JSON schema validation
- Timestamp generation and defaults

### Integration Tests
- Docker Compose service startup and health
- PostgreSQL extension availability
- Alembic migration execution (upgrade/downgrade)
- Multi-tenant data isolation
- Org CRUD operations

### Schema Tests
- Verify all tables have required columns (id, org_id, created_at, updated_at)
- Verify UUID types on id columns
- Verify foreign key constraints on org_id columns
- Verify unique constraint on org.slug
