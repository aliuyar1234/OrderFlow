# OrderFlow

B2B order automation platform for the DACH wholesale/distribution market. Automates the intake of purchase orders (PDF/Excel/CSV) from email or upload, extracts line items, maps customer SKUs to internal product codes, validates against pricing/catalog, and pushes approved orders to ERP systems.

## Architecture

Modular Monolith with Workers + SMTP Ingest, following Hexagonal Architecture (Ports & Adapters).

## Technology Stack

**Backend:**
- Python 3.12 + FastAPI (Pydantic validation)
- SQLAlchemy 2.x + Alembic (migrations)
- Celery + Redis (background jobs)
- PostgreSQL 16 with `pg_trgm` + `pgvector` extensions
- S3-compatible Object Storage (MinIO locally)

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.12+
- Git

### 1. Clone and Setup Environment

```bash
# Clone the repository
git clone <repository-url>
cd OrderFlow

# Copy environment template
cp .env.example .env

# Update .env with your local settings if needed
# Default values work for local development
```

### 2. Start Infrastructure Services

```bash
# Start PostgreSQL, Redis, and MinIO
docker compose up -d

# Verify all services are healthy
docker compose ps
```

You should see all three services with status "healthy":
- `orderflow_postgres` on port 5432
- `orderflow_redis` on port 6379
- `orderflow_minio` on ports 9000 (API) and 9001 (Console)

### 3. Setup Python Environment

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements/dev.txt
```

### 4. Run Database Migrations

```bash
# Apply all migrations
alembic upgrade head

# Verify migration status
alembic current
```

### 5. Access Services

- **PostgreSQL**: `localhost:5432`
  - Database: `orderflow`
  - User: `orderflow`
  - Password: `dev_password` (from .env)

- **Redis**: `localhost:6379`

- **MinIO Console**: http://localhost:9001
  - User: `minioadmin`
  - Password: `minioadmin`

## Development

### Running Tests

```bash
cd backend

# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test categories
pytest tests/unit
pytest tests/integration
pytest tests/schema
```

### Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Description of changes"

# Review the generated migration file in backend/migrations/versions/
# Edit if needed (auto-generation is not perfect)

# Apply migration
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

**Important:** Always review auto-generated migrations before applying them. See [docs/migrations.md](./docs/migrations.md) for detailed migration best practices and multi-tenant considerations.

### Code Quality

```bash
# Format code
black src tests
isort src tests

# Lint code
ruff check src tests

# Type checking
mypy src
```

## Project Structure

```
OrderFlow/
├── backend/
│   ├── src/
│   │   ├── models/          # SQLAlchemy models
│   │   ├── database.py      # Database session factory
│   │   └── __init__.py
│   ├── migrations/          # Alembic migrations
│   │   ├── versions/        # Migration files
│   │   ├── env.py
│   │   └── script.py.mako
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── schema/
│   ├── requirements/
│   │   ├── base.txt         # Production dependencies
│   │   └── dev.txt          # Development dependencies
│   └── alembic.ini
├── docker/
│   └── init-extensions.sql  # PostgreSQL extensions setup
├── docs/                    # Technical documentation
├── specs/                   # Feature specifications
├── docker-compose.yml       # Development services
├── .env.example             # Environment template
├── CLAUDE.md               # AI assistant context
└── README.md               # This file
```

## Multi-Tenant Architecture

OrderFlow is designed as a multi-tenant SaaS platform:

- Every table includes `org_id UUID NOT NULL` (except global system tables)
- The `org` table serves as the tenant anchor
- All queries filter by `org_id` (server-side enforced)
- Cross-tenant access returns 404 (not 403) to avoid leaking existence

## Database Conventions

Every table must include:
- `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
- `org_id UUID NOT NULL REFERENCES org(id)` (except global tables)
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`

## Documentation

- **[Database Configuration](./docs/database-configuration.md)** - Connection strings, pool settings, SSL/TLS configuration
- **[Database Migrations](./docs/migrations.md)** - Migration best practices, multi-tenant patterns, Alembic commands reference

## Contributing

See [CLAUDE.md](./CLAUDE.md) for development guidelines and architectural constraints.

## License

Proprietary - All Rights Reserved
