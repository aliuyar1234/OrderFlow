# Database Migration Best Practices

This document covers database migration workflows, conventions, and best practices for OrderFlow.

## Overview

OrderFlow uses [Alembic](https://alembic.sqlalchemy.org/) for database schema versioning and migrations. Alembic tracks schema changes as Python scripts in the `backend/migrations/versions/` directory.

### Key Principles

1. **Never auto-generate blindly:** Always review and edit generated migrations
2. **Test both upgrade and downgrade:** Every migration must be reversible
3. **Multi-tenant awareness:** All tenant-scoped tables must include `org_id`
4. **Use transactions:** Migrations run in transactions by default
5. **Data migrations separate:** Complex data migrations should be separate from schema changes

## Migration File Structure

### Naming Convention

```
{revision_id}_{description}.py
```

**Examples:**
- `001_create_org_table.py`
- `002_add_inbox_tables.py`
- `003_add_email_index.py`

### Migration Template

```python
"""Brief description of changes

Revision ID: abc123def456
Revises: previous_revision_id
Create Date: 2024-01-01 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP

# revision identifiers, used by Alembic
revision = 'abc123def456'
down_revision = 'previous_revision_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply schema changes."""
    # Add your upgrade logic here
    pass


def downgrade() -> None:
    """Revert schema changes."""
    # Add your downgrade logic here
    pass
```

## Creating Migrations

### 1. Auto-Generate Migration

```bash
cd backend

# Generate migration from model changes
alembic revision --autogenerate -m "Add user table"
```

**Output:**
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.autogenerate.compare] Detected added table 'user'
  Generating backend/migrations/versions/002_add_user_table.py ... done
```

### 2. Review Generated Migration

**CRITICAL:** Auto-generation is not perfect. Always review and edit:

```python
# GENERATED (may need edits)
def upgrade() -> None:
    op.create_table(
        'user',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(), nullable=True),  # ← Should be nullable=False
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
```

**After review:**
```python
def upgrade() -> None:
    op.create_table(
        'user',
        sa.Column('id', UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('org_id', UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.Text(), nullable=False),  # ✓ Fixed nullable
        sa.Column('created_at', TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['org_id'], ['org.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('org_id', 'email', name='uq_user_org_email')
    )

    # Add index for common queries
    op.create_index('ix_user_org_id', 'user', ['org_id'])
```

### 3. Test Migration

```bash
# Apply migration
alembic upgrade head

# Verify it applied correctly
alembic current

# Test downgrade
alembic downgrade -1

# Re-apply
alembic upgrade head
```

### 4. Manual Migration Creation

For complex changes, create an empty migration:

```bash
alembic revision -m "Migrate legacy data to new schema"
```

Then write the upgrade/downgrade logic manually.

## Multi-Tenant Migration Patterns

### Adding a New Tenant-Scoped Table

**Required columns:**
```python
def upgrade() -> None:
    op.create_table(
        'draft_order',
        # Identity
        sa.Column('id', UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),

        # Multi-tenant isolation (REQUIRED)
        sa.Column('org_id', UUID(as_uuid=True), nullable=False),

        # Business columns
        sa.Column('customer_name', sa.Text(), nullable=False),
        sa.Column('order_date', sa.Date(), nullable=True),

        # Audit timestamps (REQUIRED)
        sa.Column('created_at', TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),

        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['org_id'], ['org.id'], ondelete='CASCADE'),
    )

    # Index for tenant filtering (critical for performance)
    op.create_index('ix_draft_order_org_id', 'draft_order', ['org_id'])
```

### Adding a Column

```python
def upgrade() -> None:
    op.add_column('draft_order', sa.Column('status', sa.Text(), nullable=True))

    # Backfill existing rows
    op.execute("UPDATE draft_order SET status = 'NEW' WHERE status IS NULL")

    # Make NOT NULL after backfill
    op.alter_column('draft_order', 'status', nullable=False)

    # Add index if used in queries
    op.create_index('ix_draft_order_status', 'draft_order', ['status'])


def downgrade() -> None:
    op.drop_index('ix_draft_order_status')
    op.drop_column('draft_order', 'status')
```

### Renaming a Column

```python
def upgrade() -> None:
    # PostgreSQL supports atomic rename
    op.alter_column('draft_order', 'customer_name', new_column_name='buyer_name')


def downgrade() -> None:
    op.alter_column('draft_order', 'buyer_name', new_column_name='customer_name')
```

### Adding an Index

```python
def upgrade() -> None:
    # Standard index
    op.create_index('ix_draft_order_created_at', 'draft_order', ['created_at'])

    # Composite index for common query patterns
    op.create_index('ix_draft_order_org_status', 'draft_order', ['org_id', 'status'])

    # Partial index (only for specific conditions)
    op.create_index(
        'ix_draft_order_org_pending',
        'draft_order',
        ['org_id'],
        postgresql_where=sa.text("status = 'PENDING'")
    )


def downgrade() -> None:
    op.drop_index('ix_draft_order_org_pending')
    op.drop_index('ix_draft_order_org_status')
    op.drop_index('ix_draft_order_created_at')
```

### Adding a Foreign Key

```python
def upgrade() -> None:
    # Add column first
    op.add_column('draft_order', sa.Column('customer_id', UUID(as_uuid=True), nullable=True))

    # Add foreign key constraint
    op.create_foreign_key(
        'fk_draft_order_customer',
        'draft_order',
        'customer',
        ['customer_id'],
        ['id'],
        ondelete='SET NULL'  # or CASCADE, RESTRICT based on requirements
    )

    # Add index for FK lookups
    op.create_index('ix_draft_order_customer_id', 'draft_order', ['customer_id'])


def downgrade() -> None:
    op.drop_index('ix_draft_order_customer_id')
    op.drop_constraint('fk_draft_order_customer', 'draft_order', type_='foreignkey')
    op.drop_column('draft_order', 'customer_id')
```

## Data Migrations

### Safe Data Migration Pattern

```python
def upgrade() -> None:
    # 1. Add new column as nullable
    op.add_column('product', sa.Column('sku_normalized', sa.Text(), nullable=True))

    # 2. Backfill data in batches
    connection = op.get_bind()

    # Use raw SQL for performance
    connection.execute(sa.text("""
        UPDATE product
        SET sku_normalized = LOWER(TRIM(sku))
        WHERE sku_normalized IS NULL
    """))

    # 3. Make column NOT NULL after backfill
    op.alter_column('product', 'sku_normalized', nullable=False)

    # 4. Add index/unique constraint
    op.create_index('ix_product_sku_normalized', 'product', ['sku_normalized'])


def downgrade() -> None:
    op.drop_index('ix_product_sku_normalized')
    op.drop_column('product', 'sku_normalized')
```

### Large Data Migration (Batched)

For tables with millions of rows, use batched updates to avoid long-running transactions:

```python
def upgrade() -> None:
    from sqlalchemy import text

    connection = op.get_bind()

    # Process in batches of 10,000
    batch_size = 10000
    offset = 0

    while True:
        result = connection.execute(text(f"""
            UPDATE product
            SET sku_normalized = LOWER(TRIM(sku))
            WHERE id IN (
                SELECT id FROM product
                WHERE sku_normalized IS NULL
                LIMIT {batch_size}
            )
        """))

        rows_updated = result.rowcount
        if rows_updated == 0:
            break

        print(f"Updated {rows_updated} rows...")
```

**Note:** For very large migrations, consider:
1. Running the data migration separately from the schema migration
2. Using background jobs (Celery) for data transformation
3. Blue-green deployment strategies

## Testing Migrations

### Upgrade/Downgrade Test

```bash
# Start from base
alembic downgrade base

# Upgrade to head
alembic upgrade head

# Downgrade one revision
alembic downgrade -1

# Upgrade again
alembic upgrade head

# Check current revision
alembic current
```

### Test with Real Data

```bash
# 1. Backup production snapshot
pg_dump -U orderflow -h prod-db -d orderflow > prod_snapshot.sql

# 2. Restore to staging
psql -U orderflow -h staging-db -d orderflow < prod_snapshot.sql

# 3. Test migration on staging
alembic upgrade head

# 4. Verify data integrity
psql -U orderflow -h staging-db -d orderflow -c "SELECT COUNT(*) FROM draft_order;"
```

### Automated Testing

Add migration tests to `backend/tests/schema/`:

```python
# tests/schema/test_migrations.py
def test_migrations_up_and_down(engine):
    """Test all migrations can upgrade and downgrade cleanly."""
    from alembic.config import Config
    from alembic import command

    alembic_cfg = Config("alembic.ini")

    # Downgrade to base
    command.downgrade(alembic_cfg, "base")

    # Upgrade to head
    command.upgrade(alembic_cfg, "head")

    # Verify tables exist
    inspector = inspect(engine)
    assert "org" in inspector.get_table_names()
```

## Common Pitfalls

### ❌ DON'T: Forget org_id on tenant tables

```python
# WRONG - Missing org_id
op.create_table(
    'product',
    sa.Column('id', UUID(as_uuid=True), nullable=False),
    sa.Column('sku', sa.Text(), nullable=False),
    # ← Missing org_id!
    sa.PrimaryKeyConstraint('id')
)
```

```python
# CORRECT
op.create_table(
    'product',
    sa.Column('id', UUID(as_uuid=True), nullable=False),
    sa.Column('org_id', UUID(as_uuid=True), nullable=False),  # ✓
    sa.Column('sku', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.ForeignKeyConstraint(['org_id'], ['org.id'])
)
```

### ❌ DON'T: Use plain TIMESTAMP

```python
# WRONG - No timezone
sa.Column('created_at', sa.DateTime(), nullable=False)
```

```python
# CORRECT - TIMESTAMPTZ
sa.Column('created_at', TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()'))
```

### ❌ DON'T: Rename without downgrade

```python
# WRONG - Irreversible migration
def upgrade() -> None:
    op.alter_column('product', 'sku', new_column_name='product_code')

def downgrade() -> None:
    pass  # ← Missing reverse operation!
```

```python
# CORRECT
def upgrade() -> None:
    op.alter_column('product', 'sku', new_column_name='product_code')

def downgrade() -> None:
    op.alter_column('product', 'product_code', new_column_name='sku')  # ✓
```

### ❌ DON'T: Drop columns with data

```python
# WRONG - Data loss without warning
def upgrade() -> None:
    op.drop_column('product', 'legacy_code')
```

```python
# CORRECT - Explicit data handling
def upgrade() -> None:
    # 1. Copy data if needed
    op.execute("""
        UPDATE product
        SET notes = CONCAT(notes, ' (legacy code: ', legacy_code, ')')
        WHERE legacy_code IS NOT NULL
    """)

    # 2. Drop column
    op.drop_column('product', 'legacy_code')
```

### ❌ DON'T: Forget indexes on foreign keys

```python
# WRONG - No index on org_id (slow queries)
op.create_table(
    'product',
    sa.Column('org_id', UUID(as_uuid=True), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['org.id'])
    # ← Missing index!
)
```

```python
# CORRECT - Index for FK
op.create_table(
    'product',
    sa.Column('org_id', UUID(as_uuid=True), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['org.id'])
)
op.create_index('ix_product_org_id', 'product', ['org_id'])  # ✓
```

## Alembic Commands Reference

### Basic Commands

```bash
# Show current revision
alembic current

# Show revision history
alembic history

# Show pending migrations
alembic heads

# Upgrade to latest
alembic upgrade head

# Upgrade to specific revision
alembic upgrade abc123

# Downgrade one revision
alembic downgrade -1

# Downgrade to specific revision
alembic downgrade def456

# Downgrade to base (empty database)
alembic downgrade base
```

### Creating Migrations

```bash
# Auto-generate from model changes
alembic revision --autogenerate -m "Description"

# Create empty migration
alembic revision -m "Manual migration"

# Create migration with dependencies
alembic revision -m "Add feature" --depends-on abc123
```

### Advanced Commands

```bash
# Show SQL without executing
alembic upgrade head --sql

# Show revision details
alembic show abc123

# Stamp database to specific revision (without running migrations)
alembic stamp head

# Merge multiple heads
alembic merge -m "Merge branches" head1 head2
```

## Migration Checklist

Before merging a migration PR, verify:

- [ ] Migration file reviewed and edited (not blindly auto-generated)
- [ ] All tenant tables include `org_id UUID NOT NULL` with FK to `org.id`
- [ ] All timestamps use `TIMESTAMP(timezone=True)` (TIMESTAMPTZ)
- [ ] All tables have `id`, `created_at`, `updated_at` columns
- [ ] Foreign key columns have indexes
- [ ] Both `upgrade()` and `downgrade()` implemented
- [ ] Tested upgrade/downgrade cycle locally
- [ ] Data migration handles NULL values correctly
- [ ] No destructive operations without data backup plan
- [ ] Migration runs in reasonable time (< 5 minutes for production data volume)
- [ ] Schema verification tests pass (`pytest tests/schema/`)

## Production Deployment

### Pre-Deployment

1. **Backup database:**
   ```bash
   pg_dump -U orderflow -h prod-db -d orderflow -Fc > backup_$(date +%Y%m%d_%H%M%S).dump
   ```

2. **Test on staging with production snapshot**

3. **Review migration SQL:**
   ```bash
   alembic upgrade head --sql > migration.sql
   # Review migration.sql for unexpected changes
   ```

### Deployment

1. **Enable maintenance mode** (if downtime required)

2. **Run migration:**
   ```bash
   alembic upgrade head
   ```

3. **Verify:**
   ```bash
   alembic current
   psql -c "SELECT COUNT(*) FROM new_table;"
   ```

4. **Monitor application logs** for errors

### Rollback Plan

If migration fails or causes issues:

```bash
# Rollback migration
alembic downgrade -1

# Restore from backup (last resort)
pg_restore -U orderflow -h prod-db -d orderflow backup_20240101_120000.dump
```

## Resources

- **Alembic Documentation:** https://alembic.sqlalchemy.org/
- **SQLAlchemy Schema Definition:** https://docs.sqlalchemy.org/en/20/core/metadata.html
- **PostgreSQL Data Types:** https://www.postgresql.org/docs/current/datatype.html
- **OrderFlow SSOT Spec:** See `SSOT_SPEC.md` §5 (Database Schema)
