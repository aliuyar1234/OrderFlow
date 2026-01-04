"""Create inbound_message table

Revision ID: 005
Revises: 004
Create Date: 2026-01-04 14:00:00.000000

SSOT Reference: §5.4.5 (inbound_message table), §5.2.2 (InboundMessageStatus)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    # Create inbound_message table
    op.create_table(
        'inbound_message',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source', sa.Text(), nullable=False),
        sa.Column('source_message_id', sa.Text(), nullable=True),
        sa.Column('from_email', postgresql.CITEXT(), nullable=True),
        sa.Column('to_email', postgresql.CITEXT(), nullable=True),
        sa.Column('subject', sa.Text(), nullable=True),
        sa.Column('received_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('raw_storage_key', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False, server_default="'RECEIVED'"),
        sa.Column('error_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['org_id'], ['org.id'], ondelete='CASCADE'),
        sa.CheckConstraint("source IN ('EMAIL', 'UPLOAD')", name='ck_inbound_message_source')
    )

    # Create unique index for deduplication (org_id, source, source_message_id)
    # Partial index: only enforces uniqueness when source_message_id IS NOT NULL
    op.create_index(
        'idx_inbound_unique_source_message',
        'inbound_message',
        ['org_id', 'source', 'source_message_id'],
        unique=True,
        postgresql_where=sa.text("source_message_id IS NOT NULL")
    )

    # Create performance indexes
    op.create_index(
        'idx_inbound_org_received',
        'inbound_message',
        ['org_id', 'received_at']
    )

    op.create_index(
        'idx_inbound_org_status',
        'inbound_message',
        ['org_id', 'status']
    )

    # Create trigger for updated_at
    op.execute("""
        CREATE TRIGGER update_inbound_message_updated_at
        BEFORE UPDATE ON inbound_message
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade():
    # Drop trigger
    op.execute('DROP TRIGGER IF EXISTS update_inbound_message_updated_at ON inbound_message')

    # Drop indexes
    op.drop_index('idx_inbound_org_status', table_name='inbound_message')
    op.drop_index('idx_inbound_org_received', table_name='inbound_message')
    op.drop_index('idx_inbound_unique_source_message', table_name='inbound_message')

    # Drop table
    op.drop_table('inbound_message')
