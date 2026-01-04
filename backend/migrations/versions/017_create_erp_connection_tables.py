"""create erp connection and export tables

Revision ID: 017
Revises: 002
Create Date: 2026-01-04

SSOT Reference: §5.4.14 (erp_connection), §5.4.15 (erp_export), §5.2.9 (ERPExportStatus)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = '017'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create erp_connection and erp_export tables for ERP integration."""

    # Create erp_connection table
    op.create_table(
        'erp_connection',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('org_id', UUID(as_uuid=True), sa.ForeignKey('org.id'), nullable=False),
        sa.Column('connector_type', sa.Text, nullable=False, comment='Type of connector (e.g., DROPZONE_JSON_V1)'),
        sa.Column('config_encrypted', sa.Text, nullable=False, comment='Encrypted connector configuration JSON'),
        sa.Column('active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('last_test_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_test_success', sa.Boolean, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'))
    )

    # Create indexes for erp_connection
    op.create_index('idx_erp_connection_org_active', 'erp_connection', ['org_id', 'active'])
    op.create_index('uq_erp_connection_org_type', 'erp_connection', ['org_id', 'connector_type'], unique=True)

    # Create erp_export table
    op.create_table(
        'erp_export',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('org_id', UUID(as_uuid=True), sa.ForeignKey('org.id'), nullable=False),
        sa.Column('erp_connection_id', UUID(as_uuid=True), sa.ForeignKey('erp_connection.id'), nullable=False),
        sa.Column('draft_order_id', UUID(as_uuid=True), nullable=False, comment='FK to draft_order (add constraint when table exists)'),
        sa.Column('export_format_version', sa.Text, nullable=False, server_default='orderflow_export_json_v1'),
        sa.Column('export_storage_key', sa.Text, nullable=False, comment='S3/MinIO storage key for export file'),
        sa.Column('dropzone_path', sa.Text, nullable=True, comment='Actual SFTP/filesystem path where file was written'),
        sa.Column('status', sa.String(20), nullable=False, server_default='PENDING', comment='PENDING|SENT|ACKED|FAILED'),
        sa.Column('erp_order_id', sa.Text, nullable=True, comment='ERP order ID from acknowledgment'),
        sa.Column('error_json', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'))
    )

    # Create indexes for erp_export
    op.create_index('idx_erp_export_draft', 'erp_export', ['org_id', 'draft_order_id', sa.text('created_at DESC')])

    # Add comment to status column explaining enum values
    op.execute("""
        COMMENT ON COLUMN erp_export.status IS
        'Export status: PENDING (created but not sent), SENT (successfully written to dropzone), ACKED (ERP acknowledged), FAILED (export or ERP processing failed)'
    """)


def downgrade() -> None:
    """Drop erp_connection and erp_export tables."""
    op.drop_index('idx_erp_export_draft', table_name='erp_export')
    op.drop_table('erp_export')

    op.drop_index('uq_erp_connection_org_type', table_name='erp_connection')
    op.drop_index('idx_erp_connection_org_active', table_name='erp_connection')
    op.drop_table('erp_connection')
