"""Create erp_connection and erp_push_log tables

Revision ID: 015
Revises: 002
Create Date: 2026-01-04 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '015'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    # Create erp_connection table (SSOT §5.4.14)
    op.create_table(
        'erp_connection',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('connector_type', sa.Text(), nullable=False),
        sa.Column('config_encrypted', postgresql.BYTEA(), nullable=False),
        sa.Column('status', sa.Text(), server_default='ACTIVE', nullable=False),
        sa.Column('last_test_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['org_id'], ['org.id'], ondelete='RESTRICT'),
        sa.CheckConstraint("status IN ('ACTIVE', 'DISABLED')", name='ck_erp_connection_status')
    )

    # Create unique constraint for one active connector per org (MVP)
    # SSOT §5.4.14: UNIQUE(org_id, connector_type) WHERE status='ACTIVE'
    op.create_index(
        'uq_erp_connection_active',
        'erp_connection',
        ['org_id', 'connector_type'],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'")
    )

    # Create index for lookups
    op.create_index('idx_erp_connection_org', 'erp_connection', ['org_id', 'status'])

    # Create trigger for erp_connection.updated_at
    op.execute("""
        CREATE TRIGGER update_erp_connection_updated_at
        BEFORE UPDATE ON erp_connection
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)

    # Create erp_push_log table (for tracking push history)
    # This table tracks every push attempt with full request/response for debugging
    op.create_table(
        'erp_push_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('draft_order_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('connector_type', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('request_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('response_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('idempotency_key', sa.Text(), nullable=False),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['org_id'], ['org.id'], ondelete='RESTRICT'),
        sa.CheckConstraint("status IN ('SUCCESS', 'FAILED', 'PENDING', 'RETRYING')", name='ck_erp_push_log_status')
    )

    # Create indexes for erp_push_log
    op.create_index('idx_erp_push_log_org', 'erp_push_log', ['org_id', sa.text('created_at DESC')])
    op.create_index('idx_erp_push_log_draft', 'erp_push_log', ['draft_order_id', sa.text('created_at DESC')])
    op.create_index('idx_erp_push_log_idempotency', 'erp_push_log', ['idempotency_key'], unique=True)


def downgrade():
    # Drop erp_push_log table
    op.drop_index('idx_erp_push_log_idempotency', table_name='erp_push_log')
    op.drop_index('idx_erp_push_log_draft', table_name='erp_push_log')
    op.drop_index('idx_erp_push_log_org', table_name='erp_push_log')
    op.drop_table('erp_push_log')

    # Drop erp_connection table
    op.execute('DROP TRIGGER IF EXISTS update_erp_connection_updated_at ON erp_connection')
    op.drop_index('idx_erp_connection_org', table_name='erp_connection')
    op.drop_index('uq_erp_connection_active', table_name='erp_connection')
    op.drop_table('erp_connection')
