# Research: Platform Foundation

**Feature**: 001-platform-foundation
**Date**: 2025-12-27
**Status**: Final

## Key Decisions and Rationale

### 1. Docker Compose for Local Development

**Decision**: Use Docker Compose to orchestrate PostgreSQL, Redis, and MinIO for local development.

**Rationale**:
- Ensures consistent development environment across team members
- Eliminates "works on my machine" issues
- Simple one-command startup (`docker compose up`)
- Production services (PostgreSQL, Redis) can run same versions locally and in prod
- MinIO provides S3-compatible API locally, allowing seamless transition to AWS S3 in production

**Alternatives Considered**:
- Native installation: Rejected due to version conflicts, difficult onboarding
- Kubernetes (Minikube): Overkill for local development, slower iteration

**References**:
- SSOT §3.2 (Tech Stack)
- SSOT §14.1 (Deployment)

---

### 2. PostgreSQL 16 with pg_trgm and pgvector Extensions

**Decision**: Use PostgreSQL 16 as the primary database with pg_trgm for fuzzy text matching and pgvector for embedding storage.

**Rationale**:
- **pg_trgm**: Enables trigram-based similarity search for SKU matching (SSOT §9.2)
  - `similarity()` function for fuzzy string comparison
  - GIN indexes for fast full-text search
  - Essential for "customer SKU → internal SKU" mapping
- **pgvector**: Stores and queries embedding vectors for semantic search (SSOT §9.3)
  - Cosine similarity search for product matching
  - Hybrid search combining trigram + embedding scores
  - Native PostgreSQL storage avoids external vector DB
- **PostgreSQL 16**: Latest stable version with performance improvements
  - JSONB improvements for org settings storage
  - Better parallelism for query execution
  - Enhanced monitoring capabilities

**Alternatives Considered**:
- Separate vector database (Pinecone, Weaviate): Rejected to minimize infrastructure complexity in MVP
- Elasticsearch for fuzzy search: Rejected due to operational overhead and pg_trgm sufficiency

**References**:
- SSOT §3.2 (PostgreSQL + extensions mandated)
- SSOT §9 (Matching module relies on pg_trgm + pgvector)

---

### 3. Alembic for Database Migrations

**Decision**: Use Alembic as the migration tool with version-controlled migration files.

**Rationale**:
- Industry standard for SQLAlchemy-based projects
- Full support for upgrade and downgrade operations
- Auto-generation of migrations from model changes (with review)
- Team collaboration: migrations are code, tracked in Git
- CI/CD integration: migrations run automatically in deployment pipeline

**Best Practices**:
- **Never auto-generate blindly**: Always review and edit generated migrations
- **Test downgrade**: Every migration must have a working downgrade path (rollback safety)
- **Separate data and schema**: Schema changes in migrations, data changes in separate scripts
- **Multi-tenant awareness**: Migration env.py must have org_id context for data migrations (future)

**Alternatives Considered**:
- Django ORM migrations: Not applicable (FastAPI project)
- Flyway: Less Pythonic, primarily Java ecosystem
- Raw SQL scripts: No version tracking, error-prone

**References**:
- SSOT §3.2 (Alembic specified)
- SSOT §5.1 (Schema conventions)

---

### 4. UUID Primary Keys

**Decision**: All tables use UUID primary keys (`gen_random_uuid()`), not auto-incrementing integers.

**Rationale**:
- **Security**: No sequential ID guessing attacks
- **Distribution**: UUIDs can be generated client-side or across distributed systems
- **Merging**: No ID collisions when merging data from different sources
- **Multi-tenant**: Avoids leaking organization size via ID sequences

**Trade-offs**:
- 16 bytes vs 4/8 bytes for integers (storage cost acceptable for security benefit)
- Slightly slower index lookups (negligible in practice with modern PostgreSQL)

**Implementation**:
```sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- For gen_random_uuid()

CREATE TABLE example (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ...
);
```

**References**:
- SSOT §5.1 (UUID convention mandated)
- SSOT §11.3 (Security: ID guessing prevention)

---

### 5. Multi-Tenant Data Model: org_id Everywhere

**Decision**: Every table (except global system tables) includes `org_id UUID NOT NULL` with foreign key to org(id).

**Rationale**:
- **Compliance**: B2B SaaS requires absolute data isolation (GDPR, contracts)
- **Security**: Server-side enforcement via foreign key constraints, not just app logic
- **Simplicity**: One org_id column is simpler than row-level security or schema-per-tenant
- **Performance**: Indexed org_id filters are fast, query planner optimizes well

**Pattern**:
```sql
CREATE TABLE customer (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES org(id) ON DELETE RESTRICT,
  name TEXT NOT NULL,
  ...
);

CREATE INDEX idx_customer_org ON customer(org_id);
```

**Query Safety**:
- All SELECT queries MUST include `WHERE org_id = $1`
- API layer derives org_id from JWT claims, never from user input
- 404 (not 403) for cross-org access attempts to avoid leaking existence

**References**:
- SSOT §5.1 (Multi-tenant conventions)
- SSOT §11.2 (Tenant isolation enforcement)
- Constitution Principle III (Multi-Tenant Isolation)

---

### 6. JSONB for Org Settings

**Decision**: Store organization configuration in `org.settings_json JSONB` instead of separate settings tables.

**Rationale**:
- **Flexibility**: Settings schema can evolve without migrations for every new field
- **Queryability**: JSONB supports indexing (GIN) and path queries (`settings_json->>'default_currency'`)
- **Atomicity**: Settings are read/written as a single document (no partial updates)
- **Validation**: Pydantic schema validates settings on API layer before persistence

**Schema** (SSOT §10.1):
```json
{
  "default_currency": "EUR",
  "price_tolerance_percent": 5.0,
  "require_unit_price": false,
  "matching": {
    "auto_apply_threshold": 0.92,
    "auto_apply_gap": 0.10
  },
  "customer_detection": { ... },
  "ai": { ... },
  "extraction": { ... }
}
```

**Trade-offs**:
- Less type safety in database (mitigated by Pydantic validation in API)
- Cannot enforce foreign keys within JSONB (acceptable for configuration data)

**Alternatives Considered**:
- Separate settings table with columns: Too rigid, requires migrations
- Key-value table: More complex queries, harder to validate as a whole

**References**:
- SSOT §10.1 (Org settings schema)
- SSOT §5.4.1 (org table definition)

---

### 7. TIMESTAMPTZ for All Timestamps

**Decision**: Use `TIMESTAMPTZ` (timezone-aware) for all `created_at` and `updated_at` columns.

**Rationale**:
- **Correctness**: Stores UTC internally, displays in user's timezone
- **Global operations**: OrderFlow may serve customers in different timezones
- **Audit trail**: Unambiguous timestamp for compliance and debugging

**Pattern**:
```sql
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
```

**Auto-update trigger** (for updated_at):
```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_org_updated_at
BEFORE UPDATE ON org
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();
```

**References**:
- SSOT §5.1 (TIMESTAMPTZ convention)

---

## Technology Stack Best Practices

### Docker Compose Configuration

**Health Checks**:
```yaml
services:
  postgres:
    image: postgres:16-alpine
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U orderflow"]
      interval: 5s
      timeout: 5s
      retries: 5
    environment:
      POSTGRES_DB: orderflow
      POSTGRES_USER: orderflow
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./docker/init-extensions.sql:/docker-entrypoint-initdb.d/01-extensions.sql

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 10s
      timeout: 5s
      retries: 3
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes:
      - minio_data:/data
```

**init-extensions.sql**:
```sql
-- Ensure required PostgreSQL extensions are available
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "vector";
```

### SQLAlchemy 2.x Integration

**Session Factory**:
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://orderflow:password@localhost/orderflow")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

@contextmanager
def get_db_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

### Alembic Configuration

**env.py** (multi-tenant awareness):
```python
from alembic import context
from sqlalchemy import engine_from_config, pool
from src.models import Base  # Import all models

config = context.config

# Set database URL from environment
config.set_main_option(
    "sqlalchemy.url",
    os.getenv("DATABASE_URL", "postgresql://orderflow:password@localhost/orderflow")
)

target_metadata = Base.metadata

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # Detect column type changes
            compare_server_default=True,  # Detect default value changes
        )

        with context.begin_transaction():
            context.run_migrations()
```

---

## Integration Patterns

### Service Dependencies

```mermaid
graph TD
  App[OrderFlow Backend] -->|SQL| PG[PostgreSQL 16]
  App -->|Queue Jobs| Redis
  App -->|Store Files| MinIO
  PG -->|Extensions| TRGM[pg_trgm]
  PG -->|Extensions| VEC[pgvector]
```

### Migration Workflow

```mermaid
sequenceDiagram
  participant Dev as Developer
  participant Git as Git Repository
  participant CI as CI Pipeline
  participant DB as Database

  Dev->>Dev: Modify SQLAlchemy models
  Dev->>Dev: alembic revision --autogenerate -m "description"
  Dev->>Dev: Review and edit generated migration
  Dev->>Dev: alembic upgrade head (test locally)
  Dev->>Dev: alembic downgrade -1 (test rollback)
  Dev->>Git: Commit migration file
  Git->>CI: Trigger build
  CI->>DB: alembic upgrade head (apply to staging)
  CI->>CI: Run integration tests
  CI->>DB: Deploy to production (migration runs first)
```

---

## Performance Considerations

### Database Connection Pooling

- SQLAlchemy connection pool: 5-20 connections (default 5)
- Use `pool_pre_ping=True` to detect stale connections
- Adjust `pool_size` and `max_overflow` based on worker count (Future: Celery workers)

### Index Strategy

For org table:
```sql
CREATE UNIQUE INDEX idx_org_slug ON org(slug);
CREATE INDEX idx_org_settings_currency ON org((settings_json->>'default_currency'));
```

For multi-tenant tables:
```sql
-- Composite index for org_id + common filters
CREATE INDEX idx_customer_org_name ON customer(org_id, name);
CREATE INDEX idx_document_org_created ON document(org_id, created_at DESC);
```

### JSONB Indexing (Optional)

```sql
-- GIN index for JSONB contains/existence queries
CREATE INDEX idx_org_settings_gin ON org USING GIN (settings_json);

-- Example query:
SELECT * FROM org WHERE settings_json @> '{"default_currency": "CHF"}';
```

---

## Security Considerations

### Environment Variable Management

- Store sensitive values in `.env` file (gitignored)
- Provide `.env.example` with placeholder values
- Use different passwords for dev/staging/production
- Rotate DATABASE_URL password regularly in production

**Example .env**:
```bash
DATABASE_URL=postgresql://orderflow:dev_password@localhost:5432/orderflow
REDIS_URL=redis://localhost:6379/0
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_ENDPOINT=localhost:9000
```

### PostgreSQL Security

- Use least-privilege database user (not superuser)
- Enable SSL/TLS in production (`sslmode=require`)
- Restrict `pg_hba.conf` to specific IPs
- Regular backups with WAL archiving

---

## Testing Strategy

### Infrastructure Tests

```python
def test_postgres_extensions_available(db_session):
    """Verify pg_trgm and pgvector extensions are installed"""
    result = db_session.execute(
        "SELECT * FROM pg_extension WHERE extname IN ('pg_trgm', 'vector')"
    )
    extensions = [row[0] for row in result]
    assert 'pg_trgm' in extensions
    assert 'vector' in extensions

def test_postgres_health_check():
    """Verify PostgreSQL is accepting connections"""
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres", "pg_isready", "-U", "orderflow"],
        capture_output=True
    )
    assert result.returncode == 0

def test_redis_health_check():
    """Verify Redis is responding"""
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "redis", "redis-cli", "ping"],
        capture_output=True
    )
    assert b"PONG" in result.stdout
```

### Schema Tests

```python
def test_all_tables_have_org_id(db_session):
    """Ensure multi-tenant tables include org_id column"""
    result = db_session.execute("""
        SELECT table_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND column_name = 'org_id'
    """)
    tables_with_org_id = [row[0] for row in result]

    # Exclude global tables
    global_tables = ['alembic_version']
    result = db_session.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    """)
    all_tables = [row[0] for row in result if row[0] not in global_tables]

    for table in all_tables:
        assert table in tables_with_org_id, f"Table {table} missing org_id column"
```

---

## References

- SSOT §3.2: Tech Stack specification
- SSOT §5.1: Database conventions
- SSOT §5.4.1: org table schema
- SSOT §10.1: Org settings schema
- SSOT §14.1: Deployment configuration
- Constitution Principle III: Multi-Tenant Isolation
