"""Create product and unit_of_measure tables

Revision ID: 004
Revises: 003
Create Date: 2025-01-04 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    # Create product table
    op.create_table(
        'product',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('internal_sku', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('base_uom', sa.Text(), nullable=False),
        sa.Column('uom_conversions_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('attributes_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('updated_source_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['org_id'], ['org.id'], ondelete='RESTRICT')
    )

    # Add unique constraint on (org_id, internal_sku)
    op.create_unique_constraint(
        'uq_product_org_sku',
        'product',
        ['org_id', 'internal_sku']
    )

    # Create indexes for product table
    op.create_index('idx_product_org_sku', 'product', ['org_id', 'internal_sku'])
    op.create_index('idx_product_org_name', 'product', ['org_id', 'name'])
    op.create_index('idx_product_org_active', 'product', ['org_id', 'active'])

    # Create GIN index for fulltext search on name and description
    op.execute("""
        CREATE INDEX idx_product_search ON product
        USING GIN (to_tsvector('simple', name || ' ' || COALESCE(description, '')))
    """)

    # Create GIN index for JSONB attributes search
    op.create_index('idx_product_attributes', 'product', ['attributes_json'], postgresql_using='gin')

    # Create trigger for product.updated_at
    op.execute("""
        CREATE TRIGGER update_product_updated_at
        BEFORE UPDATE ON product
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)

    # Create unit_of_measure table
    op.create_table(
        'unit_of_measure',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('code', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('conversion_factor', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['org_id'], ['org.id'], ondelete='RESTRICT')
    )

    # Add unique constraint on (org_id, code)
    op.create_unique_constraint(
        'uq_unit_of_measure_org_code',
        'unit_of_measure',
        ['org_id', 'code']
    )

    # Create indexes for unit_of_measure table
    op.create_index('idx_uom_org_code', 'unit_of_measure', ['org_id', 'code'])

    # Create trigger for unit_of_measure.updated_at
    op.execute("""
        CREATE TRIGGER update_unit_of_measure_updated_at
        BEFORE UPDATE ON unit_of_measure
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade():
    # Drop unit_of_measure trigger
    op.execute('DROP TRIGGER IF EXISTS update_unit_of_measure_updated_at ON unit_of_measure')

    # Drop unit_of_measure indexes
    op.drop_index('idx_uom_org_code', table_name='unit_of_measure')

    # Drop unit_of_measure table
    op.drop_table('unit_of_measure')

    # Drop product trigger
    op.execute('DROP TRIGGER IF EXISTS update_product_updated_at ON product')

    # Drop product indexes
    op.drop_index('idx_product_attributes', table_name='product')
    op.execute('DROP INDEX IF EXISTS idx_product_search')
    op.drop_index('idx_product_org_active', table_name='product')
    op.drop_index('idx_product_org_name', table_name='product')
    op.drop_index('idx_product_org_sku', table_name='product')

    # Drop product table
    op.drop_table('product')
