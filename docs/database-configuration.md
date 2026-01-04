# Database Configuration

This document covers database connection configuration for OrderFlow across different environments.

## Connection String Format

OrderFlow uses PostgreSQL 16 with the standard connection string format:

```
postgresql://[user]:[password]@[host]:[port]/[database]?[parameters]
```

### Components

- **user**: Database username (default: `orderflow`)
- **password**: Database password
- **host**: Database server hostname or IP (default: `localhost`)
- **port**: PostgreSQL port (default: `5432`)
- **database**: Database name (default: `orderflow`)
- **parameters**: Optional connection parameters (e.g., `sslmode=require`)

### Example Connections

**Development (local):**
```
postgresql://orderflow:dev_password@localhost:5432/orderflow
```

**Staging:**
```
postgresql://orderflow:staging_password@staging-db.internal:5432/orderflow?sslmode=require
```

**Production:**
```
postgresql://orderflow:prod_password@prod-db.internal:5432/orderflow?sslmode=require&connect_timeout=10
```

## Environment Variables

OrderFlow reads database configuration from environment variables:

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DATABASE_URL` | Full PostgreSQL connection string | Yes | `postgresql://orderflow:dev_password@localhost:5432/orderflow` |
| `DB_PASSWORD` | Database password (used in Docker Compose) | Yes (for containers) | `dev_password` |
| `TEST_DATABASE_URL` | Connection string for test database | No | `postgresql://orderflow:dev_password@localhost:5432/orderflow_test` |

### Setting Environment Variables

**Development (.env file):**
```bash
# .env file in project root
DATABASE_URL=postgresql://orderflow:dev_password@localhost:5432/orderflow
DB_PASSWORD=dev_password
```

**Staging/Production (system environment):**
```bash
# Linux/Mac
export DATABASE_URL="postgresql://orderflow:secure_password@db.internal:5432/orderflow?sslmode=require"

# Windows PowerShell
$env:DATABASE_URL = "postgresql://orderflow:secure_password@db.internal:5432/orderflow?sslmode=require"
```

**Docker Compose:**
```yaml
environment:
  - DATABASE_URL=postgresql://orderflow:${DB_PASSWORD}@postgres:5432/orderflow
```

## Connection Pool Settings

OrderFlow uses SQLAlchemy connection pooling with the following configuration:

### Default Pool Settings

Located in `backend/src/database.py`:

```python
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,      # Verify connections before using
    echo=False,              # Set to True for SQL query logging
    pool_size=5,             # Number of persistent connections
    max_overflow=10,         # Additional connections when pool exhausted
)
```

### Pool Parameters Explained

| Parameter | Value | Description |
|-----------|-------|-------------|
| `pool_size` | `5` | Number of persistent connections maintained in the pool |
| `max_overflow` | `10` | Additional temporary connections allowed (total max: 15) |
| `pool_pre_ping` | `True` | Test connection health before using (prevents stale connections) |
| `echo` | `False` | Log all SQL statements (set `True` for debugging) |
| `pool_timeout` | `30` (default) | Seconds to wait for connection from pool |
| `pool_recycle` | `3600` (default) | Recycle connections after N seconds |

### Adjusting Pool Size

**For high-traffic applications:**
```python
# Increase pool size in src/database.py
pool_size=20,
max_overflow=40,
```

**For serverless/Lambda:**
```python
# Use NullPool to avoid persistent connections
from sqlalchemy.pool import NullPool

engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,  # No connection pooling
)
```

**For background workers:**
```python
# Smaller pool for Celery workers
pool_size=2,
max_overflow=5,
```

## SSL/TLS Configuration

### Requiring SSL Connections

**Connection string parameter:**
```
postgresql://user:pass@host:5432/db?sslmode=require
```

**SSL modes:**
- `disable`: No SSL (development only)
- `allow`: Try SSL, fallback to plain
- `prefer`: Try SSL first (default)
- `require`: Require SSL, verify nothing
- `verify-ca`: Require SSL, verify CA certificate
- `verify-full`: Require SSL, verify CA and hostname

### Production SSL Configuration

**With certificate verification:**
```
postgresql://user:pass@host:5432/db?sslmode=verify-full&sslrootcert=/path/to/ca.crt
```

**Environment variable:**
```bash
DATABASE_URL="postgresql://orderflow:password@prod-db:5432/orderflow?sslmode=verify-full&sslrootcert=/etc/ssl/certs/ca.crt"
```

## PostgreSQL Extensions

OrderFlow requires the following PostgreSQL extensions:

| Extension | Purpose | Required |
|-----------|---------|----------|
| `pg_trgm` | Fuzzy text search for SKU matching | Yes |
| `pgvector` | Vector embeddings for semantic search | Yes |
| `uuid-ossp` or `pgcrypto` | UUID generation (`gen_random_uuid()`) | Yes |

These are automatically created by the Docker initialization script (`docker/init-extensions.sql`).

### Verifying Extensions

```sql
-- Connect to database
\c orderflow

-- List installed extensions
\dx

-- Expected output:
-- pg_trgm | vector | uuid-ossp (or pgcrypto)
```

## Database Initialization

### First-Time Setup

1. **Start PostgreSQL:**
   ```bash
   docker compose up -d postgres
   ```

2. **Wait for healthy status:**
   ```bash
   docker compose ps postgres
   # Should show "healthy"
   ```

3. **Run migrations:**
   ```bash
   cd backend
   alembic upgrade head
   ```

4. **Verify connection:**
   ```bash
   # Using psql
   psql postgresql://orderflow:dev_password@localhost:5432/orderflow -c "SELECT version();"

   # Using Python
   python -c "from src.database import engine; print(engine.connect())"
   ```

## Testing Database Configuration

### Separate Test Database

OrderFlow uses a separate database for tests to avoid polluting development data:

```bash
# Create test database (one time)
psql -U orderflow -h localhost -c "CREATE DATABASE orderflow_test;"

# Run tests
pytest
```

### Test Database Connection

Set `TEST_DATABASE_URL` in `.env`:
```bash
TEST_DATABASE_URL=postgresql://orderflow:dev_password@localhost:5432/orderflow_test
```

## Troubleshooting

### Connection Refused

**Symptom:**
```
sqlalchemy.exc.OperationalError: could not connect to server: Connection refused
```

**Solutions:**
1. Check if PostgreSQL is running: `docker compose ps postgres`
2. Verify port is not blocked: `telnet localhost 5432`
3. Check firewall settings
4. Verify connection string hostname/port

### Authentication Failed

**Symptom:**
```
sqlalchemy.exc.OperationalError: FATAL: password authentication failed for user "orderflow"
```

**Solutions:**
1. Verify password in `.env` matches Docker Compose `POSTGRES_PASSWORD`
2. Check `DATABASE_URL` environment variable
3. Recreate database container: `docker compose down -v && docker compose up -d`

### SSL Required but Not Available

**Symptom:**
```
sqlalchemy.exc.OperationalError: FATAL: SSL connection is required
```

**Solutions:**
1. Add `?sslmode=require` to connection string
2. For development, disable SSL requirement in PostgreSQL config
3. For production, configure SSL certificates

### Too Many Connections

**Symptom:**
```
sqlalchemy.exc.OperationalError: FATAL: remaining connection slots reserved for replication
```

**Solutions:**
1. Check `max_connections` in PostgreSQL config
2. Reduce `pool_size + max_overflow` in `database.py`
3. Fix connection leaks (missing `session.close()`)
4. Increase PostgreSQL `max_connections` parameter

### Stale Connections

**Symptom:**
```
sqlalchemy.exc.OperationalError: server closed the connection unexpectedly
```

**Solutions:**
1. Enable `pool_pre_ping=True` (already default in OrderFlow)
2. Reduce `pool_recycle` time:
   ```python
   engine = create_engine(DATABASE_URL, pool_recycle=1800)  # 30 minutes
   ```

## Performance Tuning

### Connection Pool Sizing

**Formula:**
```
pool_size = (num_cores * 2) + effective_spindle_count
```

For typical web applications:
- **Small (1-2 workers):** `pool_size=5, max_overflow=10`
- **Medium (4-8 workers):** `pool_size=10, max_overflow=20`
- **Large (16+ workers):** `pool_size=20, max_overflow=40`

### Monitoring Connections

**Check active connections:**
```sql
SELECT count(*) FROM pg_stat_activity WHERE datname = 'orderflow';
```

**Check connection pool stats:**
```python
from src.database import engine

print(f"Pool size: {engine.pool.size()}")
print(f"Checked out: {engine.pool.checkedout()}")
print(f"Overflow: {engine.pool.overflow()}")
```

## Security Best Practices

1. **Never commit passwords:** Use `.env` files (excluded from git)
2. **Use strong passwords:** 16+ characters, alphanumeric + symbols
3. **Rotate passwords regularly:** Especially for production
4. **Require SSL in production:** `sslmode=verify-full`
5. **Use read-only users:** For reporting/analytics queries
6. **Limit connection sources:** Configure `pg_hba.conf` to restrict IPs
7. **Use secrets management:** AWS Secrets Manager, HashiCorp Vault, etc.

### Production Connection String Example

**Using AWS RDS with IAM authentication:**
```bash
DATABASE_URL="postgresql://orderflow@prod-db.rds.amazonaws.com:5432/orderflow?sslmode=verify-full&sslrootcert=/etc/ssl/certs/rds-ca-2019-root.pem"
```

**Using connection pooler (PgBouncer):**
```bash
DATABASE_URL="postgresql://orderflow:password@pgbouncer:6432/orderflow?sslmode=require"
```

## Reference

- **SQLAlchemy Engine Configuration:** https://docs.sqlalchemy.org/en/20/core/engines.html
- **PostgreSQL Connection Strings:** https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING
- **Connection Pool Sizing:** https://wiki.postgresql.org/wiki/Number_Of_Database_Connections
- **SSL Configuration:** https://www.postgresql.org/docs/current/ssl-tcp.html
