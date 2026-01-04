"""Create draft_order_line table

Revision ID: 010
Revises: 009
Create Date: 2025-12-27 15:10:00.000000

SSOT Reference: §5.4.9 (draft_order_line table)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade():
    # Create draft_order_line table (§5.4.9)
    op.create_table(
        'draft_order_line',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('draft_order_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Line identification
        sa.Column('line_no', sa.Integer(), nullable=False),

        # Customer SKU (raw and normalized per §6.1)
        sa.Column('customer_sku_raw', sa.Text(), nullable=True),
        sa.Column('customer_sku_norm', sa.Text(), nullable=True),

        # Product information
        sa.Column('product_description', sa.Text(), nullable=True),
        sa.Column('internal_sku', sa.Text(), nullable=True),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), nullable=True),

        # Quantity and pricing
        sa.Column('qty', sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column('uom', sa.Text(), nullable=True),
        sa.Column('unit_price', sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column('currency', sa.Text(), nullable=True),
        sa.Column('line_total', sa.Numeric(precision=14, scale=4), nullable=True),

        # Matching metadata (§7.8.3)
        sa.Column('match_status', sa.Text(), nullable=True),  # UNMATCHED|SUGGESTED|MATCHED|OVERRIDDEN
        sa.Column('matching_confidence', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('match_method', sa.Text(), nullable=True),  # exact_mapping|trigram|embedding|hybrid|manual
        sa.Column('match_debug_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),

        # Standard timestamps
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),

        # Primary key and foreign keys
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['org_id'], ['org.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['draft_order_id'], ['draft_order.id'], ondelete='CASCADE'),
        # Note: product_id FK will be added when product table exists
    )

    # Create unique constraint on (draft_order_id, line_no)
    op.create_unique_constraint(
        'uq_draft_order_line_order_lineno',
        'draft_order_line',
        ['draft_order_id', 'line_no']
    )

    # Create indexes (§5.4.9)
    op.create_index('idx_draft_order_line_org_draft', 'draft_order_line', ['org_id', 'draft_order_id'])
    op.create_index('idx_draft_order_line_org_internal_sku', 'draft_order_line', ['org_id', 'internal_sku'])
    op.create_index('idx_draft_order_line_org_customer_sku', 'draft_order_line', ['org_id', 'customer_sku_norm'])
    op.create_index('idx_draft_order_line_product', 'draft_order_line', ['product_id'])

    # Create trigger for updated_at
    op.execute("""
        CREATE TRIGGER update_draft_order_line_updated_at
        BEFORE UPDATE ON draft_order_line
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade():
    # Drop trigger
    op.execute('DROP TRIGGER IF EXISTS update_draft_order_line_updated_at ON draft_order_line')

    # Drop indexes
    op.drop_index('idx_draft_order_line_product', table_name='draft_order_line')
    op.drop_index('idx_draft_order_line_org_customer_sku', table_name='draft_order_line')
    op.drop_index('idx_draft_order_line_org_internal_sku', table_name='draft_order_line')
    op.drop_index('idx_draft_order_line_org_draft', table_name='draft_order_line')

    # Drop unique constraint
    op.drop_constraint('uq_draft_order_line_order_lineno', 'draft_order_line', type_='unique')

    # Drop table
    op.drop_table('draft_order_line')
