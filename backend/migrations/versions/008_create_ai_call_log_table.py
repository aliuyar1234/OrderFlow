"""Create ai_call_log table

Revision ID: 008
Revises: 007
Create Date: 2026-01-04 14:00:00.000000

SSOT Reference: §5.5.1 (ai_call_log table schema)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade():
    # Create ai_call_status enum
    op.execute("""
        CREATE TYPE ai_call_status AS ENUM ('SUCCEEDED', 'FAILED')
    """)

    # Create ai_call_log table
    op.create_table(
        'ai_call_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('call_type', sa.Text(), nullable=False),
        sa.Column('provider', sa.Text(), nullable=False),
        sa.Column('model', sa.Text(), nullable=False),
        sa.Column('request_id', sa.Text(), nullable=True),
        sa.Column('input_hash', sa.Text(), nullable=True),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('draft_order_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), nullable=True),
        sa.Column('completion_tokens', sa.Integer(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('cost_usd', sa.Integer(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('status', sa.Enum('SUCCEEDED', 'FAILED', name='ai_call_status'), nullable=False),
        sa.Column('error_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['org_id'], ['org.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['document.id'], ondelete='SET NULL'),
    )

    # Create indexes for common queries
    # Budget tracking: sum(cost_usd) WHERE org_id=X AND created_at >= today
    op.create_index('ix_ai_call_log_org_created', 'ai_call_log', ['org_id', 'created_at'])

    # Deduplication: find by input_hash
    op.create_index('ix_ai_call_log_input_hash', 'ai_call_log', ['input_hash'])

    # Document lookup
    op.create_index('ix_ai_call_log_document', 'ai_call_log', ['document_id'])

    # Performance analytics by type
    op.create_index('ix_ai_call_log_type_status', 'ai_call_log', ['call_type', 'status'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_ai_call_log_type_status', table_name='ai_call_log')
    op.drop_index('ix_ai_call_log_document', table_name='ai_call_log')
    op.drop_index('ix_ai_call_log_input_hash', table_name='ai_call_log')
    op.drop_index('ix_ai_call_log_org_created', table_name='ai_call_log')

    # Drop table
    op.drop_table('ai_call_log')

    # Drop enum
    op.execute('DROP TYPE ai_call_status')
