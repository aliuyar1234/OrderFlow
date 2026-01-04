"""Create customer_detection_candidate table

Revision ID: 013
Revises: 003
Create Date: 2026-01-04 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '013'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    # Enable pg_trgm extension for trigram similarity (required for fuzzy name matching)
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')

    # Create customer_detection_candidate table
    op.create_table(
        'customer_detection_candidate',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('draft_order_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('signals_json', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('status', sa.Text(), server_default="'CANDIDATE'", nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['org_id'], ['org.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['customer_id'], ['customer.id'], ondelete='CASCADE')
    )

    # Create indexes for efficient querying
    op.create_index('idx_customer_detection_draft', 'customer_detection_candidate', ['draft_order_id'])
    op.create_index('idx_customer_detection_org', 'customer_detection_candidate', ['org_id'])
    op.create_index('idx_customer_detection_status', 'customer_detection_candidate', ['status'])

    # Create unique constraint to prevent duplicate candidates
    op.create_unique_constraint(
        'uq_detection_candidate_draft_customer',
        'customer_detection_candidate',
        ['draft_order_id', 'customer_id']
    )

    # Create trigger for updated_at
    op.execute("""
        CREATE TRIGGER update_customer_detection_candidate_updated_at
        BEFORE UPDATE ON customer_detection_candidate
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)

    # Create GIN index on customer.name for trigram similarity search (S5)
    # This significantly improves fuzzy name matching performance
    op.execute("""
        CREATE INDEX idx_customer_name_trgm ON customer USING gin (name gin_trgm_ops)
    """)


def downgrade():
    # Drop trigram index on customer name
    op.execute('DROP INDEX IF EXISTS idx_customer_name_trgm')

    # Drop trigger
    op.execute('DROP TRIGGER IF EXISTS update_customer_detection_candidate_updated_at ON customer_detection_candidate')

    # Drop indexes
    op.drop_index('idx_customer_detection_status', table_name='customer_detection_candidate')
    op.drop_index('idx_customer_detection_org', table_name='customer_detection_candidate')
    op.drop_index('idx_customer_detection_draft', table_name='customer_detection_candidate')

    # Drop table
    op.drop_table('customer_detection_candidate')

    # Note: We don't drop pg_trgm extension as it may be used by other features
