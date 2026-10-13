-- =============================================================================
-- Migration: Khởi tạo schema cho RAG / semantic search
-- DB      : semantic_search
-- User    : app
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. Extension
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";   -- gen_random_uuid() fallback
CREATE EXTENSION IF NOT EXISTS vector;        -- pgvector

-- ---------------------------------------------------------------------------
-- 2. Bảng document_chunks
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS document_chunks (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID        NOT NULL,
    content     TEXT        NOT NULL,
    embedding   vector(1024),               -- Qwen3-Embedding-0.6B dimension (max 1024)
    tenant_id   TEXT        NOT NULL,
    language    TEXT        NOT NULL DEFAULT 'vi',
    status      TEXT        NOT NULL DEFAULT 'current'
                            CHECK (status IN ('current', 'archived', 'deleted')),
    metadata    JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 3. Index
-- ---------------------------------------------------------------------------

-- Lọc theo tenant (bắt buộc cho multi-tenant)
CREATE INDEX IF NOT EXISTS idx_document_chunks_tenant
    ON document_chunks (tenant_id);

-- Lọc theo document
CREATE INDEX IF NOT EXISTS idx_document_chunks_document
    ON document_chunks (document_id);

-- Lọc theo status (tìm kiếm thường chỉ query status = 'current')
CREATE INDEX IF NOT EXISTS idx_document_chunks_status
    ON document_chunks (status);

-- Vector ANN index – dùng HNSW (pgvector >= 0.5)
-- cosine distance phù hợp với embedding chuẩn hoá L2
-- Tạo sau khi insert dữ liệu đầy đủ sẽ nhanh hơn, nhưng để sẵn ở đây.
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw
    ON document_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- GIN index cho tìm kiếm full-text trong metadata JSONB
CREATE INDEX IF NOT EXISTS idx_document_chunks_metadata
    ON document_chunks USING gin (metadata);

-- ---------------------------------------------------------------------------
-- 4. Trigger tự cập nhật updated_at
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE OR REPLACE TRIGGER trg_document_chunks_updated_at
    BEFORE UPDATE ON document_chunks
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
