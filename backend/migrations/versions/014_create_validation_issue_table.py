"""Create validation_issue table

Revision ID: 014
Revises: 010
Create Date: 2025-12-27 15:00:00.000000

SSOT Reference: §5.4.13, §7.3, §7.4
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '014'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade():
    # Create ENUM types for validation_issue
    op.execute("""
        CREATE TYPE validation_issue_severity AS ENUM ('INFO', 'WARNING', 'ERROR')
    """)

    op.execute("""
        CREATE TYPE validation_issue_status AS ENUM ('OPEN', 'ACKNOWLEDGED', 'RESOLVED', 'OVERRIDDEN')
    """)

    # Create validation_issue table (SSOT §5.4.13)
    op.create_table(
        'validation_issue',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('draft_order_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('draft_order_line_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('type', sa.Text(), nullable=False),
        sa.Column('severity', postgresql.ENUM('INFO', 'WARNING', 'ERROR', name='validation_issue_severity'), nullable=False),
        sa.Column('status', postgresql.ENUM('OPEN', 'ACKNOWLEDGED', 'RESOLVED', 'OVERRIDDEN', name='validation_issue_status'), nullable=False, server_default='OPEN'),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('details_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('resolved_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('resolved_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('acknowledged_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('acknowledged_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['org_id'], ['org.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['draft_order_id'], ['draft_order.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['draft_order_line_id'], ['draft_order_line.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resolved_by_user_id'], ['user.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['acknowledged_by_user_id'], ['user.id'], ondelete='SET NULL')
    )

    # Create indexes for validation_issue (SSOT indexing patterns)
    op.create_index('idx_validation_issue_org_draft', 'validation_issue', ['org_id', 'draft_order_id'])
    op.create_index('idx_validation_issue_org_line', 'validation_issue', ['org_id', 'draft_order_line_id'])
    op.create_index('idx_validation_issue_org_status', 'validation_issue', ['org_id', 'status'])
    op.create_index('idx_validation_issue_org_severity', 'validation_issue', ['org_id', 'severity'])
    op.create_index('idx_validation_issue_type', 'validation_issue', ['type'])

    # Create trigger for validation_issue.updated_at
    op.execute("""
        CREATE TRIGGER update_validation_issue_updated_at
        BEFORE UPDATE ON validation_issue
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade():
    # Drop validation_issue trigger
    op.execute('DROP TRIGGER IF EXISTS update_validation_issue_updated_at ON validation_issue')

    # Drop validation_issue indexes
    op.drop_index('idx_validation_issue_type', table_name='validation_issue')
    op.drop_index('idx_validation_issue_org_severity', table_name='validation_issue')
    op.drop_index('idx_validation_issue_org_status', table_name='validation_issue')
    op.drop_index('idx_validation_issue_org_line', table_name='validation_issue')
    op.drop_index('idx_validation_issue_org_draft', table_name='validation_issue')

    # Drop validation_issue table
    op.drop_table('validation_issue')

    # Drop ENUM types
    op.execute('DROP TYPE validation_issue_status')
    op.execute('DROP TYPE validation_issue_severity')
