"""Create user and audit_log tables

Revision ID: 002
Revises: 001
Create Date: 2025-12-27 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Ensure CITEXT extension exists for case-insensitive email
    op.execute('CREATE EXTENSION IF NOT EXISTS "citext"')

    # Create user table (T006)
    op.create_table(
        'user',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', postgresql.CITEXT(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('role', sa.Text(), nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), server_default='ACTIVE', nullable=False),
        sa.Column('last_login_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['org_id'], ['org.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('org_id', 'email', name='uq_user_org_email'),
        sa.CheckConstraint("role IN ('ADMIN', 'INTEGRATOR', 'OPS', 'VIEWER')", name='ck_user_role'),
        sa.CheckConstraint("status IN ('ACTIVE', 'DISABLED')", name='ck_user_status')
    )

    # Create indexes for user table (T008)
    op.create_index('idx_user_org_role', 'user', ['org_id', 'role'])
    op.create_index('idx_user_email', 'user', ['email'])

    # Create trigger for user.updated_at (T006)
    op.execute("""
        CREATE TRIGGER update_user_updated_at
        BEFORE UPDATE ON "user"
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)

    # Create audit_log table (T007)
    op.create_table(
        'audit_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('entity_type', sa.Text(), nullable=True),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_address', postgresql.INET(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['org_id'], ['org.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['actor_id'], ['user.id'], ondelete='SET NULL')
    )

    # Create indexes for audit_log table (T009)
    op.create_index('idx_audit_org_created', 'audit_log', ['org_id', sa.text('created_at DESC')])
    op.create_index('idx_audit_actor', 'audit_log', ['actor_id', sa.text('created_at DESC')])
    op.create_index('idx_audit_action', 'audit_log', ['action', sa.text('created_at DESC')])
    op.create_index('idx_audit_entity', 'audit_log', ['entity_type', 'entity_id'])


def downgrade():
    # Drop audit_log indexes
    op.drop_index('idx_audit_entity', table_name='audit_log')
    op.drop_index('idx_audit_action', table_name='audit_log')
    op.drop_index('idx_audit_actor', table_name='audit_log')
    op.drop_index('idx_audit_org_created', table_name='audit_log')

    # Drop audit_log table
    op.drop_table('audit_log')

    # Drop user trigger
    op.execute('DROP TRIGGER IF EXISTS update_user_updated_at ON "user"')

    # Drop user indexes
    op.drop_index('idx_user_email', table_name='user')
    op.drop_index('idx_user_org_role', table_name='user')

    # Drop user table
    op.drop_table('user')

    # Note: We don't drop CITEXT extension as it may be used elsewhere
