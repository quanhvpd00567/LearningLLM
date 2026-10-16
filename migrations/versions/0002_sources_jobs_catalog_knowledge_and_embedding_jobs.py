"""catalog knowledge and embedding jobs"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = '0002_sources_jobs'
down_revision = '0001_pgvector_baseline'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('categories',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('slug', sa.String(length=120), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    op.create_table('jobs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('job_type', sa.Text(), nullable=False),
    sa.Column('source_type', sa.Text(), nullable=False),
    sa.Column('source_id', sa.Uuid(), nullable=False),
    sa.Column('source_version', sa.Integer(), nullable=False),
    sa.Column('embedding_model', sa.Text(), nullable=False),
    sa.Column('pipeline_version', sa.Integer(), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('max_attempts', sa.Integer(), nullable=False),
    sa.Column('available_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('locked_by', sa.Text(), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("job_type IN ('embed_source', 'delete_source_embeddings')", name='ck_job_type'),
    sa.CheckConstraint("source_type IN ('product', 'knowledge')", name='ck_job_source_type'),
    sa.CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed', 'superseded')", name='ck_job_status'),
    sa.CheckConstraint('attempts >= 0 AND max_attempts > 0', name='ck_job_attempts'),
    sa.CheckConstraint('source_version >= 1 AND pipeline_version >= 1', name='ck_job_versions'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source_type', 'source_id', 'source_version', 'job_type', 'embedding_model', 'pipeline_version', name='uq_job_source_profile')
    )
    op.create_index('idx_jobs_poll', 'jobs', ['status', 'available_at'], unique=False)
    op.create_index('idx_jobs_source', 'jobs', ['source_type', 'source_id'], unique=False)
    op.create_table('knowledge_documents',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('tenant_id', sa.Text(), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('source_version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('source_version >= 1', name='ck_knowledge_version'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('products',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('category_id', sa.Uuid(), nullable=False),
    sa.Column('tenant_id', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('attributes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('source_version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('source_version >= 1', name='ck_product_version'),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('product_variants',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('product_id', sa.Uuid(), nullable=False),
    sa.Column('sku', sa.String(length=120), nullable=False),
    sa.Column('options', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('price', sa.Numeric(precision=14, scale=0), nullable=False),
    sa.Column('stock', sa.Integer(), nullable=False),
    sa.CheckConstraint('price >= 0', name='ck_variant_price'),
    sa.CheckConstraint('stock >= 0', name='ck_variant_stock'),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('sku')
    )
    op.create_index(op.f('ix_product_variants_product_id'), 'product_variants', ['product_id'], unique=False)
    op.add_column('document_chunks', sa.Column('source_type', sa.Text(), nullable=True))
    op.add_column('document_chunks', sa.Column('source_version', sa.Integer(), nullable=True))
    op.add_column('document_chunks', sa.Column('embedding_model', sa.Text(), nullable=True))
    op.add_column('document_chunks', sa.Column('pipeline_version', sa.Integer(), nullable=True))
    op.add_column('document_chunks', sa.Column('chunk_index', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('document_chunks', 'chunk_index')
    op.drop_column('document_chunks', 'pipeline_version')
    op.drop_column('document_chunks', 'embedding_model')
    op.drop_column('document_chunks', 'source_version')
    op.drop_column('document_chunks', 'source_type')
    op.drop_index(op.f('ix_product_variants_product_id'), table_name='product_variants')
    op.drop_table('product_variants')
    op.drop_table('products')
    op.drop_table('knowledge_documents')
    op.drop_index('idx_jobs_source', table_name='jobs')
    op.drop_index('idx_jobs_poll', table_name='jobs')
    op.drop_table('jobs')
    op.drop_table('categories')
