"""Create org table

Revision ID: 001
Revises:
Create Date: 2025-12-27 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Ensure required extensions exist
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"')

    # Create updated_at trigger function (T012 - reusable for all tables)
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
          NEW.updated_at = NOW();
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create org table
    op.create_table(
        'org',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('slug', sa.Text(), nullable=False),
        sa.Column('settings_json', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create unique index on slug (T023)
    op.create_index('idx_org_slug', 'org', ['slug'], unique=True)

    # Create GIN index on settings_json for JSONB queries (T024)
    op.create_index('idx_org_settings_json', 'org', ['settings_json'], postgresql_using='gin')

    # Create trigger for updated_at
    op.execute("""
        CREATE TRIGGER update_org_updated_at
        BEFORE UPDATE ON org
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade():
    # Drop trigger
    op.execute('DROP TRIGGER IF EXISTS update_org_updated_at ON org')

    # Drop indexes
    op.drop_index('idx_org_settings_json', table_name='org')
    op.drop_index('idx_org_slug', table_name='org')

    # Drop table (cascade would remove dependent data, but we use RESTRICT in FK constraints)
    op.drop_table('org')

    # Note: We don't drop extensions or functions as they may be used by other tables
    # Manual cleanup required if truly removing everything
