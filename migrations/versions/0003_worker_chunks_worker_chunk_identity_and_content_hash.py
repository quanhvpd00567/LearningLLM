"""worker chunk identity and content hash"""
from alembic import op
import sqlalchemy as sa

revision = '0003_worker_chunks'
down_revision = '0002_sources_jobs'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('document_chunks', sa.Column('content_hash', sa.String(length=64), nullable=True))
    op.create_unique_constraint('uq_chunk_source_profile', 'document_chunks', ['source_type', 'document_id', 'source_version', 'embedding_model', 'pipeline_version', 'chunk_index'])


def downgrade():
    op.drop_constraint('uq_chunk_source_profile', 'document_chunks', type_='unique')
    op.drop_column('document_chunks', 'content_hash')
