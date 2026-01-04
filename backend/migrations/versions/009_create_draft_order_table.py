"""Create draft_order table

Revision ID: 009
Revises: 003
Create Date: 2025-12-27 15:00:00.000000

SSOT Reference: §5.4.8 (draft_order table)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '009'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    # Create draft_order table (§5.4.8)
    op.create_table(
        'draft_order',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('inbound_message_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('extraction_run_id', postgresql.UUID(as_uuid=True), nullable=True),

        # Status and state machine
        sa.Column('status', sa.Text(), nullable=False, server_default='NEW'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),  # For optimistic locking (FR-022)

        # Header fields from extraction
        sa.Column('external_order_number', sa.Text(), nullable=True),
        sa.Column('order_date', sa.Date(), nullable=True),
        sa.Column('currency', sa.Text(), nullable=True),
        sa.Column('requested_delivery_date', sa.Date(), nullable=True),

        # Address and notes (JSONB per §5.4.8)
        sa.Column('ship_to_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('bill_to_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),

        # Confidence scores (§7.8)
        sa.Column('confidence_score', sa.Numeric(precision=5, scale=4), nullable=True),  # Overall confidence
        sa.Column('extraction_confidence', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('customer_confidence', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('matching_confidence', sa.Numeric(precision=5, scale=4), nullable=True),

        # Ready-check result (§6.3)
        sa.Column('ready_check_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),

        # Approval tracking
        sa.Column('approved_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approved_at', sa.TIMESTAMP(timezone=True), nullable=True),

        # ERP export tracking
        sa.Column('erp_order_id', sa.Text(), nullable=True),
        sa.Column('pushed_at', sa.TIMESTAMP(timezone=True), nullable=True),

        # Error tracking
        sa.Column('error', sa.Text(), nullable=True),

        # Soft delete (FR-023)
        sa.Column('deleted_at', sa.TIMESTAMP(timezone=True), nullable=True),

        # Standard timestamps
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),

        # Primary key and foreign keys
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['org_id'], ['org.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['customer_id'], ['customer.id'], ondelete='RESTRICT'),
        # Note: document_id, inbound_message_id, extraction_run_id FKs will be added when those tables exist
    )

    # Create indexes (§5.4.8)
    op.create_index('idx_draft_order_org_status', 'draft_order', ['org_id', 'status', 'created_at'])
    op.create_index('idx_draft_order_org_customer', 'draft_order', ['org_id', 'customer_id'])
    op.create_index('idx_draft_order_org_created', 'draft_order', ['org_id', 'created_at'])
    op.create_index('idx_draft_order_document', 'draft_order', ['document_id'])
    op.create_index('idx_draft_order_extraction_run', 'draft_order', ['extraction_run_id'])

    # Create trigger for updated_at
    op.execute("""
        CREATE TRIGGER update_draft_order_updated_at
        BEFORE UPDATE ON draft_order
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade():
    # Drop trigger
    op.execute('DROP TRIGGER IF EXISTS update_draft_order_updated_at ON draft_order')

    # Drop indexes
    op.drop_index('idx_draft_order_extraction_run', table_name='draft_order')
    op.drop_index('idx_draft_order_document', table_name='draft_order')
    op.drop_index('idx_draft_order_org_created', table_name='draft_order')
    op.drop_index('idx_draft_order_org_customer', table_name='draft_order')
    op.drop_index('idx_draft_order_org_status', table_name='draft_order')

    # Drop table
    op.drop_table('draft_order')
