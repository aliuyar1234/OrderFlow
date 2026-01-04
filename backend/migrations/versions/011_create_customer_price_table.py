"""Create customer_price table

Revision ID: 011
Revises: 004
Create Date: 2025-12-27 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '011'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    # Create customer_price table per §5.4.11
    op.create_table(
        'customer_price',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('internal_sku', sa.Text(), nullable=False),
        sa.Column('currency', sa.Text(), nullable=False),
        sa.Column('uom', sa.Text(), nullable=False),
        sa.Column('unit_price', sa.Numeric(18, 4), nullable=False),
        sa.Column('min_qty', sa.Numeric(18, 3), server_default=sa.text('1.000'), nullable=False),
        sa.Column('valid_from', sa.Date(), nullable=True),
        sa.Column('valid_to', sa.Date(), nullable=True),
        sa.Column('source', sa.Text(), server_default=sa.text("'IMPORT'"), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Add foreign key constraints
    op.create_foreign_key(
        'fk_customer_price_org',
        'customer_price', 'org',
        ['org_id'], ['id'],
        ondelete='RESTRICT'
    )

    op.create_foreign_key(
        'fk_customer_price_customer',
        'customer_price', 'customer',
        ['customer_id'], ['id'],
        ondelete='RESTRICT'
    )

    # Add check constraints
    op.create_check_constraint(
        'ck_customer_price_unit_price_positive',
        'customer_price',
        sa.text('unit_price > 0')
    )

    op.create_check_constraint(
        'ck_customer_price_min_qty_positive',
        'customer_price',
        sa.text('min_qty > 0')
    )

    # Create indexes per §5.4.11
    op.create_index(
        'idx_customer_price_lookup',
        'customer_price',
        ['org_id', 'customer_id', 'internal_sku']
    )

    op.create_index(
        'idx_customer_price_tier_lookup',
        'customer_price',
        ['org_id', 'customer_id', 'internal_sku', 'min_qty']
    )

    # Create trigger for updated_at
    op.execute("""
        CREATE TRIGGER update_customer_price_updated_at
        BEFORE UPDATE ON customer_price
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade():
    # Drop trigger
    op.execute('DROP TRIGGER IF EXISTS update_customer_price_updated_at ON customer_price')

    # Drop indexes
    op.drop_index('idx_customer_price_tier_lookup', table_name='customer_price')
    op.drop_index('idx_customer_price_lookup', table_name='customer_price')

    # Drop foreign keys
    op.drop_constraint('fk_customer_price_customer', 'customer_price', type_='foreignkey')
    op.drop_constraint('fk_customer_price_org', 'customer_price', type_='foreignkey')

    # Drop check constraints
    op.drop_constraint('ck_customer_price_min_qty_positive', 'customer_price')
    op.drop_constraint('ck_customer_price_unit_price_positive', 'customer_price')

    # Drop table
    op.drop_table('customer_price')
