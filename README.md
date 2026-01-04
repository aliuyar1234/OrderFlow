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

**Frontend:**
- Next.js 14 + React 18
- TypeScript
- TailwindCSS
- TanStack Query

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.12+
- Node.js 18+ (for frontend)
- Git

### 1. Clone and Setup Environment

```bash
# Clone the repository
git clone https://github.com/aliuyar1234/OrderFlow.git
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
- `orderflow_postgres` on port 5433
- `orderflow_redis` on port 6379
- `orderflow_minio` on ports 9000 (API) and 9001 (Console)

### 3. Setup Backend

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

### 5. Setup Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### 6. Access Services

- **Backend API**: http://localhost:8000
- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs

- **PostgreSQL**: `localhost:5433`
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

# Run all tests (352 tests)
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test categories
pytest tests/unit
pytest tests/integration
pytest tests/schema
pytest tests/security
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
│   │   ├── api/              # FastAPI routes
│   │   ├── auth/             # Authentication & authorization
│   │   ├── domain/           # Business logic (hexagonal core)
│   │   ├── infrastructure/   # External adapters (DB, S3, SMTP)
│   │   ├── models/           # SQLAlchemy models
│   │   ├── workers/          # Celery background tasks
│   │   └── main.py           # Application entrypoint
│   ├── migrations/           # Alembic migrations
│   ├── tests/
│   │   ├── unit/             # Unit tests
│   │   ├── integration/      # Integration tests
│   │   ├── schema/           # Database schema tests
│   │   └── security/         # Security tests
│   └── requirements/
│       ├── base.txt          # Production dependencies
│       └── dev.txt           # Development dependencies
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js app router pages
│   │   └── components/       # React components
│   ├── package.json
│   └── tailwind.config.ts
├── docker/
│   └── init-extensions.sql   # PostgreSQL extensions setup
├── docs/                     # Technical documentation
├── specs/                    # Feature specifications
├── docker-compose.yml        # Development services
├── .env.example              # Environment template
└── README.md
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

## API Documentation

Once the backend is running, access the interactive API docs at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## License

MIT License - See [LICENSE](./LICENSE) for details.
