"""Create extraction_run table

Revision ID: 007
Revises: 006
Create Date: 2026-01-04 12:00:00.000000

SSOT Reference: §5.4.7 (extraction_run table), §7 (Extraction Logic)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    # Create ExtractionRunStatus enum
    extraction_run_status_enum = postgresql.ENUM(
        'PENDING',
        'RUNNING',
        'SUCCEEDED',
        'FAILED',
        name='extractionrunstatus',
        create_type=True
    )
    extraction_run_status_enum.create(op.get_bind())

    # Create extraction_run table
    op.create_table(
        'extraction_run',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('extractor_version', sa.Text(), nullable=False),
        sa.Column('status', postgresql.ENUM('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', name='extractionrunstatus'), nullable=False),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('finished_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('output_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Canonical extraction output (ExtractionOrderHeader + lines)'),
        sa.Column('metrics_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Runtime metrics (runtime_ms, page_count, etc.)'),
        sa.Column('error_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['org_id'], ['org.id'], name='fk_extraction_run_org_id'),
        # Note: document table will be created in future migration (007)
        # For now, we'll add the FK later or rely on application-level validation
        comment='Tracks extraction attempts and results for documents'
    )

    # Create indexes
    # Primary index for querying extractions by org and document
    op.create_index(
        'idx_extraction_run_org_doc_created',
        'extraction_run',
        ['org_id', 'document_id', 'created_at'],
        postgresql_ops={'created_at': 'DESC'}
    )

    # Index for status-based queries (e.g., finding failed extractions)
    op.create_index(
        'idx_extraction_run_org_status',
        'extraction_run',
        ['org_id', 'status']
    )

    # GIN index on output_json for JSON queries
    op.create_index(
        'idx_extraction_run_output_json',
        'extraction_run',
        ['output_json'],
        postgresql_using='gin'
    )

    # Create trigger for updated_at
    op.execute("""
        CREATE TRIGGER update_extraction_run_updated_at
        BEFORE UPDATE ON extraction_run
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade():
    # Drop trigger
    op.execute('DROP TRIGGER IF EXISTS update_extraction_run_updated_at ON extraction_run')

    # Drop indexes
    op.drop_index('idx_extraction_run_output_json', table_name='extraction_run')
    op.drop_index('idx_extraction_run_org_status', table_name='extraction_run')
    op.drop_index('idx_extraction_run_org_doc_created', table_name='extraction_run')

    # Drop table
    op.drop_table('extraction_run')

    # Drop enum
    op.execute('DROP TYPE extractionrunstatus')
