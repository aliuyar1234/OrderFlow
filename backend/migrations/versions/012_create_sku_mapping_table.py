"""Create sku_mapping table

Revision ID: 012
Revises: 004
Create Date: 2025-12-27 15:00:00.000000

SSOT Reference: §5.4.12 (sku_mapping table schema)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '012'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    # Create sku_mapping table
    op.create_table(
        'sku_mapping',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('customer_sku_norm', sa.Text(), nullable=False),
        sa.Column('customer_sku_raw_sample', sa.Text(), nullable=True),
        sa.Column('internal_sku', sa.Text(), nullable=False),
        sa.Column('uom_from', sa.Text(), nullable=True),
        sa.Column('uom_to', sa.Text(), nullable=True),
        sa.Column('pack_factor', sa.Numeric(18, 6), nullable=True),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('confidence', sa.Numeric(5, 4), nullable=False, server_default='0.0'),
        sa.Column('support_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('reject_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_used_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['org_id'], ['org.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['customer_id'], ['customer.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['user.id'], ondelete='SET NULL')
    )

    # Add unique constraint on (org_id, customer_id, customer_sku_norm) for CONFIRMED/SUGGESTED mappings
    # Note: PostgreSQL partial unique index allows duplicates for REJECTED/DEPRECATED
    op.create_index(
        'uq_sku_mapping_customer_sku_active',
        'sku_mapping',
        ['org_id', 'customer_id', 'customer_sku_norm'],
        unique=True,
        postgresql_where=sa.text("status IN ('CONFIRMED', 'SUGGESTED')")
    )

    # Create indexes for sku_mapping table
    op.create_index('idx_sku_mapping_org_customer', 'sku_mapping', ['org_id', 'customer_id'])
    op.create_index('idx_sku_mapping_org_internal_sku', 'sku_mapping', ['org_id', 'internal_sku'])
    op.create_index('idx_sku_mapping_status', 'sku_mapping', ['org_id', 'status'])
    op.create_index('idx_sku_mapping_last_used', 'sku_mapping', ['org_id', 'last_used_at'])

    # Create trigger for sku_mapping.updated_at
    op.execute("""
        CREATE TRIGGER update_sku_mapping_updated_at
        BEFORE UPDATE ON sku_mapping
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)

    # Add check constraint for status enum
    op.create_check_constraint(
        'ck_sku_mapping_status',
        'sku_mapping',
        "status IN ('SUGGESTED', 'CONFIRMED', 'REJECTED', 'DEPRECATED')"
    )

    # Add check constraint for confidence range
    op.create_check_constraint(
        'ck_sku_mapping_confidence',
        'sku_mapping',
        'confidence >= 0.0 AND confidence <= 1.0'
    )


def downgrade():
    # Drop trigger
    op.execute('DROP TRIGGER IF EXISTS update_sku_mapping_updated_at ON sku_mapping')

    # Drop indexes
    op.drop_index('idx_sku_mapping_last_used', table_name='sku_mapping')
    op.drop_index('idx_sku_mapping_status', table_name='sku_mapping')
    op.drop_index('idx_sku_mapping_org_internal_sku', table_name='sku_mapping')
    op.drop_index('idx_sku_mapping_org_customer', table_name='sku_mapping')
    op.drop_index('uq_sku_mapping_customer_sku_active', table_name='sku_mapping')

    # Drop table
    op.drop_table('sku_mapping')
