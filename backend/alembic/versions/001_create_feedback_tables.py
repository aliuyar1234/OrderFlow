"""Create feedback_event and doc_layout_profile tables

Revision ID: 001_feedback_tables
Revises:
Create Date: 2026-01-04

Implements SSOT §5.5.3 (doc_layout_profile) and §5.5.5 (feedback_event)
for learning loop and quality monitoring.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_feedback_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create doc_layout_profile table (SSOT §5.5.3)
    op.create_table(
        'doc_layout_profile',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('org.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('layout_fingerprint', sa.Text(), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('document.id', ondelete='SET NULL'), nullable=False),
        sa.Column('fingerprint_method', sa.Text(), nullable=False),
        sa.Column('anchors_json', postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('seen_count', sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column('last_seen_at', postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()"))
    )

    # Create indexes for doc_layout_profile
    op.create_index(
        'idx_doc_layout_profile_unique',
        'doc_layout_profile',
        ['org_id', 'layout_fingerprint'],
        unique=True
    )
    op.create_index(
        'idx_doc_layout_profile_org_seen',
        'doc_layout_profile',
        ['org_id', sa.text('last_seen_at DESC')]
    )

    # Create feedback_event table (SSOT §5.5.5)
    op.create_table(
        'feedback_event',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('org.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('actor_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('user.id', ondelete='SET NULL'), nullable=True),
        sa.Column('event_type', sa.Text(), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('document.id', ondelete='SET NULL'), nullable=True),
        sa.Column('draft_order_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('draft_order.id', ondelete='SET NULL'), nullable=True),
        sa.Column('draft_order_line_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('draft_order_line.id', ondelete='SET NULL'), nullable=True),
        sa.Column('layout_fingerprint', sa.Text(), nullable=True),
        sa.Column('before_json', postgresql.JSONB(), nullable=True),
        sa.Column('after_json', postgresql.JSONB(), nullable=True),
        sa.Column('meta_json', postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()"))
    )

    # Create indexes for feedback_event
    op.create_index(
        'idx_feedback_event_org_created',
        'feedback_event',
        ['org_id', sa.text('created_at DESC')]
    )
    op.create_index(
        'idx_feedback_event_org_type_created',
        'feedback_event',
        ['org_id', 'event_type', sa.text('created_at DESC')]
    )
    op.create_index(
        'idx_feedback_event_org_layout',
        'feedback_event',
        ['org_id', 'layout_fingerprint']
    )


def downgrade() -> None:
    # Drop feedback_event table and indexes
    op.drop_index('idx_feedback_event_org_layout', table_name='feedback_event')
    op.drop_index('idx_feedback_event_org_type_created', table_name='feedback_event')
    op.drop_index('idx_feedback_event_org_created', table_name='feedback_event')
    op.drop_table('feedback_event')

    # Drop doc_layout_profile table and indexes
    op.drop_index('idx_doc_layout_profile_org_seen', table_name='doc_layout_profile')
    op.drop_index('idx_doc_layout_profile_unique', table_name='doc_layout_profile')
    op.drop_table('doc_layout_profile')
