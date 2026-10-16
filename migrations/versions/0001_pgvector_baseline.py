"""Baseline compatible with the original sql/init.sql schema."""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0001_pgvector_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # Existing installations retain their data; fresh installations get this schema.
    table = sa.Table(
        "document_chunks", sa.MetaData(),
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", UUID(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024)),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False, server_default="vi"),
        sa.Column("status", sa.Text(), nullable=False, server_default="current"),
        sa.Column("metadata", JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('current', 'archived', 'deleted')", name="document_chunks_status_check"),
    )
    # IF NOT EXISTS also supports generation with alembic upgrade --sql.
    from sqlalchemy.schema import CreateTable
    op.execute(CreateTable(table, if_not_exists=True))
    for name, column in [("tenant", "tenant_id"), ("document", "document_id"), ("status", "status")]:
        op.execute(f"CREATE INDEX IF NOT EXISTS idx_document_chunks_{name} ON document_chunks ({column})")
    op.execute("CREATE INDEX IF NOT EXISTS idx_document_chunks_metadata ON document_chunks USING gin (metadata)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw ON document_chunks USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)")
    op.execute("""CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$ BEGIN
        NEW.updated_at = now(); RETURN NEW; END; $$""")
    op.execute("""CREATE OR REPLACE TRIGGER trg_document_chunks_updated_at
        BEFORE UPDATE ON document_chunks FOR EACH ROW EXECUTE FUNCTION set_updated_at()""")


def downgrade():
    op.drop_table("document_chunks")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
    # Keep the extension; other tables can depend on it.
