"""Create product_embedding table with pgvector support

Revision ID: 016
Revises: 004
Create Date: 2026-01-04 14:00:00.000000

SSOT Reference: §5.5.2 (product_embedding table), §7.7.2 (HNSW index)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '016'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    # Enable pgvector extension (idempotent)
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Create product_embedding table
    op.create_table(
        'product_embedding',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('embedding_model', sa.String(100), nullable=False),
        sa.Column('embedding_dim', sa.Integer(), nullable=False, server_default='1536'),
        # Vector column using pgvector (dimension 1536 for text-embedding-3-small)
        # Note: SQLAlchemy pgvector type will be imported at runtime
        sa.Column('embedding', postgresql.ARRAY(sa.Float), nullable=False),  # Placeholder - will be VECTOR in actual DB
        sa.Column('text_hash', sa.String(64), nullable=False),  # SHA256 hex
        sa.Column('updated_at_source', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['org_id'], ['org.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['product_id'], ['product.id'], ondelete='CASCADE'),
    )

    # Fix: Actually create the vector column with proper type
    # Drop the placeholder ARRAY column and create VECTOR column
    op.execute('ALTER TABLE product_embedding DROP COLUMN embedding')
    op.execute('ALTER TABLE product_embedding ADD COLUMN embedding VECTOR(1536) NOT NULL')

    # Create unique index: one embedding per product per model (allows model migration)
    op.create_index(
        'idx_product_embedding_unique',
        'product_embedding',
        ['org_id', 'product_id', 'embedding_model'],
        unique=True
    )

    # Create standard indexes
    op.create_index('idx_product_embedding_org', 'product_embedding', ['org_id'])
    op.create_index('idx_product_embedding_product', 'product_embedding', ['product_id'])
    op.create_index('idx_product_embedding_model', 'product_embedding', ['embedding_model'])
    op.create_index('idx_product_embedding_text_hash', 'product_embedding', ['text_hash'])

    # Create HNSW index for fast cosine similarity search
    # SSOT §7.7.2: m=16, ef_construction=200 for 10k products
    # This index enables <50ms k-NN search on 10k+ products
    op.execute("""
        CREATE INDEX idx_product_embedding_hnsw
        ON product_embedding
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 200)
    """)

    # Create trigger for updated_at
    op.execute("""
        CREATE TRIGGER update_product_embedding_updated_at
        BEFORE UPDATE ON product_embedding
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade():
    # Drop trigger
    op.execute('DROP TRIGGER IF EXISTS update_product_embedding_updated_at ON product_embedding')

    # Drop HNSW index (must be explicit for non-standard index types)
    op.execute('DROP INDEX IF EXISTS idx_product_embedding_hnsw')

    # Drop standard indexes
    op.drop_index('idx_product_embedding_text_hash', table_name='product_embedding')
    op.drop_index('idx_product_embedding_model', table_name='product_embedding')
    op.drop_index('idx_product_embedding_product', table_name='product_embedding')
    op.drop_index('idx_product_embedding_org', table_name='product_embedding')
    op.drop_index('idx_product_embedding_unique', table_name='product_embedding')

    # Drop table
    op.drop_table('product_embedding')

    # Note: We don't drop the vector extension as other tables might use it
    # op.execute('DROP EXTENSION IF EXISTS vector')
