"""Create customer and customer_contact tables

Revision ID: 003
Revises: 002
Create Date: 2025-12-27 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    # Create customer table (T004)
    op.create_table(
        'customer',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('erp_customer_number', sa.Text(), nullable=True),
        sa.Column('email', postgresql.CITEXT(), nullable=True),
        sa.Column('default_currency', sa.Text(), nullable=False),
        sa.Column('default_language', sa.Text(), nullable=False),
        sa.Column('billing_address', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('shipping_address', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['org_id'], ['org.id'], ondelete='RESTRICT')
    )

    # Add unique constraint on (org_id, erp_customer_number) (T006)
    op.create_unique_constraint(
        'uq_customer_org_erp_number',
        'customer',
        ['org_id', 'erp_customer_number']
    )

    # Create indexes for customer table (T008)
    op.create_index('idx_customer_org_name', 'customer', ['org_id', 'name'])
    op.create_index('idx_customer_org_erp', 'customer', ['org_id', 'erp_customer_number'])

    # Create trigger for customer.updated_at
    op.execute("""
        CREATE TRIGGER update_customer_updated_at
        BEFORE UPDATE ON customer
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)

    # Create customer_contact table (T005)
    op.create_table(
        'customer_contact',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', postgresql.CITEXT(), nullable=False),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('phone', sa.Text(), nullable=True),
        sa.Column('role', sa.Text(), nullable=True),
        sa.Column('is_primary', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['org_id'], ['org.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['customer_id'], ['customer.id'], ondelete='CASCADE')
    )

    # Add unique constraint on (customer_id, email) (T007)
    op.create_unique_constraint(
        'uq_customer_contact_customer_email',
        'customer_contact',
        ['customer_id', 'email']
    )

    # Create indexes for customer_contact table (T009)
    op.create_index('idx_customer_contact_org_customer', 'customer_contact', ['org_id', 'customer_id'])
    op.create_index('idx_customer_contact_email', 'customer_contact', ['org_id', 'email'])

    # Create trigger for customer_contact.updated_at
    op.execute("""
        CREATE TRIGGER update_customer_contact_updated_at
        BEFORE UPDATE ON customer_contact
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade():
    # Drop customer_contact trigger
    op.execute('DROP TRIGGER IF EXISTS update_customer_contact_updated_at ON customer_contact')

    # Drop customer_contact indexes
    op.drop_index('idx_customer_contact_email', table_name='customer_contact')
    op.drop_index('idx_customer_contact_org_customer', table_name='customer_contact')

    # Drop customer_contact table
    op.drop_table('customer_contact')

    # Drop customer trigger
    op.execute('DROP TRIGGER IF EXISTS update_customer_updated_at ON customer')

    # Drop customer indexes
    op.drop_index('idx_customer_org_erp', table_name='customer')
    op.drop_index('idx_customer_org_name', table_name='customer')

    # Drop customer table
    op.drop_table('customer')
