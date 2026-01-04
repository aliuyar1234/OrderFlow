"""Create document table for object storage

Revision ID: 006
Revises: 005
Create Date: 2026-01-04 00:00:00.000000

SSOT Reference: §5.4.6 (document table schema)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    """Create document table with storage keys and deduplication support."""

    # Create DocumentStatus enum
    op.execute("""
        CREATE TYPE documentstatus AS ENUM (
            'UPLOADED',
            'STORED',
            'PROCESSING',
            'EXTRACTED',
            'FAILED'
        )
    """)

    # Create document table (SSOT §5.4.6)
    op.create_table(
        'document',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('inbound_message_id', postgresql.UUID(as_uuid=True), nullable=True),

        # File metadata
        sa.Column('file_name', sa.Text(), nullable=False),
        sa.Column('mime_type', sa.Text(), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('sha256', sa.Text(), nullable=False),

        # Storage keys (S3/MinIO)
        sa.Column('storage_key', sa.Text(), nullable=False),
        sa.Column('preview_storage_key', sa.Text(), nullable=True),
        sa.Column('extracted_text_storage_key', sa.Text(), nullable=True),

        # Processing status
        sa.Column('status', postgresql.ENUM('UPLOADED', 'STORED', 'PROCESSING', 'EXTRACTED', 'FAILED',
                                           name='documentstatus', create_type=False),
                 nullable=False, server_default='UPLOADED'),

        # Document analysis metadata
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('text_coverage_ratio', sa.Numeric(4, 3), nullable=True),
        sa.Column('layout_fingerprint', sa.Text(), nullable=True),

        # Error tracking
        sa.Column('error_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),

        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['org_id'], ['org.id'], ondelete='RESTRICT'),
    )

    # Note: inbound_message foreign key will be added when inbound_message table is created
    # For now, we'll skip it to avoid dependency issues

    # Create indexes (SSOT §5.4.6)
    op.create_index('idx_document_org_created', 'document', ['org_id', 'created_at'])
    op.create_index('idx_document_org_sha256', 'document', ['org_id', 'sha256'])

    # Create unique constraint for deduplication (SSOT §5.4.6)
    # Same file within org: (org_id, sha256, file_name, size_bytes)
    op.create_unique_constraint(
        'uq_document_dedup',
        'document',
        ['org_id', 'sha256', 'file_name', 'size_bytes']
    )


def downgrade():
    """Drop document table and enum."""

    # Drop indexes
    op.drop_index('idx_document_org_sha256', table_name='document')
    op.drop_index('idx_document_org_created', table_name='document')

    # Drop unique constraint
    op.drop_constraint('uq_document_dedup', 'document', type_='unique')

    # Drop table
    op.drop_table('document')

    # Drop enum
    op.execute('DROP TYPE documentstatus')
