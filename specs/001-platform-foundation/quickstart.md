# Quickstart: Platform Foundation

**Feature**: 001-platform-foundation
**Date**: 2025-12-27

This guide walks you through setting up the OrderFlow development environment from scratch.

## Prerequisites

- **Docker**: Version 20.10 or later ([Install Docker](https://docs.docker.com/get-docker/))
- **Docker Compose**: Version 2.0 or later (included with Docker Desktop)
- **Python**: Version 3.12 ([Install Python](https://www.python.org/downloads/))
- **Git**: For version control

**Verify Prerequisites**:
```bash
docker --version          # Should show 20.10+
docker compose version    # Should show 2.0+
python --version          # Should show 3.12.x
```

## Quick Start (5 minutes)

### 1. Clone Repository (or create from template)

```bash
git clone https://github.com/your-org/orderflow.git
cd orderflow
```

### 2. Create Environment File

```bash
cp .env.example .env
```

Edit `.env` if needed (defaults work for local development):

```bash
# Database
DATABASE_URL=postgresql://orderflow:dev_password@localhost:5432/orderflow
DB_PASSWORD=dev_password

# Redis
REDIS_URL=redis://localhost:6379/0

# MinIO (S3-compatible storage)
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_ENDPOINT=localhost:9000
MINIO_BUCKET=orderflow-dev
```

### 3. Start Infrastructure Services

```bash
docker compose up -d
```

This starts:
- PostgreSQL 16 (with pg_trgm + pgvector extensions)
- Redis 7
- MinIO (S3-compatible storage)

**Verify Health**:
```bash
docker compose ps
```

All services should show `healthy` status.

### 4. Install Python Dependencies

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements/dev.txt
```

### 5. Run Database Migrations

```bash
alembic upgrade head
```

Expected output:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 001, Create org table
```

### 6. Verify Setup

```bash
# Connect to PostgreSQL and check extensions
docker compose exec postgres psql -U orderflow -d orderflow -c "\dx"
```

Expected output should include:
```
 pg_trgm    | 1.6   | public | text similarity measurement and index searching
 vector     | 0.5.0 | public | vector data type and ivfflat and hnsw access methods
```

### 7. Create Test Organization

```bash
# Open Python shell
python
```

```python
from src.database import SessionLocal
from src.models.org import Org

# Create session
session = SessionLocal()

# Create test org
test_org = Org(
    name="Test Organization",
    slug="test-org",
    settings_json={}
)
session.add(test_org)
session.commit()

print(f"Created org: {test_org.id}")
session.close()
```

### 8. Verify Org Created

```bash
docker compose exec postgres psql -U orderflow -d orderflow \
  -c "SELECT id, name, slug FROM org;"
```

You should see your test organization.

## Development Workflow

### Starting Services

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# View specific service logs
docker compose logs -f postgres
```

### Stopping Services

```bash
# Stop all services (preserves data)
docker compose stop

# Stop and remove containers (preserves volumes)
docker compose down

# Stop and remove everything including data (DANGEROUS)
docker compose down -v
```

### Running Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1

# View current migration version
alembic current

# View migration history
alembic history
```

### Creating New Migrations

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "Add user table"

# Create empty migration for data changes
alembic revision -m "Seed initial data"

# IMPORTANT: Always review auto-generated migrations before applying!
```

### Database Access

**Via psql**:
```bash
docker compose exec postgres psql -U orderflow -d orderflow
```

**Via Python**:
```python
from src.database import SessionLocal

session = SessionLocal()
# Use session...
session.close()
```

**Via Database GUI** (optional):
- **pgAdmin**: http://localhost:5050 (if configured in docker-compose)
- **DBeaver**: Connect to `localhost:5432`, database `orderflow`, user `orderflow`

### MinIO Console

Access MinIO web UI at http://localhost:9001

- **Username**: minioadmin (from MINIO_ROOT_USER)
- **Password**: minioadmin (from MINIO_ROOT_PASSWORD)

Create bucket `orderflow-dev` if it doesn't exist.

### Redis CLI

```bash
docker compose exec redis redis-cli

# Test Redis
> PING
PONG
> SET test "hello"
OK
> GET test
"hello"
```

## Testing

### Run All Tests

```bash
cd backend
pytest
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest tests/unit/

# Integration tests (require services running)
pytest tests/integration/

# Schema tests
pytest tests/schema/
```

### Test with Coverage

```bash
pytest --cov=src --cov-report=html
open htmlcov/index.html  # View coverage report
```

## Troubleshooting

### PostgreSQL Won't Start

**Error**: `port 5432 already in use`

**Solution**:
```bash
# Stop local PostgreSQL service
sudo systemctl stop postgresql  # Linux
brew services stop postgresql   # macOS

# OR change port in docker-compose.yml
ports:
  - "5433:5432"  # External:Internal

# Update DATABASE_URL in .env
DATABASE_URL=postgresql://orderflow:dev_password@localhost:5433/orderflow
```

### Extensions Not Available

**Error**: `extension "pg_trgm" is not available`

**Solution**:
```bash
# Rebuild postgres with init script
docker compose down -v
docker compose up -d postgres

# Verify init script ran
docker compose logs postgres | grep "CREATE EXTENSION"
```

### Migration Fails

**Error**: `Can't locate revision identified by '001'`

**Solution**:
```bash
# Check alembic version table
docker compose exec postgres psql -U orderflow -d orderflow \
  -c "SELECT * FROM alembic_version;"

# If empty, stamp with current version
alembic stamp head

# Or recreate database
docker compose down -v
docker compose up -d
alembic upgrade head
```

### Permission Denied on Docker

**Error**: `Permission denied while trying to connect to the Docker daemon socket`

**Solution** (Linux):
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in, or
newgrp docker
```

### Python Module Not Found

**Error**: `ModuleNotFoundError: No module named 'src'`

**Solution**:
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements/dev.txt

# Add backend directory to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

## Service URLs Reference

| Service | URL | Credentials |
|---------|-----|-------------|
| PostgreSQL | localhost:5432 | User: `orderflow`, Password: `dev_password` |
| Redis | localhost:6379 | No auth (dev only) |
| MinIO API | localhost:9000 | Access Key: `minioadmin`, Secret: `minioadmin` |
| MinIO Console | http://localhost:9001 | Same as API |

## Next Steps

After completing this quickstart:

1. **Implement Authentication**: See [002-auth-rbac/plan.md](../../002-auth-rbac/plan.md)
2. **Read SSOT**: Familiarize yourself with [SSOT_SPEC.md](../../../SSOT_SPEC.md)
3. **Review Constitution**: Understand architectural principles in [.specify/memory/constitution.md](../../../.specify/memory/constitution.md)

## File Structure Reference

```
orderflow/
├── .env                          # Environment variables (gitignored)
├── .env.example                  # Template for .env
├── docker-compose.yml            # Development services
├── backend/
│   ├── alembic.ini               # Alembic config
│   ├── migrations/               # Database migrations
│   ├── src/                      # Application code
│   │   ├── database.py           # Session factory
│   │   └── models/
│   │       └── org.py            # Org model
│   ├── tests/                    # All tests
│   ├── requirements/
│   │   ├── base.txt              # Production deps
│   │   └── dev.txt               # Dev deps (includes base)
│   └── venv/                     # Virtual environment (gitignored)
└── docs/                         # Documentation
```

## Development Best Practices

### Before Committing

```bash
# Run tests
pytest

# Check code style (if configured)
black src/ tests/
flake8 src/ tests/

# Check types (if configured)
mypy src/
```

### Database Workflow

1. **Modify Models** (e.g., `src/models/org.py`)
2. **Generate Migration**: `alembic revision --autogenerate -m "description"`
3. **Review Migration**: Edit generated file in `migrations/versions/`
4. **Test Upgrade**: `alembic upgrade head`
5. **Test Downgrade**: `alembic downgrade -1`
6. **Re-upgrade**: `alembic upgrade head`
7. **Commit Both**: Model changes + migration file

### Environment Variables

- **Never commit** `.env` file (contains secrets)
- **Always update** `.env.example` when adding new variables
- **Document** new variables in this guide

## Resources

- **SSOT Specification**: [SSOT_SPEC.md](../../../SSOT_SPEC.md)
- **Constitution**: [.specify/memory/constitution.md](../../../.specify/memory/constitution.md)
- **Docker Compose Docs**: https://docs.docker.com/compose/
- **Alembic Docs**: https://alembic.sqlalchemy.org/
- **SQLAlchemy 2.0 Docs**: https://docs.sqlalchemy.org/en/20/
- **PostgreSQL pg_trgm**: https://www.postgresql.org/docs/16/pgtrgm.html
- **pgvector**: https://github.com/pgvector/pgvector
